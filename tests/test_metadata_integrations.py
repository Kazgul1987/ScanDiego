import json, sqlite3
from app.models.metadata import ExternalGame, MetadataStatus
from app.providers.fake import FakeArtworkProvider, FakeMetadataProvider
from app.providers.factory import create_artwork_provider, create_metadata_provider, UnknownProviderError
from app.providers.igdb import IGDBProvider
from app.providers.steamgriddb import SteamGridDBProvider
from app.services.artwork_service import ArtworkService
from app.services.cover_queue_service import CoverQueueService
from app.services.credential_store import CredentialStore
from app.services.game_matching_service import GameMatchingService
from app.services.match_review_service import MatchReviewService
from app.services.metadata_queue_service import MetadataQueueService
from app.settings import MetadataSettings
from tests.test_metadata import prepared
import pytest

class Keys:
    def __init__(self): self.data={}
    def set_password(self, service, name, value): self.data[(service,name)]=value
    def get_password(self, service, name): return self.data.get((service,name))

def test_manual_lock_survives_normal_queue_and_direct_refresh(tmp_path):
    db=prepared(tmp_path); row=db._conn.execute("SELECT * FROM games").fetchone(); provider=FakeMetadataProvider([ExternalGame("m","Provider title","Game Boy Advance",publisher="P",release_year=2000)])
    db.apply_candidate_manually(row["id"],ExternalGame("m","User title","Game Boy Advance"),"fake",100)
    assert db.enqueue_metadata()==0
    assert db.enqueue_metadata([row["id"]],True)==1
    MetadataQueueService(db,provider,GameMatchingService(),interval=0).process()
    updated=db._conn.execute("SELECT * FROM games").fetchone()
    assert provider.get_calls==1 and provider.search_calls==0 and updated["metadata_locked"]==1 and updated["external_game_id"]=="m"

def test_manual_bulk_cover_changes_only_artwork(tmp_path):
    db=prepared(tmp_path); row=db._conn.execute("SELECT * FROM games").fetchone()
    db.apply_candidate_manually(row["id"],ExternalGame("m","Chosen","Game Boy Advance"),"fake",99)
    before=dict(db._conn.execute("SELECT * FROM games").fetchone()); assert db.enqueue_covers()==1
    CoverQueueService(db,ArtworkService(FakeArtworkProvider(),tmp_path/"covers"),0).process()
    after=dict(db._conn.execute("SELECT * FROM games").fetchone())
    assert after["cover_path"] and after["canonical_title"]==before["canonical_title"] and after["external_game_id"]=="m" and after["metadata_locked"]==1

def test_review_search_apply_no_match_and_replace(tmp_path):
    db=prepared(tmp_path); game_id=db._conn.execute("SELECT id FROM games").fetchone()[0]
    provider=FakeMetadataProvider([ExternalGame("2","Better title","Game Boy Advance",publisher="P")]); service=MatchReviewService(db,provider,GameMatchingService(50,20))
    assert service.search(game_id,"Better title")[0]["external_game_id"]=="2"
    service.apply(game_id,"2",98); row=db._conn.execute("SELECT * FROM games").fetchone()
    assert row["metadata_match_method"]=="manual" and row["metadata_locked"]==1
    service.no_match(game_id); assert db._conn.execute("SELECT metadata_status FROM games").fetchone()[0]=="no_match" and not service.candidates(game_id)

def test_credentials_keyring_environment_and_plaintext_migration(tmp_path,monkeypatch):
    keys=Keys(); store=CredentialStore(keys); store.set("igdb_client_secret","saved"); assert store.get("igdb_client_secret")=="saved"
    monkeypatch.setenv("SCANDIEGO_IGDB_CLIENT_SECRET","environment"); assert store.get("igdb_client_secret")=="environment"
    path=tmp_path/"settings.json"; path.write_text(json.dumps({"igdb_client_secret":"old","steamgriddb_api_key":"grid"}))
    monkeypatch.delenv("SCANDIEGO_IGDB_CLIENT_SECRET"); loaded=MetadataSettings.load(path,store)
    assert loaded.igdb_client_secret=="old" and "igdb_client_secret" not in path.read_text()
    loaded.save(path,store); assert "steamgriddb_api_key" not in path.read_text()

def test_missing_keyring_is_safe(tmp_path):
    settings=MetadataSettings(igdb_client_secret="secret")
    with pytest.raises(RuntimeError): settings.save(tmp_path/"s.json",CredentialStore(backend=False))
    assert "secret" not in (tmp_path/"s.json").read_text()

def test_provider_factory_selection_and_error():
    settings=MetadataSettings(); assert isinstance(create_metadata_provider(settings),IGDBProvider); assert isinstance(create_artwork_provider(settings),SteamGridDBProvider)
    settings.metadata_provider="other"
    with pytest.raises(UnknownProviderError): create_metadata_provider(settings)

def test_schema_four_migrates_additively(tmp_path):
    db=prepared(tmp_path); db._conn.execute("PRAGMA user_version=4"); db._conn.commit(); path=db.db_path; db.close()
    from app.database.db_manager import DatabaseManager
    migrated=DatabaseManager(path); cols=migrated._columns("games")
    assert {"metadata_locked","artwork_source","artwork_external_game_id","artwork_status"} <= cols
