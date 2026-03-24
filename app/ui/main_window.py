from __future__ import annotations

import csv
import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.database.db_manager import DatabaseManager, DatabaseError
from app.models.drive import DriveInfo
from app.services.drive_service import DriveService
from app.services.scanner_worker import ScannerWorker
from app.utils.formatting import human_size
from app.utils.paths import get_database_path

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ScanDiego")
        self.resize(1400, 850)

        self.db = DatabaseManager(get_database_path())
        self.drive_service = DriveService()
        self.connected_drives: list[DriveInfo] = []
        self.current_rows: list[dict] = []

        self.scan_thread: QThread | None = None
        self.scan_worker: ScannerWorker | None = None

        self._build_ui()
        self.refresh_drives()
        self.reload_db()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.scan_worker:
            self.scan_worker.cancel()
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.quit()
            self.scan_thread.wait(2_000)
        self.db.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        drives_box = QGroupBox("Angeschlossene Laufwerke")
        drives_layout = QVBoxLayout(drives_box)

        controls_layout = QHBoxLayout()
        self.btn_refresh_drives = QPushButton("Laufwerke aktualisieren")
        self.btn_scan_selected = QPushButton("Ausgewähltes Laufwerk scannen")
        self.btn_scan_all = QPushButton("Alle externen Laufwerke scannen")
        self.btn_cancel_scan = QPushButton("Scan abbrechen")
        self.btn_cancel_scan.setEnabled(False)

        controls_layout.addWidget(self.btn_refresh_drives)
        controls_layout.addWidget(self.btn_scan_selected)
        controls_layout.addWidget(self.btn_scan_all)
        controls_layout.addWidget(self.btn_cancel_scan)

        self.chk_archive_only_dirs = QCheckBox(
            "Nur Ordner mit .rar/.zip ohne ISO/ROM melden"
        )

        self.drive_table = QTableView()
        self.drive_model = QStandardItemModel(0, 4)
        self.drive_model.setHorizontalHeaderLabels(
            ["Laufwerk", "Label", "Volume Serial", "Dateisystem"]
        )
        self.drive_table.setModel(self.drive_model)
        self.drive_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.drive_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.drive_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.drive_table.horizontalHeader().setStretchLastSection(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        drives_layout.addLayout(controls_layout)
        drives_layout.addWidget(self.chk_archive_only_dirs)
        drives_layout.addWidget(self.drive_table)
        drives_layout.addWidget(self.progress)
        top_layout.addWidget(drives_box)

        # Bottom section
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suche nach Titel, Dateiname oder Pfad")
        self.drive_filter = QComboBox()
        self.drive_filter.addItem("Alle Festplatten", "")
        self.btn_reload_db = QPushButton("Datenbank neu laden")
        self.btn_export = QPushButton("Export als CSV")
        self.btn_open_folder = QPushButton("Ordner öffnen")

        filter_layout.addWidget(QLabel("Suche:"))
        filter_layout.addWidget(self.search_input, 1)
        filter_layout.addWidget(QLabel("Filter Festplatte:"))
        filter_layout.addWidget(self.drive_filter)
        filter_layout.addWidget(self.btn_reload_db)
        filter_layout.addWidget(self.btn_export)
        filter_layout.addWidget(self.btn_open_folder)

        self.games_table = QTableView()
        self.games_model = QStandardItemModel(0, 8)
        self.games_model.setHorizontalHeaderLabels(
            [
                "Typ",
                "Titel",
                "Dateiname",
                "Festplatte",
                "Laufwerk",
                "Dateipfad",
                "Dateigröße",
                "Letzter Scan",
            ]
        )
        self.games_table.setModel(self.games_model)
        self.games_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.games_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.games_table.horizontalHeader().setStretchLastSection(True)
        self.games_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        details_box = QGroupBox("Details")
        details_layout = QFormLayout(details_box)
        self.detail_title = QLabel("-")
        self.detail_full_path = QTextEdit()
        self.detail_full_path.setReadOnly(True)
        self.detail_full_path.setMaximumHeight(55)
        self.detail_drive = QLabel("-")
        self.detail_last_seen = QLabel("-")
        self.detail_modified = QLabel("-")
        self.detail_missing = QLabel("-")
        details_layout.addRow("Titel:", self.detail_title)
        details_layout.addRow("Vollständiger Pfad:", self.detail_full_path)
        details_layout.addRow("Festplatte:", self.detail_drive)
        details_layout.addRow("Letzte Sichtung:", self.detail_last_seen)
        details_layout.addRow("Datei geändert:", self.detail_modified)
        details_layout.addRow("Status:", self.detail_missing)

        bottom_layout.addLayout(filter_layout)
        bottom_layout.addWidget(self.games_table, 1)
        bottom_layout.addWidget(details_box)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([320, 530])

        layout.addWidget(splitter)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

        self._wire_events()

    def _wire_events(self) -> None:
        self.btn_refresh_drives.clicked.connect(self.refresh_drives)
        self.btn_scan_selected.clicked.connect(self.scan_selected_drive)
        self.btn_scan_all.clicked.connect(self.scan_all_drives)
        self.btn_cancel_scan.clicked.connect(self.cancel_scan)
        self.btn_reload_db.clicked.connect(self.reload_db)
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_open_folder.clicked.connect(self.open_selected_folder)

        self.search_input.textChanged.connect(self.reload_db)
        self.drive_filter.currentIndexChanged.connect(self.reload_db)

        self.games_table.selectionModel().selectionChanged.connect(self.update_details)
        self.games_table.doubleClicked.connect(self.open_selected_folder)
        self.games_table.customContextMenuRequested.connect(self._show_context_menu)

    def refresh_drives(self) -> None:
        self.connected_drives = self.drive_service.list_external_drives()
        self.drive_model.setRowCount(0)

        for drive in self.connected_drives:
            row = [
                QStandardItem(drive.letter),
                QStandardItem(drive.label),
                QStandardItem(drive.volume_serial),
                QStandardItem(drive.filesystem),
            ]
            self.drive_model.appendRow(row)

        self.statusBar().showMessage(f"{len(self.connected_drives)} Laufwerke gefunden.")

    def _selected_drive(self) -> DriveInfo | None:
        idx = self.drive_table.currentIndex()
        if not idx.isValid():
            return None
        row = idx.row()
        if row < 0 or row >= len(self.connected_drives):
            return None
        return self.connected_drives[row]

    def scan_selected_drive(self) -> None:
        drive = self._selected_drive()
        if drive is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Laufwerk auswählen.")
            return
        self._start_scan([drive])

    def scan_all_drives(self) -> None:
        if not self.connected_drives:
            QMessageBox.information(self, "Hinweis", "Keine externen Laufwerke gefunden.")
            return
        self._start_scan(self.connected_drives)

    def _start_scan(self, drives: list[DriveInfo]) -> None:
        if self.scan_thread and self.scan_thread.isRunning():
            QMessageBox.warning(self, "Scan aktiv", "Es läuft bereits ein Scan.")
            return

        self.progress.setVisible(True)
        self.btn_cancel_scan.setEnabled(True)
        self.statusBar().showMessage("Scan gestartet...")

        self.scan_thread = QThread(self)
        self.scan_worker = ScannerWorker(
            self.db.db_path,
            drives,
            report_archive_only_dirs=self.chk_archive_only_dirs.isChecked(),
        )
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)

        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.finished.connect(self.scan_thread.quit)

        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.start()

    def cancel_scan(self) -> None:
        if self.scan_worker:
            self.scan_worker.cancel()
        self.statusBar().showMessage("Scan-Abbruch angefordert...")

    def on_scan_progress(self, message: str, processed: int, found: int) -> None:
        self.statusBar().showMessage(f"{message} | Geprüft: {processed} | Treffer: {found}")

    def on_scan_error(self, message: str) -> None:
        QMessageBox.critical(self, "Scan-Fehler", f"Der Scan wurde abgebrochen:\n{message}")
        self.progress.setVisible(False)
        self.btn_cancel_scan.setEnabled(False)

    def on_scan_finished(self, stats: dict) -> None:
        self.progress.setVisible(False)
        self.btn_cancel_scan.setEnabled(False)
        self.scan_worker = None
        self.scan_thread = None
        self.reload_db()
        self.refresh_drives()
        msg = (
            f"Scan beendet. Geprüft: {stats['processed']}, Treffer: {stats['found']}, "
            f"Fehler: {stats['errors']}"
        )
        if stats.get("cancelled"):
            msg = "Scan abgebrochen. " + msg
        self.statusBar().showMessage(msg)

        archive_only_dirs = stats.get("archive_only_dirs", [])
        if archive_only_dirs:
            self._show_archive_only_dirs_dialog(archive_only_dirs)

    def reload_db(self) -> None:
        try:
            search = self.search_input.text().strip()
            drive_filter = self.drive_filter.currentData() if self.drive_filter.count() else ""
            rows = self.db.list_entries(search=search, drive_filter=drive_filter or "")
        except DatabaseError as exc:
            QMessageBox.critical(self, "DB-Fehler", str(exc))
            return

        self.current_rows = [dict(row) for row in rows]

        self.games_model.setRowCount(0)
        for row in self.current_rows:
            status_suffix = " (fehlt)" if row["is_missing"] else ""
            ui_row = [
                QStandardItem(row["category"].upper()),
                QStandardItem(row["title"] + status_suffix),
                QStandardItem(row["file_name"]),
                QStandardItem(row["drive_label"]),
                QStandardItem(row["drive_letter"]),
                QStandardItem(row["full_path"]),
                QStandardItem(human_size(row["file_size"])),
                QStandardItem(row["scan_date"]),
            ]
            self.games_model.appendRow(ui_row)

        self._reload_drive_filter()
        self.statusBar().showMessage(f"{len(self.current_rows)} Einträge geladen.")

    def _reload_drive_filter(self) -> None:
        previous = self.drive_filter.currentData()
        self.drive_filter.blockSignals(True)
        self.drive_filter.clear()
        self.drive_filter.addItem("Alle Festplatten", "")

        for row in self.db.list_distinct_drives():
            label = row["drive_label"] or row["drive_id"]
            self.drive_filter.addItem(f"{label} ({row['drive_id']})", row["drive_id"])

        idx = self.drive_filter.findData(previous)
        if idx >= 0:
            self.drive_filter.setCurrentIndex(idx)
        self.drive_filter.blockSignals(False)

    def update_details(self) -> None:
        idx = self.games_table.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        if row < 0 or row >= len(self.current_rows):
            return

        data = self.current_rows[row]
        self.detail_title.setText(data["title"])
        self.detail_full_path.setPlainText(data["full_path"])
        self.detail_drive.setText(
            f"{data['drive_label']} ({data['drive_letter']}, {data['drive_id']})"
        )
        self.detail_last_seen.setText(data["last_seen_date"])
        self.detail_modified.setText(data["modified_time"])
        self.detail_missing.setText("Nicht gefunden" if data["is_missing"] else "Vorhanden")

    def _selected_row_data(self) -> dict | None:
        idx = self.games_table.currentIndex()
        if not idx.isValid():
            return None
        row = idx.row()
        if row < 0 or row >= len(self.current_rows):
            return None
        return self.current_rows[row]

    def open_selected_folder(self) -> None:
        row = self._selected_row_data()
        if row is None:
            return
        path = Path(row["full_path"])
        folder = path.parent
        if not folder.exists():
            QMessageBox.warning(self, "Pfad fehlt", "Der Ordner existiert nicht mehr.")
            return
        subprocess.Popen(["explorer", str(folder)])

    def copy_selected_path(self) -> None:
        row = self._selected_row_data()
        if row is None:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(row["full_path"])
        self.statusBar().showMessage("Pfad in Zwischenablage kopiert.")

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        act_open = QAction("Ordner öffnen", self)
        act_copy = QAction("Pfad kopieren", self)
        act_open.triggered.connect(self.open_selected_folder)
        act_copy.triggered.connect(self.copy_selected_path)
        menu.addAction(act_open)
        menu.addAction(act_copy)
        menu.exec(self.games_table.viewport().mapToGlobal(pos))

    def export_csv(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            "CSV exportieren",
            os.path.expanduser("~/scandiego_export.csv"),
            "CSV-Datei (*.csv)",
        )
        if not target:
            return

        try:
            with open(target, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(
                    [
                        "category",
                        "title",
                        "file_name",
                        "full_path",
                        "drive_label",
                        "drive_letter",
                        "drive_id",
                        "file_size",
                        "modified_time",
                        "scan_date",
                        "last_seen_date",
                        "is_missing",
                    ]
                )
                for row in self.current_rows:
                    writer.writerow(
                        [
                            row["category"],
                            row["title"],
                            row["file_name"],
                            row["full_path"],
                            row["drive_label"],
                            row["drive_letter"],
                            row["drive_id"],
                            row["file_size"],
                            row["modified_time"],
                            row["scan_date"],
                            row["last_seen_date"],
                            row["is_missing"],
                        ]
                    )
            QMessageBox.information(self, "Export", "CSV wurde erfolgreich exportiert.")
        except OSError as exc:
            LOGGER.exception("CSV export failed")
            QMessageBox.critical(self, "Export-Fehler", str(exc))

    def _show_archive_only_dirs_dialog(self, archive_only_dirs: list[str]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Ordnerhinweise: Nur Archive ohne ROM/Image")
        dialog.resize(900, 500)

        layout = QVBoxLayout(dialog)
        description = QLabel(
            "Folgende Ordner enthalten .rar/.zip, aber keine .iso/.nsp/.xci/.bin/.cue/.img:"
        )
        layout.addWidget(description)

        table = QTableView(dialog)
        model = QStandardItemModel(0, 1, table)
        model.setHorizontalHeaderLabels(["Ordnerpfad"])
        for folder_path in archive_only_dirs:
            model.appendRow([QStandardItem(folder_path)])
        table.setModel(model)
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()
