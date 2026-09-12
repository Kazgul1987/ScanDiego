from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableView, QVBoxLayout)

from app.models.content import MediaContentType
from app.services.duplicate_detection_service import DuplicateGroup
from app.utils.formatting import human_size


ASSIGNABLE_CATEGORIES = {
    "DLC ohne Hauptspiel", "Update ohne Hauptspiel", "Unsichere Content-Zuordnung",
}
INVALID_MEDIA_CATEGORY = "Wahrscheinlich falsch erkannte Medien"


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
            invalid = category == INVALID_MEDIA_CATEGORY
            preferred = [name for name in (("selected", "title", "platform", "file_name", "reason",
                         "confidence", "safety_level", "full_path") if invalid else
                         ("title", "platform", "file_name", "full_path", "folder_path", "reason",
                         "content_type", "possible_base_title", "current_game", "suggested_parent_game",
                         "content_detection_confidence", "content_detection_method", "extension", "file_size",
                         "drive_id", "metadata_status", "last_seen"))
                         if name == "selected" or (rows and name in rows[0])]
            labels = {"selected": "Auswahl", "title": "Spiel", "platform": "Plattform",
                      "file_name": "Datei", "reason": "Grund", "confidence": "Confidence",
                      "safety_level": "Bewertung", "full_path": "Pfad"}
            model.setHorizontalHeaderLabels([labels.get(name, name) for name in preferred] or ["Ergebnis"])
            for row in rows:
                items = []
                for name in preferred:
                    if name == "selected":
                        item = QStandardItem()
                        item.setCheckable(True)
                        item.setCheckState(Qt.CheckState.Unchecked)
                    else:
                        value = row[name]
                        if name == "file_size": value = human_size(value)
                        if name == "confidence": value = f"{float(value):.0%}"
                        if name == "safety_level":
                            value = {"safe": "Sicher", "likely": "Sehr wahrscheinlich",
                                     "review": "Prüfen"}.get(value, value)
                        item = QStandardItem(str(value if value is not None else ""))
                    items.append(item)
                model.appendRow(items)
        table.setModel(model)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        if db is not None and category in ASSIGNABLE_CATEGORIES:
            assign = QPushButton("Hauptspiel zuordnen", self)
            remove = QPushButton("Zuordnung entfernen", self)
            assign.clicked.connect(self._assign_parent)
            remove.clicked.connect(self._remove_parent)
            layout.addWidget(assign)
            layout.addWidget(remove)
        if db is not None and category == INVALID_MEDIA_CATEGORY:
            controls = QHBoxLayout()
            for label, level in (("Alle auswählen", None), ("Alle sicheren auswählen", "safe")):
                button = QPushButton(label, self)
                button.clicked.connect(lambda _checked=False, value=level: self._check_rows(value))
                controls.addWidget(button)
            clear = QPushButton("Auswahl aufheben", self)
            clear.clicked.connect(lambda: self._check_rows("none"))
            controls.addWidget(clear)
            layout.addLayout(controls)
            remove = QPushButton("Ausgewählte aus ScanDiego entfernen", self)
            recheck = QPushButton("Neu prüfen", self)
            self.remove_invalid_button = remove
            remove.clicked.connect(self._remove_invalid_media)
            recheck.clicked.connect(self.accept)
            layout.addWidget(remove)
            layout.addWidget(recheck)
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

    def _remove_invalid_media(self) -> None:
        ids = [row["media_file_id"] for index, row in enumerate(self.rows)
               if self.table.model().item(index, 0).checkState() == Qt.CheckState.Checked]
        if not ids:
            QMessageBox.information(self, "Aus ScanDiego entfernen", "Keine Einträge ausgewählt.")
            return
        selected = [row for row in self.rows if row["media_file_id"] in set(ids)]
        groups = Counter(row["reason"] for row in selected)
        details = "\n".join(f"{count:>6}  {reason}" for reason, count in groups.most_common())
        message = (f"{len(ids):,} Einträge werden aus ScanDiego entfernt.\n\nDavon:\n{details}\n\n"
                   "Es werden nur Einträge aus der ScanDiego-Datenbank entfernt.\n"
                   "Die Originaldateien auf den Laufwerken bleiben unverändert.")
        if QMessageBox.question(self, "Entfernung bestätigen", message,
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        self.db.remove_misclassified_media(ids)
        self.accept()

    def _check_rows(self, level: str | None) -> None:
        """Checkbox selection is explicit; review rows are never selected by safe actions."""
        model = self.table.model()
        for index, row in enumerate(self.rows):
            checked = level is None or row.get("safety_level") == level
            if level == "none":
                checked = False
            model.item(index, 0).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
