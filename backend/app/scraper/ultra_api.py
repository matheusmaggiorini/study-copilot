from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page

from app.config import settings
from app.scraper.parsers import clean_text, is_in_current_week, parse_due_date, slug_id, strip_html


class UltraApiClient:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.origin = settings.blackboard_origin

    async def get_json(self, path: str) -> dict[str, Any] | list[Any] | None:
        url = f"{self.origin}{path}"
        response = await self.page.request.get(
            url,
            headers={
                "Accept": "application/json",
                "Referer": settings.blackboard_courses_url,
            },
        )
        if not response.ok:
            return None
        try:
            return await response.json()
        except Exception:
            return None

    async def fetch_courses(self) -> list[dict]:
        payload = await self.get_json("/learn/api/public/v1/users/me/courses?limit=50")
        if not payload:
            return []

        courses: list[dict] = []
        for membership in payload.get("results", []):
            course_id = membership.get("courseId")
            if not course_id:
                continue

            detail = await self.get_json(f"/learn/api/public/v1/courses/{course_id}")
            name = clean_text((detail or {}).get("name")) or course_id
            courses.append(
                {
                    "id": course_id,
                    "name": name,
                    "url": f"{self.origin}/ultra/courses/{course_id}/outline",
                }
            )

        return courses

    async def fetch_activity_stream(self) -> list[dict]:
        return []

    async def fetch_calendar_items(self) -> list[dict]:
        return []

    async def fetch_course_announcements(self, course_id: str, course_name: str) -> list[dict]:
        payload = await self.get_json(
            f"/learn/api/public/v1/courses/{course_id}/announcements?limit=20"
        )
        if not payload:
            return []

        items: list[dict] = []
        for entry in payload.get("results", []):
            title = clean_text(entry.get("title"))
            if not title:
                continue
            items.append(
                {
                    "kind": "announcement",
                    "id": slug_id("announcement", course_id, title, entry.get("id", "")),
                    "course_id": course_id,
                    "course_name": course_name,
                    "title": title,
                    "body": strip_html(entry.get("body")),
                    "posted_at": _iso_or_text(entry.get("created") or entry.get("modified")),
                    "url": f"{self.origin}/ultra/courses/{course_id}/outline",
                }
            )
        return items

    async def fetch_course_assignments(self, course_id: str, course_name: str) -> list[dict]:
        payload = await self.get_json(
            f"/learn/api/public/v1/courses/{course_id}/contents?recursive=true&limit=100"
        )
        if not payload:
            return []

        items: list[dict] = []
        for entry in payload.get("results", []):
            title = clean_text(entry.get("title"))
            if not title:
                continue

            handler = (entry.get("contentHandler") or {}).get("id") or ""
            due_at = _iso_or_text(
                entry.get("endDate")
                or entry.get("dueDate")
                or entry.get("availability", {}).get("adaptiveRelease", {}).get("end")
            )
            has_due = bool(due_at)
            is_task = any(
                token in handler.lower()
                for token in ("assignment", "asmt", "test", "quiz", "assessment", "scorm")
            )

            if not has_due and not is_task:
                continue

            items.append(
                {
                    "kind": "assignment",
                    "id": slug_id("assignment", course_id, title, due_at or entry.get("id", "")),
                    "course_id": course_id,
                    "course_name": course_name,
                    "title": title,
                    "due_at": due_at,
                    "status": clean_text(entry.get("status")),
                    "url": f"{self.origin}/ultra/courses/{course_id}/outline",
                }
            )
        return items

    async def fetch_course_grades(self, course_id: str, course_name: str) -> list[dict]:
        payload = await self.get_json(
            f"/learn/api/public/v1/courses/{course_id}/gradebook/columns?limit=50"
        )
        if not payload:
            return []

        items: list[dict] = []
        for column in payload.get("results", []):
            name = clean_text(column.get("name"))
            if not name:
                continue

            grades = column.get("grades") or column.get("columnGrades") or []
            grade_entry = grades[0] if isinstance(grades, list) and grades else {}
            possible = column.get("score", {}).get("possible")
            score = grade_entry.get("score")
            display = grade_entry.get("displayGrade") or grade_entry.get("text")

            score_text = _format_score(display or score)
            max_score = _format_score(possible)
            percentage = None
            if score_text and max_score:
                try:
                    percentage = f"{round((float(score_text) / float(max_score)) * 100, 1)}%"
                except ValueError:
                    percentage = None

            items.append(
                {
                    "id": slug_id(course_id, name, score_text or ""),
                    "course_id": course_id,
                    "course_name": course_name,
                    "item_name": name,
                    "score": score_text,
                    "max_score": max_score,
                    "percentage": percentage,
                    "feedback": clean_text(grade_entry.get("feedback")),
                }
            )
        return items


def _iso_or_text(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return parse_due_date(text)


def _format_score(value: Any) -> str | None:
    if value is None:
        return None
    text = clean_text(str(value))
    return text or None
