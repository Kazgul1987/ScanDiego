from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from app.models.game_entry import MediaEntry
from app.models.content import (ContentDetectionMethod, ContentDetectionResult,
                                MediaContentType)
from app.services.content_association_service import ContentAssociationService
from app.models.scan import ScanStatus
from app.models.metadata import ExternalGame, MetadataStatus
from app.services.duplicate_detection_service import DuplicateDetectionService, DuplicateGroup, DuplicateStatus
from app.utils.date_utils import now_iso

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 6


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
                "last_seen TEXT", "scan_id TEXT", "is_active INTEGER NOT NULL DEFAULT 1",
            ):
                self._add_column("archive_only_dirs", definition)
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS unknown_media_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drive_id TEXT NOT NULL, full_path TEXT NOT NULL, file_name TEXT NOT NULL,
                    extension TEXT NOT NULL, file_size INTEGER NOT NULL, last_seen TEXT NOT NULL,
                    scan_id TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(drive_id, full_path));
                CREATE INDEX IF NOT EXISTS idx_unknown_drive_active
                    ON unknown_media_candidates(drive_id, is_active);
            """)
            self._conn.execute("UPDATE archive_only_dirs SET last_seen=COALESCE(last_seen, scan_date)")
            for definition in (
                "platform TEXT NOT NULL DEFAULT 'Unknown'",
                "platform_overridden INTEGER NOT NULL DEFAULT 0",
                "file_hash TEXT", "hash_type TEXT", "hash_calculated_at TEXT",
                "game_id INTEGER", "media_file_id INTEGER",
                "content_type TEXT NOT NULL DEFAULT 'unknown'", "content_title TEXT",
                "content_version TEXT", "content_id TEXT", "base_content_id TEXT",
                "content_detection_method TEXT NOT NULL DEFAULT 'unknown'",
                "content_detection_confidence REAL NOT NULL DEFAULT 0",
                "content_parent_game_id INTEGER", "content_region TEXT",
                "content_locked INTEGER NOT NULL DEFAULT 0",
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
                    metadata_status TEXT NOT NULL DEFAULT 'not_requested',
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
            self._add_column("games", "metadata_status TEXT NOT NULL DEFAULT 'not_requested'")
            for definition in (
                "content_type TEXT NOT NULL DEFAULT 'unknown'", "content_title TEXT",
                "content_version TEXT", "content_id TEXT", "base_content_id TEXT",
                "content_detection_method TEXT NOT NULL DEFAULT 'unknown'",
                "content_detection_confidence REAL NOT NULL DEFAULT 0",
                "content_parent_game_id INTEGER REFERENCES games(id)", "content_region TEXT",
                "content_locked INTEGER NOT NULL DEFAULT 0",
            ):
                self._add_column("media_files", definition)
            for definition in (
                "external_game_id TEXT", "external_platform_id TEXT", "canonical_title TEXT",
                "release_date TEXT", "description TEXT", "metadata_last_updated TEXT",
                "metadata_match_score REAL", "metadata_match_method TEXT", "cover_source TEXT",
                "metadata_locked INTEGER NOT NULL DEFAULT 0", "artwork_source TEXT",
                "artwork_external_game_id TEXT", "artwork_status TEXT NOT NULL DEFAULT 'not_requested'",
            ):
                self._add_column("games", definition)
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS metadata_match_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL, external_game_id TEXT NOT NULL,
                    title TEXT NOT NULL, platform TEXT, release_date TEXT,
                    release_year INTEGER, score REAL NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(game_id, provider, external_game_id));
                CREATE INDEX IF NOT EXISTS idx_games_metadata_status ON games(metadata_status);
                CREATE INDEX IF NOT EXISTS idx_candidates_game ON metadata_match_candidates(game_id);
                CREATE INDEX IF NOT EXISTS idx_files_content_type ON media_files(content_type);
                CREATE INDEX IF NOT EXISTS idx_files_content_id ON media_files(content_id);
                CREATE INDEX IF NOT EXISTS idx_files_base_content_id ON media_files(base_content_id);
                CREATE INDEX IF NOT EXISTS idx_files_parent_game ON media_files(content_parent_game_id);
            """)
            # Interrupted work is safe to reconstruct on next startup.
            self._conn.execute("UPDATE games SET metadata_status=? WHERE metadata_status=?", (MetadataStatus.QUEUED, MetadataStatus.SEARCHING))
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
            "SELECT * FROM media_entries WHERE drive_id=? AND full_path=?",
            (entry.drive_id, entry.full_path),
        ).fetchone()
        if existing and existing["platform_overridden"]:
            payload["platform"] = existing["platform"]
            payload["platform_overridden"] = 1
        if existing and existing["content_locked"]:
            for name in ("content_type", "content_title", "content_version", "content_id",
                         "base_content_id", "content_detection_method", "content_detection_confidence",
                         "content_parent_game_id", "content_region", "content_locked"):
                payload[name] = existing[name]
        game_id, media_id = self._upsert_normalized(payload)
        if payload.get("content_type") in {MediaContentType.UPDATE, MediaContentType.DLC, MediaContentType.ADDON}:
            payload["content_parent_game_id"] = game_id
            self._conn.execute("UPDATE media_files SET content_parent_game_id=? WHERE id=? AND content_locked=0", (game_id, media_id))
        payload.update(game_id=game_id, media_file_id=media_id)
        self._conn.execute("""
            INSERT INTO media_entries (category,title,original_filename,full_path,file_name,file_extension,
              file_size,modified_time,drive_letter,drive_label,drive_id,scan_date,last_seen_date,is_missing,
              platform,platform_overridden,file_hash,hash_type,hash_calculated_at,game_id,media_file_id,
              content_type,content_title,content_version,content_id,base_content_id,content_detection_method,
              content_detection_confidence,content_parent_game_id,content_region,content_locked)
            VALUES (:category,:title,:original_filename,:full_path,:file_name,:file_extension,:file_size,
              :modified_time,:drive_letter,:drive_label,:drive_id,:scan_date,:last_seen_date,:is_missing,
              :platform,:platform_overridden,:file_hash,:hash_type,:hash_calculated_at,:game_id,:media_file_id,
              :content_type,:content_title,:content_version,:content_id,:base_content_id,:content_detection_method,
              :content_detection_confidence,:content_parent_game_id,:content_region,:content_locked)
            ON CONFLICT(drive_id,full_path) DO UPDATE SET category=excluded.category,title=excluded.title,
              original_filename=excluded.original_filename,file_name=excluded.file_name,
              file_extension=excluded.file_extension,file_size=excluded.file_size,
              modified_time=excluded.modified_time,drive_letter=excluded.drive_letter,
              drive_label=excluded.drive_label,scan_date=excluded.scan_date,last_seen_date=excluded.last_seen_date,
              is_missing=0, platform=CASE WHEN media_entries.platform_overridden=1 THEN media_entries.platform ELSE excluded.platform END,
              game_id=CASE WHEN media_entries.content_locked=1 THEN media_entries.game_id ELSE excluded.game_id END,
              media_file_id=excluded.media_file_id,
              content_type=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_type ELSE excluded.content_type END,
              content_title=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_title ELSE excluded.content_title END,
              content_version=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_version ELSE excluded.content_version END,
              content_id=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_id ELSE excluded.content_id END,
              base_content_id=CASE WHEN media_entries.content_locked=1 THEN media_entries.base_content_id ELSE excluded.base_content_id END,
              content_detection_method=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_detection_method ELSE excluded.content_detection_method END,
              content_detection_confidence=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_detection_confidence ELSE excluded.content_detection_confidence END,
              content_parent_game_id=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_parent_game_id ELSE excluded.content_parent_game_id END,
              content_region=CASE WHEN media_entries.content_locked=1 THEN media_entries.content_region ELSE excluded.content_region END
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
        existing_file = self._conn.execute("SELECT game_id,content_locked FROM media_files WHERE drive_id=? AND full_path=?", (drive_pk, item["full_path"])).fetchone()
        if existing_file and existing_file["content_locked"]:
            game_pk = existing_file["game_id"]
        self._conn.execute("""INSERT INTO media_files(game_id,drive_id,full_path,file_name,extension,file_size,modified_time,last_seen,is_missing,file_hash,hash_type,hash_calculated_at,created_at,
            content_type,content_title,content_version,content_id,base_content_id,content_detection_method,content_detection_confidence,content_parent_game_id,content_region,content_locked)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(drive_id,full_path) DO UPDATE SET
            game_id=CASE WHEN media_files.content_locked=1 THEN media_files.game_id ELSE excluded.game_id END,file_name=excluded.file_name,
            extension=excluded.extension,file_size=excluded.file_size,modified_time=excluded.modified_time,last_seen=excluded.last_seen,is_missing=0""",
            (game_pk, drive_pk, item["full_path"], item["file_name"], item.get("file_extension", ""), item["file_size"],
             item["modified_time"], timestamp, item.get("is_missing", 0), item.get("file_hash"), item.get("hash_type"),
             item.get("hash_calculated_at"), item.get("scan_date") or timestamp,
             item.get("content_type", MediaContentType.UNKNOWN), item.get("content_title"), item.get("content_version"),
             item.get("content_id"), item.get("base_content_id"), item.get("content_detection_method", ContentDetectionMethod.UNKNOWN),
             item.get("content_detection_confidence", 0), item.get("content_parent_game_id"), item.get("content_region"), item.get("content_locked", 0)))
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

    def upsert_archive_only_dir(self, drive_id: str, folder_path: str, scan_date: str,
                                scan_id: str | None = None) -> None:
        self._conn.execute("""INSERT INTO archive_only_dirs(drive_id,folder_path,scan_date,last_seen,scan_id,is_active)
            VALUES(?,?,?,?,?,1) ON CONFLICT(drive_id,folder_path) DO UPDATE SET
            scan_date=excluded.scan_date,last_seen=excluded.last_seen,scan_id=excluded.scan_id,is_active=1""",
            (drive_id, folder_path, scan_date, scan_date, scan_id))

    def upsert_unknown_candidate(self, drive_id: str, full_path: str, file_name: str,
                                 extension: str, file_size: int, seen_at: str, scan_id: str) -> None:
        self._conn.execute("""INSERT INTO unknown_media_candidates
            (drive_id,full_path,file_name,extension,file_size,last_seen,scan_id,is_active)
            VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(drive_id,full_path) DO UPDATE SET
            file_name=excluded.file_name,extension=excluded.extension,file_size=excluded.file_size,
            last_seen=excluded.last_seen,scan_id=excluded.scan_id,is_active=1""",
            (drive_id, full_path, file_name, extension, file_size, seen_at, scan_id))

    def finalize_auxiliary_scan(self, drive_id: str, scan_id: str, status: ScanStatus,
                                archive_tracking_enabled: bool = True) -> None:
        """Deactivate stale scan findings only when traversal was completely reliable."""
        if status is not ScanStatus.COMPLETED:
            LOGGER.info("Bereinigung zusätzlicher Scanergebnisse übersprungen: %s", status)
            return
        if archive_tracking_enabled:
            self._conn.execute("UPDATE archive_only_dirs SET is_active=0 WHERE drive_id=? AND COALESCE(scan_id,'')<>?", (drive_id, scan_id))
        self._conn.execute("UPDATE unknown_media_candidates SET is_active=0 WHERE drive_id=? AND scan_id<>?", (drive_id, scan_id))

    def duplicate_groups(self, status: DuplicateStatus | None = None) -> list[DuplicateGroup]:
        groups = DuplicateDetectionService().groups([dict(row) for row in self.list_entries()])
        return [group for group in groups if status is None or group.status is status]

    def cleanup_details(self, category: str) -> list[Any]:
        duplicate_categories = {
            "Mögliche Dubletten": DuplicateStatus.POSSIBLE,
            "Wahrscheinliche Dubletten": DuplicateStatus.PROBABLE,
            "Bestätigte Dubletten": DuplicateStatus.CONFIRMED,
        }
        if category in duplicate_categories:
            return self.duplicate_groups(duplicate_categories[category])
        queries = {
            "Archive noch nicht entpackt": "SELECT * FROM archive_only_dirs WHERE is_active=1 ORDER BY folder_path",
            "Fehlende Dateien": "SELECT * FROM media_entries WHERE is_missing=1 ORDER BY title",
            "Unbekannte Plattformen": "SELECT * FROM media_entries WHERE platform='Unknown' ORDER BY title",
            "Unbekannte Dateiformate": "SELECT * FROM unknown_media_candidates WHERE is_active=1 ORDER BY full_path",
            "Metadaten fehlgeschlagen": "SELECT * FROM games WHERE metadata_status='failed' ORDER BY title",
            "Match prüfen": "SELECT * FROM games WHERE metadata_status='ambiguous' ORDER BY title",
            "Spiele ohne Cover": "SELECT * FROM games WHERE metadata_status IN ('matched','manual') AND COALESCE(cover_path,'')='' ORDER BY title",
            "Unvollständige Metadaten": "SELECT * FROM games WHERE metadata_status='incomplete' ORDER BY title",
            "DLC ohne Hauptspiel": self._content_cleanup_query("content_type IN ('dlc','addon') AND content_parent_game_id IS NULL"),
            "Update ohne Hauptspiel": self._content_cleanup_query("content_type='update' AND content_parent_game_id IS NULL"),
            "Unbekannter Content-Typ": self._content_cleanup_query("content_type='unknown'"),
            "Unsichere Content-Zuordnung": self._content_cleanup_query("content_type IN ('update','dlc','addon') AND content_parent_game_id IS NULL AND content_detection_confidence>0"),
            "Manuell zu prüfen": self._content_cleanup_query("content_type IN ('update','dlc','addon') AND content_parent_game_id IS NULL"),
            "Mehrere Base-Game-Dateien": """SELECT g.title,g.platform,COUNT(*) AS base_file_count,
                GROUP_CONCAT(mf.file_name, ' | ') AS file_name FROM games g JOIN media_files mf ON mf.game_id=g.id
                WHERE mf.content_type='base_game' AND mf.is_missing=0 GROUP BY g.id HAVING COUNT(*)>1 ORDER BY g.title""",
        }
        return list(self._conn.execute(queries[category]).fetchall())

    @staticmethod
    def _content_cleanup_query(predicate: str) -> str:
        return f"""SELECT mf.file_name,g.platform,mf.content_type,mf.content_title AS possible_base_title,
            g.title AS current_game,pg.title AS suggested_parent_game,mf.content_detection_confidence,
            mf.content_detection_method,mf.full_path FROM media_files mf JOIN games g ON g.id=mf.game_id
            LEFT JOIN games pg ON pg.id=mf.content_parent_game_id WHERE {predicate} ORDER BY mf.file_name"""

    def cleanup_counts(self) -> dict[str, int]:
        categories = ("Archive noch nicht entpackt", "Mögliche Dubletten", "Wahrscheinliche Dubletten",
                      "Bestätigte Dubletten", "Fehlende Dateien", "Unbekannte Plattformen",
                      "Unbekannte Dateiformate", "Metadaten fehlgeschlagen", "Match prüfen",
                      "Spiele ohne Cover", "Unvollständige Metadaten", "DLC ohne Hauptspiel",
                      "Update ohne Hauptspiel", "Unbekannter Content-Typ", "Mehrere Base-Game-Dateien",
                      "Unsichere Content-Zuordnung", "Manuell zu prüfen")
        return {category: len(self.cleanup_details(category)) for category in categories}

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
            clauses.append("(media_entries.title LIKE ? OR file_name LIKE ? OR full_path LIKE ?)"); token=f"%{search.strip()}%"; params += [token]*3
        if drive_filter.strip(): clauses.append("media_entries.drive_id = ?"); params.append(drive_filter)
        if platform_filter.strip(): clauses.append("media_entries.platform = ?"); params.append(platform_filter)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try: return list(self._conn.execute(f"""SELECT media_entries.*,
            games.canonical_title, games.release_year AS metadata_release_year, games.publisher,
            games.developer, games.description, games.cover_path, games.cover_source,
            games.metadata_source, games.metadata_status, games.metadata_match_score,
            games.metadata_match_method, games.external_game_id, games.metadata_locked,
            games.artwork_source, games.artwork_external_game_id, games.artwork_status
            FROM media_entries LEFT JOIN games ON games.id=media_entries.game_id
            {where} ORDER BY media_entries.title COLLATE NOCASE""", params).fetchall())
        except sqlite3.Error as exc:
            LOGGER.exception("Datenbankabfrage fehlgeschlagen"); raise DatabaseError(str(exc)) from exc

    def list_distinct_drives(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT DISTINCT drive_id,drive_label FROM media_entries ORDER BY drive_label COLLATE NOCASE").fetchall())

    def game_content_files(self, game_id: int) -> list[sqlite3.Row]:
        return list(self._conn.execute("""SELECT * FROM media_files WHERE game_id=?
            ORDER BY CASE content_type WHEN 'base_game' THEN 0 WHEN 'update' THEN 1
            WHEN 'dlc' THEN 2 WHEN 'addon' THEN 2 ELSE 3 END, file_name COLLATE NOCASE""", (game_id,)))

    def content_analysis_candidates(self, force: bool = False) -> list[sqlite3.Row]:
        where = "content_locked=0" if force else "content_locked=0 AND content_type='unknown'"
        return list(self._conn.execute(f"SELECT * FROM media_files WHERE {where} ORDER BY id"))

    def _association_games(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._conn.execute("""SELECT g.*,
            EXISTS(SELECT 1 FROM media_files b WHERE b.game_id=g.id AND b.content_type='base_game') AS has_base,
            (SELECT b.content_id FROM media_files b WHERE b.game_id=g.id AND b.content_type='base_game' AND b.content_id IS NOT NULL LIMIT 1) AS content_id,
            (SELECT b.base_content_id FROM media_files b WHERE b.game_id=g.id AND b.content_type='base_game' AND b.base_content_id IS NOT NULL LIMIT 1) AS base_content_id
            FROM games g""")]

    def apply_content_detection(self, media_file_id: int, result: ContentDetectionResult) -> None:
        row = self._conn.execute("""SELECT mf.*,g.platform,g.title AS game_title
            FROM media_files mf JOIN games g ON g.id=mf.game_id WHERE mf.id=?""", (media_file_id,)).fetchone()
        if not row or row["content_locked"]:
            if row: LOGGER.info("Content-Lock respektiert: media=%s", media_file_id)
            return
        association = ContentAssociationService().associate(result, row["platform"], self._association_games(), dict(row))
        parent = association.parent_game_id
        # Base files remain on their current Game. Supplemental content moves only
        # after a unique conservative association.
        new_game = row["game_id"] if result.content_type in {MediaContentType.BASE_GAME, MediaContentType.DEMO, MediaContentType.UNKNOWN} or parent is None else parent
        timestamp = now_iso()
        with self._conn:
            self._conn.execute("""UPDATE media_files SET game_id=?,content_type=?,content_title=?,content_version=?,
                content_id=?,base_content_id=?,content_detection_method=?,content_detection_confidence=?,
                content_parent_game_id=?,content_region=? WHERE id=?""", (new_game, result.content_type,
                result.title, result.version, result.content_id, result.base_content_id, result.method,
                result.confidence, parent, result.region, media_file_id))
            self._conn.execute("""UPDATE media_entries SET game_id=?,title=CASE WHEN ? IS NOT NULL THEN ? ELSE title END,
                content_type=?,content_title=?,content_version=?,content_id=?,base_content_id=?,content_detection_method=?,
                content_detection_confidence=?,content_parent_game_id=?,content_region=? WHERE media_file_id=?""",
                (new_game, parent, result.title, result.content_type, result.title, result.version, result.content_id,
                 result.base_content_id, result.method, result.confidence, parent, result.region, media_file_id))
            self._delete_empty_legacy_game(row["game_id"], new_game, timestamp)

    def _delete_empty_legacy_game(self, old_game_id: int, new_game_id: int, timestamp: str) -> None:
        if old_game_id == new_game_id:
            return
        game = self._conn.execute("SELECT * FROM games WHERE id=?", (old_game_id,)).fetchone()
        if not game or self._conn.execute("SELECT 1 FROM media_files WHERE game_id=?", (old_game_id,)).fetchone():
            return
        relevant = (game["metadata_locked"] or game["external_game_id"] or game["cover_path"] or
                    game["metadata_status"] not in {"not_requested", "failed"})
        if relevant:
            LOGGER.info("Leeres Legacy-Game %s wegen relevanter Metadaten beibehalten", old_game_id)
            return
        self._conn.execute("DELETE FROM games WHERE id=?", (old_game_id,))
        LOGGER.info("Leeres, ungelocktes Legacy-Content-Game %s konsolidiert", old_game_id)

    def set_manual_content(self, media_file_id: int, content_type: MediaContentType,
                           parent_game_id: int | None, title: str | None = None) -> None:
        row = self._conn.execute("SELECT game_id FROM media_files WHERE id=?", (media_file_id,)).fetchone()
        if not row: raise DatabaseError("MediaFile nicht gefunden")
        game_id = parent_game_id or row["game_id"]
        with self._conn:
            self._conn.execute("""UPDATE media_files SET game_id=?,content_type=?,content_title=?,
                content_parent_game_id=?,content_detection_method='manual',content_detection_confidence=1,content_locked=1 WHERE id=?""",
                (game_id, content_type, title, parent_game_id, media_file_id))
            self._conn.execute("""UPDATE media_entries SET game_id=?,content_type=?,content_title=?,
                content_parent_game_id=?,content_detection_method='manual',content_detection_confidence=1,content_locked=1 WHERE media_file_id=?""",
                (game_id, content_type, title, parent_game_id, media_file_id))
        LOGGER.info("Manuelle Zuordnung / Content-Lock: media=%s parent=%s", media_file_id, parent_game_id)

    def enqueue_metadata(self, game_ids: Iterable[int] | None = None, force: bool = False) -> int:
        params: list[Any] = []
        base_filter = """EXISTS(SELECT 1 FROM media_files mf WHERE mf.game_id=games.id AND mf.content_type='base_game')
            OR NOT EXISTS(SELECT 1 FROM media_files mf WHERE mf.game_id=games.id AND mf.content_type<>'unknown')"""
        where = f"metadata_status='not_requested' AND ({base_filter})"
        if game_ids is not None:
            ids = list(game_ids)
            if not ids: return 0
            where = f"id IN ({','.join('?' for _ in ids)}) AND ({base_filter})"; params.extend(ids)
            # A durable lock, not the transient queue status, protects user decisions.
            if not force: where += " AND metadata_locked=0"
            else: where += " AND (metadata_locked=0 OR external_game_id IS NOT NULL)"
        cursor = self._conn.execute(f"UPDATE games SET metadata_status=? WHERE {where}", [MetadataStatus.QUEUED, *params])
        self._conn.commit(); return cursor.rowcount

    def queued_games(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("""SELECT * FROM games WHERE metadata_status=? AND
            (EXISTS(SELECT 1 FROM media_files mf WHERE mf.game_id=games.id AND mf.content_type='base_game')
             OR NOT EXISTS(SELECT 1 FROM media_files mf WHERE mf.game_id=games.id AND mf.content_type<>'unknown')) ORDER BY id""", (MetadataStatus.QUEUED,)))

    def set_metadata_status(self, game_id: int, status: MetadataStatus) -> None:
        self._conn.execute("UPDATE games SET metadata_status=?, updated_at=? WHERE id=?", (status, now_iso(), game_id)); self._conn.commit()

    def save_candidates(self, game_id: int, provider: str, ranked) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM metadata_match_candidates WHERE game_id=?", (game_id,))
            for match in ranked[:10]:
                game = match.game
                self._conn.execute("""INSERT INTO metadata_match_candidates
                    (game_id,provider,external_game_id,title,platform,release_date,release_year,score,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (game_id, provider, game.external_id, game.title, game.platform,
                    game.release_date, game.release_year, match.score, now_iso()))

    def list_candidates(self, game_id: int) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT * FROM metadata_match_candidates WHERE game_id=? ORDER BY score DESC", (game_id,)))

    def apply_metadata(self, game_id: int, game: ExternalGame, provider: str, score: float,
                       method: str, status: MetadataStatus = MetadataStatus.MATCHED) -> None:
        current = self._conn.execute("SELECT metadata_locked FROM games WHERE id=?", (game_id,)).fetchone()
        if not current: raise DatabaseError("Spiel nicht gefunden")
        if current[0] and method not in {"manual", "refresh"}: return
        timestamp = now_iso()
        with self._conn:
            self._conn.execute("""UPDATE games SET canonical_title=?,external_game_id=?,external_platform_id=?,
                release_date=?,release_year=?,publisher=?,developer=?,description=?,region=?,metadata_source=?,
                metadata_status=?,metadata_last_updated=?,metadata_match_score=?,metadata_match_method=?,
                metadata_locked=CASE WHEN ?='manual' THEN 1 ELSE metadata_locked END,updated_at=? WHERE id=?""",
                (game.title, game.external_id, game.external_platform_id, game.release_date, game.release_year,
                 game.publisher, game.developer, game.description, game.region, provider, status, timestamp, score, method, method, timestamp, game_id))
            self._conn.execute("DELETE FROM metadata_match_candidates WHERE game_id=?", (game_id,))

    def apply_candidate_manually(self, game_id: int, external: ExternalGame, provider: str, score: float) -> None:
        self.apply_metadata(game_id, external, provider, score, "manual", MetadataStatus.MANUAL)
        LOGGER.info("Manueller Metadata-Match game=%s provider=%s", game_id, provider)

    def set_cover(self, game_id: int, path: str | None, source: str | None) -> None:
        self._conn.execute("UPDATE games SET cover_path=?,cover_source=?,updated_at=? WHERE id=?", (path, source, now_iso(), game_id)); self._conn.commit()

    def remove_cover(self, game_id: int) -> str | None:
        row = self._conn.execute("SELECT cover_path FROM games WHERE id=?", (game_id,)).fetchone()
        self._conn.execute("UPDATE games SET cover_path=NULL,cover_source=NULL,artwork_status='not_requested' WHERE id=?", (game_id,)); self._conn.commit()
        return row[0] if row else None

    def enqueue_covers(self, game_ids: Iterable[int] | None = None, force: bool = False) -> int:
        params: list[Any] = []
        where = "external_game_id IS NOT NULL AND COALESCE(cover_path,'')='' AND artwork_status NOT IN ('queued','searching')"
        if game_ids is not None:
            ids = list(game_ids)
            if not ids: return 0
            where += f" AND id IN ({','.join('?' for _ in ids)})"; params.extend(ids)
        if force: where = where.replace(" AND COALESCE(cover_path,'')=''", "")
        cursor = self._conn.execute(f"UPDATE games SET artwork_status='queued' WHERE {where}", params)
        self._conn.commit(); return cursor.rowcount

    def queued_covers(self):
        return list(self._conn.execute("SELECT * FROM games WHERE artwork_status='queued' ORDER BY id"))

    def set_artwork_result(self, game_id: int, status: str, path: str | None = None,
                           source: str | None = None, external_id: str | None = None) -> None:
        self._conn.execute("""UPDATE games SET artwork_status=?,cover_path=COALESCE(?,cover_path),
            cover_source=COALESCE(?,cover_source),artwork_source=COALESCE(?,artwork_source),
            artwork_external_game_id=COALESCE(?,artwork_external_game_id),updated_at=? WHERE id=?""",
            (status, path, source, source, external_id, now_iso(), game_id)); self._conn.commit()

    def reset_metadata(self, game_id: int) -> None:
        with self._conn:
            self._conn.execute("""UPDATE games SET metadata_status='not_requested',metadata_source=NULL,external_game_id=NULL,
                external_platform_id=NULL,canonical_title=NULL,release_date=NULL,release_year=NULL,publisher=NULL,
                developer=NULL,description=NULL,region=NULL,metadata_last_updated=NULL,metadata_match_score=NULL,
                metadata_match_method=NULL,metadata_locked=0 WHERE id=?""", (game_id,))
            self._conn.execute("DELETE FROM metadata_match_candidates WHERE game_id=?", (game_id,))
