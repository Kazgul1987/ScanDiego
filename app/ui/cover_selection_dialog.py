from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
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
    apply_worker_class = ApplyCandidateWorker

    def __init__(self, game_row, db_path, settings, parent=None):
        super().__init__(parent); self.row, self.db_path, self.settings = game_row, db_path, settings
        self.candidates = []
        self._search_thread = self._search_worker = None
        self._apply_thread = self._apply_worker = None
        self._apply_succeeded = False; self._applied_result = None; self._apply_error = None
        title = game_row["canonical_title"] or game_row["title"]
        self.setWindowTitle(f"Cover auswählen – {title}"); self.resize(780, 600)
        layout = QVBoxLayout(self); self.info = QLabel("SteamGridDB-Cover werden gesucht …")
        self.list = QListWidget(); self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(160, 240)); self.list.setGridSize(QSize(185, 300))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use = self.buttons.addButton("Dieses Cover verwenden", QDialogButtonBox.ButtonRole.AcceptRole)
        self.use.setEnabled(False); layout.addWidget(self.info); layout.addWidget(self.list); layout.addWidget(self.buttons)
        self.buttons.rejected.connect(self._request_reject); self.use.clicked.connect(self._apply)
        self.list.currentItemChanged.connect(
            lambda current, _: self.use.setEnabled(
                current is not None and current.data(Qt.ItemDataRole.UserRole) is not None))
        self._search(title)

    def _search(self, title):
        game = ExternalGame(str(self.row["external_game_id"] or ""), title, self.row["platform"],
                            release_date=self.row["release_date"], release_year=self.row["release_year"])
        thread = QThread(self); worker = CandidateWorker(game, self.settings)
        self._search_thread, self._search_worker = thread, worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run); worker.loaded.connect(self._loaded); worker.failed.connect(self._failed)
        worker.loaded.connect(thread.quit); worker.failed.connect(thread.quit)
        worker.loaded.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); thread.finished.connect(self._on_search_thread_finished)
        thread.start()

    def _on_search_thread_finished(self):
        self._search_worker = None; self._search_thread = None

    def _loaded(self, candidates, previews):
        self.candidates = candidates; self.list.clear()
        game_ids = list(dict.fromkeys(candidate.external_game_id for candidate in candidates))
        for external_game_id in game_ids:
            grouped = [(index, candidate, previews[index]) for index, candidate in enumerate(candidates)
                       if candidate.external_game_id == external_game_id]
            first = grouped[0][1]
            if len(game_ids) > 1:
                heading = QListWidgetItem(f"{first.game_title}  ·  Match: {first.score:.0f} %")
                heading.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(heading)
            for index, candidate, body in grouped:
                pixmap = QPixmap(); pixmap.loadFromData(body)
                details = f"{candidate.width or '?'} × {candidate.height or '?'}"
                if candidate.style:
                    details += f" · {candidate.style}"
                item = QListWidgetItem(QIcon(pixmap), details)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.list.addItem(item)
        self.info.setText(f"{len(candidates)} Cover gefunden" if candidates else "Keine Cover gefunden.")

    def _failed(self, message): self.info.setText("Cover-Suche fehlgeschlagen: " + message)

    def _has_active_thread(self):
        # A newly started QThread may not report isRunning() until the next event
        # cycle, so ownership itself is the reliable active-operation marker.
        return self._apply_thread is not None or self._search_thread is not None

    def _request_reject(self):
        if self._has_active_thread():
            self.info.setText("Bitte warten, bis der laufende Vorgang beendet ist …")
            return
        self.reject()

    def _apply(self):
        item = self.list.currentItem()
        if item is None or item.data(Qt.ItemDataRole.UserRole) is None: return
        candidate = self.candidates[item.data(Qt.ItemDataRole.UserRole)]
        self.use.setEnabled(False); self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(False)
        self.info.setText("Cover wird heruntergeladen …")
        self._apply_succeeded = False; self._applied_result = None; self._apply_error = None
        thread = QThread(self)
        worker = self.apply_worker_class(self.db_path, self.row["id"], candidate, self.settings)
        self._apply_thread, self._apply_worker = thread, worker
        worker.moveToThread(thread); thread.started.connect(worker.run)
        worker.finished.connect(self._on_apply_worker_success); worker.failed.connect(self._on_apply_worker_failed)
        worker.finished.connect(thread.quit); worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); thread.finished.connect(self._on_apply_thread_finished)
        thread.start()

    @Slot(str)
    def _on_apply_worker_success(self, result):
        self._apply_succeeded = True; self._applied_result = result

    @Slot(str)
    def _on_apply_worker_failed(self, message):
        self._apply_error = message

    @Slot()
    def _on_apply_thread_finished(self):
        succeeded, error = self._apply_succeeded, self._apply_error
        self._apply_worker = None; self._apply_thread = None
        if succeeded:
            self.cover_applied.emit()
            self.accept()
            return
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(True)
        current = self.list.currentItem()
        self.use.setEnabled(current is not None and current.data(Qt.ItemDataRole.UserRole) is not None)
        if error:
            self._failed(error)

    def closeEvent(self, event: QCloseEvent):
        if self._has_active_thread():
            event.ignore()
            self.info.setText("Bitte warten, bis der laufende Vorgang beendet ist …")
            return
        super().closeEvent(event)
