from __future__ import annotations
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLineEdit, QVBoxLayout, QPushButton, QMessageBox
from app.settings import MetadataSettings
from app.services.provider_health_worker import ProviderHealthWorker


class MetadataSettingsDialog(QDialog):
    def __init__(self, settings: MetadataSettings, parent=None):
        super().__init__(parent); self.settings = settings; self.setWindowTitle("Metadaten & Cover")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.metadata_provider = QComboBox(); self.metadata_provider.addItem("IGDB", "igdb")
        self.artwork_provider = QComboBox(); self.artwork_provider.addItem("SteamGridDB", "steamgriddb")
        self.metadata_provider.setCurrentIndex(max(0,self.metadata_provider.findData(settings.metadata_provider)))
        self.artwork_provider.setCurrentIndex(max(0,self.artwork_provider.findData(settings.artwork_provider)))
        self.client_id = QLineEdit(settings.igdb_client_id); self.secret = QLineEdit(settings.igdb_client_secret)
        self.api_key = QLineEdit(settings.steamgriddb_api_key)
        self.secret.setEchoMode(QLineEdit.EchoMode.Password); self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.auto = QCheckBox(); self.auto.setChecked(settings.automatic_search)
        self.covers = QCheckBox(); self.covers.setChecked(settings.automatic_covers)
        self.auto_score = QDoubleSpinBox(); self.auto_score.setRange(75, 100); self.auto_score.setValue(settings.automatic_threshold)
        self.ambiguous_score = QDoubleSpinBox(); self.ambiguous_score.setRange(0, 99); self.ambiguous_score.setValue(settings.ambiguous_threshold)
        for label, widget in (("Metadata-Provider",self.metadata_provider),("IGDB Client-ID",self.client_id),("IGDB Client-Secret",self.secret),("Artwork-Provider",self.artwork_provider),("SteamGridDB API-Key",self.api_key),("Automatisch nach Scan",self.auto),("Cover automatisch laden",self.covers),("Automatisch ab Score",self.auto_score),("Unklar ab Score",self.ambiguous_score)): form.addRow(label, widget)
        layout.addLayout(form); self.test_button=QPushButton("Verbindung testen"); self.test_button.clicked.connect(self.test_connection); layout.addWidget(self.test_button); buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.health_thread=None; self.health_worker=None
    def test_connection(self):
        self._copy_values(); self.test_button.setEnabled(False)
        self.health_thread=QThread(self); self.health_worker=ProviderHealthWorker(self.settings); self.health_worker.moveToThread(self.health_thread)
        self.health_thread.started.connect(self.health_worker.run); self.health_worker.finished.connect(self._health_finished); self.health_worker.finished.connect(self.health_thread.quit); self.health_thread.start()
    def _health_finished(self, results):
        self.test_button.setEnabled(True); QMessageBox.information(self,"Verbindungstest","\n".join(("✓" if ok else "✗")+f" {label}: {message}" for label,ok,message in results))
    def _copy_values(self):
        self.settings.metadata_provider=self.metadata_provider.currentData(); self.settings.artwork_provider=self.artwork_provider.currentData(); self.settings.igdb_client_id=self.client_id.text(); self.settings.igdb_client_secret=self.secret.text(); self.settings.steamgriddb_api_key=self.api_key.text(); self.settings.automatic_search=self.auto.isChecked(); self.settings.automatic_covers=self.covers.isChecked(); self.settings.automatic_threshold=self.auto_score.value(); self.settings.ambiguous_threshold=self.ambiguous_score.value()
    def accept(self):
        self._copy_values(); self.settings.save(); super().accept()
