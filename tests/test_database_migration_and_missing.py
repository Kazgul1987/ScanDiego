import sqlite3
from app.database.db_manager import DatabaseManager
from app.models.game_entry import MediaEntry
from app.models.scan import ScanStatus


def media(timestamp="2025-01-01T00:00:00+00:00"):
    return MediaEntry(None, "rom", "Game", "Game.iso", "/rom/Game.iso", "Game.iso", ".iso", 1,
                      timestamp, "D:", "Disk", "ABC", timestamp, timestamp, 0)


def test_legacy_database_is_migrated_without_data_loss(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE media_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
      title TEXT NOT NULL, original_filename TEXT NOT NULL, full_path TEXT NOT NULL, file_name TEXT NOT NULL,
      file_extension TEXT NOT NULL, file_size INTEGER NOT NULL, modified_time TEXT NOT NULL, drive_letter TEXT NOT NULL,
      drive_label TEXT, drive_id TEXT NOT NULL, scan_date TEXT NOT NULL, last_seen_date TEXT NOT NULL,
      is_missing INTEGER NOT NULL DEFAULT 0, UNIQUE(drive_id,full_path))""")
    conn.execute("INSERT INTO media_entries(category,title,original_filename,full_path,file_name,file_extension,file_size,modified_time,drive_letter,drive_label,drive_id,scan_date,last_seen_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("rom","Old Game","Old.iso","/Old.iso","Old.iso",".iso",1,"t","D:","Disk","ABC","t","t"))
    conn.commit(); conn.close()
    db = DatabaseManager(path)
    assert db.list_entries()[0]["title"] == "Old Game"
    assert db._conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db._conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0] == 1
    db.close()


def test_missing_only_changes_after_completed_scan(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media()); db.commit()
    for status in (ScanStatus.FAILED, ScanStatus.CANCELLED, ScanStatus.COMPLETED_WITH_WARNINGS):
        assert db.mark_missing_for_completed_scan("ABC", "2026-01-01", status) == 0
        assert db.list_entries()[0]["is_missing"] == 0
    assert db.mark_missing_for_completed_scan("ABC", "2026-01-01", ScanStatus.COMPLETED) == 1
    db.commit()
    assert db.list_entries()[0]["is_missing"] == 1
    db.close()
