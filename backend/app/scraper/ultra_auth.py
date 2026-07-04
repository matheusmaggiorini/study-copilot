from __future__ import annotations

import asyncio

from playwright.async_api import BrowserContext, Page

from app.config import settings


def _is_humber_url(url: str) -> bool:
    return "learn.humber.ca" in url.lower()


def _is_idp_url(url: str) -> bool:
    lowered = url.lower()
    markers = (
        "microsoftonline",
        "login.microsoft",
        "adfs",
        "shibboleth",
        "oauth",
        "login.live",
    )
    return any(marker in lowered for marker in markers)


def _is_login_gateway(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ("/login", "/signin", "webapps/login"))


async def is_logged_in(page: Page) -> bool:
    url = page.url

    if _is_idp_url(url):
        return False

    if not _is_humber_url(url):
        return False

    if _is_login_gateway(url):
        return False

    if "/ultra/" in url.lower() or "/webapps/" in url.lower():
        return True

    title = (await page.title()).lower()
    if "blackboard" in title or "humber" in title:
        return True

    try:
        selectors = (
            "a[href*='/ultra/course']",
            "a[href*='/ultra/courses/']",
            "[data-course-id]",
            "bb-course-list",
            "bb-base-navigation",
        )
        for selector in selectors:
            if await page.locator(selector).count() > 0:
                return True
    except Exception:
        pass

    return False


async def find_logged_in_page(context: BrowserContext) -> Page | None:
    for page in context.pages:
        try:
            if await is_logged_in(page):
                return page
        except Exception:
            continue
    return None


async def wait_for_login(
    context: BrowserContext,
    timeout_seconds: int = 600,
    on_tick=None,
) -> Page:
    elapsed = 0
    while elapsed < timeout_seconds:
        page = await find_logged_in_page(context)
        if page:
            return page

        current_url = context.pages[0].url if context.pages else settings.blackboard_login_url
        if on_tick:
            on_tick(current_url, elapsed)

        await asyncio.sleep(1)
        elapsed += 1

    urls = ", ".join(page.url for page in context.pages[:4]) or "nenhuma"
    raise RuntimeError(
        "Tempo esgotado. Faça login com sua conta Humber no Edge e aguarde voltar ao Blackboard. "
        f"URLs abertas: {urls}"
    )


async def wait_for_ultra_shell(page: Page, timeout_ms: int = 90_000) -> None:
    await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=25_000)
    except Exception:
        pass
    await page.wait_for_timeout(3000)
