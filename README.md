# Study Copilot

Assistente pessoal **zero custo** que lê o Blackboard da Humber, organiza a semana de estudos e conversa com você via IA local (Ollama).

> Projeto de portfólio: automação real com Playwright, API REST interna do Blackboard Ultra, backend FastAPI e frontend Next.js — sem depender de serviços pagos.

![Dashboard filtrado por semana](docs/screenshots/dashboard.png)

## Propósito

Faculdade gera muito ruído: dezenas de anúncios, tarefas espalhadas e prazos escondidos no texto. O **Study Copilot** centraliza isso em um painel simples que responde:

- O que importa **nesta semana** (alertas, lições, anúncios)
- Como estão as **notas**
- O que fazer **agora** (briefing + chat com contexto real)

Tudo roda **localmente**: sessão do Blackboard, banco SQLite e Ollama na sua máquina.

## O que faz

| Recurso | Descrição |
|---|---|
| Login SSO | Abre Chromium via Playwright; você faz login Microsoft/Humber uma vez |
| Sync | Puxa cursos, anúncios, conteúdos e notas do Blackboard Ultra |
| Alertas | Provas, quizzes e prazos detectados por data no texto |
| Filtro semanal | Dashboard mostra só o que cai na semana calendário (seg–dom) |
| Briefing | Resumo matinal gerado pelo Ollama com dados reais |
| Chat | Perguntas como “o que entregar hoje?” usando contexto sincronizado |

## Stack (100% grátis)

- **Backend:** Python, FastAPI, Playwright, SQLite
- **Frontend:** Next.js 15, React, Tailwind CSS
- **IA:** Ollama local (`llama3.2` ou similar)

## Como foi feito

### 1. Acesso ao Blackboard (sem API oficial)

O Blackboard Ultra da Humber **não expõe API pública estável** para alunos. A solução:

1. **Login** em subprocesso separado (`login.py`) — evita conflito com SSO/Windows
2. **Sessão persistida** em `data/session.json` + perfil Chromium
3. **Chamadas REST internas** descobertas via DevTools, por exemplo:
   - `GET /learn/api/public/v1/users/me/courses`
   - `GET /learn/api/public/v1/courses/{id}/announcements`
   - `GET /learn/api/public/v1/courses/{id}/contents?recursive=true`
   - `GET /learn/api/public/v1/courses/{id}/gradebook/columns`

### 2. Sync robusto no Windows

Playwright não roda bem dentro do loop asyncio do uvicorn no Windows. Por isso:

- Sync dispara **`sync_job.py` como subprocesso**
- API FastAPI só orquestra e lê o SQLite depois

### 3. Inteligência de datas

Muitos prazos vêm só no **texto** do anúncio (“Midterm on July 9”), não em `due_at`. O parser:

- Extrai datas em formatos `Jul 9`, `09/07/2026`, `June 29, 2026`
- Filtra por **semana calendário** (segunda a domingo)
- Gera alertas só para itens relevantes à semana atual

### 4. UI focada na semana

O dashboard não lista histórico inteiro (35 anúncios, 75 tarefas). Mostra apenas:

- Alertas da semana
- Lições com prazo na semana
- Anúncios com evento na semana

## Arquitetura

```text
┌─────────────┐     REST      ┌──────────────┐     Playwright    ┌──────────────┐
│  Next.js    │ ◄──────────► │   FastAPI    │ ◄──────────────► │  Blackboard  │
│  Dashboard  │   :3000/:8000 │   + SQLite   │   session.json  │  Humber SSO  │
└─────────────┘               └──────┬───────┘                 └──────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │    Ollama    │
                              │  (opcional)  │
                              └──────────────┘
```

```text
study-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py              # rotas FastAPI
│   │   ├── scraper/
│   │   │   ├── browser.py       # login + sync browsers
│   │   │   ├── ultra_api.py     # APIs internas Humber
│   │   │   ├── sync.py          # orquestração do sync
│   │   │   └── parsers.py       # HTML, datas, filtros
│   │   ├── services/
│   │   │   ├── alerts.py        # geração de alertas
│   │   │   ├── relevance.py     # lógica da semana
│   │   │   └── week_filter.py   # filtro do dashboard
│   │   └── db/database.py       # SQLite
│   ├── login.py                 # login SSO standalone
│   └── sync_job.py              # sync em subprocesso
├── frontend/
│   └── components/Dashboard.tsx # UI principal
├── docs/screenshots/            # prints para README
└── start-all.ps1                # sobe backend + frontend
```

## Setup rápido

### Pré-requisitos

- Python 3.12+
- Node.js 18+
- [Ollama](https://ollama.com/) (opcional, para chat/briefing)

### 1. Ollama (opcional)

```bash
ollama pull llama3.2
ollama serve
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Configure `.env` (exemplo Humber):

```env
BLACKBOARD_LOGIN_URL=https://learn.humber.ca
BLACKBOARD_COURSES_URL=https://learn.humber.ca/ultra/course
SYNC_HEADLESS=false
```

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Atalho (Windows)

```powershell
.\start-all.ps1
```

Abra **http://localhost:3000**

## Primeiro uso

1. **Conectar Blackboard** — janela Chromium abre; faça login SSO/MFA da Humber
2. **Sincronizar agora** — baixa cursos, anúncios, tarefas e notas
3. Veja alertas e anúncios **desta semana**
4. Use **Briefing do dia** ou o chat (com Ollama ligado)

## Screenshots

| Dashboard semanal | Descrição |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | Alertas, lições e anúncios filtrados para a semana 29/06–05/07 |

## Segurança

**Nunca commite:**

- `.env`
- `data/session.json`
- `data/study_copilot.db`
- perfil do navegador em `data/browser_profile/`

Esses arquivos já estão no `.gitignore`.

## Limitações conhecidas

- HTML e APIs variam por universidade — parsers podem precisar ajuste
- Sessão SSO expira; reconecte quando o sync falhar
- Nem todo conteúdo traz `due_at`; prazos dependem de extração de texto
- Ollama offline desabilita chat/briefing, mas o dashboard funciona


## Licença

MIT — use livremente para estudo e portfólio.
