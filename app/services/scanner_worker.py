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

    def __init__(self, db: DatabaseManager, drives: list[DriveInfo]) -> None:
        super().__init__()
        self.db = db
        self.drives = drives
        self._cancelled = False
        self._allowed_extensions = {".iso", ".nsp", ".xci", ".bin", ".cue", ".img"}

    @Slot()
    def run(self) -> None:
        scan_ts = now_iso()
        processed = 0
        found = 0
        errors = 0

        try:
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
                    for entry in self._iter_files(root):
                        if self._cancelled:
                            break
                        processed += 1

                        if entry.suffix.lower() not in self._allowed_extensions:
                            if processed % 100 == 0:
                                self.progress.emit(
                                    f"Durchsuche: {root}", processed, found
                                )
                            continue

                        try:
                            stat = entry.stat()
                            media = MediaEntry(
                                id=None,
                                category=category,
                                title=clean_title_from_filename(entry.name),
                                original_filename=entry.name,
                                full_path=str(entry.resolve()),
                                file_name=entry.name,
                                file_extension=entry.suffix.lower(),
                                file_size=stat.st_size,
                                modified_time=ts_to_iso(stat.st_mtime),
                                drive_letter=drive.letter,
                                drive_label=drive.label,
                                drive_id=drive.volume_serial,
                                scan_date=scan_ts,
                                last_seen_date=scan_ts,
                                is_missing=0,
                            )
                            self.db.upsert_entry(media)
                            found += 1
                        except OSError as exc:
                            errors += 1
                            LOGGER.warning("Datei konnte nicht gelesen werden: %s (%s)", entry, exc)

                        if processed % 25 == 0:
                            self.progress.emit(
                                f"Scanne {drive.display_name}", processed, found
                            )

                self.db.mark_missing_for_drive(drive.volume_serial, scan_ts)

            self.db.commit()
            self.finished.emit(
                {
                    "cancelled": self._cancelled,
                    "processed": processed,
                    "found": found,
                    "errors": errors,
                }
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Scan crashed")
            self.error.emit(str(exc))

    def cancel(self) -> None:
        self._cancelled = True

    def _iter_files(self, root: Path):
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with current.iterdir() as it:
                    for child in it:
                        if self._cancelled:
                            return
                        if child.is_dir():
                            stack.append(child)
                        elif child.is_file():
                            yield child
            except (PermissionError, OSError) as exc:
                LOGGER.warning("Ordner nicht lesbar: %s (%s)", current, exc)
