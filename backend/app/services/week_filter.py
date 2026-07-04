from __future__ import annotations

from app.scraper.parsers import strip_html
from app.services.relevance import (
    best_date_in_week,
    enrich_assignments_from_announcements,
    is_relevant_for_week,
    priority_for_item,
    week_bounds,
    week_label,
)


def _format_when(item: dict) -> str:
    when = best_date_in_week(item)
    return when.strftime("%d/%m") if when else ""


def _build_week_alerts(items: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    seen: set[str] = set()

    ranked = sorted(
        items,
        key=lambda item: (priority_for_item(item), _format_when(item), item.get("title", "")),
    )

    for item in ranked:
        when = best_date_in_week(item)
        if not when:
            continue

        title = strip_html(item.get("title") or item.get("item_name") or "Evento")
        course = item.get("course_name", "Curso")
        body = strip_html(item.get("body") or "")
        preview = body[:120] + ("..." if len(body) > 120 else "")

        dedupe_key = f"{item.get('course_id')}|{when.isoformat()}|{priority_for_item(item)}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        lower = title.lower()
        if "midterm" in lower or "exam" in lower:
            severity = "high"
            alert_title = "Prova esta semana"
        elif "quiz" in lower or "test" in lower:
            severity = "medium"
            alert_title = "Quiz esta semana"
        else:
            severity = "info"
            alert_title = "Prazo esta semana"

        alerts.append(
            {
                "id": f"week-{item.get('id', dedupe_key)}",
                "kind": "important",
                "severity": severity,
                "title": alert_title,
                "message": f"{title} — {course} ({_format_when(item)}). {preview}".strip(),
                "related_id": item.get("id"),
                "dismissed": 0,
            }
        )

    return alerts[:8]


def filter_dashboard_for_week(payload: dict) -> dict:
    label = week_label()
    start, end = week_bounds()

    raw_announcements = list(payload.get("announcements", []))
    raw_assignments = list(payload.get("assignments", []))

    enrich_assignments_from_announcements(raw_assignments, raw_announcements)

    announcements = [
        {
            **item,
            "title": strip_html(item.get("title")),
            "body": strip_html(item.get("body")),
            "when": _format_when(item),
        }
        for item in raw_announcements
        if is_relevant_for_week(item)
    ]

    assignments = [
        {
            **item,
            "title": strip_html(item.get("title")),
            "when": _format_when(item),
        }
        for item in raw_assignments
        if is_relevant_for_week(item)
    ]

    week_items = [*announcements, *assignments]
    alerts = _build_week_alerts(week_items)

    if not alerts:
        alerts.append(
            {
                "id": 0,
                "kind": "all_clear",
                "severity": "info",
                "title": "Semana tranquila",
                "message": f"Nada agendado para {label}.",
                "related_id": None,
                "dismissed": 0,
            }
        )

    announcements.sort(key=lambda item: (priority_for_item(item), item.get("when", "")))
    assignments.sort(key=lambda item: (priority_for_item(item), item.get("when", "")))

    return {
        **payload,
        "week_label": label,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "announcements": announcements,
        "assignments": assignments,
        "grades": [],
        "alerts": alerts,
    }
