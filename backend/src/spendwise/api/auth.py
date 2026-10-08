"""Register, log in, who am I, delete my account."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from ..db import get_session
from ..models import Budget, ImportBatch, MerchantCategory, Transaction, User
from ..security import create_token, hash_password, verify_password
from .deps import client_ip, get_current_user, login_ip_limiter, login_limiter, register_limiter
from .schemas import DeleteAccountIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
_DUMMY_HASH = hash_password("timing-equaliser")  # see login()


def _token(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_token(user.id, user.token_salt), user=UserOut(id=user.id, email=user.email, name=user.name)
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, session: Session = Depends(get_session)):
    if not register_limiter.hit(f"register:{client_ip(request)}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-ups from here. Try again later.")
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # two sign-ups with one email at the same moment
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.") from None
    session.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenOut)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """OAuth2 password flow: the form field is called `username`, and holds the email."""
    email = form.username.strip().lower()
    if len(email) > 254 or len(form.password) > 128:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    ip = client_ip(request)
    key = f"login:{ip}:{email}"
    if not login_ip_limiter.hit(f"ip:{ip}") or not login_limiter.hit(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Wait 15 minutes.")
    user = session.exec(select(User).where(User.email == email)).first()
    # verify against a dummy hash when the email doesn't exist, so the response time doesn't reveal
    # which emails have accounts
    ok = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    login_limiter.reset(key)
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, name=user.name)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    """Deletes the account and every row that belongs to it."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password.")
    for model in (Transaction, ImportBatch, Budget, MerchantCategory):
        session.exec(delete(model).where(model.user_id == user.id))
    session.delete(user)
    session.commit()
