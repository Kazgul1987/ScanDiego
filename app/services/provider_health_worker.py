from PySide6.QtCore import QObject, Signal, Slot
from app.providers.factory import create_artwork_provider, create_metadata_provider

class ProviderHealthWorker(QObject):
    finished=Signal(list)
    @Slot()
    def run(self):
        results=[]
        for label, factory in (("Metadaten",create_metadata_provider),("Artwork",create_artwork_provider)):
            try: result=factory(self.settings).health_check(); results.append((label,result.success,result.message))
            except Exception as exc: results.append((label,False,str(exc)))
        self.finished.emit(results)
    def __init__(self,settings): super().__init__(); self.settings=settings
