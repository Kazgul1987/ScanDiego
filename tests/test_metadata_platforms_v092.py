from app.models.metadata import ExternalGame, ExternalPlatform, MetadataStatus
from app.providers.fake import FakeMetadataProvider
from app.providers.igdb import IGDBProvider
from app.services.game_matching_service import GameMatchingService
from app.services.match_review_service import MatchReviewService
from app.services.metadata_queue_service import MetadataQueueService
from tests.test_metadata import prepared
from tests.test_metadata import entry


def platforms():
    return [
        ExternalPlatform("6", "PC (Microsoft Windows)", "PC"),
        ExternalPlatform("167", "PlayStation 5", "PlayStation"),
        ExternalPlatform("169", "Xbox Series X|S", "Xbox"),
    ]


def game(choices=None):
    return ExternalGame("7", "007 First Light", release_year=2026, publisher="IOI",
                        developer="IOI", available_platforms=choices or platforms())


def test_igdb_candidate_keeps_every_platform():
    result = IGDBProvider._map({"id": 7, "name": "007 First Light", "platforms": [
        {"id": 6, "name": "PC (Microsoft Windows)"},
        {"id": 167, "name": "PlayStation 5"},
        {"id": 169, "name": "Xbox Series X|S"},
    ]})
    assert [(p.external_platform_id, p.normalized_platform) for p in result.available_platforms] == [
        ("6", "PC"), ("167", "PlayStation"), ("169", "Xbox")]
    assert result.platform == "" and result.external_platform_id is None


def test_matching_known_pc_accepts_multi_and_penalizes_xbox_only():
    matcher = GameMatchingService()
    multi = matcher.score("007 First Light", "PC", game())
    xbox = matcher.score("007 First Light", "PC", game([platforms()[2]]))
    assert multi.platform_match and multi.score == 100
    assert not xbox.platform_match and xbox.score <= 55


def test_automatic_unknown_multi_is_ambiguous(tmp_path):
    db = prepared(tmp_path, "007 First Light", "Unknown")
    db.enqueue_metadata()
    MetadataQueueService(db, FakeMetadataProvider([game()]), GameMatchingService(70, 50), interval=0).process()
    row = db._conn.execute("SELECT * FROM games").fetchone()
    assert row["metadata_status"] == "ambiguous"
    assert row["platform"] == "Unknown" and row["external_platform_id"] is None


def test_automatic_unknown_single_platform_resolves_platform(tmp_path):
    db = prepared(tmp_path, "007 First Light", "Unknown")
    only_pc = game([platforms()[0]])
    db.enqueue_metadata()
    MetadataQueueService(db, FakeMetadataProvider([only_pc]), GameMatchingService(70, 50), interval=0).process()
    row = db._conn.execute("SELECT * FROM games").fetchone()
    assert row["platform"] == "PC" and row["external_platform_id"] == "6"


def test_manual_platform_selection_and_overwrite_protection(tmp_path):
    db = prepared(tmp_path, "007 First Light", "Unknown")
    game_id = db._conn.execute("SELECT id FROM games").fetchone()[0]
    service = MatchReviewService(db, FakeMetadataProvider([game()]), GameMatchingService())
    service.apply(game_id, "7", 100, "6")
    row = db._conn.execute("SELECT * FROM games").fetchone()
    assert (row["platform"], row["external_platform_id"], row["metadata_status"], row["metadata_locked"]) == ("PC", "6", "manual", 1)

    # A conflicting choice without explicit local update is redirected to the known local platform.
    service.apply(game_id, "7", 100, "169", False)
    row = db._conn.execute("SELECT * FROM games").fetchone()
    assert row["platform"] == "PC" and row["external_platform_id"] == "6"
    service.apply(game_id, "7", 100, "169", True)
    row = db._conn.execute("SELECT * FROM games").fetchone()
    assert row["platform"] == "Xbox" and row["external_platform_id"] == "169"


def test_manual_platform_lock_updates_projection(tmp_path):
    db = prepared(tmp_path, "Locked", "Unknown")
    game_id = db._conn.execute("SELECT id FROM games").fetchone()[0]
    db.set_game_platform(game_id, "PC")
    assert db._conn.execute("SELECT platform_overridden FROM games").fetchone()[0] == 1
    assert db._conn.execute("SELECT platform,platform_overridden FROM media_entries").fetchone()[:] == ("PC", 1)
    original_id = game_id
    db.upsert_entry(entry("Locked", "Unknown"))
    projected = db._conn.execute("SELECT game_id,platform FROM media_entries").fetchone()
    assert projected[:] == (original_id, "PC")


def test_bulk_retries_failed_but_protects_other_states(tmp_path):
    db = prepared(tmp_path, "not-1", "PC")
    now = "2026"
    states = ["not_requested", "failed", "failed", "failed", "matched", "manual"]
    for index, state in enumerate(states, 2):
        db._conn.execute("INSERT INTO games(title,platform,metadata_status,metadata_locked,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                         (f"game-{index}", "PC", state, int(state == "manual"), now, now))
    db._conn.commit()
    assert db.enqueue_metadata() == 5
    counts = dict(db._conn.execute("SELECT metadata_status,COUNT(*) FROM games GROUP BY metadata_status"))
    assert counts == {"manual": 1, "matched": 1, "queued": 5}
