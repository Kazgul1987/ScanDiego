from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.database.db_manager import DatabaseManager
from app.models.drive import DriveInfo
from app.models.game_entry import MediaEntry
from app.utils.date_utils import now_iso, ts_to_iso
from app.utils.formatting import clean_title_from_filename

LOGGER = logging.getLogger(__name__)


class ScannerWorker(QObject):
    progress = Signal(str, int, int)  # message, processed, found
    error = Signal(str)
    finished = Signal(dict)

    def __init__(
        self,
        db_path: Path,
        drives: list[DriveInfo],
        report_archive_only_dirs: bool = False,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.drives = drives
        self.report_archive_only_dirs = report_archive_only_dirs
        self._cancelled = False
        self._allowed_extensions = {".iso", ".nsp", ".xci", ".bin", ".cue", ".img"}
        self._archive_extensions = {".rar", ".zip"}

    @Slot()
    def run(self) -> None:
        scan_ts = now_iso()
        processed = 0
        found = 0
        errors = 0
        archive_only_dirs: list[str] = []
        seen_archive_only_dirs: set[Path] = set()
        db: DatabaseManager | None = None

        try:
            db = DatabaseManager(self.db_path)

            for drive in self.drives:
                if self._cancelled:
                    break

                roots = [
                    Path(f"{drive.letter}\\Games"),
                    Path(f"{drive.letter}\\ROMs"),
                ]

                for root in roots:
                    if self._cancelled:
                        break
                    if not root.exists():
                        continue

                    category = "game" if root.name.lower() == "games" else "rom"
                    stack = [root]
                    while stack:
                        if self._cancelled:
                            break

                        current = stack.pop()
                        try:
                            children = list(current.iterdir())
                        except (PermissionError, OSError) as exc:
                            LOGGER.warning("Ordner nicht lesbar: %s (%s)", current, exc)
                            errors += 1
                            continue

                        has_rom_or_image = False
                        has_archive = False

                        for child in children:
                            if self._cancelled:
                                break
                            try:
                                if child.is_dir():
                                    stack.append(child)
                                    continue
                                if not child.is_file():
                                    continue
                            except OSError as exc:
                                errors += 1
                                LOGGER.warning(
                                    "Eintrag konnte nicht geprüft werden: %s (%s)",
                                    child,
                                    exc,
                                )
                                continue

                            processed += 1
                            suffix = child.suffix.lower()
                            if suffix in self._allowed_extensions:
                                has_rom_or_image = True
                                try:
                                    stat = child.stat()
                                    media = MediaEntry(
                                        id=None,
                                        category=category,
                                        title=clean_title_from_filename(child.name),
                                        original_filename=child.name,
                                        full_path=str(child.resolve()),
                                        file_name=child.name,
                                        file_extension=suffix,
                                        file_size=stat.st_size,
                                        modified_time=ts_to_iso(stat.st_mtime),
                                        drive_letter=drive.letter,
                                        drive_label=drive.label,
                                        drive_id=drive.volume_serial,
                                        scan_date=scan_ts,
                                        last_seen_date=scan_ts,
                                        is_missing=0,
                                    )
                                    db.upsert_entry(media)
                                    found += 1
                                except OSError as exc:
                                    errors += 1
                                    LOGGER.warning(
                                        "Datei konnte nicht gelesen werden: %s (%s)",
                                        child,
                                        exc,
                                    )
                            elif suffix in self._archive_extensions:
                                has_archive = True

                            if processed % 25 == 0:
                                self.progress.emit(
                                    f"Scanne {drive.display_name}", processed, found
                                )

                        if (
                            self.report_archive_only_dirs
                            and has_archive
                            and not has_rom_or_image
                        ):
                            resolved_dir = current.resolve()
                            if resolved_dir not in seen_archive_only_dirs:
                                seen_archive_only_dirs.add(resolved_dir)
                                archive_only_dirs.append(str(resolved_dir))
                                db.upsert_archive_only_dir(
                                    drive_id=drive.volume_serial,
                                    folder_path=str(resolved_dir),
                                    scan_date=scan_ts,
                                )

                db.mark_missing_for_drive(drive.volume_serial, scan_ts)

            db.commit()
            self.finished.emit(
                {
                    "cancelled": self._cancelled,
                    "processed": processed,
                    "found": found,
                    "errors": errors,
                    "archive_only_dirs": archive_only_dirs,
                }
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Scan crashed")
            self.error.emit(str(exc))
        finally:
            if db is not None:
                db.close()

    def cancel(self) -> None:
        self._cancelled = True
