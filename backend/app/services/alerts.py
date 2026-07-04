from __future__ import annotations

from app.scraper.parsers import parse_percentage, strip_html
from app.services.relevance import (
    best_date_in_week,
    is_relevant_for_week,
    priority_for_item,
    week_label,
)


def build_alerts(
    announcements: list[dict],
    assignments: list[dict],
    grades: list[dict],
) -> list[dict]:
    alerts: list[dict] = []
    label = week_label()
    seen: set[str] = set()

    candidates = [
        *(item for item in announcements if is_relevant_for_week(item)),
        *(item for item in assignments if is_relevant_for_week(item)),
    ]
    candidates.sort(key=lambda item: (priority_for_item(item), best_date_in_week(item) or ""))

    for item in candidates:
        when = best_date_in_week(item)
        if not when:
            continue

        title = strip_html(item.get("title", "Evento"))
        course = item.get("course_name", "Curso")
        body_preview = strip_html(item.get("body"))[:120]
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
                "kind": "important",
                "severity": severity,
                "title": alert_title,
                "message": f"{title} — {course} ({when.strftime('%d/%m')}). {body_preview}".strip(),
                "related_id": item.get("id"),
            }
        )

    course_scores: dict[str, list[float]] = {}
    for grade in grades:
        percentage = parse_percentage(grade.get("percentage") or grade.get("score"))
        if percentage is None:
            continue
        course_scores.setdefault(grade["course_name"], []).append(percentage)

    for course_name, values in course_scores.items():
        average = round(sum(values) / len(values), 2)
        if average < 60:
            alerts.append(
                {
                    "kind": "grade_warning",
                    "severity": "high",
                    "title": "Nota baixa detectada",
                    "message": f"Média aproximada em {course_name}: {average}%.",
                    "related_id": slug_course(course_name),
                }
            )

    if not alerts:
        alerts.append(
            {
                "kind": "all_clear",
                "severity": "info",
                "title": "Semana tranquila",
                "message": f"Nada agendado para {label}.",
                "related_id": None,
            }
        )

    return alerts


def slug_course(course_name: str) -> str:
    return course_name.lower().replace(" ", "-")[:32]
