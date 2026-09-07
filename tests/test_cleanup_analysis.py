from app.database.db_manager import DatabaseManager, SCHEMA_VERSION
from app.models.game_entry import MediaEntry
from app.models.scan import ScanStatus


def media(path: str, size: int = 100, title: str = "Game", platform: str = "PC") -> MediaEntry:
    timestamp = "2026-01-01T00:00:00+00:00"
    return MediaEntry(None, "rom", title, path.rsplit("/", 1)[-1], path,
                      path.rsplit("/", 1)[-1], ".iso", size, timestamp,
                      "D:", "Disk", "ABC", timestamp, timestamp, 0, platform)


def test_duplicate_dashboard_count_matches_group_details(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entries([media("/a.iso"), media("/b.iso"), media("/c.iso", 200)])
    counts = db.cleanup_counts()
    assert counts["Wahrscheinliche Dubletten"] == len(db.cleanup_details("Wahrscheinliche Dubletten")) == 1
    assert counts["Mögliche Dubletten"] == len(db.cleanup_details("Mögliche Dubletten")) == 1
    db.close()


def test_confirmed_groups_require_matching_hash_type(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entries([media("/a.iso"), media("/b.iso")]); db.commit()
    rows = db.list_entries()
    db.save_hash(rows[0]["media_file_id"], "same", "sha256")
    db.save_hash(rows[1]["media_file_id"], "same", "sha1")
    assert db.cleanup_counts()["Bestätigte Dubletten"] == 0
    db.save_hash(rows[1]["media_file_id"], "same", "sha256")
    assert db.cleanup_counts()["Bestätigte Dubletten"] == 1
    assert len(db.cleanup_details("Bestätigte Dubletten")[0].entries) == 2
    db.close()


def test_archive_lifecycle_only_cleans_after_success(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_archive_only_dir("ABC", "/ROMs/PS2", "t1", "scan-1"); db.commit()
    assert len(db.cleanup_details("Archive noch nicht entpackt")) == 1
    for status in (ScanStatus.CANCELLED, ScanStatus.FAILED, ScanStatus.COMPLETED_WITH_WARNINGS):
        db.finalize_auxiliary_scan("ABC", "scan-2", status)
        assert len(db.cleanup_details("Archive noch nicht entpackt")) == 1
    db.finalize_auxiliary_scan("ABC", "scan-2", ScanStatus.COMPLETED)
    assert db.cleanup_details("Archive noch nicht entpackt") == []
    db.close()


def test_unknown_candidate_lifecycle_and_counts(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_unknown_candidate("ABC", "/ROMs/game.xyz", "game.xyz", ".xyz", 7, "t1", "scan-1")
    db.commit()
    assert db.cleanup_counts()["Unbekannte Dateiformate"] == 1
    db.finalize_auxiliary_scan("ABC", "scan-2", ScanStatus.CANCELLED)
    assert db.cleanup_counts()["Unbekannte Dateiformate"] == 1
    db.finalize_auxiliary_scan("ABC", "scan-2", ScanStatus.FAILED)
    assert db.cleanup_counts()["Unbekannte Dateiformate"] == 1
    db.finalize_auxiliary_scan("ABC", "scan-2", ScanStatus.COMPLETED)
    assert db.cleanup_counts()["Unbekannte Dateiformate"] == 0
    db.close()


def test_schema_v3_is_idempotent(tmp_path):
    path = tmp_path / "db.sqlite"
    DatabaseManager(path).close()
    db = DatabaseManager(path)
    assert db._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert "metadata_status" in db._columns("games")
    assert db._conn.execute("SELECT name FROM sqlite_master WHERE name='unknown_media_candidates'").fetchone()
    db.close()


def test_every_cleanup_count_uses_its_detail_analysis(tmp_path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    db.upsert_entry(media("/unknown.iso", platform="Unknown")); db.commit()
    counts = db.cleanup_counts()
    assert set(counts) == {
        "Archive noch nicht entpackt", "Mögliche Dubletten", "Wahrscheinliche Dubletten",
        "Bestätigte Dubletten", "Fehlende Dateien", "Unbekannte Plattformen",
        "Unbekannte Dateiformate", "Metadaten fehlgeschlagen", "Match prüfen",
        "Spiele ohne Cover", "Unvollständige Metadaten",
    }
    assert all(count == len(db.cleanup_details(category)) for category, count in counts.items())
    # The default means no provider was requested, not that metadata retrieval failed.
    assert counts["Metadaten fehlgeschlagen"] == 0
    assert counts["Unvollständige Metadaten"] == 0
    db._conn.execute("UPDATE games SET metadata_status='failed'"); db.commit()
    assert db.cleanup_counts()["Metadaten fehlgeschlagen"] == 1
    db.close()
