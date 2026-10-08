"""Command line.

spendwise serve      run migrations, then start the API (and the built web app) on :8000
spendwise demo       create the demo user and import the sample statement
spendwise migrate    bring the database schema up to date (Alembic)
"""

import argparse
import logging
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
DEMO_EMAIL, DEMO_PASSWORD = "demo@spendwise.dev", "demo-password"
DEMO_BUDGETS = {
    "food": 4000,
    "groceries": 1500,
    "travel": 2500,
    "shopping": 2500,
    "bills": 1200,
    "entertainment": 800,
    "rent": 7000,
}


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    from .config import get_settings

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def demo() -> None:
    from sqlmodel import Session, select

    from .api.deps import get_ai
    from .db import get_engine
    from .models import Budget, User
    from .security import hash_password
    from .services.imports import import_statement

    migrate()
    ai = get_ai()
    print("AI:", "on (Groq)" if ai else "off: set GROQ_API_KEY to let the AI sort unknown merchants")
    with Session(get_engine()) as s:
        user = s.exec(select(User).where(User.email == DEMO_EMAIL)).first()
        if user is None:
            user = User(email=DEMO_EMAIL, name="Demo Student", password_hash=hash_password(DEMO_PASSWORD))
            s.add(user)
            s.commit()
            s.refresh(user)
        path = DATA / "sample_statement.csv"
        batch, skipped, by_source = import_statement(s, user, path.read_bytes(), path.name, ai)
        print(
            f"Imported {batch.added} payments ({batch.duplicates} already there, {batch.skipped} skipped); "
            f"categories by {by_source}"
        )
        for cat, rupees in DEMO_BUDGETS.items():
            if not s.exec(select(Budget).where(Budget.user_id == user.id, Budget.category == cat)).first():
                s.add(Budget(user_id=user.id, category=cat, limit_paise=rupees * 100))
        s.commit()
    print(f"Log in with  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")


def main() -> None:
    p = argparse.ArgumentParser(prog="spendwise", description="SpendWise: UPI expense tracker with AI")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    sub.add_parser("demo", help="create the demo user with sample data")
    sub.add_parser("migrate", help="apply database migrations")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "migrate":
        migrate()
    elif a.cmd == "demo":
        demo()
    else:
        import uvicorn

        migrate()
        print(f"SpendWise: http://{a.host}:{a.port}   API docs: http://{a.host}:{a.port}/docs")
        uvicorn.run("spendwise.main:app", host=a.host, port=a.port, reload=a.reload)


if __name__ == "__main__":
    main()
