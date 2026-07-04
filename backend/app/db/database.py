import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.config import settings
from app.services.week_filter import filter_dashboard_for_week


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                course_id TEXT,
                course_name TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                posted_at TEXT,
                url TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                course_id TEXT,
                course_name TEXT NOT NULL,
                title TEXT NOT NULL,
                due_at TEXT,
                status TEXT,
                url TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            );

            CREATE TABLE IF NOT EXISTS grades (
                id TEXT PRIMARY KEY,
                course_id TEXT,
                course_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                score TEXT,
                max_score TEXT,
                percentage TEXT,
                feedback TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                related_id TEXT,
                created_at TEXT NOT NULL,
                dismissed INTEGER DEFAULT 0
            );
            """
        )
        await db.commit()


async def clear_academic_data() -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("DELETE FROM announcements")
        await db.execute("DELETE FROM assignments")
        await db.execute("DELETE FROM grades")
        await db.execute("DELETE FROM courses")
        await db.commit()


async def upsert_courses(courses: list[dict]) -> None:
    now = _utc_now()
    async with aiosqlite.connect(settings.database_path) as db:
        for course in courses:
            await db.execute(
                """
                INSERT INTO courses (id, name, url, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    updated_at = excluded.updated_at
                """,
                (course["id"], course["name"], course.get("url"), now),
            )
        await db.commit()


async def upsert_announcements(items: list[dict]) -> None:
    now = _utc_now()
    async with aiosqlite.connect(settings.database_path) as db:
        for item in items:
            await db.execute(
                """
                INSERT INTO announcements (
                    id, course_id, course_name, title, body, posted_at, url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    course_name = excluded.course_name,
                    title = excluded.title,
                    body = excluded.body,
                    posted_at = excluded.posted_at,
                    url = excluded.url,
                    updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    item.get("course_id"),
                    item["course_name"],
                    item["title"],
                    item.get("body"),
                    item.get("posted_at"),
                    item.get("url"),
                    now,
                ),
            )
        await db.commit()


async def upsert_assignments(items: list[dict]) -> None:
    now = _utc_now()
    async with aiosqlite.connect(settings.database_path) as db:
        for item in items:
            await db.execute(
                """
                INSERT INTO assignments (
                    id, course_id, course_name, title, due_at, status, url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    course_name = excluded.course_name,
                    title = excluded.title,
                    due_at = excluded.due_at,
                    status = excluded.status,
                    url = excluded.url,
                    updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    item.get("course_id"),
                    item["course_name"],
                    item["title"],
                    item.get("due_at"),
                    item.get("status"),
                    item.get("url"),
                    now,
                ),
            )
        await db.commit()


async def upsert_grades(items: list[dict]) -> None:
    now = _utc_now()
    async with aiosqlite.connect(settings.database_path) as db:
        for item in items:
            await db.execute(
                """
                INSERT INTO grades (
                    id, course_id, course_name, item_name, score, max_score,
                    percentage, feedback, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    course_name = excluded.course_name,
                    item_name = excluded.item_name,
                    score = excluded.score,
                    max_score = excluded.max_score,
                    percentage = excluded.percentage,
                    feedback = excluded.feedback,
                    updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    item.get("course_id"),
                    item["course_name"],
                    item["item_name"],
                    item.get("score"),
                    item.get("max_score"),
                    item.get("percentage"),
                    item.get("feedback"),
                    now,
                ),
            )
        await db.commit()


async def replace_alerts(items: list[dict]) -> None:
    now = _utc_now()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("DELETE FROM alerts WHERE dismissed = 0")
        for item in items:
            await db.execute(
                """
                INSERT INTO alerts (kind, severity, title, message, related_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item["kind"],
                    item["severity"],
                    item["title"],
                    item["message"],
                    item.get("related_id"),
                    now,
                ),
            )
        await db.commit()


async def start_sync_run() -> int:
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "INSERT INTO sync_runs (started_at, status) VALUES (?, ?)",
            (_utc_now(), "running"),
        )
        await db.commit()
        return cursor.lastrowid


async def finish_sync_run(run_id: int, status: str, message: str | None = None) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            UPDATE sync_runs
            SET finished_at = ?, status = ?, message = ?
            WHERE id = ?
            """,
            (_utc_now(), status, message, run_id),
        )
        await db.commit()


async def fetch_all(table: str) -> list[dict]:
    order_column = "created_at" if table == "alerts" else "updated_at"
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT * FROM {table} ORDER BY {order_column} DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetch_dashboard_payload() -> dict:
    announcements = await fetch_all("announcements")
    assignments = await fetch_all("assignments")
    grades = await fetch_all("grades")
    alerts = await fetch_all("alerts")
    courses = await fetch_all("courses")

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
        )
        last_sync = await cursor.fetchone()

    raw = {
        "courses": courses,
        "announcements": announcements,
        "assignments": assignments,
        "grades": grades,
        "alerts": [a for a in alerts if not a.get("dismissed")],
        "last_sync": dict(last_sync) if last_sync else None,
    }
    return filter_dashboard_for_week(raw)


async def export_context_for_agent() -> str:
    payload = await fetch_dashboard_payload()
    return json.dumps(payload, ensure_ascii=False, indent=2)
