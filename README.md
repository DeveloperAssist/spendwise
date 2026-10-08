# SpendWise: UPI expense tracker with an AI money assistant

Import your bank or UPI statement, and SpendWise shows where your money really goes. It sorts every
payment, tracks budgets, finds your subscriptions, flags unusual spending, and lets you **ask an AI
agent questions about your own money**, answered from real numbers.

A full-stack, multi-user web app: **FastAPI · PostgreSQL · SQLModel · React + TypeScript · an
LLM agent with tool calling · Docker · CI**. A free final-year project by
[Developers Assist](https://www.youtube.com/@developersAssist), with a video that explains every file.

![SpendWise dashboard](docs/screenshots/dashboard.png)

| AI assistant (agent with tools) | Insights | Phone |
|---|---|---|
| ![assistant](docs/screenshots/assistant.png) | ![insights](docs/screenshots/insights.png) | ![mobile](docs/screenshots/mobile-dashboard.png) |

## Features

- **Real statement import (CSV or Excel).**
  - Finds the header row under the bank's title lines.
  - Understands three layouts: Debit/Credit columns, a Dr/Cr type column, or signed amounts.
  - Turns messy narrations like `UPI/DR/6123…/SWIGGY/YESB/swiggy@ybl/Payment` into **Swiggy**.
  - Skips duplicates **across overlapping statements**, and reports bad rows with line numbers.
  - Any import can be undone.
- **Automatic categories, cheapest answer first:**
  1. what you taught it;
  2. keyword rules (whole words only, so "Coca-Cola" isn't Ola);
  3. **one** LLM call for all unknown merchants, with the answers checked against the allowed list.

  It learns from every fix you make.
- **Dashboard:**
  - spent, income, savings rate, daily average and a month-end forecast;
  - spending by category with the change vs last month;
  - income vs spending over 6 months, and a day-by-day chart.
- **Budgets** per category, marked "Almost there" at 80% and "Over budget" past 100%.
- **Insights:**
  - recurring payments, split into *bills* (rent, phone) and *subscriptions* (Netflix, Spotify);
  - **unusual payments** (3× your usual amount for that category).
- **AI assistant (agentic AI).**
  - Ask "How much did I spend on Swiggy in August?" or "Which subscription should I cancel?".
  - The model **calls typed, read-only Python tools** scoped to your account, then answers only
    from their results.
  - Every answer shows the tools it used.
- **AI monthly insights:** three tips written *only* from numbers Python computed.
- **Accounts:**
  - register and log in with JWT; passwords hashed with Argon2;
  - every user sees only their own data;
  - export to CSV, or delete your account and all your data.

## Architecture

```mermaid
flowchart LR
  UI["React + TypeScript<br/>(Vite, TanStack Query, Recharts)"] -->|JSON over HTTPS + JWT| API
  subgraph API["FastAPI"]
    R["Routes<br/>auth · transactions · imports · budgets · analytics · ai"] --> S["Services<br/>importer · merchants · categorizer · analytics"]
    R --> A["AI layer<br/>AIService · tools · LLM interface"]
    A -->|read-only, user-scoped| S
  end
  S --> DB[("PostgreSQL / SQLite<br/>SQLModel + Alembic")]
  A -->|function calling| G["Groq LLM<br/>(gpt-oss-120b)"]
```

**How the assistant answers a question:**

```mermaid
sequenceDiagram
  participant U as You
  participant API as FastAPI
  participant M as LLM (Groq)
  participant T as Python tools
  U->>API: "Swiggy in August?"
  API->>M: question + tool schemas + rules
  M-->>API: call spending_on_merchant(merchant="Swiggy", 2026-08)
  API->>T: validate args (Pydantic), run for THIS user only
  T-->>API: {"total_spent": 1624.0, "payments": 6}
  API->>M: tool result
  M-->>API: "You spent ₹1,624 on Swiggy in August."
  API-->>U: answer + the tool calls it made
```

### Decisions worth explaining in an interview

| Decision | Why |
|---|---|
| **Money is stored as integer paise**, never floats | `0.1 + 0.2 != 0.3` in floating point; integer paise always add up exactly. |
| **The AI never does maths** | Python computes every total; the LLM only phrases or chooses tools. That stops it inventing numbers. |
| **Tools are typed, read-only and user-scoped** | The model can't write data or reach another user's rows, whatever a prompt or a merchant name says. |
| **Rules before AI, and one batched AI call** | Free and exact for known merchants; much cheaper and faster than one call per payment. |
| **Dedup key = date + merchant + amount + nth occurrence** | Overlapping statements don't double-count, and two genuine ₹20 chais on one day are both kept. |
| **`LLM` is a small interface** | Tests use a fake model (no network, no key). Changing provider means writing one new class. |
| **Alembic migrations, SQLite and PostgreSQL** | The same code runs on a laptop and in production; CI runs the whole test suite on both. |

## Quick start

### Option 1: Docker (app + PostgreSQL)

```bash
git clone https://github.com/DeveloperAssist/spendwise.git
cd spendwise
cp .env.example .env        # then set JWT_SECRET (and GROQ_API_KEY for the AI features)
docker compose up --build   # http://localhost:8000
```

### Option 2: Local development

You need [uv](https://docs.astral.sh/uv/) (it installs Python for you) and Node.js 20+.

```bash
# backend: http://127.0.0.1:8000, API docs at /docs
cd backend
uv sync
uv run spendwise demo       # demo user + 6 months of sample payments
uv run spendwise serve

# frontend (second terminal): http://localhost:5173
cd frontend
npm install
npm run dev
```

Log in with **demo@spendwise.dev / demo-password**.

### Turn on the AI (free)

Get a key at [console.groq.com/keys](https://console.groq.com/keys) and put it in `backend/.env`:

```
GROQ_API_KEY=gsk_...
```

Without a key everything still works: unknown merchants show as *Unsorted*, and the AI pages explain
how to switch it on.

## Configuration

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./spendwise.db` | e.g. `postgresql+psycopg://user:pass@host/db` |
| `JWT_SECRET` | random per run (dev only) | **Required** in production, 32+ characters |
| `ENVIRONMENT` | `dev` | `prod` refuses to start without a strong `JWT_SECRET` |
| `GROQ_API_KEY` | none | Turns on the AI features |
| `AI_MODEL` | `openai/gpt-oss-120b` | Any Groq model that supports tool calling |
| `AI_CALLS_PER_HOUR` | `40` | Per user: protects your free quota |
| `AI_CALLS_PER_DAY` | `2000` | For the whole server: sign-ups are open, so the quota is shared |
| `TIMEZONE` | `Asia/Kolkata` | What "today" and "this month" mean (servers usually run on UTC) |
| `MAX_UPLOAD_MB` | `2` | Statement upload size limit |

## Tests and quality

```bash
cd backend
uv run pytest                    # 113 tests, ~10 s, no network or key needed
uv run ruff check . && uv run ruff format --check .
TEST_DATABASE_URL=postgresql+psycopg://user:pass@127.0.0.1:5432/test uv run pytest   # same suite on PostgreSQL
```

The tests cover:
- **Messy input:** statement formats, Excel files, Windows-1252 encoding, US and Indian date order,
  bad rows, absurd amounts, duplicates across overlapping statements, undoing an import.
- **Hostile files:** a zip-bomb `.xlsx` is refused before unzipping, and a sheet that claims a
  million rows is read quickly.
- **Security:** users can't see each other's data, forged, expired or `alg=none` tokens are rejected,
  login attempts are rate-limited (and a stranger can't lock you out), an old token can't open a
  new account, exported CSVs are safe from spreadsheet formula injection, and `%`/`_` in a search
  are escaped.
- **The analytics maths.**
- **The AI agent loop**, with a scripted fake model: bad tool names and bad arguments, the step
  limit, plain-text-only history, and rate limits.

GitHub Actions runs lint, both test suites, a migration check, the frontend type-check and build, and
a Docker build on every push.

## Security

- **Passwords:** Argon2-hashed. Login is rate-limited per email and per IP, sign-ups per IP, and the
  response time doesn't reveal which emails have accounts.
- **Tokens:** signed JWTs with an expiry. Each carries the account's random salt, so a token from a
  deleted account never fits a new one. A weak secret blocks production start-up.
- **Data access:** every query filters by the logged-in user, and someone else's id returns 404.
- **Uploads:** size-limited before reading, parsed in a worker thread, and Excel files are checked for
  zip bombs and capped at a fixed number of rows and columns.
- **Exports:** spreadsheet formulas are neutralised.
- **AI safety:** tools are read-only. Statement text is labelled as data, never instructions. Only
  plain user and assistant turns are accepted as chat history. AI calls have a per-user hourly limit
  and a server-wide daily cap, so nobody can drain the free quota.
- **Containers and headers:** the container runs as a non-root user, and responses carry
  `nosniff` / `DENY` security headers.

## Project structure

```
backend/
  src/spendwise/
    api/          routes: auth, transactions, imports, budgets + analytics + ai (insights.py), schemas, deps
    services/     money, merchants (narration cleaning), importer, imports, categorizer, analytics
    ai/           llm.py (interface + Groq), tools.py (the agent's tools), service.py (agent loop)
    migrations/   Alembic
    models.py  config.py  security.py  db.py  main.py  cli.py
  tests/          113 pytest tests
  data/           sample_statement.csv (MADE-UP practice data) + the script that generates it
frontend/src/
  pages/          Dashboard, Transactions, Import, Budgets, Insights, Assistant, Settings, AuthPage
  components/     Layout (sidebar + mobile tabs), shared UI, ErrorBoundary
  lib/            api client, auth context, month context, formatting, categories
Dockerfile  docker-compose.yml  .github/workflows/ci.yml
```

## Make it yours (ideas for your resume)

- Read **PDF** statements (try `pdfplumber`).
- **Email or WhatsApp alerts** when a budget turns "Almost there".
- **Shared expenses** for a hostel room (split bills between friends).
- Run the AI on a **local model** with Ollama instead of Groq: implement the `LLM` interface.
- **Deploy** it (Render, Railway or a VPS) and put the live link on your resume.

## License

MIT. Use it, change it, learn from it. If it helped you, star the repo and subscribe to
[Developers Assist](https://www.youtube.com/@developersAssist).

> The sample statement in `backend/data/` is made-up data for practice. It isn't anyone's real account.
