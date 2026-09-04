from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from app.models.game_entry import MediaEntry
from app.models.scan import ScanStatus
from app.utils.date_utils import now_iso

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 2


class DatabaseError(RuntimeError):
    pass


class DatabaseManager:
    """SQLite gateway which keeps the legacy table as a compatible scan projection."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        try:
            self._migrate()
        except sqlite3.Error as exc:
            LOGGER.exception("Datenbankmigration fehlgeschlagen")
            self._conn.rollback()
            raise DatabaseError(str(exc)) from exc

    def _columns(self, table: str) -> set[str]:
        return {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})")}

    def _add_column(self, table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in self._columns(table):
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def _migrate(self) -> None:
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        LOGGER.info("Datenbankschema wird geprüft (Version %s -> %s)", current, SCHEMA_VERSION)
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS media_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
                    title TEXT NOT NULL, original_filename TEXT NOT NULL,
                    full_path TEXT NOT NULL, file_name TEXT NOT NULL,
                    file_extension TEXT NOT NULL, file_size INTEGER NOT NULL,
                    modified_time TEXT NOT NULL, drive_letter TEXT NOT NULL,
                    drive_label TEXT, drive_id TEXT NOT NULL, scan_date TEXT NOT NULL,
                    last_seen_date TEXT NOT NULL, is_missing INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(drive_id, full_path));
                CREATE TABLE IF NOT EXISTS archive_only_dirs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, drive_id TEXT NOT NULL,
                    folder_path TEXT NOT NULL, scan_date TEXT NOT NULL,
                    UNIQUE(drive_id, folder_path));
            """)
            for definition in (
                "platform TEXT NOT NULL DEFAULT 'Unknown'",
                "platform_overridden INTEGER NOT NULL DEFAULT 0",
                "file_hash TEXT", "hash_type TEXT", "hash_calculated_at TEXT",
                "game_id INTEGER", "media_file_id INTEGER",
            ):
                self._add_column("media_entries", definition)
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS drives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, volume_serial TEXT NOT NULL UNIQUE,
                    label TEXT, last_drive_letter TEXT, last_seen TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, sort_title TEXT,
                    platform TEXT NOT NULL DEFAULT 'Unknown', platform_overridden INTEGER NOT NULL DEFAULT 0,
                    release_year INTEGER, publisher TEXT, developer TEXT, region TEXT, edition TEXT,
                    cover_path TEXT, cover_url TEXT, metadata_source TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(title, platform));
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL REFERENCES games(id),
                    drive_id INTEGER NOT NULL REFERENCES drives(id), full_path TEXT NOT NULL,
                    file_name TEXT NOT NULL, extension TEXT NOT NULL, file_size INTEGER NOT NULL,
                    modified_time TEXT NOT NULL, last_seen TEXT NOT NULL,
                    is_missing INTEGER NOT NULL DEFAULT 0, file_hash TEXT, hash_type TEXT,
                    hash_calculated_at TEXT, created_at TEXT NOT NULL,
                    UNIQUE(drive_id, full_path));
                CREATE TABLE IF NOT EXISTS scan_runs (
                    id TEXT PRIMARY KEY, drive_volume_serial TEXT NOT NULL, scope TEXT NOT NULL,
                    status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
                    checked_files INTEGER NOT NULL DEFAULT 0, found_files INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0, error_message TEXT);
                CREATE INDEX IF NOT EXISTS idx_media_title ON media_entries(title);
                CREATE INDEX IF NOT EXISTS idx_media_drive_id ON media_entries(drive_id);
                CREATE INDEX IF NOT EXISTS idx_media_last_seen ON media_entries(last_seen_date);
                CREATE INDEX IF NOT EXISTS idx_media_platform ON media_entries(platform);
                CREATE INDEX IF NOT EXISTS idx_files_game ON media_files(game_id);
                CREATE INDEX IF NOT EXISTS idx_scan_drive ON scan_runs(drive_volume_serial, started_at);
                CREATE INDEX IF NOT EXISTS idx_archive_only_drive_id ON archive_only_dirs(drive_id);
            """)
            self._backfill_normalized_tables()
            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        LOGGER.info("Datenbankschema Version %s ist bereit", SCHEMA_VERSION)

    def _backfill_normalized_tables(self) -> None:
        rows = self._conn.execute("SELECT * FROM media_entries WHERE game_id IS NULL OR media_file_id IS NULL").fetchall()
        for row in rows:
            game_id, media_id = self._upsert_normalized(dict(row))
            self._conn.execute("UPDATE media_entries SET game_id=?, media_file_id=? WHERE id=?", (game_id, media_id, row["id"]))

    def close(self) -> None:
        self._conn.close()

    def start_scan(self, drive_id: str, scope: str) -> str:
        scan_id = str(uuid.uuid4())
        self._conn.execute("INSERT INTO scan_runs(id, drive_volume_serial, scope, status, started_at) VALUES(?,?,?,?,?)",
                           (scan_id, drive_id, scope, ScanStatus.RUNNING, now_iso()))
        self._conn.commit()
        return scan_id

    def finish_scan(self, scan_id: str, status: ScanStatus, checked: int, found: int,
                    warnings: int = 0, error: str | None = None) -> None:
        self._conn.execute("UPDATE scan_runs SET status=?, finished_at=?, checked_files=?, found_files=?, warning_count=?, error_message=? WHERE id=?",
                           (status, now_iso(), checked, found, warnings, error, scan_id))
        self._conn.commit()

    def upsert_entries(self, entries: Iterable[MediaEntry]) -> None:
        try:
            with self._conn:
                for entry in entries:
                    self._upsert_entry_no_commit(entry)
        except sqlite3.Error as exc:
            LOGGER.exception("Batch-Upsert fehlgeschlagen")
            raise DatabaseError(str(exc)) from exc

    def upsert_entry(self, entry: MediaEntry) -> None:
        self._upsert_entry_no_commit(entry)

    def _upsert_entry_no_commit(self, entry: MediaEntry) -> None:
        payload: dict[str, Any] = asdict(entry); payload.pop("id", None)
        existing = self._conn.execute(
            "SELECT platform, platform_overridden FROM media_entries WHERE drive_id=? AND full_path=?",
            (entry.drive_id, entry.full_path),
        ).fetchone()
        if existing and existing["platform_overridden"]:
            payload["platform"] = existing["platform"]
            payload["platform_overridden"] = 1
        game_id, media_id = self._upsert_normalized(payload)
        payload.update(game_id=game_id, media_file_id=media_id)
        self._conn.execute("""
            INSERT INTO media_entries (category,title,original_filename,full_path,file_name,file_extension,
              file_size,modified_time,drive_letter,drive_label,drive_id,scan_date,last_seen_date,is_missing,
              platform,platform_overridden,file_hash,hash_type,hash_calculated_at,game_id,media_file_id)
            VALUES (:category,:title,:original_filename,:full_path,:file_name,:file_extension,:file_size,
              :modified_time,:drive_letter,:drive_label,:drive_id,:scan_date,:last_seen_date,:is_missing,
              :platform,:platform_overridden,:file_hash,:hash_type,:hash_calculated_at,:game_id,:media_file_id)
            ON CONFLICT(drive_id,full_path) DO UPDATE SET category=excluded.category,title=excluded.title,
              original_filename=excluded.original_filename,file_name=excluded.file_name,
              file_extension=excluded.file_extension,file_size=excluded.file_size,
              modified_time=excluded.modified_time,drive_letter=excluded.drive_letter,
              drive_label=excluded.drive_label,scan_date=excluded.scan_date,last_seen_date=excluded.last_seen_date,
              is_missing=0, platform=CASE WHEN media_entries.platform_overridden=1 THEN media_entries.platform ELSE excluded.platform END,
              game_id=excluded.game_id,media_file_id=excluded.media_file_id
        """, payload)

    def _upsert_normalized(self, item: dict[str, Any]) -> tuple[int, int]:
        timestamp = item.get("last_seen_date") or now_iso()
        self._conn.execute("""INSERT INTO drives(volume_serial,label,last_drive_letter,last_seen) VALUES(?,?,?,?)
            ON CONFLICT(volume_serial) DO UPDATE SET label=excluded.label,last_drive_letter=excluded.last_drive_letter,last_seen=excluded.last_seen""",
            (item["drive_id"], item.get("drive_label"), item.get("drive_letter"), timestamp))
        drive_pk = self._conn.execute("SELECT id FROM drives WHERE volume_serial=?", (item["drive_id"],)).fetchone()[0]
        platform = item.get("platform") or "Unknown"
        self._conn.execute("""INSERT INTO games(title,sort_title,platform,platform_overridden,created_at,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(title,platform) DO UPDATE SET updated_at=excluded.updated_at""",
            (item["title"], item["title"].casefold(), platform, item.get("platform_overridden", 0), timestamp, timestamp))
        game_pk = self._conn.execute("SELECT id FROM games WHERE title=? AND platform=?", (item["title"], platform)).fetchone()[0]
        self._conn.execute("""INSERT INTO media_files(game_id,drive_id,full_path,file_name,extension,file_size,modified_time,last_seen,is_missing,file_hash,hash_type,hash_calculated_at,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(drive_id,full_path) DO UPDATE SET game_id=excluded.game_id,file_name=excluded.file_name,
            extension=excluded.extension,file_size=excluded.file_size,modified_time=excluded.modified_time,last_seen=excluded.last_seen,is_missing=0""",
            (game_pk, drive_pk, item["full_path"], item["file_name"], item.get("file_extension", ""), item["file_size"],
             item["modified_time"], timestamp, item.get("is_missing", 0), item.get("file_hash"), item.get("hash_type"),
             item.get("hash_calculated_at"), item.get("scan_date") or timestamp))
        media_pk = self._conn.execute("SELECT id FROM media_files WHERE drive_id=? AND full_path=?", (drive_pk, item["full_path"])).fetchone()[0]
        return game_pk, media_pk

    def mark_missing_for_completed_scan(self, drive_id: str, scan_date: str, status: ScanStatus) -> int:
        if status is not ScanStatus.COMPLETED:
            LOGGER.info("Missing-Markierung übersprungen: Scanstatus %s", status)
            return 0
        cursor = self._conn.execute("UPDATE media_entries SET is_missing=1 WHERE drive_id=? AND last_seen_date < ?", (drive_id, scan_date))
        self._conn.execute("""UPDATE media_files SET is_missing=1 WHERE drive_id=(SELECT id FROM drives WHERE volume_serial=?) AND last_seen < ?""", (drive_id, scan_date))
        return cursor.rowcount

    def mark_missing_for_drive(self, drive_id: str, scan_date: str) -> None:
        """Legacy API; callers must explicitly use safe scan completion instead."""
        raise DatabaseError("Missing status requires a completed scan status")

    def upsert_archive_only_dir(self, drive_id: str, folder_path: str, scan_date: str) -> None:
        self._conn.execute("""INSERT INTO archive_only_dirs(drive_id,folder_path,scan_date) VALUES(?,?,?)
            ON CONFLICT(drive_id,folder_path) DO UPDATE SET scan_date=excluded.scan_date""", (drive_id, folder_path, scan_date))

    def cleanup_counts(self) -> dict[str, int]:
        def count(sql: str) -> int: return int(self._conn.execute(sql).fetchone()[0])
        return {"Archive noch nicht entpackt": count("SELECT COUNT(*) FROM archive_only_dirs"),
                "Mögliche Dubletten": count("SELECT COUNT(*) FROM (SELECT title,platform,file_size FROM media_entries GROUP BY title,platform,file_size HAVING COUNT(*)>1)"),
                "Bestätigte Dubletten": count("SELECT COUNT(*) FROM (SELECT file_hash FROM media_entries WHERE file_hash IS NOT NULL GROUP BY file_hash HAVING COUNT(*)>1)"),
                "Fehlende Dateien": count("SELECT COUNT(*) FROM media_entries WHERE is_missing=1"),
                "Unbekannte Plattformen": count("SELECT COUNT(*) FROM media_entries WHERE platform='Unknown'"),
                "Unbekannte Dateiformate": 0,
                "Spiele ohne Metadaten": count("SELECT COUNT(*) FROM games WHERE metadata_source IS NULL")}

    def save_hash(self, media_file_id: int, digest: str, hash_type: str) -> None:
        calculated_at = now_iso()
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE media_files SET file_hash=?, hash_type=?, hash_calculated_at=? WHERE id=?",
                    (digest, hash_type, calculated_at, media_file_id),
                )
                self._conn.execute(
                    "UPDATE media_entries SET file_hash=?, hash_type=?, hash_calculated_at=? WHERE media_file_id=?",
                    (digest, hash_type, calculated_at, media_file_id),
                )
        except sqlite3.Error as exc:
            LOGGER.exception("Hash konnte nicht gespeichert werden")
            raise DatabaseError(str(exc)) from exc

    def commit(self) -> None: self._conn.commit()

    def list_entries(self, search: str = "", drive_filter: str = "", platform_filter: str = "") -> list[sqlite3.Row]:
        clauses, params = [], []
        if search.strip():
            clauses.append("(title LIKE ? OR file_name LIKE ? OR full_path LIKE ?)"); token=f"%{search.strip()}%"; params += [token]*3
        if drive_filter.strip(): clauses.append("drive_id = ?"); params.append(drive_filter)
        if platform_filter.strip(): clauses.append("platform = ?"); params.append(platform_filter)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try: return list(self._conn.execute(f"SELECT * FROM media_entries {where} ORDER BY title COLLATE NOCASE", params).fetchall())
        except sqlite3.Error as exc:
            LOGGER.exception("Datenbankabfrage fehlgeschlagen"); raise DatabaseError(str(exc)) from exc

    def list_distinct_drives(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT DISTINCT drive_id,drive_label FROM media_entries ORDER BY drive_label COLLATE NOCASE").fetchall())
