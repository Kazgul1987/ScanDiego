from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout)
from app.services.platform_detection_service import PlatformDetectionService

class SearchWorker(QObject):
    finished=Signal(list); failed=Signal(str)
    def __init__(self, service, game_id, text): super().__init__(); self.service=service; self.game_id=game_id; self.text=text
    @Slot()
    def run(self):
        try: self.finished.emit([dict(x) for x in self.service.search(self.game_id,self.text)])
        except Exception as exc: self.failed.emit(str(exc))

class MatchReviewDialog(QDialog):
    """Candidate picker shared by ambiguous reviews and explicit rematching."""
    def __init__(self, game, service, parent=None):
        super().__init__(parent); self.game=dict(game); self.service=service; self.thread=None; self.worker=None
        self.setWindowTitle("Match prüfen / ändern"); layout=QVBoxLayout(self)
        layout.addWidget(QLabel(f"{self.game['title']} — {self.game['platform']} — {self.game.get('release_year') or 'Jahr unbekannt'}"))
        self.search=QLineEdit(self.game["title"]); again=QPushButton("Erneut suchen"); again.clicked.connect(self._search)
        line=QHBoxLayout(); line.addWidget(self.search); line.addWidget(again); layout.addLayout(line)
        self.list=QListWidget(); self.list.currentItemChanged.connect(self._candidate_changed); layout.addWidget(self.list)
        layout.addWidget(QLabel(f"Lokal erkannte Plattform: {self.game['platform']}"))
        self.platform_label=QLabel("Verfügbare Plattformen:"); layout.addWidget(self.platform_label)
        self.platform=QComboBox(); self.platform.addItem("Bitte eine Plattform auswählen", None); layout.addWidget(self.platform)
        self.change_platform=QCheckBox("Lokale Plattform ebenfalls ändern")
        self.change_platform.setVisible(self.game["platform"] != "Unknown"); layout.addWidget(self.change_platform)
        choose=QPushButton("Ausgewählten Match verwenden"); none=QPushButton("Kein passender Treffer")
        choose.clicked.connect(self._apply); none.clicked.connect(self._none); layout.addWidget(choose); layout.addWidget(none)
        self._show([dict(x) for x in service.candidates(self.game["id"])])
    def _show(self, rows):
        self.list.clear()
        for row in rows:
            platforms=self.service.db.candidate_platforms(row)
            names=", ".join(p.external_platform_name for p in platforms) or row['platform'] or "?"
            self.list.addItem(f"{row['title']}\nRelease: {row['release_year'] or '?'}\nPlattformen: {names}\n{row['provider']} — {row['score']:.0f} %")
            self.list.item(self.list.count()-1).setData(256, row)
        if self.list.count(): self.list.setCurrentRow(0)
    def _candidate_changed(self, item, _previous=None):
        self.platform.clear(); self.platform.addItem("Bitte eine Plattform auswählen", None)
        if not item: return
        choices=self.service.db.candidate_platforms(item.data(256))
        for choice in choices:
            self.platform.addItem(choice.external_platform_name, choice)
        local=PlatformDetectionService.family(self.game["platform"])
        matching=next((i for i in range(1,self.platform.count()) if self.platform.itemData(i).normalized_platform==local),-1)
        if matching > 0: self.platform.setCurrentIndex(matching)
        elif len(choices)==1: self.platform.setCurrentIndex(1)
        else: self.platform.setCurrentIndex(0)
    def _search(self):
        if self.thread and self.thread.isRunning(): return
        self.thread=QThread(self); self.worker=SearchWorker(self.service,self.game["id"],self.search.text().strip()); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.finished.connect(self._show); self.worker.failed.connect(lambda m: QMessageBox.warning(self,"Suche",m))
        self.worker.finished.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.thread.start()
    def _apply(self):
        item=self.list.currentItem()
        if not item: return
        selected=self.platform.currentData()
        if not selected:
            QMessageBox.information(self,"Plattform","Bitte eine Plattform auswählen."); return
        local=PlatformDetectionService.family(self.game["platform"])
        if local != "Unknown" and selected.normalized_platform != local and not self.change_platform.isChecked():
            QMessageBox.information(self,"Plattform","Für eine abweichende Plattform bitte „Lokale Plattform ebenfalls ändern“ aktivieren."); return
        row=item.data(256); self.service.apply(self.game["id"],row["external_game_id"],row["score"],
            selected.external_platform_id,self.change_platform.isChecked()); self.accept()
    def _none(self): self.service.no_match(self.game["id"]); self.accept()
