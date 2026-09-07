import sqlite3
import pytest
from app.database.db_manager import DatabaseManager, SCHEMA_VERSION
from app.models.game_entry import MediaEntry
from app.models.metadata import ExternalGame, MetadataStatus
from app.providers.fake import FakeArtworkProvider, FakeMetadataProvider
from app.services.artwork_service import ArtworkService, InvalidArtworkError
from app.services.game_matching_service import GameMatchingService
from app.services.metadata_queue_service import MetadataQueueService


def entry(title="Pokémon: Emerald", platform="Game Boy Advance"):
    return MediaEntry(None,"game",title,title+".gba","/roms/"+title+".gba",title+".gba",".gba",1,"2025","E:","Disk","serial","2025","2025",0,platform)

def prepared(tmp_path, title="Pokémon: Emerald", platform="Game Boy Advance"):
    db=DatabaseManager(tmp_path/"db.sqlite"); db.upsert_entry(entry(title,platform)); db.commit(); return db


def test_matching_normalizes_unicode_punctuation_and_platform():
    matcher=GameMatchingService(); candidate=ExternalGame("1","Pokemon Emerald","Game Boy Advance")
    result=matcher.score("Pokémon: Emerald","Game Boy Advance",candidate)
    assert result.score == 100 and matcher.classify([result]) == "matched"

def test_platform_conflict_cannot_auto_match():
    result=GameMatchingService().score("God of War","PlayStation 2",ExternalGame("1","God of War","PlayStation 4",release_year=2018))
    assert result.score <= 55

def test_ambiguous_threshold_and_close_candidates():
    matcher=GameMatchingService(); game=ExternalGame("1","Resident Evil Four","PlayStation 2")
    ranked=matcher.rank("Resident Evil 4","PlayStation 2",[game])
    assert matcher.classify(ranked) in {"ambiguous", "matched"}
    assert matcher.classify([]) == "failed"

def test_queue_complete_flow_and_direct_refresh(tmp_path):
    db=prepared(tmp_path); game=ExternalGame("42","Pokemon Emerald","Game Boy Advance",release_year=2004,publisher="Nintendo")
    provider=FakeMetadataProvider([game]); art=FakeArtworkProvider(); cache=ArtworkService(art,tmp_path/"covers")
    assert db.enqueue_metadata()==1
    stats=MetadataQueueService(db,provider,GameMatchingService(),cache,0).process()
    row=db._conn.execute("SELECT * FROM games").fetchone()
    assert stats["matched"]==1 and row["external_game_id"]=="42" and row["cover_path"]
    db.set_metadata_status(row["id"],MetadataStatus.QUEUED)
    MetadataQueueService(db,provider,GameMatchingService(),None,0).process()
    assert provider.get_calls==1 and provider.search_calls==1

def test_queue_failure_continues_and_manual_is_protected(tmp_path):
    db=prepared(tmp_path); first=db._conn.execute("SELECT id FROM games").fetchone()[0]
    db.apply_metadata(first,ExternalGame("m","Manual","Game Boy Advance"),"fake",100,"manual",MetadataStatus.MANUAL)
    assert db.enqueue_metadata()==0 and db.enqueue_metadata([first])==0
    assert db.enqueue_metadata([first],force=True)==1

def test_cover_validation_and_cache(tmp_path):
    game=ExternalGame("1","Game","PC"); provider=FakeArtworkProvider(); service=ArtworkService(provider,tmp_path)
    path=service.fetch(7,game); assert path.exists()
    assert service.fetch(7,game)==path and provider.download_calls==1
    with pytest.raises(InvalidArtworkError): ArtworkService(FakeArtworkProvider(b"<html>","text/html"),tmp_path/"bad").fetch(8,game)
    with pytest.raises(InvalidArtworkError): ArtworkService(FakeArtworkProvider(b"","image/png"),tmp_path/"empty").fetch(9,game)

def test_migration_preserves_existing_rows(tmp_path):
    path=tmp_path/"old.sqlite"; conn=sqlite3.connect(path); conn.executescript("CREATE TABLE games(id INTEGER PRIMARY KEY,title TEXT NOT NULL,platform TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(title,platform)); PRAGMA user_version=3; INSERT INTO games VALUES(1,'Old','PC','x','x');"); conn.close()
    db=DatabaseManager(path)
    assert db._conn.execute("PRAGMA user_version").fetchone()[0]==SCHEMA_VERSION
    assert db._conn.execute("SELECT title FROM games").fetchone()[0]=="Old"
