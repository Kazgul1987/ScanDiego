from pathlib import Path

import pytest

from app.database.db_manager import DatabaseManager, SCHEMA_VERSION
from app.models.game_entry import MediaEntry
from app.services.media_validation_service import MediaValidationService
from app.services.platform_detection_service import PlatformDetectionService


def classify(path: str):
    platform = PlatformDetectionService().detect(path)
    return MediaValidationService.classify(path, detected_platform=platform)


@pytest.mark.parametrize("path,reason", [
    ("Games/Tom Clancys Splinter Cell/LIPSYNCH/int/S0/00_15_01.bin", "rejected_pc_game_internal_binary"),
    ("Games/InstalledGame/Data/foo.bin", "rejected_pc_game_internal_binary"),
    ("Games/Return to Monkey Island/shaders/DebugLinesVertex.cso", "rejected_shader_cso"),
    ("Games/Return to Monkey Island/rendering/DistortionFragment.cso", "rejected_shader_cso"),
    ("README.md", "rejected_markdown_file"),
    ("ROMs/Ryujinx/cache/snapshot_blob.bin", "rejected_emulator_cache"),
    ("ROMs/Cemu_2.0-39/shaderCache/a/0005000010143600_shaders.bin", "rejected_emulator_cache"),
    ("ROMs/Dolphin-x64/Sys/codehandler.bin", "rejected_emulator_cache"),
    ("ROMs/Drastic/system/drastic_bios_arm7.bin", "rejected_emulator_cache"),
    ("ROMs/Switch/Pokemon Scarlet (Certificate).bin", "rejected_switch_cartridge_metadata"),
    ("ROMs/Switch/Pokemon Scarlet (Initial Data).bin", "rejected_switch_cartridge_metadata"),
    ("ROMs/Switch/Pokemon Brilliant Diamond (Card UID).bin", "rejected_switch_cartridge_metadata"),
    ("Game/PS3_GAME/USRDIR/EBOOT.BIN", "rejected_ps3_internal_file"),
])
def test_real_false_positives_are_rejected(path, reason):
    result = classify(path)
    assert not result.is_media
    assert result.reason == reason


@pytest.mark.parametrize("path", [
    "ROMs/PSP/God of War.cso", "ROMs/Mega Drive/Sonic.md",
    "ROMs/PS1/Some Game.bin", "ROMs/Switch/Mario.nsp",
    "ROMs/Switch/Zelda.xci", "ROMs/GBA/Metroid.gba",
    "ROMs/SNES/Zelda.sfc", "ROMs/N64/Mario.z64",
])
def test_real_media_remains_accepted(path):
    assert classify(path).is_media


def test_cue_is_primary_and_all_referenced_tracks_are_companions(tmp_path):
    folder = tmp_path / "ROMs" / "PS1"
    folder.mkdir(parents=True)
    cue = folder / "Game.cue"
    tracks = [folder / f"Track0{number}.bin" for number in range(1, 4)]
    cue.write_text("\n".join(f'FILE "{track.name}" BINARY' for track in tracks), encoding="utf-8")
    for track in tracks:
        track.write_bytes(b"track")
    siblings = list(folder.iterdir())
    assert classify(str(cue)).is_media
    for track in tracks:
        result = MediaValidationService.classify(
            track, detected_platform=PlatformDetectionService().detect(track), sibling_files=siblings)
        assert not result.is_media
        assert result.reason == "rejected_cue_companion_bin"
        assert result.companion_file == "Game.cue"


def _entry(path: Path, title: str) -> MediaEntry:
    return MediaEntry(None, "rom", title, path.name, str(path), path.name, path.suffix,
                      path.stat().st_size, "2026-01-01T00:00:00", "X:", "Test", "serial",
                      "2026-01-01T00:00:00", "2026-01-01T00:00:00", 0,
                      str(PlatformDetectionService().detect(path)))


def test_cleanup_removes_only_db_records_and_preserves_multi_media_game(tmp_path):
    db = DatabaseManager(tmp_path / "library.db")
    bad = tmp_path / "ROMs" / "Switch" / "README.md"
    good = tmp_path / "ROMs" / "Switch" / "README.nsp"
    good.parent.mkdir(parents=True); bad.write_text("keep me", encoding="utf-8"); good.write_bytes(b"game")
    db.upsert_entries([_entry(bad, "Shared"), _entry(good, "Shared")])
    db.commit()
    findings = db.cleanup_details("Wahrscheinlich falsch erkannte Medien")
    assert [row["file_name"] for row in findings] == ["README.md"]
    assert db.remove_misclassified_media([findings[0]["media_file_id"]]) == 1
    assert bad.exists()
    assert len(db.game_content_files(findings[0]["game_id"])) == 1
    db.close()


def test_cleanup_removes_orphan_game_without_deleting_file(tmp_path):
    db = DatabaseManager(tmp_path / "library.db")
    bad = tmp_path / "README.md"; bad.write_text("keep me", encoding="utf-8")
    db.upsert_entries([_entry(bad, "Readme")]); db.commit()
    finding = db.cleanup_details("Wahrscheinlich falsch erkannte Medien")[0]
    db.remove_misclassified_media([finding["media_file_id"]])
    assert bad.exists()
    assert not db._conn.execute("SELECT 1 FROM games WHERE id=?", (finding["game_id"],)).fetchone()
    assert SCHEMA_VERSION == 8
    db.close()
