from __future__ import annotations
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLineEdit, QVBoxLayout
from app.settings import MetadataSettings


class MetadataSettingsDialog(QDialog):
    def __init__(self, settings: MetadataSettings, parent=None):
        super().__init__(parent); self.settings = settings; self.setWindowTitle("Metadaten & Cover")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.metadata_provider = QComboBox(); self.metadata_provider.addItem("IGDB", "igdb")
        self.artwork_provider = QComboBox(); self.artwork_provider.addItem("SteamGridDB", "steamgriddb")
        self.client_id = QLineEdit(settings.igdb_client_id); self.secret = QLineEdit(settings.igdb_client_secret)
        self.api_key = QLineEdit(settings.steamgriddb_api_key)
        self.secret.setEchoMode(QLineEdit.EchoMode.Password); self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.auto = QCheckBox(); self.auto.setChecked(settings.automatic_search)
        self.covers = QCheckBox(); self.covers.setChecked(settings.automatic_covers)
        self.auto_score = QDoubleSpinBox(); self.auto_score.setRange(75, 100); self.auto_score.setValue(settings.automatic_threshold)
        self.ambiguous_score = QDoubleSpinBox(); self.ambiguous_score.setRange(0, 99); self.ambiguous_score.setValue(settings.ambiguous_threshold)
        for label, widget in (("Metadata-Provider",self.metadata_provider),("IGDB Client-ID",self.client_id),("IGDB Client-Secret",self.secret),("Artwork-Provider",self.artwork_provider),("SteamGridDB API-Key",self.api_key),("Automatisch nach Scan",self.auto),("Cover automatisch laden",self.covers),("Automatisch ab Score",self.auto_score),("Unklar ab Score",self.ambiguous_score)): form.addRow(label, widget)
        layout.addLayout(form); buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def accept(self):
        self.settings.igdb_client_id=self.client_id.text(); self.settings.igdb_client_secret=self.secret.text(); self.settings.steamgriddb_api_key=self.api_key.text(); self.settings.automatic_search=self.auto.isChecked(); self.settings.automatic_covers=self.covers.isChecked(); self.settings.automatic_threshold=self.auto_score.value(); self.settings.ambiguous_threshold=self.ambiguous_score.value(); self.settings.save(); super().accept()
