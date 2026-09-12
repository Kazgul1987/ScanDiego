from pathlib import Path

import pytest

from app.services.media_validation_service import MediaValidationService
from app.services.platform_detection_service import PlatformDetectionService


def classify(path: Path, scan_root: Path):
    return MediaValidationService.classify(
        path, scan_root=scan_root,
        detected_platform=PlatformDetectionService().detect(path),
    )


@pytest.mark.parametrize("relative", [
    "PS1/BIN/Final Fantasy VII.bin",
    "PS1/Data/Game.bin",
    "PlayStation/Content/Game.bin",
    "Sega CD/BIN/Game.bin",
    "PSP/Resources/God of War.cso",
    "PSP/Data/Crisis Core.cso",
    "Mega Drive/Sonic.md",
])
def test_weak_generic_folders_do_not_override_platform_context(tmp_path, relative):
    root = tmp_path / "ROMs"
    result = classify(root / relative, root)
    assert result.is_media
    assert result.reason == "accepted_platform_context"


@pytest.mark.parametrize("relative", [
    "InstalledGame/Data/foo.bin",
    "InstalledGame/Engine/Content/foo.bin",
    "Tom Clancys Splinter Cell/LIPSYNCH/int/S0/foo.bin",
    "Return to Monkey Island/Resources/DebugLinesVertex.cso",
    "Return to Monkey Island/Graphics/PostProcessLightingFragment.cso",
])
def test_installed_game_internals_remain_rejected(tmp_path, relative):
    root = tmp_path / "Games"
    assert not classify(root / relative, root).is_media


@pytest.mark.parametrize("relative", [
    "PS1/BIOS/scph1001.bin",
    "Switch/Pokemon Scarlet (Certificate).bin",
    "PS3/Game/PS3_GAME/USRDIR/EBOOT.BIN",
    "Mega Drive/README.md",
])
def test_hard_exclusions_override_platform_context(tmp_path, relative):
    root = tmp_path / "ROMs"
    assert not classify(root / relative, root).is_media


def test_cue_companion_precedes_platform_acceptance(tmp_path):
    root = tmp_path / "ROMs"
    folder = root / "PS1" / "BIN"
    folder.mkdir(parents=True)
    cue = folder / "Game.cue"
    binary = folder / "Game.bin"
    cue.write_text('FILE "Game.bin" BINARY\n', encoding="utf-8")
    binary.write_bytes(b"track")
    siblings = list(folder.iterdir())

    assert MediaValidationService.classify(cue, root, sibling_files=siblings).is_media
    result = MediaValidationService.classify(binary, root, sibling_files=siblings)
    assert not result.is_media
    assert result.reason == "rejected_cue_companion_bin"


def test_scan_root_limits_platform_context():
    platform = PlatformDetectionService().detect(r"C:\ROMs\PS1\BIN\Game.bin")
    accepted = MediaValidationService.classify(
        r"C:\ROMs\PS1\BIN\Game.bin", r"C:\ROMs", platform)
    rejected = MediaValidationService.classify(
        r"C:\ROMs\PS1\BIN\Game.bin", r"C:\Games\InstalledGame", platform)

    assert accepted.is_media
    assert accepted.reason == "accepted_platform_context"
    assert not rejected.is_media
    assert rejected.reason == "ambiguous_insufficient_context"

    installed = MediaValidationService.classify(
        r"C:\Games\InstalledGame\Data\Game.bin",
        r"C:\Games\InstalledGame",
        PlatformDetectionService().detect(r"C:\Games\InstalledGame\Data\Game.bin"),
    )
    assert not installed.is_media
    assert installed.reason == "rejected_pc_game_internal_binary"
