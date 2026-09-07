from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTableView, QVBoxLayout

from app.services.duplicate_detection_service import DuplicateGroup
from app.utils.formatting import human_size


class CleanupDetailsDialog(QDialog):
    """One read-only detail table shared by all cleanup categories."""

    def __init__(self, category: str, findings: Sequence[Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Aufräumen – {category}")
        self.resize(1100, 600)
        layout = QVBoxLayout(self)
        description = ("Folgende Ordner enthalten unterstützte Archive, aber keine erkannte "
                       "Spiele-/ROM-Datei." if category == "Archive noch nicht entpackt"
                       else f"Gefundene Einträge für „{category}“. Es werden keine Dateien verändert.")
        layout.addWidget(QLabel(description))
        table = QTableView(self)
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
            preferred = [name for name in ("title", "platform", "file_name", "full_path", "folder_path",
                         "extension", "file_size", "drive_id", "metadata_status", "last_seen")
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
