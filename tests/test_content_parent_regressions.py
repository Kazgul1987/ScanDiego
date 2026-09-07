import pytest

from app.database.db_manager import DatabaseError, DatabaseManager
from app.models.content import ContentDetectionMethod, MediaContentType
from app.models.game_entry import MediaEntry
from app.services.content_detection_service import ContentDetectionService


def media(path: str, kind: MediaContentType, title: str = "Game") -> MediaEntry:
    return MediaEntry(None, "rom", title, path, path, path.rsplit("/", 1)[-1], ".nsp", 10,
                      "2026-01-01", "D:", "Drive", "serial", "2026-01-01", "2026-01-01", 0,
                      "Switch", content_type=kind, content_title=title,
                      content_detection_method=ContentDetectionMethod.FILENAME,
                      content_detection_confidence=.9)


@pytest.mark.parametrize(("kind", "category"), [
    (MediaContentType.DLC, "DLC ohne Hauptspiel"),
    (MediaContentType.UPDATE, "Update ohne Hauptspiel"),
])
def test_supplemental_only_has_no_self_parent_and_cleanup_matches(tmp_path, kind, category):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media(f"/Game {kind.value}.nsp", kind))
    row = db._conn.execute("SELECT game_id,content_parent_game_id FROM media_files").fetchone()
    assert row["content_parent_game_id"] is None
    assert db.cleanup_counts()[category] == len(db.cleanup_details(category)) == 1


@pytest.mark.parametrize("order", [
    (MediaContentType.DLC, MediaContentType.BASE_GAME),
    (MediaContentType.BASE_GAME, MediaContentType.DLC),
])
def test_base_and_dlc_group_identically_in_both_scan_orders(tmp_path, order):
    db = DatabaseManager(tmp_path / "db.sqlite")
    for index, kind in enumerate(order):
        db.upsert_entry(media(f"/{index}-{kind.value}.nsp", kind))
    rows = db._conn.execute("SELECT game_id,content_parent_game_id,content_type FROM media_files").fetchall()
    base_game = next(row["game_id"] for row in rows if row["content_type"] == "base_game")
    dlc = next(row for row in rows if row["content_type"] == "dlc")
    assert dlc["game_id"] == dlc["content_parent_game_id"] == base_game
    assert db._conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0] == 2


def test_two_dlc_only_files_never_parent_each_other(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entries([media("/Game DLC 1.nsp", MediaContentType.DLC),
                       media("/Game DLC 2.nsp", MediaContentType.DLC)])
    assert [row[0] for row in db._conn.execute(
        "SELECT content_parent_game_id FROM media_files ORDER BY id")] == [None, None]


def test_startup_repairs_existing_locked_self_parent_without_unlocking(tmp_path):
    path = tmp_path / "db.sqlite"
    db = DatabaseManager(path)
    db.upsert_entry(media("/Game DLC.nsp", MediaContentType.DLC))
    row = db._conn.execute("SELECT id,game_id FROM media_files").fetchone()
    db._conn.execute("UPDATE media_files SET content_parent_game_id=game_id,content_locked=1 WHERE id=?", (row["id"],))
    db._conn.execute("UPDATE media_entries SET content_parent_game_id=game_id,content_locked=1 WHERE media_file_id=?", (row["id"],))
    db.commit(); db.close()
    repaired = DatabaseManager(path)
    result = repaired._conn.execute(
        "SELECT content_parent_game_id,content_locked FROM media_files").fetchone()
    assert tuple(result) == (None, 1)


def test_manual_parent_assignment_lock_and_removal(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media("/Base.nsp", MediaContentType.BASE_GAME, "Base"))
    db.upsert_entry(media("/DLC.nsp", MediaContentType.DLC, "DLC Holder"))
    base_id = db._conn.execute("SELECT id FROM games WHERE title='Base'").fetchone()[0]
    media_id = db._conn.execute("SELECT id FROM media_files WHERE file_name='DLC.nsp'").fetchone()[0]
    db.set_manual_content(media_id, MediaContentType.DLC, base_id, "Base")
    assigned = db._conn.execute("SELECT game_id,content_parent_game_id,content_locked,content_detection_method FROM media_files WHERE id=?", (media_id,)).fetchone()
    assert tuple(assigned) == (base_id, base_id, 1, "manual")
    db.reconcile_content_associations()
    assert db._conn.execute("SELECT content_parent_game_id FROM media_files WHERE id=?", (media_id,)).fetchone()[0] == base_id
    db.remove_manual_content_parent(media_id)
    removed = db._conn.execute("SELECT content_parent_game_id,content_locked,content_type FROM media_files WHERE id=?", (media_id,)).fetchone()
    assert tuple(removed) == (None, 0, "dlc")


def test_manual_self_parent_without_base_is_rejected(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media("/DLC.nsp", MediaContentType.DLC))
    row = db._conn.execute("SELECT id,game_id FROM media_files").fetchone()
    with pytest.raises(DatabaseError):
        db.set_manual_content(row["id"], MediaContentType.DLC, row["game_id"])


@pytest.mark.parametrize(("name", "expected"), [
    ("0100F2C0115B6000.nsp", "0100F2C0115B6000"),
    ("Game 0100F2C0115B6000.nsp", "0100F2C0115B6000"),
    ("Game [0100F2C0115B6000].nsp", "0100F2C0115B6000"),
    ("Game ABCD.nsp", None),
    ("Game 0100F2C0115B600G.nsp", None),
    ("Game A0100F2C0115B6000B.nsp", None),
    ("Game 0100F2C0115B60000100F2C0115B6000.nsp", None),
])
def test_conservative_unbracketed_switch_title_id(tmp_path, name, expected):
    result = ContentDetectionService().detect(tmp_path / name)
    assert result.content_id == expected
