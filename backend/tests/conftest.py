import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from spendwise.ai.llm import Reply, ToolCall
from spendwise.ai.service import AIService
from spendwise.api import deps
from spendwise.db import create_tables, get_session, make_engine
from spendwise.main import create_app

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"


class FakeLLM:
    """A scripted language model: no network, no key. `script` is a list of Reply objects (or a
    function of the messages) returned in order; every request is recorded."""

    def __init__(self, script=None, categories=None):
        self.script = list(script or [])
        self.categories = categories or {}
        self.requests: list[dict] = []

    def chat(self, messages, tools=None, json_mode=False):
        self.requests.append({"messages": messages, "tools": tools, "json_mode": json_mode})
        if json_mode:  # the categorize call
            names = json.loads(messages[-1]["content"].split("Merchants: ", 1)[1])
            return Reply(content=json.dumps({n: self.categories.get(n, "other") for n in names}))
        if self.script:
            step = self.script.pop(0)
            return step(messages) if callable(step) else step
        return Reply(content="- A fact.\n- A warning.\n- A tip.")


def tool_call(name: str, **args) -> Reply:
    return Reply(tool_calls=[ToolCall(id=f"call_{name}", name=name, arguments=json.dumps(args))])


@pytest.fixture
def engine(tmp_path):
    """SQLite by default. Set TEST_DATABASE_URL to run every test against PostgreSQL too (CI does)."""
    url = os.environ.get("TEST_DATABASE_URL")
    e = make_engine(url or f"sqlite:///{tmp_path / 'test.db'}")
    if url:
        SQLModel.metadata.drop_all(e)
    create_tables(e)
    yield e
    e.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def ai_holder():
    """Tests set ai_holder["ai"] to an AIService(FakeLLM(...)) to switch the AI on."""
    return {"ai": None}


@pytest.fixture
def client(engine, ai_holder):
    app = create_app()

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[deps.get_ai] = lambda: ai_holder["ai"]
    for limiter in (deps.ai_limiter, deps.ai_daily, deps.login_limiter, deps.login_ip_limiter, deps.register_limiter):
        limiter._events.clear()
    with TestClient(app) as c:
        yield c


def register(client, email="asha@example.com", name="Asha", password="correct-horse-1") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "name": name, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def upload(client, headers, data: bytes | None = None, name="statement.csv"):
    data = SAMPLE.read_bytes() if data is None else data
    return client.post("/api/imports", headers=headers, files={"file": (name, data, "text/csv")})


def fake_ai(script=None, categories=None) -> AIService:
    return AIService(FakeLLM(script, categories))
