from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import database as db
from app.models import ChatRequest, ChatResponse, StatusResponse
from app.services.login_state import read_login_status, write_login_status
from app.services.ollama import build_morning_briefing, chat_with_context, ollama_is_available

BACKEND_DIR = Path(__file__).resolve().parent.parent
LOGIN_SCRIPT = BACKEND_DIR / "login.py"
SYNC_SCRIPT = BACKEND_DIR / "sync_job.py"
_login_process: subprocess.Popen | None = None

app = FastAPI(title="Study Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _login_process_running() -> bool:
    global _login_process
    return _login_process is not None and _login_process.poll() is None


def _run_sync_job() -> dict:
    completed = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        message = stderr or stdout or "Falha ao sincronizar o Blackboard."
        return {"ok": False, "message": message}

    output = (completed.stdout or "").strip()
    if not output:
        return {"ok": False, "message": "Sync não retornou dados."}

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"ok": False, "message": "Resposta inválida do sync."}


@app.on_event("startup")
async def startup() -> None:
    await db.init_db()
    write_login_status("idle", "Clique em Conectar Blackboard para abrir o navegador.")


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    return StatusResponse(
        session_exists=settings.session_path.exists(),
        ollama_available=await ollama_is_available(),
        blackboard_login_url=settings.blackboard_login_url,
        blackboard_courses_url=settings.blackboard_courses_url,
    )


def _spawn_login_process() -> None:
    global _login_process

    if _login_process_running():
        return

    creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    _login_process = subprocess.Popen(
        [sys.executable, str(LOGIN_SCRIPT)],
        cwd=str(BACKEND_DIR),
        creationflags=creationflags,
    )


@app.post("/auth/login")
async def auth_login() -> dict:
    current = read_login_status()

    if current.get("status") == "running" and _login_process_running():
        return {
            "ok": True,
            "status": "running",
            "message": current.get("message", "Login em andamento."),
        }

    write_login_status(
        "running",
        "Abrindo navegador em nova janela. Faça login com sua conta da Humber.",
        current_url=settings.blackboard_login_url,
    )

    try:
        _spawn_login_process()
    except Exception as exc:
        write_login_status("failed", "Não foi possível abrir o navegador.", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ok": True,
        "status": "running",
        "message": "Navegador aberto. Faça login SSO da Humber e aguarde.",
    }


@app.get("/auth/login/status")
async def auth_login_status() -> dict:
    payload = read_login_status()

    if payload.get("status") == "running" and not _login_process_running():
        payload["status"] = "failed"
        payload["message"] = "Processo de login encerrou antes de concluir."
        payload["error"] = payload.get("error") or "Tente conectar novamente."

    payload["session_exists"] = settings.session_path.exists()
    return payload


@app.post("/sync")
async def sync() -> dict:
    result = await asyncio.to_thread(_run_sync_job)
    if not result.get("ok"):
        detail = (result.get("message") or "").strip() or "Falha ao sincronizar o Blackboard."
        raise HTTPException(status_code=400, detail=detail)
    return result


@app.get("/dashboard")
async def dashboard() -> dict:
    return await db.fetch_dashboard_payload()


@app.get("/briefing")
async def briefing() -> dict:
    if not await ollama_is_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama não está rodando. Instale e execute: ollama serve",
        )
    context = await db.export_context_for_agent()
    text = await build_morning_briefing(context)
    return {"briefing": text}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="Mensagem vazia")
    if not await ollama_is_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama não está rodando. Instale e execute: ollama serve",
        )
    context = await db.export_context_for_agent()
    reply = await chat_with_context(payload.message.strip(), context)
    return ChatResponse(reply=reply)
