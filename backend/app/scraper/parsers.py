from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

DATE_PATTERNS = (
    r"(\d{1,2}/\d{1,2}/\d{2,4})",
    r"(\d{4}-\d{2}-\d{2})",
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})",
)

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

IMPORTANT_EVENT_KEYWORDS = (
    "midterm",
    "final exam",
    "exam",
    "quiz",
    "test",
    "prova",
    "assignment due",
    "entrega",
    "due date",
    "reading week",
)


def slug_id(*parts: str) -> str:
    raw = "|".join(p.strip().lower() for p in parts if p)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return clean_text(value)
    soup = BeautifulSoup(value, "lxml")
    return clean_text(soup.get_text(" ", strip=True))


def current_week_bounds(reference: datetime | None = None) -> tuple[datetime.date, datetime.date]:
    today = (reference or datetime.now()).date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def parse_item_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    text = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    parsed = parse_due_date(value)
    if not parsed:
        return None
    try:
        return datetime.fromisoformat(parsed[:10]).date()
    except ValueError:
        return None


def is_in_current_week(value: str | None, reference: datetime | None = None) -> bool:
    item_date = parse_item_date(value)
    if not item_date:
        return False
    today = (reference or datetime.now()).date()
    end = today + timedelta(days=6)
    return today <= item_date <= end


def is_important_event(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in IMPORTANT_EVENT_KEYWORDS)


def extract_dates_from_text(text: str | None, reference: datetime | None = None) -> list[datetime.date]:
    if not text:
        return []

    plain = strip_html(text)
    today = (reference or datetime.now()).date()
    year = today.year
    found: list[datetime.date] = []

    month_day = re.finditer(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
        plain,
        re.IGNORECASE,
    )
    for match in month_day:
        month_key = match.group(1).lower()[:3]
        day = int(match.group(2))
        match_year = int(match.group(3)) if match.group(3) else year
        month = MONTHS.get(month_key)
        if not month:
            continue
        try:
            found.append(datetime(match_year, month, day).date())
        except ValueError:
            continue

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, plain, re.IGNORECASE):
            parsed = parse_item_date(match.group(1))
            if parsed:
                found.append(parsed)

    short_form = re.finditer(r"\b(Jul|Jun|Jan|Feb|Mar|Apr|May|Aug|Sep|Oct|Nov|Dec)\.?\s*(\d{1,2})\b", plain, re.IGNORECASE)
    for match in short_form:
        month_key = match.group(1).lower()[:3]
        day = int(match.group(2))
        month = MONTHS.get(month_key)
        if not month:
            continue
        try:
            found.append(datetime(year, month, day).date())
        except ValueError:
            continue

    return sorted(set(found))


def parse_due_date(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    if "today" in lowered or "hoje" in lowered:
        return datetime.now(timezone.utc).date().isoformat()
    if "tomorrow" in lowered or "amanh" in lowered:
        return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    return text.strip()[:80] or None


def is_due_soon(due_at: str | None, days: int = 3) -> bool:
    if not due_at:
        return False
    try:
        due = datetime.fromisoformat(due_at[:10]).date()
    except ValueError:
        return False
    today = datetime.now(timezone.utc).date()
    return today <= due <= today + timedelta(days=days)


def parse_percentage(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([\d.,]+)\s*%", value)
    if match:
        return float(match.group(1).replace(",", "."))
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            score = float(re.sub(r"[^\d.]", "", left))
            maximum = float(re.sub(r"[^\d.]", "", right))
            if maximum:
                return round((score / maximum) * 100, 2)
        except ValueError:
            return None
    return None


def extract_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    courses: list[dict] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        name = clean_text(anchor.get_text())
        if not name or len(name) < 3:
            continue
        if not any(token in href.lower() for token in ("course_id", "/courses/", "ultra/courses")):
            continue
        full_url = urljoin(base_url, href)
        course_id = slug_id(full_url, name)
        if course_id in seen:
            continue
        seen.add(course_id)
        courses.append({"id": course_id, "name": name, "url": full_url})

    return courses


def parse_announcements(html: str, course_name: str, course_id: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    selectors = [
        ".announcement",
        ".js-announcement",
        "[data-type='announcement']",
        ".list-item-announcement",
        "li.announcements",
    ]
    nodes = []
    for selector in selectors:
        nodes.extend(soup.select(selector))

    if not nodes:
        for heading in soup.select("h3, h4, .item-title, .element-details h4"):
            title = clean_text(heading.get_text())
            if not title:
                continue
            body_node = heading.find_next(["p", "div", "span"])
            body = clean_text(body_node.get_text()) if body_node else ""
            link = heading.find_parent("a") or heading.find("a")
            url = urljoin(base_url, link["href"]) if link and link.get("href") else None
            items.append(
                {
                    "id": slug_id(course_id, title, body[:40]),
                    "course_id": course_id,
                    "course_name": course_name,
                    "title": title,
                    "body": body,
                    "posted_at": None,
                    "url": url,
                }
            )
        return items[:20]

    for node in nodes[:20]:
        title_node = node.select_one("h3, h4, .item-title, .announcement-title")
        title = clean_text(title_node.get_text() if title_node else node.get_text()[:120])
        if not title:
            continue
        body_node = node.select_one("p, .announcement-content, .details")
        body = clean_text(body_node.get_text()) if body_node else clean_text(node.get_text())
        date_node = node.select_one("time, .date, .posted-on")
        posted_at = clean_text(date_node.get_text()) if date_node else None
        link = node.select_one("a[href]")
        url = urljoin(base_url, link["href"]) if link else None
        items.append(
            {
                "id": slug_id(course_id, title, posted_at or ""),
                "course_id": course_id,
                "course_name": course_name,
                "title": title,
                "body": body,
                "posted_at": posted_at,
                "url": url,
            }
        )

    return items


def parse_assignments(html: str, course_name: str, course_id: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    rows = soup.select(
        ".todo-item, .activity-item, .due-date-list-item, li[data-item-type], .contentListRow"
    )
    if not rows:
        rows = soup.select("a[href*='due'], a[href*='assignment'], a[href*='content']")

    for row in rows[:30]:
        if row.name == "a":
            title = clean_text(row.get_text())
            url = urljoin(base_url, row.get("href", ""))
            due_text = None
        else:
            title_node = row.select_one("h3, h4, .item-title, .activity-title, a")
            title = clean_text(title_node.get_text() if title_node else row.get_text()[:120])
            link = row.select_one("a[href]")
            url = urljoin(base_url, link["href"]) if link else None
            due_node = row.select_one(".due-date, time, .date, .due")
            due_text = clean_text(due_node.get_text()) if due_node else None

        if not title or len(title) < 3:
            continue

        status_node = row.select_one(".status, .submitted, .attempts")
        status = clean_text(status_node.get_text()) if status_node else None
        items.append(
            {
                "id": slug_id(course_id, title, due_text or ""),
                "course_id": course_id,
                "course_name": course_name,
                "title": title,
                "due_at": parse_due_date(due_text),
                "status": status,
                "url": url,
            }
        )

    return items


def parse_grades(html: str, course_name: str, course_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    rows = soup.select("tr, .grade-row, .grades_list row, li.grade-item")
    for row in rows:
        cells = row.select("td, .grade, .score, span")
        texts = [clean_text(cell.get_text()) for cell in cells if clean_text(cell.get_text())]
        if len(texts) < 2:
            continue

        item_name = texts[0]
        score = texts[1] if len(texts) > 1 else None
        max_score = texts[2] if len(texts) > 2 else None
        percentage = None
        feedback = None

        for text in texts:
            if "%" in text:
                percentage = text
            if len(text) > 40 and text not in {item_name, score, max_score}:
                feedback = text

        if item_name.lower() in {"item", "grade", "nota", "activity"}:
            continue

        items.append(
            {
                "id": slug_id(course_id, item_name, score or ""),
                "course_id": course_id,
                "course_name": course_name,
                "item_name": item_name,
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "feedback": feedback,
            }
        )

    return items[:40]


def course_paths(origin: str, course_url: str) -> dict[str, str]:
    parsed = urlparse(course_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "announcements": urljoin(base, f"{parsed.path.rstrip('/')}/announcements"),
        "grades": urljoin(base, f"{parsed.path.rstrip('/')}/grades"),
        "outline": course_url,
    }
