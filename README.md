# Study Copilot

> Your Blackboard, without the noise — sync courses locally, see what matters this week, ask an AI what to do first.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A local-first assistant for [Blackboard Ultra](https://www.blackboard.com/). Built around Humber College's instance, but configurable for other campuses.

**No paid APIs. No cloud. Your session stays on your machine.**

![Weekly dashboard — alerts, lessons, and announcements filtered to the current week](docs/screenshots/dashboard.png)

---

## Why this exists

Every semester, Blackboard becomes a pile of announcements, hidden deadlines, and grades spread across seven courses. Most due dates aren't even in a proper field — they're somewhere in a paragraph from Week 3.

Study Copilot pulls that data locally, extracts dates from the text when Blackboard doesn't provide them, and gives you one place to see:

- what's **due this week**
- what **professors posted** that actually matters now
- how your **grades** look
- what to **prioritize** (with Ollama, if you want a chat)

---

## Features

| | |
|---|---|
| **SSO login** | Playwright opens Chromium — sign in once via Microsoft/Humber, session saved locally |
| **Blackboard sync** | Courses, announcements, content items, gradebook columns |
| **Weekly filter** | Dashboard shows the current calendar week (Mon–Sun), not your whole semester |
| **Smart alerts** | Midterms, quizzes, and deadlines parsed from announcement text |
| **Morning briefing** | Optional daily summary via Ollama |
| **Personal chat** | Ask things like *"what should I submit first?"* using real synced data |

---

## Tech stack

**Backend** — Python, FastAPI, Playwright, SQLite  
**Frontend** — Next.js, React, Tailwind CSS  
**AI** — Ollama (`llama3.2` or any model you prefer)

All free, all local.

---

## How it works

Blackboard doesn't expose a stable public API for students. The workaround:

1. **Browser login** — `login.py` runs as a separate process so SSO popups work on Windows
2. **Session reuse** — internal REST endpoints (found via DevTools) fetch the data:
   ```
   GET /learn/api/public/v1/users/me/courses
   GET /learn/api/public/v1/courses/{id}/announcements
   GET /learn/api/public/v1/courses/{id}/contents?recursive=true
   GET /learn/api/public/v1/courses/{id}/gradebook/columns
   ```
3. **Local storage** — everything lands in SQLite, served through FastAPI

**Windows gotchas I ran into:**

- Playwright can't run inside uvicorn's asyncio loop reliably → sync uses `sync_job.py` as a subprocess
- Most assignments return `due_at: null` → dates get parsed from announcement bodies (`"Midterm on July 9"`, etc.)
- A full sync can return 35+ announcements and 75+ items → week filter keeps the dashboard usable

```
┌──────────────┐      REST       ┌─────────────────┐     Playwright     ┌─────────────┐
│   Next.js    │ ◄────────────► │  FastAPI + SQLite│ ◄────────────────► │  Blackboard │
│   :3000      │                │      :8000       │                    │  (Humber)   │
└──────────────┘                └────────┬─────────┘                    └─────────────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │   Ollama    │
                                  │  (optional) │
                                  └─────────────┘
```

---

## Quick start

**Requirements:** Python 3.12+, Node 18+, optionally [Ollama](https://ollama.com/)

```powershell
# Clone and run (Windows)
git clone https://github.com/matheusmaggiorini/study-copilot.git
cd study-copilot
.\start-all.ps1
```

Open **http://localhost:3000** → **Connect Blackboard** → sign in → **Sync now**.

<details>
<summary>Manual setup</summary>

**Ollama** (optional):

```bash
ollama pull llama3.2
ollama serve
```

**Backend:**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Edit `backend/.env` for your campus:

```env
BLACKBOARD_LOGIN_URL=https://learn.humber.ca
BLACKBOARD_COURSES_URL=https://learn.humber.ca/ultra/course
SYNC_HEADLESS=false
```

</details>

---

## Project structure

```
study-copilot/
├── backend/
│   ├── app/scraper/       # browser login, Ultra API, HTML/date parsers
│   ├── app/services/      # alerts, week filter, Ollama integration
│   ├── app/db/            # SQLite persistence
│   ├── login.py           # standalone SSO login
│   └── sync_job.py        # sync subprocess (Windows-safe)
├── frontend/
│   └── components/Dashboard.tsx
├── docs/screenshots/
└── start-all.ps1
```

---

## Privacy

These files stay on your machine and are **gitignored** — never commit them:

- `.env`
- `data/session.json`
- `data/study_copilot.db`
- `data/browser_profile/`

---

## Known limitations

- Blackboard varies by institution — parsers may need tweaks for your school
- SSO sessions expire; reconnect when sync fails
- Chat/briefing require Ollama; the dashboard works without it
- Text-based date parsing isn't perfect when deadlines aren't structured

---

## License

MIT — free to use for learning and portfolio projects.
