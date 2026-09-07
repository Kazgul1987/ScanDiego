from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMessageBox, QPushButton, QVBoxLayout)

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
        self.list=QListWidget(); layout.addWidget(self.list)
        choose=QPushButton("Ausgewählten Match verwenden"); none=QPushButton("Kein passender Treffer")
        choose.clicked.connect(self._apply); none.clicked.connect(self._none); layout.addWidget(choose); layout.addWidget(none)
        self._show([dict(x) for x in service.candidates(self.game["id"])])
    def _show(self, rows):
        self.list.clear()
        for row in rows:
            self.list.addItem(f"{row['title']} — {row['platform'] or '?'} — {row['release_year'] or '?'} — {row['provider']} — {row['score']:.0f} %")
            self.list.item(self.list.count()-1).setData(256, row)
    def _search(self):
        if self.thread and self.thread.isRunning(): return
        self.thread=QThread(self); self.worker=SearchWorker(self.service,self.game["id"],self.search.text().strip()); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.finished.connect(self._show); self.worker.failed.connect(lambda m: QMessageBox.warning(self,"Suche",m))
        self.worker.finished.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.thread.start()
    def _apply(self):
        item=self.list.currentItem()
        if not item: return
        row=item.data(256); self.service.apply(self.game["id"],row["external_game_id"],row["score"]); self.accept()
    def _none(self): self.service.no_match(self.game["id"]); self.accept()
