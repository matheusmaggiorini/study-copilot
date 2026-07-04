"""Abre o Edge para login SSO da Humber em janela separada."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.services.login_state import write_login_status
from app.scraper.browser import interactive_login


def tick(current_url: str, elapsed: int) -> None:
    minutes = elapsed // 60
    write_login_status(
        "running",
        f"Aguardando login SSO ({minutes}m). Use sua conta Humber no navegador que abriu.",
        current_url=current_url,
    )


async def main() -> None:
    write_login_status(
        "running",
        "Navegador aberto. Faça login com sua conta da Humber (Microsoft).",
        current_url="https://learn.humber.ca",
    )

    try:
        result = await interactive_login(timeout_seconds=600, on_tick=tick)
        write_login_status("success", result["message"], current_url=result.get("current_url"))
        print(result["message"])
        print(result.get("current_url"))
    except Exception as exc:
        write_login_status("failed", "Falha ao conectar o Blackboard.", error=str(exc))
        print(f"ERRO: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    asyncio.run(main())
