from __future__ import annotations

from bs4 import BeautifulSoup

from app.config import settings
from app.db import database as db
from app.scraper.browser import BlackboardBrowser
from app.scraper.parsers import extract_links, parse_announcements, parse_assignments, parse_grades
from app.scraper.ultra_api import UltraApiClient
from app.scraper.ultra_auth import is_logged_in, wait_for_ultra_shell
from app.services.alerts import build_alerts


async def _safe_goto(page, url: str) -> bool:
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        await wait_for_ultra_shell(page)
        return bool(response and response.ok)
    except Exception:
        return False


async def sync_blackboard() -> dict:
    run_id = await db.start_sync_run()

    if not settings.session_path.exists() and not settings.browser_profile_dir.exists():
        await db.finish_sync_run(
            run_id,
            "failed",
            "Sessão não encontrada. Clique em Conectar Blackboard primeiro.",
        )
        return {"ok": False, "message": "Sessão não encontrada. Faça login primeiro."}

    try:
        async with BlackboardBrowser() as browser:
            page = await browser.new_page()
            await _safe_goto(page, settings.blackboard_courses_url)

            if not await is_logged_in(page):
                await db.finish_sync_run(run_id, "failed", "Sessão expirada. Faça login novamente.")
                return {"ok": False, "message": "Sessão expirada. Faça login novamente."}

            api = UltraApiClient(page)
            courses = await api.fetch_courses()

            if not courses:
                html = await page.content()
                courses = extract_links(BeautifulSoup(html, "lxml"), page.url)

            all_announcements: list[dict] = []
            all_assignments: list[dict] = []
            all_grades: list[dict] = []

            stream_items = await api.fetch_activity_stream()
            calendar_items = await api.fetch_calendar_items()

            for item in stream_items + calendar_items:
                if item["kind"] == "announcement":
                    all_announcements.append(item)
                else:
                    all_assignments.append(item)

            for course in courses[:15]:
                course_id = course["id"]
                course_name = course["name"]

                all_announcements.extend(await api.fetch_course_announcements(course_id, course_name))
                all_assignments.extend(await api.fetch_course_assignments(course_id, course_name))
                all_grades.extend(await api.fetch_course_grades(course_id, course_name))

            if not all_assignments:
                html = await page.content()
                all_assignments.extend(
                    parse_assignments(html, course_name="Geral", course_id="general", base_url=page.url)
                )

            if not all_announcements:
                for course in courses[:8]:
                    if await _safe_goto(page, course["url"]):
                        all_announcements.extend(
                            parse_announcements(
                                await page.content(),
                                course_name=course["name"],
                                course_id=course["id"],
                                base_url=page.url,
                            )
                        )

            if not all_grades:
                for course in courses[:8]:
                    grade_url = f"{settings.blackboard_origin}/ultra/courses/{course['id']}/grades"
                    if await _safe_goto(page, grade_url):
                        all_grades.extend(
                            parse_grades(
                                await page.content(),
                                course_name=course["name"],
                                course_id=course["id"],
                            )
                        )

            deduped_assignments = _dedupe(all_assignments, "id")
            deduped_announcements = _dedupe(all_announcements, "id")
            deduped_grades = _dedupe(all_grades, "id")

            await db.clear_academic_data()
            await db.upsert_courses(courses)
            await db.upsert_announcements(_strip_kind(deduped_announcements))
            await db.upsert_assignments(_strip_kind(deduped_assignments))
            await db.upsert_grades(deduped_grades)

            alerts = build_alerts(deduped_announcements, deduped_assignments, deduped_grades)
            await db.replace_alerts(alerts)
            await browser.save_session()

            summary = {
                "ok": True,
                "courses": len(courses),
                "announcements": len(deduped_announcements),
                "assignments": len(deduped_assignments),
                "grades": len(deduped_grades),
                "alerts": len(alerts),
                "source": "humber_ultra_api",
            }
            await db.finish_sync_run(run_id, "success", str(summary))
            return summary

    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__ or "Erro desconhecido no sync"
        await db.finish_sync_run(run_id, "failed", message)
        return {"ok": False, "message": message}


def _dedupe(items: list[dict], key: str) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        value = item.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def _strip_kind(items: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for item in items:
        copy = {key: value for key, value in item.items() if key != "kind"}
        cleaned.append(copy)
    return cleaned
