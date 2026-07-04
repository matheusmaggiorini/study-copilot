from __future__ import annotations

import asyncio
from typing import Callable

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.config import settings
from app.scraper.ultra_auth import is_logged_in, wait_for_login, wait_for_ultra_shell


class LoginBrowser:
    async def __aenter__(self) -> "LoginBrowser":
        settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(settings.browser_profile_dir.resolve()),
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
            viewport=None,
        )
        self._context.set_default_timeout(120_000)
        self._context.on("page", lambda popup: asyncio.create_task(_focus_page(popup)))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._context.close()
        await self._playwright.stop()

    @property
    def context(self) -> BrowserContext:
        return self._context

    async def new_page(self) -> Page:
        if self.context.pages:
            return self.context.pages[0]
        return await self.context.new_page()

    async def save_session(self) -> None:
        settings.session_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(settings.session_path))


class SyncBrowser:
    def __init__(self, *, headless: bool | None = None) -> None:
        self._headless = settings.sync_headless if headless is None else headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Browser context not initialized")
        return self._context

    async def __aenter__(self) -> "SyncBrowser":
        if not settings.session_path.exists():
            raise RuntimeError("Sessão não encontrada. Conecte o Blackboard primeiro.")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(
            storage_state=str(settings.session_path),
            viewport={"width": 1440, "height": 900},
        )
        self._context.set_default_timeout(120_000)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        return await self.context.new_page()

    async def save_session(self) -> None:
        settings.session_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(settings.session_path))


BlackboardBrowser = SyncBrowser


async def interactive_login(
    timeout_seconds: int = 600,
    on_tick: Callable[[str, int], None] | None = None,
) -> dict:
    settings.session_path.parent.mkdir(parents=True, exist_ok=True)

    async with LoginBrowser() as browser:
        page = await browser.new_page()
        await page.goto(settings.blackboard_courses_url, wait_until="domcontentloaded", timeout=120_000)
        await page.wait_for_timeout(2500)

        if not await is_logged_in(page):
            page = await wait_for_login(
                browser.context,
                timeout_seconds=timeout_seconds,
                on_tick=on_tick,
            )

        await page.bring_to_front()
        await page.goto(settings.blackboard_courses_url, wait_until="domcontentloaded", timeout=120_000)
        await wait_for_ultra_shell(page)

        if not await is_logged_in(page):
            raise RuntimeError("Login não confirmado. Aguarde a página de cursos carregar completamente.")

        await browser.save_session()
        return {
            "ok": True,
            "message": "Blackboard Humber conectado com sucesso.",
            "session_path": str(settings.session_path),
            "current_url": page.url,
        }


async def _focus_page(page: Page) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=30_000)
        await page.bring_to_front()
    except Exception:
        pass
