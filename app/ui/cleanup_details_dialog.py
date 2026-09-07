from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableView, QVBoxLayout)

from app.models.content import MediaContentType
from app.services.duplicate_detection_service import DuplicateGroup
from app.utils.formatting import human_size


ASSIGNABLE_CATEGORIES = {
    "DLC ohne Hauptspiel", "Update ohne Hauptspiel", "Unsichere Content-Zuordnung",
}


class ManualParentDialog(QDialog):
    def __init__(self, db, finding: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.db, self.finding = db, finding
        self.setWindowTitle("Hauptspiel zuordnen")
        layout = QFormLayout(self)
        layout.addRow("Datei:", QLabel(str(finding.get("file_name", ""))))
        layout.addRow("Content-Typ:", QLabel(str(finding.get("content_type", ""))))
        layout.addRow("Erkannter Basistitel:", QLabel(str(finding.get("possible_base_title", ""))))
        layout.addRow("Plattform:", QLabel(str(finding.get("platform", ""))))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Spiele suchen …")
        self.games = QComboBox(self)
        layout.addRow("Suche:", self.search)
        layout.addRow("Hauptspiel:", self.games)
        self.search.textChanged.connect(self._reload)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        assign = buttons.addButton("Zuordnen", QDialogButtonBox.ButtonRole.AcceptRole)
        assign.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._reload()

    def _reload(self) -> None:
        self.games.clear()
        for game in self.db.manual_parent_candidates(self.finding["media_file_id"], self.search.text()):
            self.games.addItem(f'{game["title"]} · {game["platform"]} · Base', game["id"])

    @property
    def parent_game_id(self) -> int | None:
        return self.games.currentData()


class CleanupDetailsDialog(QDialog):
    """Detail table with focused manual actions for supplemental content."""

    def __init__(self, category: str, findings: Sequence[Any], parent=None, db=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Aufräumen – {category}")
        self.resize(1100, 600)
        layout = QVBoxLayout(self)
        description = ("Folgende Ordner enthalten unterstützte Archive, aber keine erkannte "
                       "Spiele-/ROM-Datei." if category == "Archive noch nicht entpackt"
                       else f"Gefundene Einträge für „{category}“. Es werden keine Dateien verändert.")
        layout.addWidget(QLabel(description))
        table = QTableView(self)
        self.table, self.db, self.rows = table, db, []
        model = QStandardItemModel(table)
        if findings and isinstance(findings[0], DuplicateGroup):
            model.setHorizontalHeaderLabels(
                ["Gruppe", "Status", "Spiel", "Plattform", "Dateiname", "Pfad",
                 "Dateigröße", "Laufwerk", "Hashstatus"])
            for group_number, group in enumerate(findings, 1):
                for entry in group.entries:
                    model.appendRow([QStandardItem(str(group_number)), QStandardItem(group.status.value),
                        QStandardItem(str(entry.get("title", ""))), QStandardItem(str(entry.get("platform", ""))),
                        QStandardItem(str(entry.get("file_name", ""))), QStandardItem(str(entry.get("full_path", ""))),
                        QStandardItem(human_size(int(entry.get("file_size", 0)))),
                        QStandardItem(str(entry.get("drive_label") or entry.get("drive_id", ""))),
                        QStandardItem(f"{entry.get('hash_type')}: {entry.get('file_hash')}" if entry.get("file_hash") else "nicht berechnet")])
        else:
            rows = [dict(item) for item in findings]
            self.rows = rows
            preferred = [name for name in ("title", "platform", "file_name", "full_path", "folder_path",
                         "content_type", "possible_base_title", "current_game", "suggested_parent_game",
                         "content_detection_confidence", "content_detection_method", "extension", "file_size",
                         "drive_id", "metadata_status", "last_seen")
                         if rows and name in rows[0]]
            model.setHorizontalHeaderLabels(preferred or ["Ergebnis"])
            for row in rows:
                model.appendRow([QStandardItem(human_size(row[name]) if name == "file_size"
                                                else str(row[name] if row[name] is not None else ""))
                                 for name in preferred])
        table.setModel(model)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        if db is not None and category in ASSIGNABLE_CATEGORIES:
            assign = QPushButton("Hauptspiel zuordnen", self)
            remove = QPushButton("Zuordnung entfernen", self)
            assign.clicked.connect(self._assign_parent)
            remove.clicked.connect(self._remove_parent)
            layout.addWidget(assign)
            layout.addWidget(remove)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _selected(self) -> dict[str, Any] | None:
        index = self.table.currentIndex()
        return self.rows[index.row()] if index.isValid() and index.row() < len(self.rows) else None

    def _assign_parent(self) -> None:
        finding = self._selected()
        if not finding:
            QMessageBox.information(self, "Hauptspiel zuordnen", "Bitte zuerst eine Datei auswählen.")
            return
        dialog = ManualParentDialog(self.db, finding, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.parent_game_id is not None:
            self.db.set_manual_content(finding["media_file_id"],
                MediaContentType(finding["content_type"]), dialog.parent_game_id,
                finding.get("possible_base_title"))
            self.accept()

    def _remove_parent(self) -> None:
        finding = self._selected()
        if not finding:
            QMessageBox.information(self, "Zuordnung entfernen", "Bitte zuerst eine Datei auswählen.")
            return
        self.db.remove_manual_content_parent(finding["media_file_id"])
        self.accept()
