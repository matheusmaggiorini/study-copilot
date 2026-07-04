from __future__ import annotations

import httpx

from app.config import settings


SYSTEM_PROMPT = """
Você é o Study Copilot, assistente pessoal acadêmico do Matheus.
Responda em português do Brasil, de forma clara, amigável e objetiva.
Use SOMENTE os dados fornecidos no contexto JSON (notas, anúncios, tarefas, alertas).
Se faltar informação, diga o que falta em vez de inventar.
Priorize: entregas de hoje, prazos próximos, anúncios importantes e notas baixas.
Quando analisar notas, explique a situação e sugira ações práticas.
""".strip()


async def chat_with_context(user_message: str, context_json: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CONTEXTO ATUAL:\n{context_json}\n\n"
        f"PERGUNTA DO USUÁRIO:\n{user_message}\n\n"
        "Resposta:"
    )

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "Não consegui gerar uma resposta agora.")


async def build_morning_briefing(context_json: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CONTEXTO ATUAL:\n{context_json}\n\n"
        "Monte um briefing matinal curto com:\n"
        "1) o que fazer hoje\n"
        "2) prazos próximos\n"
        "3) anúncios relevantes\n"
        "4) alertas sobre notas\n"
        "Use bullets e tom de assistente pessoal."
    )

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "Briefing indisponível no momento.")


async def ollama_is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
