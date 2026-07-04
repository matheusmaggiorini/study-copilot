from __future__ import annotations

from datetime import date, datetime

from app.scraper.parsers import (
    current_week_bounds,
    extract_dates_from_text,
    is_important_event,
    parse_item_date,
    strip_html,
)

IMPORTANT_KINDS = {
    "midterm",
    "exam",
    "quiz",
    "test",
    "prova",
    "assignment",
    "entrega",
    "lab",
    "project",
}


def week_bounds(reference: datetime | None = None) -> tuple[date, date]:
    return current_week_bounds(reference)


def week_label(reference: datetime | None = None) -> str:
    start, end = week_bounds(reference)
    return f"{start.strftime('%d/%m')} – {end.strftime('%d/%m')}"


def _item_text(item: dict) -> str:
    parts = [
        item.get("title"),
        item.get("body"),
        item.get("name"),
        item.get("item_name"),
        item.get("message"),
    ]
    return strip_html(" ".join(str(p) for p in parts if p))


def _event_dates_for_item(item: dict) -> list[date]:
    dates: list[date] = []
    due = parse_item_date(item.get("due_at"))
    if due:
        dates.append(due)
    dates.extend(extract_dates_from_text(_item_text(item)))
    return sorted(set(dates))


def dates_in_week(item: dict, reference: datetime | None = None) -> list[date]:
    start, end = week_bounds(reference)
    return [value for value in _event_dates_for_item(item) if start <= value <= end]


def is_relevant_for_week(item: dict, reference: datetime | None = None) -> bool:
    return bool(dates_in_week(item, reference))


def best_date_in_week(item: dict, reference: datetime | None = None) -> date | None:
    in_week = dates_in_week(item, reference)
    return min(in_week) if in_week else None


def enrich_assignments_from_announcements(
    assignments: list[dict],
    announcements: list[dict],
) -> None:
    for assignment in assignments:
        if dates_in_week(assignment):
            continue

        assignment_title = (assignment.get("title") or "").lower()
        if not any(keyword in assignment_title for keyword in IMPORTANT_KINDS):
            continue

        for announcement in announcements:
            if announcement.get("course_id") != assignment.get("course_id"):
                continue
            when = best_date_in_week(announcement)
            if not when:
                continue
            ann_title = (announcement.get("title") or "").lower()
            if not any(keyword in ann_title for keyword in IMPORTANT_KINDS):
                continue
            assignment["due_at"] = when.isoformat()
            break


def priority_for_item(item: dict) -> int:
    text = _item_text(item).lower()
    if "midterm" in text or "final exam" in text:
        return 1
    if "exam" in text or "test" in text:
        return 2
    if "quiz" in text:
        return 3
    if "assignment" in text or "entrega" in text or "lab" in text:
        return 4
    return 5
