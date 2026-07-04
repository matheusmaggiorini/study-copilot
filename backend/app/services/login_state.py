from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings


def write_login_status(
    status: str,
    message: str,
    *,
    error: str | None = None,
    current_url: str | None = None,
) -> None:
    settings.login_status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "message": message,
        "error": error,
        "current_url": current_url,
        "session_exists": settings.session_path.exists(),
    }
    settings.login_status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_login_status() -> dict[str, Any]:
    if settings.login_status_path.exists():
        try:
            return json.loads(settings.login_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return {
        "status": "idle",
        "message": "Aguardando conexão.",
        "error": None,
        "current_url": None,
        "session_exists": settings.session_path.exists(),
    }
