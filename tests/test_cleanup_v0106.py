from pathlib import Path

from app.services.misclassified_media_service import (
    classify_candidate, infer_scan_root, safety_level,
)


def row(path: str, platform: str = "PC") -> dict:
    return {"media_file_id": 1, "game_id": 2, "title": "Historical",
            "platform": platform, "full_path": path,
            "file_name": Path(path).name}


def test_windows_scan_roots_are_reconstructed_by_path_components():
    assert infer_scan_root(r"G:\ROMs\PS1\BIN\Game.bin") == r"G:\ROMs"
    assert infer_scan_root(r"G:\Games\InstalledGame\Data\foo.bin") == r"G:\Games"
    assert classify_candidate(row(r"G:\ROMs\PS1\BIN\Game.bin", "PlayStation"), []) is None
    candidate = classify_candidate(row(r"G:\Games\InstalledGame\Data\foo.bin"), [])
    assert candidate and candidate.safety_level == "likely"


def test_hard_rejections_have_safe_safety_level():
    cases = [
        (r"G:\Games\Tool\README.md", "rejected_markdown_file"),
        (r"G:\Games\Tool\DebugLinesVertex.cso", "rejected_shader_cso"),
        (r"G:\Games\Pokemon Scarlet (Certificate).bin", "rejected_switch_cartridge_metadata"),
        (r"G:\Games\PS3_GAME\USRDIR\EBOOT.BIN", "rejected_ps3_internal_file"),
    ]
    for path, reason in cases:
        candidate = classify_candidate(row(path), [])
        assert candidate and (candidate.reason, candidate.safety_level) == (reason, "safe")


def test_uncertain_or_rootless_results_are_review_only():
    assert safety_level("ambiguous_insufficient_context", 1, r"G:\Games") == "review"
    assert safety_level("rejected_markdown_file", 1, None) == "review"


def test_cue_tracks_only_are_cleanup_candidates(tmp_path):
    root = tmp_path / "ROMs"
    folder = root / "PS1"
    folder.mkdir(parents=True)
    cue = folder / "Game.cue"
    first, second = folder / "Track01.bin", folder / "Track02.bin"
    cue.write_text('FILE "Track01.bin" BINARY\nFILE "Track02.bin" BINARY\n', encoding="utf-8")
    first.touch(); second.touch()
    siblings = list(folder.iterdir())
    assert classify_candidate(row(str(cue), "PlayStation"), siblings) is None
    candidates = [classify_candidate(row(str(path), "PlayStation"), siblings)
                  for path in (first, second)]
    assert all(item and item.reason == "rejected_cue_companion_bin"
               and item.safety_level == "safe" for item in candidates)
