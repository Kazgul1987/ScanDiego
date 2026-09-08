from app.database.db_manager import DatabaseManager, SCHEMA_VERSION
from app.models.content import ContentDetectionMethod, ContentDetectionResult, MediaContentType
from app.models.game_entry import MediaEntry


def media(path, title="Game", kind=MediaContentType.UNKNOWN):
    return MediaEntry(None, "rom", title, path, path, path.rsplit("/", 1)[-1], ".nsp", 10,
                      "2026-01-01", "D:", "Drive", "serial", "2026-01-01", "2026-01-01", 0,
                      "Switch", content_type=kind, content_title=title,
                      content_detection_method=ContentDetectionMethod.FILENAME,
                      content_detection_confidence=.9)


def test_schema_six_fields_and_multiple_content_files_group_to_one_game(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    assert SCHEMA_VERSION == 8
    columns = db._columns("media_files")
    assert {"content_type", "content_title", "content_version", "content_id", "base_content_id",
            "content_detection_method", "content_detection_confidence", "content_parent_game_id",
            "content_region", "content_locked"} <= columns
    db.upsert_entries([media("/Game.xci", kind=MediaContentType.BASE_GAME),
                       media("/Game.nsp", kind=MediaContentType.BASE_GAME),
                       media("/Game DLC 1.nsp", kind=MediaContentType.DLC),
                       media("/Game DLC 2.nsp", kind=MediaContentType.DLC),
                       media("/Game Update.nsp", kind=MediaContentType.UPDATE)])
    db.commit()
    assert db._conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    counts = dict(db._conn.execute("SELECT content_type,COUNT(*) FROM media_files GROUP BY content_type"))
    assert counts == {"base_game": 2, "dlc": 2, "update": 1}
    assert db.cleanup_counts()["Mehrere Base-Game-Dateien"] == 1


def test_legacy_dlc_game_is_safely_consolidated_and_metadata_queue_filters(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media("/base.nsp", "Super Smash Bros Ultimate", MediaContentType.BASE_GAME))
    db.upsert_entry(media("/dlc.nsp", "Super Smash Bros Ultimate Joker DLC"))
    db.commit()
    base_id = db._conn.execute("SELECT id FROM games WHERE title='Super Smash Bros Ultimate'").fetchone()[0]
    dlc = db._conn.execute("SELECT id,game_id FROM media_files WHERE file_name='dlc.nsp'").fetchone()
    old_id = dlc["game_id"]
    result = ContentDetectionResult(MediaContentType.DLC, "Super Smash Bros Ultimate",
                                    confidence=.9, method=ContentDetectionMethod.FILENAME)
    db.apply_content_detection(dlc["id"], result)
    moved = db._conn.execute("SELECT game_id,content_parent_game_id FROM media_files WHERE id=?", (dlc["id"],)).fetchone()
    assert tuple(moved) == (base_id, base_id)
    assert db._conn.execute("SELECT 1 FROM games WHERE id=?", (old_id,)).fetchone() is None
    assert db.enqueue_metadata() == 1
    assert [row["id"] for row in db.queued_games()] == [base_id]


def test_manual_content_lock_survives_automatic_analysis(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media("/base.nsp", "Base", MediaContentType.BASE_GAME))
    db.upsert_entry(media("/locked.nsp")); db.commit()
    media_id = db._conn.execute("SELECT id FROM media_files WHERE file_name='locked.nsp'").fetchone()[0]
    game_id = db._conn.execute("SELECT id FROM games WHERE title='Base'").fetchone()[0]
    db.set_manual_content(media_id, MediaContentType.DLC, game_id, "Manual")
    db.apply_content_detection(media_id, ContentDetectionResult(MediaContentType.UPDATE, "Changed", confidence=.9))
    row = db._conn.execute("SELECT content_type,content_title,content_locked FROM media_files WHERE id=?", (media_id,)).fetchone()
    assert tuple(row) == ("dlc", "Manual", 1)
