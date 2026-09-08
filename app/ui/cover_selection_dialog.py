from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget,
                               QListWidgetItem, QVBoxLayout)

from app.database.db_manager import DatabaseManager
from app.models.metadata import ExternalGame
from app.providers.factory import create_artwork_provider
from app.services.artwork_service import ArtworkService


class CandidateWorker(QObject):
    loaded = Signal(list, list)
    failed = Signal(str)

    def __init__(self, game, settings):
        super().__init__(); self.game, self.settings = game, settings

    @Slot()
    def run(self):
        try:
            provider = create_artwork_provider(self.settings)
            candidates = provider.search_artwork_candidates(self.game, 10)
            previews = []
            for candidate in candidates:
                try:
                    body, _ = provider.http.request(candidate.thumb_url or candidate.image_url).body, None
                    previews.append(body)
                except Exception:
                    previews.append(b"")
            self.loaded.emit(candidates, previews)
        except Exception as exc:
            self.failed.emit(str(exc))


class ApplyCandidateWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, db_path, game_id, candidate, settings):
        super().__init__(); self.db_path, self.game_id = db_path, game_id
        self.candidate, self.settings = candidate, settings

    @Slot()
    def run(self):
        db = DatabaseManager(self.db_path)
        try:
            service = ArtworkService(create_artwork_provider(self.settings))
            old = db._conn.execute("SELECT cover_path FROM games WHERE id=?", (self.game_id,)).fetchone()[0]
            path = service.apply_candidate(self.game_id, self.candidate)
            db.set_manual_artwork(self.game_id, str(path), service.provider.name,
                                  self.candidate.external_game_id, self.candidate.artwork_id)
            if old and old != str(path) and not db.cover_path_is_shared(old, self.game_id): service.remove(old)
            self.finished.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            db.close()


class CoverSelectionDialog(QDialog):
    """Non-blocking-network artwork chooser; all provider I/O runs in workers."""
    cover_applied = Signal()

    def __init__(self, game_row, db_path, settings, parent=None):
        super().__init__(parent); self.row, self.db_path, self.settings = game_row, db_path, settings
        self.candidates = []; self.thread = None; self.worker = None
        title = game_row["canonical_title"] or game_row["title"]
        self.setWindowTitle(f"Cover auswählen – {title}"); self.resize(780, 600)
        layout = QVBoxLayout(self); self.info = QLabel("SteamGridDB-Cover werden gesucht …")
        self.list = QListWidget(); self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(160, 240)); self.list.setGridSize(QSize(185, 300))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use = self.buttons.addButton("Dieses Cover verwenden", QDialogButtonBox.ButtonRole.AcceptRole)
        self.use.setEnabled(False); layout.addWidget(self.info); layout.addWidget(self.list); layout.addWidget(self.buttons)
        self.buttons.rejected.connect(self.reject); self.use.clicked.connect(self._apply)
        self.list.currentRowChanged.connect(lambda row: self.use.setEnabled(row >= 0))
        self._search(title)

    def _search(self, title):
        game = ExternalGame(str(self.row["external_game_id"] or ""), title, self.row["platform"],
                            release_date=self.row["release_date"], release_year=self.row["release_year"])
        self.thread = QThread(self); self.worker = CandidateWorker(game, self.settings); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.loaded.connect(self._loaded); self.worker.failed.connect(self._failed)
        self.worker.loaded.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.thread.start()

    def _loaded(self, candidates, previews):
        self.candidates = candidates; self.list.clear()
        for candidate, body in zip(candidates, previews):
            pixmap = QPixmap(); pixmap.loadFromData(body)
            text = f"{candidate.game_title}\n{candidate.width or '?'} × {candidate.height or '?'} · ID {candidate.artwork_id}"
            self.list.addItem(QListWidgetItem(QIcon(pixmap), text))
        self.info.setText(f"{len(candidates)} Cover gefunden" if candidates else "Keine Cover gefunden.")

    def _failed(self, message): self.info.setText("Cover-Suche fehlgeschlagen: " + message)

    def _apply(self):
        row = self.list.currentRow()
        if row < 0: return
        self.use.setEnabled(False); self.info.setText("Cover wird heruntergeladen …")
        self.thread = QThread(self); self.worker = ApplyCandidateWorker(self.db_path, self.row["id"], self.candidates[row], self.settings)
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(lambda _: (self.cover_applied.emit(), self.accept()))
        self.worker.failed.connect(self._failed); self.worker.finished.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit)
        self.thread.start()
