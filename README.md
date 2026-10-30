# Resume Matcher

A full-stack app that scores a resume against a job description. Students check their own resume and get tips. HR users screen a batch of resumes and get a ranked shortlist.

**Stack:** FastAPI, MySQL, SQLAlchemy, JWT auth, React (Vite), Groq LLM, Pydantic.

## What it does

**Student account**
- Upload one resume and a job description (paste or file).
- Get a match score, matching and missing skills, a short verdict, and tips to improve the resume.
- Resume format checks (readable text, contact details, sections, links, length).
- History of past checks, each one deletable.

**HR account** (needs an invite code to sign up)
- Save job descriptions once and reuse them.
- Upload up to 10 resumes per batch. Screening runs in the background and the page shows live progress.
- Ranked table, score chart, search, adjustable "top N" highlight.
- Must-have skills: candidates missing one are flagged and can be hidden.
- Blind mode hides names, emails and file names on screen and in the CSV.
- Shortlist or reject each candidate, compare up to 3 side by side, download results as CSV.

## Architecture

### Overall system

The React app talks to the FastAPI backend over HTTP. Every request carries a JWT. The backend checks who the user is, does the work, saves results in MySQL, and calls Groq only for reading text and answering skill questions.

```mermaid
flowchart TB
    A["<b>Browser: React app</b><br/>Login, Student pages, HR pages<br/>api.js adds the JWT token to every request"]
    B["<b>FastAPI entry: main.py</b><br/>CORS and error handling"]
    C["<b>Security: deps.py</b><br/>Verify JWT, load user, check role"]
    D["<b>Routers</b><br/>auth, student, hr"]
    E["<b>Services</b><br/>documents.py: read PDF, DOCX, TXT<br/>engine.py: parse, check skills, score<br/>common.py: daily limits, reuse parsed JD<br/>serializers.py: blind mode, CSV"]
    F["<b>Background task: process_batch</b><br/>HR batches, 3 resumes at a time"]
    G[("<b>MySQL</b><br/>users, job_descriptions,<br/>batches, analyses")]
    H["<b>Groq API</b><br/>Language model"]

    A -->|"HTTP request + JWT"| B
    B --> C
    C --> D
    D --> E
    D -->|"HR batch upload"| F
    F --> E
    D -->|"read and write"| G
    F -->|"save results"| G
    E -->|"parse JD, parse resume, check skills"| H
```

### How the score is calculated

The AI only answers whether each skill is present. Python calculates the final number, so the same resume gets the same score.

```mermaid
flowchart TD
    A["Resume text"] --> B["Remove wrapper tags, cap length, flag injection phrases"]
    B --> C["AI: parse resume into structured data"]
    C --> D["Remove name, email, phone"]
    D --> E["AI: for each required and preferred skill, present or not, plus evidence quote"]
    E --> F{"Skill or quote really found in resume text?"}
    F -->|yes| G["Count the skill"]
    F -->|no| H["Do not count, add a warning flag"]
    G --> I["Python calculates score"]
    H --> I
    I --> J["70% required skills + 15% preferred skills + 15% experience"]
    J --> K["Score 0 to 100 with breakdown"]
```

### HR batch flow

A batch runs in the background so the upload returns immediately. The page checks progress every 2 seconds until the batch is done.

```mermaid
sequenceDiagram
    actor H as HR user
    participant R as React app
    participant F as FastAPI
    participant B as Background task
    participant G as Groq
    participant D as MySQL

    H->>R: Choose job, add must-haves, upload resumes
    R->>F: POST /hr/batches (with JWT)
    F->>D: Create batch and one pending row per resume
    F-->>R: Batch id (returns immediately)
    F->>B: Start process_batch
    loop every 2 seconds
        R->>F: GET /hr/batches/id
        F->>D: Read progress
        F-->>R: Status and results so far
    end
    par 3 resumes at a time
        B->>G: Parse and check skills
        G-->>B: Answers
        B->>D: Save score or error for that resume
    end
    B->>D: Mark batch done
    R->>F: GET /hr/batches/id?blind=true
    F-->>R: Ranked list, names hidden in blind mode
    H->>R: Shortlist, reject, compare, download CSV
```

## How the score works

The AI never invents the percentage. It only answers one question per skill: "does this resume show this skill, and where?" Python then calculates the score:

| Part | Weight |
|---|---|
| Required skills found | 70% |
| Preferred skills found | 15% |
| Years of experience vs. the minimum asked | 15% |

If a part does not apply (for example no preferred skills in the job description), the other weights are scaled up so the score still runs from 0 to 100. The result screen shows this breakdown, so every score can be explained.

Other safeguards in `backend/app/services/engine.py`:
- Temperature 0 and a fixed seed, so repeated runs stay close.
- Every AI answer is validated with Pydantic. Missing or null fields fall back to defaults. A bad answer is retried once.
- **Claim checking:** if the AI says a skill is present, the skill or its evidence quote must really appear in the resume text. Otherwise it is not counted.
- **Prompt injection:** uploaded text is wrapped in tags and treated as data, wrapper tags inside the text are stripped, and phrases like "ignore previous instructions" flag the candidate for a manual look.
- **Privacy in scoring:** name, email and phone are removed from what the scoring step sees, including when they appear inside free text.
- Retries with backoff on the real Groq rate-limit and connection errors.

## Run it on your computer

You need Python 3.11 or newer, Node 20 or newer, MySQL 8, and a free Groq API key.

**1. Create the database** (in MySQL Workbench or the `mysql` command line):
```
CREATE DATABASE resume_matcher CHARACTER SET utf8mb4;
```

**2. Backend** (run these inside the `backend` folder)
```
python -m venv venv
venv\Scripts\activate          # on Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # on Mac/Linux: cp .env.example .env
```
Open `backend/.env` and fill in these four values:

| Setting | What to put |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/resume_matcher?charset=utf8mb4`. Use your own MySQL password. If it has symbols like `@` or `#`, pick a simpler one, because they break the URL. |
| `JWT_SECRET` | A long random string that only you know. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `HR_INVITE_CODE` | Any code you make up. People must type it to sign up as HR. |
| `GROQ_API_KEY` | Create one at console.groq.com under API Keys. |

**What is `JWT_SECRET`?** When someone logs in, the server hands their browser a token that says who they are. The server signs that token with this secret, and checks the signature on every request. Anyone who knows the secret could forge a token and pretend to be any user, including HR, so keep it private and never upload it to GitHub. If you change it, everyone is logged out.

Then start the backend:
```
uvicorn app.main:app --reload
```
Check `http://127.0.0.1:8000/health` and the API docs at `http://127.0.0.1:8000/docs`. Tables are created automatically on first start.

**3. Frontend** (run these inside the `frontend` folder)
```
npm install
npm run dev
```
Open `http://localhost:5173`.

## Tests

```
cd backend
pytest -q
```
51 tests cover auth, roles, data isolation between accounts, the score maths, the AI safeguards, student and HR flows, CSV safety and file validation. They use a fake AI, so they need no API key and cost nothing. By default they run on a temporary in-memory database. To run them on a real MySQL database, set `TEST_DATABASE_URL` to an empty test database first (the GitHub Actions workflow does this).

## Measure the accuracy yourself

`backend/eval` compares the new scoring with the original "AI invents the percentage" method on 6 sample resumes. It needs your Groq key:

```
cd backend
python -m eval.run_eval --runs 5 --baseline
```

It prints the spread between repeated runs for both methods, and how well the ranking agrees with the human scores in `sample_data/cases.json`. Replace the sample files with your own (remove personal details first) for a more convincing result. Only quote numbers you have measured.

## API overview

| Method and path | Who | Purpose |
|---|---|---|
| POST `/auth/register`, `/auth/login` | anyone | Sign up (HR needs invite code) and log in |
| GET `/auth/me`, DELETE `/auth/me` | logged in | Profile, delete account and all data |
| POST `/student/analyze` | student | Score one resume |
| GET/DELETE `/student/history[/{id}]` | student | Past checks |
| POST/GET/DELETE `/hr/jds[/{id}]` | HR | Job descriptions |
| POST `/hr/batches` | HR | Start a batch (runs in the background) |
| GET `/hr/batches[/{id}]` | HR | Progress, ranked results, stats (`?blind=true`) |
| GET `/hr/batches/{id}/export` | HR | CSV download |
| GET `/hr/analyses/{id}`, PATCH `.../decision` | HR | One candidate, shortlist or reject |

## Project layout

```
backend/app/
  main.py            app setup, CORS, error handlers
  core/              settings, JWT and password hashing, login limiter
  db/session.py      database connection
  models.py          tables
  deps.py            current user and role checks
  routers/           auth.py, student.py, hr.py
  services/          engine.py (AI and scoring), documents.py, common.py, serializers.py
backend/tests/       automated tests
backend/eval/        accuracy measurement
frontend/src/        React app (pages, components, auth context, API client)
```

## Security notes

- Passwords are hashed with bcrypt. Tokens are signed JWTs that expire after 60 minutes (change with `ACCESS_TOKEN_MINUTES`).
- HR signup needs `HR_INVITE_CODE`. Roles are checked on the server from the database, not trusted from the token.
- Every query is filtered by the logged-in user, so accounts cannot see each other's data.
- 8 failed logins from the same address and email lock that login for 15 minutes.
- Daily analysis limits per account protect your Groq quota.
- Uploads are limited by type, size and file signature. Uploaded files are never saved, only the results.
- CSV exports are protected against spreadsheet formula injection.

## Known limitations

- Scanned or image-only resumes are not read (OCR is a good next feature).
- The in-memory login limiter resets on restart and is per process. Use Redis if you run several servers.
- Tables are created with `create_all`. For a long-lived deployment, add Alembic migrations.
- Batches run in the API process. A server restart during a batch will interrupt it. A job queue (Celery or RQ) is the next step at scale.
- The AI can still misjudge a skill. The claim check blocks invented evidence but cannot catch every mistake, and a resume that lists a skill it does not really have will still get credit for it. Treat scores as a screening aid, not a decision.
- The JWT is stored in the browser's localStorage, the same approach as many small apps. HttpOnly cookies are stronger if you deploy this for real users.