from app.models.metadata import ExternalGame, MetadataStatus
from tests.test_metadata import prepared


def _add_content(db, game_id, content_type, suffix):
    source = db._conn.execute("SELECT * FROM media_files WHERE game_id=? LIMIT 1", (game_id,)).fetchone()
    db._conn.execute("""INSERT INTO media_files
        (game_id,drive_id,full_path,file_name,extension,file_size,modified_time,last_seen,is_missing,created_at,content_type)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (game_id, source["drive_id"], source["full_path"]+suffix,
        source["file_name"]+suffix, source["extension"], source["file_size"], source["modified_time"],
        source["last_seen"], 0, source["created_at"], content_type))
    db._conn.commit()


def test_game_cards_are_aggregated_with_content_counts(tmp_path):
    db = prepared(tmp_path, "007 First Light", "PC")
    game_id = db._conn.execute("SELECT id FROM games").fetchone()[0]
    db._conn.execute("UPDATE media_files SET content_type='base_game' WHERE game_id=?", (game_id,))
    for i in range(2): _add_content(db, game_id, "update", f"-u{i}")
    for i in range(3): _add_content(db, game_id, "dlc", f"-d{i}")
    cards = db.list_game_cards()
    assert len(cards) == 1 and cards[0]["update_count"] == 2 and cards[0]["dlc_count"] == 3


def test_game_card_search_filter_and_sort_are_game_centric(tmp_path):
    db = prepared(tmp_path, "Zulu", "PC")
    first = db._conn.execute("SELECT id FROM games").fetchone()[0]
    _add_content(db, first, "update", "-update")
    db.upsert_entry(__import__('tests.test_metadata', fromlist=['entry']).entry("Alpha", "Xbox")); db.commit()
    assert [r["display_title"] for r in db.list_game_cards(sort="title_asc")] == ["Alpha", "Zulu"]
    assert len(db.list_game_cards(search="Zulu")) == 1
    assert [r["platform"] for r in db.list_game_cards(platform="PC", cover="without")] == ["PC"]


def test_bulk_cover_eligibility_stale_file_and_duplicate_protection(tmp_path):
    db = prepared(tmp_path, "Missing cover", "PC")
    game_id = db._conn.execute("SELECT id FROM games").fetchone()[0]
    db.apply_metadata(game_id, ExternalGame("sg", "Canonical", "PC"), "fake", 100, "manual", MetadataStatus.MANUAL)
    db.set_cover(game_id, str(tmp_path / "gone.jpg"), "fake")
    assert db.enqueue_covers() == 1
    assert db.enqueue_covers() == 0


def test_bulk_cover_rejects_ambiguous_and_failed_metadata(tmp_path):
    db = prepared(tmp_path, "Ambiguous", "PC")
    game_id = db._conn.execute("SELECT id FROM games").fetchone()[0]
    db._conn.execute("UPDATE games SET external_game_id='x',metadata_status='ambiguous' WHERE id=?", (game_id,))
    db._conn.commit(); assert db.enqueue_covers() == 0
    db._conn.execute("UPDATE games SET metadata_status='failed' WHERE id=?", (game_id,))
    db._conn.commit(); assert db.enqueue_covers() == 0
