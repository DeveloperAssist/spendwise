# SpendWise: UPI expense tracker with an AI money assistant

[![CI](https://github.com/DeveloperAssist/spendwise/actions/workflows/ci.yml/badge.svg)](https://github.com/DeveloperAssist/spendwise/actions/workflows/ci.yml)
![Python 3.14](https://img.shields.io/badge/python-3.14-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

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

**Contents:** [Features](#features) · [Get it running](#get-it-running-step-by-step) ·
[Take the tour](#take-the-10-minute-tour) · [Turn on the AI](#turn-on-the-ai-free) ·
[Your own statement](#use-your-own-bank-statement) · [Troubleshooting](#troubleshooting) ·
[Read the code](#read-the-code-in-this-order) · [Architecture](#architecture) · [Tests](#tests-and-quality) ·
[Make it yours](#make-it-yours-ideas-for-your-resume)

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

## Get it running (step by step)

New to this? Follow the steps in order. It takes about 10 minutes the first time, and **you don't
need an AI key** to start.

### Step 1: Install the tools (once)

| Tool | Why | Install | Check it worked |
|---|---|---|---|
| **Git** | to download the code | [git-scm.com/downloads](https://git-scm.com/downloads) | `git --version` |
| **uv** | runs the Python backend and installs the right Python **for you** | see below | `uv --version` |
| **Node.js** 20.19 or newer (the LTS) | builds the React web app | [nodejs.org](https://nodejs.org/) | `node --version` |
| Docker Desktop *(optional)* | only for the Docker way, with PostgreSQL | [docker.com](https://www.docker.com/products/docker-desktop/) | `docker --version` |

Install **uv**:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> After installing anything, **close the terminal and open a new one**, or the new command won't be found.
> You don't need to install Python yourself: uv downloads Python 3.14 the first time you run it.

### Step 2: Get the code

```bash
git clone https://github.com/DeveloperAssist/spendwise.git
cd spendwise
```

(No Git? Click the green **Code** button on GitHub → **Download ZIP**, unzip it, and open a terminal
in that folder.)

### Step 3: Build the web app (once, and again after you change frontend code)

```bash
cd frontend
npm install
npm run build
cd ..
```

`npm install` takes a minute the first time. `npm run build` type-checks the code and writes the
finished web app to `frontend/dist/`.

### Step 4: Load the demo data and start the server

```bash
cd backend
uv sync                 # first time only: downloads Python and every package
uv run spendwise demo   # creates a demo account with 6 months of made-up payments
uv run spendwise serve  # starts the app
```

`spendwise demo` should end like this:

```
AI: off: set GROQ_API_KEY to let the AI sort unknown merchants
Imported 227 payments (0 already there, 0 skipped); categories by {'rule': 209, 'other': 18}
Log in with  demo@spendwise.dev  /  demo-password
```

You'll also see a warning that `JWT_SECRET` is not set. That's fine on your own computer (it only
means you're logged out when the server restarts; see [Troubleshooting](#troubleshooting)).

Leave `spendwise serve` running (stop it with **Ctrl + C**).

### Step 5: Open it

Go to **http://127.0.0.1:8000** and log in with **demo@spendwise.dev / demo-password**.
The API's interactive docs are at **http://127.0.0.1:8000/docs**.

That's it. Next, [take the tour](#take-the-10-minute-tour), then [turn on the AI](#turn-on-the-ai-free).

### Changing the code? Use development mode

In development mode, the web app reloads the moment you save a file. Use two terminals:

```bash
# terminal 1: the API on :8000, restarts when you change Python code
cd backend
uv run spendwise serve --reload
```

```bash
# terminal 2: the web app on :5173, forwards /api calls to :8000
cd frontend
npm run dev
```

Then open **http://localhost:5173**.

### The Docker way (app + PostgreSQL, like production)

You need only Git and Docker Desktop.

```bash
git clone https://github.com/DeveloperAssist/spendwise.git
cd spendwise
cp .env.example .env    # Windows Command Prompt: copy .env.example .env
```

Open `.env` and set `JWT_SECRET` to a long random string. Either of these prints one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
openssl rand -base64 48
```

Then start everything:

```bash
docker compose up --build    # first build takes a few minutes
```

Open **http://localhost:8000** and click **Create an account**. To get data, open **Import**, click
**Download the sample statement**, and drop that file onto the upload box.
Port 8000 busy? Add `APP_PORT=8001` to `.env` and open http://localhost:8001 instead.

## Take the 10-minute tour

Logged in as the demo user? Try these, in order:

1. **Dashboard.** September 2026 shows ₹24,903 spent against ₹23,000 income. Shopping jumped 730%:
   one ₹8,999 purchase did that. Budgets show Shopping "Over budget".
2. **Transactions.** Search `swiggy`. Change any payment's category: **every payment to that merchant
   follows**, and future imports remember it.
3. **Import.** Click **Download the sample statement**, then import that same file again. You get
   **0 new payments · 227 already there**: duplicates are skipped. Undo it under *Past imports*.
4. **Budgets.** Change a limit and watch the dashboard's bars update.
5. **Insights.** Netflix and Spotify are *subscriptions*; rent and the phone bill are *bills*.
   Croma ₹8,999 is flagged as **unusual: 9.4× your usual** shopping payment.
6. **AI Assistant** (needs [the AI on](#turn-on-the-ai-free)). Try:
   - *Which subscriptions can I cancel to save money?*
   - *Why did my spending jump in September?*
   - *Show my 3 biggest payments in September*

   Under each answer you can see which tool the AI called, such as `compare_months` or `find_transactions`.
7. **API docs** at `/docs`. Click **Authorize**, log in with the demo email and password, and call any
   endpoint yourself.

## Turn on the AI (free)

1. Go to [console.groq.com/keys](https://console.groq.com/keys), sign in, and click **Create API Key**.
   Copy the key: it starts with `gsk_`.
2. In the `backend` folder, copy the example settings file:

   ```bash
   cd backend
   cp .env.example .env    # Windows Command Prompt: copy .env.example .env
   ```

3. Open `backend/.env` and paste your key after the `=`, with no quotes or spaces:

   ```
   GROQ_API_KEY=gsk_your_key_here
   ```

4. Stop the server (Ctrl + C) and start it again: `uv run spendwise serve`.

Now the Assistant page and the **Get AI insights** buttons work.
If you ran `spendwise demo` *before* adding the key, 18 payments stay in *Other*. To let the AI sort
them, start fresh: stop the server, delete `backend/spendwise.db`, and run `uv run spendwise demo` again.

For Docker, put `GROQ_API_KEY=...` in the **top-level** `.env` instead, and run `docker compose up -d`.

> **Never commit `.env` or share your key.** Both `.env` files are already in `.gitignore`.
> Without a key, nothing leaves your computer. With a key, merchant names (for sorting) and the numbers
> the assistant looks up are sent to Groq to write the answer.

## Use your own bank statement

Most banks let you download your account statement from net banking as **Excel (.xlsx)** or **CSV**.
SpendWise reads it if it has:

- a **date** column: *Date*, *Txn Date*, *Transaction Date*, *Value Date* or *Posting Date*;
- a **description** column: *Narration*, *Description*, *Particulars*, *Remarks*, *Details* or *Paid to*;
- the **amount**, in one of three layouts:
  - separate *Debit* and *Credit* (or *Withdrawal* and *Deposit*) columns;
  - an *Amount* column plus a *Dr/Cr* or *Type* column;
  - one signed *Amount* column, where minus means money out.

Title lines above the table (bank name, account number, dates) are fine: SpendWise finds the header
row. Rows it can't read are skipped and listed under **Why were rows skipped?**. The upload limit is
2 MB, and PDF statements aren't supported yet (a good feature to add).

Your statement is stored only in **your own database**. With the AI on, only merchant names and the
numbers the assistant looks up are sent to Groq (see [Turn on the AI](#turn-on-the-ai-free)).

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv`, `npm` or `git` is "not recognized" / "command not found" | Close the terminal and open a new one after installing. On Windows, sign out and in again if that doesn't help. |
| Windows: *npm.ps1 cannot be loaded because running scripts is disabled* | Use **Command Prompt** instead of PowerShell, or type `npm.cmd` instead of `npm`. |
| `npm run build` says your Node.js version is too old | Install the current LTS from [nodejs.org](https://nodejs.org/), at least 20.19. |
| http://127.0.0.1:8000 shows a JSON message saying *the web app isn't built yet* | Do [Step 3](#step-3-build-the-web-app-once-and-again-after-you-change-frontend-code), then reload the page. |
| *Address already in use* / port 8000 is busy | Run `uv run spendwise serve --port 8001` and open http://127.0.0.1:8001. In development mode, also change the port in `frontend/vite.config.ts`. |
| You're logged out every time you restart the server | Without `JWT_SECRET`, development mode makes a new one on each start. Set `JWT_SECRET` in `backend/.env` (see the comment in `.env.example`). |
| The AI pages say the AI is off | The key goes in **`backend/.env`** for local runs (in the top-level `.env` for Docker), with no quotes. Restart the server after editing. |
| *That's a lot of AI questions! Try again in a while.* | Each user gets 40 AI calls an hour (`AI_CALLS_PER_HOUR`), and Groq's free tier has its own limits. Wait a little, then try again. |
| Docker: *set JWT_SECRET in .env* | Create `.env` from `.env.example` and fill in `JWT_SECRET` (see [the Docker way](#the-docker-way-app--postgresql-like-production)). |
| You want to start over with fresh data | Stop the server, delete `backend/spendwise.db`, then run `uv run spendwise demo` again. |
| Something else | [Open an issue](https://github.com/DeveloperAssist/spendwise/issues) with the full error text and the command you ran. |

## Read the code in this order

Each step builds on the one before. Every file is small and has one job.

| # | File | What you learn |
|---|---|---|
| 1 | `backend/src/spendwise/services/money.py` | Why money is stored as whole paise, and how text like "₹1,299.50" becomes `129950` safely |
| 2 | `services/merchants.py` | Turning a bank narration into a clean merchant name |
| 3 | `services/importer.py` | Reading any bank's CSV or Excel: header detection, date formats, debit/credit layouts, bad rows |
| 4 | `services/categorizer.py` | Learned answers → keyword rules → one batched AI call |
| 5 | `services/analytics.py` | Every number on the dashboard, recurring payments, unusual payments |
| 6 | `ai/llm.py` → `ai/tools.py` → `ai/service.py` | The AI agent: an LLM interface, typed read-only tools, and the tool-calling loop with its limits |
| 7 | `api/deps.py` → `api/*.py` | Logins, rate limits, and the REST routes |
| 8 | `models.py`, `migrations/` | The database tables and how Alembic changes them safely |
| 9 | `frontend/src/lib/api.ts` → `pages/Dashboard.tsx` | How the React app calls the API and draws the charts |
| 10 | `backend/tests/` | How each piece is proven, including a fake AI that needs no internet |

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

## Configuration

Set these in `backend/.env` for local runs, or in the top-level `.env` for Docker.

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
uv run pytest                    # 114 tests, ~10 s, no network or key needed
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

GitHub Actions runs lint, a migration check, both test suites, the frontend type-check and build, and
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
    services/     money, merchants (narration cleaning), importer, imports, categorizer, analytics, clock
    ai/           llm.py (interface + Groq), tools.py (the agent's tools), service.py (agent loop)
    migrations/   Alembic
    models.py  config.py  security.py  db.py  main.py  cli.py
  tests/          114 pytest tests
  data/           sample_statement.csv (MADE-UP practice data) + the script that generates it
  .env.example    local settings (copy to .env)
frontend/src/
  pages/          Dashboard, Transactions, Import, Budgets, Insights, Assistant, Settings, AuthPage
  components/     Layout (sidebar + mobile tabs), shared UI, ErrorBoundary
  lib/            api client, auth context, month context, formatting, categories
Dockerfile  docker-compose.yml  .env.example (Docker settings)  .github/workflows/ci.yml
```

## Using it for your final-year project

- **Understand every file before you present it.** Your examiner will ask *why*, not *what*. The
  [decisions table](#decisions-worth-explaining-in-an-interview) lists the questions worth preparing.
- **Make it yours.** Add at least one feature from the list below, and you have something to talk
  about that nobody else in your batch has.
- **Be honest about where it came from.** Fork it, keep the license, and say what you added.

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
