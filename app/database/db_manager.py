from __future__ import annotations

import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.models.game_entry import MediaEntry

LOGGER = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    pass


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS media_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                full_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_time TEXT NOT NULL,
                drive_letter TEXT NOT NULL,
                drive_label TEXT,
                drive_id TEXT NOT NULL,
                scan_date TEXT NOT NULL,
                last_seen_date TEXT NOT NULL,
                is_missing INTEGER NOT NULL DEFAULT 0,
                UNIQUE(drive_id, full_path)
            );

            CREATE INDEX IF NOT EXISTS idx_media_title ON media_entries(title);
            CREATE INDEX IF NOT EXISTS idx_media_drive_id ON media_entries(drive_id);
            CREATE INDEX IF NOT EXISTS idx_media_last_seen ON media_entries(last_seen_date);
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_entry(self, entry: MediaEntry) -> None:
        payload: dict[str, Any] = asdict(entry)
        payload.pop("id", None)

        sql = """
        INSERT INTO media_entries (
            category, title, original_filename, full_path, file_name, file_extension,
            file_size, modified_time, drive_letter, drive_label, drive_id,
            scan_date, last_seen_date, is_missing
        ) VALUES (
            :category, :title, :original_filename, :full_path, :file_name, :file_extension,
            :file_size, :modified_time, :drive_letter, :drive_label, :drive_id,
            :scan_date, :last_seen_date, :is_missing
        )
        ON CONFLICT(drive_id, full_path)
        DO UPDATE SET
            category=excluded.category,
            title=excluded.title,
            original_filename=excluded.original_filename,
            file_name=excluded.file_name,
            file_extension=excluded.file_extension,
            file_size=excluded.file_size,
            modified_time=excluded.modified_time,
            drive_letter=excluded.drive_letter,
            drive_label=excluded.drive_label,
            scan_date=excluded.scan_date,
            last_seen_date=excluded.last_seen_date,
            is_missing=0
        """
        try:
            self._conn.execute(sql, payload)
        except sqlite3.Error as exc:
            LOGGER.exception("Failed to upsert entry: %s", entry.full_path)
            raise DatabaseError(str(exc)) from exc

    def mark_missing_for_drive(self, drive_id: str, scan_date: str) -> None:
        self._conn.execute(
            """
            UPDATE media_entries
            SET is_missing=1
            WHERE drive_id=? AND last_seen_date < ?
            """,
            (drive_id, scan_date),
        )

    def commit(self) -> None:
        self._conn.commit()

    def list_entries(self, search: str = "", drive_filter: str = "") -> list[sqlite3.Row]:
        clauses = []
        params: list[Any] = []

        if search.strip():
            clauses.append("(title LIKE ? OR file_name LIKE ? OR full_path LIKE ?)")
            token = f"%{search.strip()}%"
            params.extend([token, token, token])

        if drive_filter.strip():
            clauses.append("drive_id = ?")
            params.append(drive_filter)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self._conn.execute(
            f"""
            SELECT *
            FROM media_entries
            {where_sql}
            ORDER BY title COLLATE NOCASE ASC
            """,
            params,
        )
        return list(cursor.fetchall())

    def list_distinct_drives(self) -> list[sqlite3.Row]:
        cursor = self._conn.execute(
            """
            SELECT DISTINCT drive_id, drive_label
            FROM media_entries
            ORDER BY drive_label COLLATE NOCASE
            """
        )
        return list(cursor.fetchall())
