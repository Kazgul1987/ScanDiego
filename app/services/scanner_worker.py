from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config import ARCHIVE_EXTENSIONS, SCAN_BATCH_SIZE, SUPPORTED_MEDIA_EXTENSIONS
from app.database.db_manager import DatabaseManager
from app.models.drive import DriveInfo
from app.models.game_entry import MediaEntry
from app.models.scan import ScanStatus
from app.services.platform_detection_service import PlatformDetectionService
from app.services.title_normalization_service import TitleNormalizationService
from app.utils.date_utils import now_iso, ts_to_iso

LOGGER = logging.getLogger(__name__)


class ScannerWorker(QObject):
    progress = Signal(str, int, int, int, float, str)
    error = Signal(str)
    finished = Signal(dict)

    def __init__(self, db_path: Path, drives: list[DriveInfo], report_archive_only_dirs: bool = False) -> None:
        super().__init__()
        self.db_path, self.drives = db_path, drives
        self.report_archive_only_dirs = report_archive_only_dirs
        self._cancelled = False
        self._titles = TitleNormalizationService()
        self._platforms = PlatformDetectionService()

    @Slot()
    def run(self) -> None:
        started = time.monotonic(); processed = found = warnings = 0
        archive_only_dirs: list[str] = []; db: DatabaseManager | None = None
        overall_status = ScanStatus.COMPLETED
        try:
            db = DatabaseManager(self.db_path)
            for drive in self.drives:
                if self._cancelled: overall_status = ScanStatus.CANCELLED; break
                drive_started = now_iso(); drive_processed = drive_found = drive_warnings = 0
                scan_id = db.start_scan(drive.volume_serial, "Games;ROMs")
                LOGGER.info("Scan gestartet: %s (%s)", drive.display_name, scan_id)
                batch: list[MediaEntry] = []
                try:
                    for root in (Path(f"{drive.letter}\\Games"), Path(f"{drive.letter}\\ROMs")):
                        if self._cancelled: break
                        if not root.exists(): continue
                        category = "game" if root.name.lower() == "games" else "rom"
                        stack = [root]
                        while stack and not self._cancelled:
                            current = stack.pop()
                            self.progress.emit(str(current), processed, found, warnings, time.monotonic()-started, ScanStatus.RUNNING)
                            has_media = has_archive = False
                            try:
                                iterator = current.iterdir()
                                for child in iterator:
                                    if self._cancelled: break
                                    try:
                                        if child.is_dir(): stack.append(child); continue
                                        if not child.is_file(): continue
                                        processed += 1; drive_processed += 1
                                        suffix = child.suffix.lower()
                                        if suffix in SUPPORTED_MEDIA_EXTENSIONS:
                                            has_media = True; stat = child.stat(); timestamp = now_iso()
                                            batch.append(MediaEntry(None, category, self._titles.normalize(child.name), child.name,
                                                str(child.resolve()), child.name, suffix, stat.st_size, ts_to_iso(stat.st_mtime),
                                                drive.letter, drive.label, drive.volume_serial, timestamp, timestamp, 0,
                                                str(self._platforms.detect(child))))
                                            found += 1; drive_found += 1
                                            if len(batch) >= SCAN_BATCH_SIZE: db.upsert_entries(batch); batch.clear()
                                        elif suffix in ARCHIVE_EXTENSIONS: has_archive = True
                                    except OSError as exc:
                                        warnings += 1; drive_warnings += 1
                                        LOGGER.warning("Eintrag nicht lesbar: %s (%s)", child, exc)
                                    if processed % 25 == 0:
                                        self.progress.emit(str(current), processed, found, warnings, time.monotonic()-started, ScanStatus.RUNNING)
                            except (PermissionError, OSError) as exc:
                                warnings += 1; drive_warnings += 1
                                LOGGER.warning("Ordner nicht lesbar: %s (%s)", current, exc)
                                continue
                            if self.report_archive_only_dirs and has_archive and not has_media:
                                resolved = str(current.resolve())
                                if resolved not in archive_only_dirs:
                                    archive_only_dirs.append(resolved)
                                    db.upsert_archive_only_dir(drive.volume_serial, resolved, drive_started)
                    if batch: db.upsert_entries(batch)
                    status = (ScanStatus.CANCELLED if self._cancelled else
                              ScanStatus.COMPLETED_WITH_WARNINGS if drive_warnings else ScanStatus.COMPLETED)
                    if status is ScanStatus.COMPLETED:
                        db.mark_missing_for_completed_scan(drive.volume_serial, drive_started, status)
                    db.finish_scan(scan_id, status, drive_processed, drive_found, drive_warnings)
                    LOGGER.info("Scan beendet: %s, Status=%s", drive.display_name, status)
                    if status is not ScanStatus.COMPLETED: overall_status = status
                except Exception as exc:
                    db.finish_scan(scan_id, ScanStatus.FAILED, drive_processed, drive_found, drive_warnings, str(exc))
                    LOGGER.exception("Scan fehlgeschlagen: %s", drive.display_name)
                    overall_status = ScanStatus.FAILED
                    raise
            db.commit()
            self.finished.emit({"status": str(overall_status), "cancelled": self._cancelled,
                "processed": processed, "found": found, "errors": warnings,
                "warnings": warnings, "elapsed": time.monotonic()-started,
                "archive_only_dirs": archive_only_dirs})
        except Exception as exc:
            LOGGER.exception("Scan abgebrochen durch Fehler")
            self.error.emit(str(exc))
            self.finished.emit({"status": str(ScanStatus.FAILED), "cancelled": False,
                "processed": processed, "found": found, "errors": warnings,
                "warnings": warnings, "elapsed": time.monotonic()-started, "archive_only_dirs": archive_only_dirs})
        finally:
            if db: db.close()

    @Slot()
    def cancel(self) -> None:
        self._cancelled = True
        LOGGER.info("Scan-Abbruch angefordert")
