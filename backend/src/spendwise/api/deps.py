"""Things FastAPI hands to every route: the database session, the logged-in user, the AI.

Because routes ask for these with Depends(...), tests can swap each one for a fake.
"""

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from ..ai.llm import GroqLLM
from ..ai.service import AIService
from ..config import get_settings
from ..db import get_session
from ..models import User
from ..security import RateLimiter, read_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# AI: per user per hour, and for the whole server per day (sign-ups are open; the free quota is shared)
ai_limiter = RateLimiter(limit=get_settings().ai_calls_per_hour, window=3600)
ai_daily = RateLimiter(limit=get_settings().ai_calls_per_day, window=24 * 3600)
# logins: per email AND address (a stranger can't lock you out of your own account), plus per address
login_limiter = RateLimiter(limit=10, window=15 * 60)
login_ip_limiter = RateLimiter(limit=50, window=15 * 60)
register_limiter = RateLimiter(limit=10, window=3600)


def client_ip(request: Request) -> str:
    # behind a reverse proxy, configure it (e.g. uvicorn --proxy-headers) so this is the real client
    return request.client.host if request.client else "unknown"


def get_current_user(token: str = Depends(oauth2), session: Session = Depends(get_session)) -> User:
    claims = read_token(token)
    user = session.get(User, claims[0]) if claims else None
    if user is None or user.token_salt != claims[1]:  # a token only fits the account it was issued for
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Please log in again.", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


@lru_cache(maxsize=4)
def _ai_for_key(key: str, model: str) -> AIService:
    return AIService(GroqLLM(key, model))


def get_ai() -> AIService | None:
    """The AI service, or None when no Groq key is configured (the app works without it)."""
    s = get_settings()
    key = s.groq_key()
    return _ai_for_key(key, s.ai_model) if key else None


def charge_ai(user: User) -> bool:
    """Count one AI request for this user. False when they (or the whole server) are over the limit."""
    return ai_limiter.hit(f"user:{user.id}") and ai_daily.hit("server")


def require_ai(ai: AIService | None = Depends(get_ai), user: User = Depends(get_current_user)) -> AIService:
    if ai is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI is off: add a free Groq API key (GROQ_API_KEY) to turn it on."
        )
    if not charge_ai(user):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "That's a lot of AI questions! Try again in a while.")
    return ai


class MeteredAI:
    """The AI for background helpers (categorising during an import or a new payment). Each real call
    is charged to the user's quota; over the limit, it simply answers nothing and rules decide."""

    def __init__(self, ai: AIService, user: User):
        self.ai, self.user = ai, user

    def categorize(self, merchants: list[str], categories: list[str]) -> dict[str, str]:
        if not charge_ai(self.user):
            return {}
        return self.ai.categorize(merchants, categories)


def optional_ai(ai: AIService | None = Depends(get_ai), user: User = Depends(get_current_user)) -> MeteredAI | None:
    return MeteredAI(ai, user) if ai is not None else None
