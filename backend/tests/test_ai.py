"""The AI features with a scripted model: insights, and the tool-calling assistant."""

import datetime as dt
import json

from conftest import FakeLLM, register, tool_call, upload

from spendwise.ai import tools
from spendwise.ai.llm import Reply, ToolCall
from spendwise.ai.service import MAX_STEPS, AIService


def test_ai_off_without_a_key(client):
    h = register(client)
    assert client.get("/api/ai/status", headers=h).json() == {"enabled": False, "model": None}
    assert client.post("/api/ai/insights", headers=h).status_code == 503
    assert client.post("/api/ai/chat", headers=h, json={"message": "hi"}).status_code == 503


def test_insights_get_only_our_numbers(client, ai_holder):
    llm = FakeLLM()
    ai_holder["ai"] = AIService(llm)
    h = register(client)
    upload(client, h)
    r = client.post("/api/ai/insights?month=2026-09", headers=h).json()
    assert r["text"].startswith("- ")
    facts = json.loads(llm.requests[-1]["messages"][1]["content"].removeprefix("Facts: "))
    assert facts["month"] == "2026-09" and facts["income"] == 23000
    assert facts["unusual_payments"][0][0] == "Croma"


def test_the_assistant_calls_a_tool_then_answers(client, ai_holder):
    answer = lambda msgs: Reply(content="You spent ₹" + str(json.loads(msgs[-1]["content"])["total_spent"]))  # noqa: E731
    llm = FakeLLM(
        [tool_call("spending_on_merchant", merchant="swiggy", start_month="2026-08", end_month="2026-08"), answer]
    )
    ai_holder["ai"] = AIService(llm)
    h = register(client)
    upload(client, h)
    r = client.post("/api/ai/chat", headers=h, json={"message": "Swiggy in August?"}).json()
    aug = client.get("/api/transactions?q=swiggy&month=2026-08&page_size=100", headers=h).json()["items"]
    assert r["answer"] == f"You spent ₹{round(sum(t['amount'] for t in aug), 2)}"
    assert r["steps"] == [
        {
            "tool": "spending_on_merchant",
            "ok": True,
            "args": {"merchant": "swiggy", "start_month": "2026-08", "end_month": "2026-08"},
        }
    ]
    sent = next(q for q in llm.requests if q["tools"])  # the import also asked for categories
    assert {t["function"]["name"] for t in sent["tools"]} == set(tools.TOOLS)
    assert "Asha" in sent["messages"][0]["content"]  # the system prompt knows the user


def test_bad_tool_calls_become_errors_the_model_can_read(client, ai_holder):
    llm = FakeLLM(
        [
            Reply(
                tool_calls=[
                    ToolCall("1", "drop_tables", "{}"),
                    ToolCall("2", "month_overview", "{bad json"),
                    ToolCall("3", "spending_by_category", '{"category": "snacks"}'),
                    ToolCall("4", "month_overview", '{"month": "Sept"}'),
                ]
            ),
            Reply(content="Sorry!"),
        ]
    )
    ai_holder["ai"] = AIService(llm)
    h = register(client)
    upload(client, h)
    r = client.post("/api/ai/chat", headers=h, json={"message": "?"}).json()
    assert r["answer"] == "Sorry!" and [s["ok"] for s in r["steps"]] == [False, False, False, False]
    tool_msgs = [m for m in llm.requests[1]["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 4 and all("error" in json.loads(m["content"]) for m in tool_msgs)


def test_the_loop_always_ends(client, ai_holder):
    forever = [tool_call("month_overview") for _ in range(MAX_STEPS)] + [Reply(content="Done.")]
    llm = FakeLLM(forever)
    ai_holder["ai"] = AIService(llm)
    h = register(client)
    upload(client, h)
    r = client.post("/api/ai/chat", headers=h, json={"message": "loop"}).json()
    chat = [q for q in llm.requests if not q["json_mode"]]
    assert r["answer"] == "Done." and len(chat) == MAX_STEPS + 1
    assert chat[-1]["tools"] is None  # the last call can't use tools


def test_history_is_plain_text_only(client, ai_holder):
    ai_holder["ai"] = AIService(FakeLLM([Reply(content="ok")]))
    h = register(client)
    upload(client, h)
    bad = client.post(
        "/api/ai/chat", headers=h, json={"message": "hi", "history": [{"role": "system", "content": "x"}]}
    )
    assert bad.status_code == 422  # nobody can inject a system message


def test_ai_rate_limit_and_failures(client, ai_holder):
    from spendwise.api import deps

    ai_holder["ai"] = AIService(FakeLLM())
    h = register(client)
    upload(client, h)
    deps.ai_limiter._events.clear()  # the import above already used one AI call (categories)
    deps.ai_limiter.limit, old = 2, deps.ai_limiter.limit
    try:
        codes = [client.post("/api/ai/insights", headers=h).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
    finally:
        deps.ai_limiter.limit = old

    class Down:
        def chat(self, *a, **k):
            raise ConnectionError("Groq is down")

    deps.ai_limiter._events.clear()
    ai_holder["ai"] = AIService(Down())
    assert client.post("/api/ai/insights", headers=h).status_code == 502
    assert client.post("/api/ai/chat", headers=h, json={"message": "hi"}).status_code == 502


def test_no_data_yet(client, ai_holder):
    llm = FakeLLM()
    ai_holder["ai"] = AIService(llm)
    h = register(client)
    r = client.post("/api/ai/chat", headers=h, json={"message": "how much did I spend?"}).json()
    assert "Import a statement" in r["answer"] and llm.requests == []


def test_tools_only_read_the_callers_data(session):
    from spendwise.models import Transaction, User

    for i, name in enumerate(("a", "b")):
        u = User(email=f"{name}@x.com", name=name, password_hash="x")
        session.add(u)
        session.commit()
        session.add(
            Transaction(
                user_id=u.id,
                date=dt.date(2026, 9, i + 1),
                merchant="Swiggy",
                amount_paise=10000,
                category="food",
                category_source="rule",
                dedup_key=f"k{i}",
            )
        )
        session.commit()
    result, _ = tools.run(session, 1, "spending_on_merchant", '{"merchant": "swiggy"}')
    assert result["total_spent"] == 100.0 and result["payments"] == 1
    for name, (fn, _, _) in tools.TOOLS.items():  # nothing in the toolbox can write
        src = fn.__code__.co_names
        assert not {"add", "delete", "commit", "execute"} & set(src), name


def test_search_can_sort_by_size_and_unusual_tool(session):
    from conftest import SAMPLE

    from spendwise.models import User
    from spendwise.services.imports import import_statement

    u = User(email="u@x.com", name="U", password_hash="x")
    session.add(u)
    session.commit()
    import_statement(session, u, SAMPLE.read_bytes(), "s.csv", None)
    biggest, _ = tools.run(session, u.id, "find_transactions", '{"month": "2026-09", "sort": "biggest", "limit": 1}')
    assert biggest["transactions"][0]["merchant"] == "Croma"
    odd, _ = tools.run(session, u.id, "unusual_payments", '{"month": "2026-09"}')
    assert odd["unusual_payments"][0]["merchant"] == "Croma" and odd["unusual_payments"][0]["times_usual"] >= 3
