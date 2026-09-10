from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import Iterable

from app.config import SUPPORTED_MEDIA_EXTENSIONS
from app.models.platform import Platform

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaValidationResult:
    is_media: bool
    confidence: float
    reason: str
    media_kind: str | None = None
    detected_platform: str | None = None
    companion_file: str | None = None
    excluded_by_rule: str | None = None


class MediaValidationService:
    """Fast, conservative validation layered on top of extension detection."""

    HIGH_CONFIDENCE_EXTENSIONS = frozenset({
        ".nsp", ".xci", ".nsz", ".xcz", ".3ds", ".cia", ".gba", ".gbc",
        ".gb", ".nds", ".n64", ".z64", ".v64", ".sfc", ".smc", ".gen",
        ".chd", ".rvz", ".wbfs", ".wia", ".gcz",
    })
    AMBIGUOUS_EXTENSIONS = frozenset({".bin", ".cso", ".md", ".img", ".iso"})
    _internal_segments = frozenset({
        "lipsynch", "shadercache", "shaders", "cache", "sys", "system", "bios",
        "firmware", "backup", "temp", "tmp", "resources", "resource", "logs",
        "log", "crash", "dumps", "profiles",
        "bin", "binaries", "data", "content", "engine", "localization", "movies",
    })
    _emulators = ("ryujinx", "cemu", "dolphin", "drastic")
    _disc_platforms = frozenset({
        Platform.PLAYSTATION, Platform.PLAYSTATION_2, Platform.PSP,
        Platform.SATURN, Platform.DREAMCAST,
    })

    @classmethod
    def classify(cls, path: str | Path, scan_root: str | Path | None = None,
                 detected_platform: str | Platform | None = None,
                 sibling_files: Iterable[str | Path] | None = None) -> MediaValidationResult:
        raw = str(path)
        pure = PureWindowsPath(raw) if "\\" in raw else PurePath(raw)
        extension, name = pure.suffix.casefold(), pure.name.casefold()
        platform = cls._platform(detected_platform)
        segments = [re.sub(r"[-_.]+", " ", part).strip().casefold()
                    for part in pure.parts[:-1]]

        def result(accepted: bool, confidence: float, reason: str, **kwargs) -> MediaValidationResult:
            value = MediaValidationResult(accepted, confidence, reason,
                detected_platform=str(platform) if platform else None, **kwargs)
            LOGGER.debug("Medienvalidierung %s: %s", raw, reason)
            return value

        if extension not in SUPPORTED_MEDIA_EXTENSIONS:
            return result(False, 1.0, "unsupported_extension")
        if extension in cls.HIGH_CONFIDENCE_EXTENSIONS:
            return result(True, .98, "accepted_high_confidence_extension", media_kind="image")
        if extension == ".cue":
            return result(True, .99, "accepted_cue_sheet", media_kind="disc_manifest")
        if extension not in cls.AMBIGUOUS_EXTENSIONS:
            return result(True, .9, "accepted_supported_extension", media_kind="image")

        if extension == ".bin":
            if name == "eboot.bin" and "ps3 game" in segments and "usrdir" in segments:
                return result(False, 1.0, "rejected_ps3_internal_file", excluded_by_rule="ps3_game_usrdir")
            if any(token in name for token in ("certificate", "initial data", "card uid")):
                return result(False, 1.0, "rejected_switch_cartridge_metadata", excluded_by_rule="switch_metadata")
            internal_names = {"snapshot_blob.bin", "v8_context_snapshot.bin", "codehandler.bin", "dsp_coef.bin", "dsp_rom.bin"}
            if (name in internal_names or name.endswith(("_shaders.bin", "_spirv.bin"))
                    or re.search(r"(^|_)bios_", name)):
                reason = "rejected_emulator_cache" if cls._has_emulator(segments) else "rejected_internal_binary"
                return result(False, 1.0, reason, excluded_by_rule="internal_filename")
            cue = cls._referencing_cue(path, sibling_files)
            if cue:
                return result(False, 1.0, "rejected_cue_companion_bin",
                              companion_file=cue, excluded_by_rule="cue_primary")
            if cls._has_emulator(segments) and cls._has_internal_segment(segments):
                return result(False, .99, "rejected_emulator_cache", excluded_by_rule="emulator_internal_path")
            if cls._has_internal_segment(segments):
                return result(False, .98, "rejected_pc_game_internal_binary", excluded_by_rule="internal_path")
            if platform in cls._disc_platforms:
                return result(True, .9, "accepted_platform_context", media_kind="disc_image")
            return result(False, .85, "ambiguous_insufficient_context")

        if extension == ".cso":
            if (name.endswith(("vertex.cso", "fragment.cso", "pixel.cso", "geometry.cso", "compute.cso"))
                    or "shader" in name or any(x in segments for x in ("shaders", "rendering", "graphics", "resources"))):
                return result(False, 1.0, "rejected_shader_cso", excluded_by_rule="shader")
            if platform in {Platform.PSP, Platform.PLAYSTATION_2}:
                return result(True, .95, "accepted_platform_context", media_kind="compressed_iso")
            return result(False, .8, "ambiguous_insufficient_context")

        if extension == ".md":
            if (name in {"readme.md", "changelog.md", "contributing.md", "license.md", "thirdparty.md"}
                    or name.endswith("_readme.md")):
                return result(False, 1.0, "rejected_markdown_file", excluded_by_rule="documentation_name")
            if platform == Platform.MEGA_DRIVE:
                return result(True, .9, "accepted_platform_context", media_kind="rom")
            return result(False, .99, "rejected_markdown_file")

        obvious_non_game = ("driver", "installer", "recovery", "linux distro", "software", "tools")
        context = " ".join((*segments, name))
        if any(token in context for token in obvious_non_game):
            return result(False, .95, "rejected_non_game_disk_image", excluded_by_rule="non_game_image")
        if platform not in (None, Platform.UNKNOWN) or any(x in segments for x in ("games", "roms", "discs", "isos", "iso collection")):
            return result(True, .85, "accepted_platform_context", media_kind="disc_image")
        return result(False, .65, "ambiguous_insufficient_context")

    @staticmethod
    def _platform(value: str | Platform | None) -> Platform | None:
        if isinstance(value, Platform):
            return value
        try:
            return Platform(value) if value else None
        except ValueError:
            return None

    @classmethod
    def _has_emulator(cls, segments: list[str]) -> bool:
        return any(any(segment.startswith(name) for name in cls._emulators) for segment in segments)

    @classmethod
    def _has_internal_segment(cls, segments: list[str]) -> bool:
        return any(segment.replace(" ", "") in cls._internal_segments for segment in segments)

    @staticmethod
    def _referencing_cue(path: str | Path, sibling_files: Iterable[str | Path] | None) -> str | None:
        target = (PureWindowsPath(str(path)) if "\\" in str(path) else PurePath(str(path))).name.casefold()
        siblings = list(sibling_files or ())
        for sibling in siblings:
            sibling_path = Path(sibling)
            if sibling_path.suffix.casefold() != ".cue":
                continue
            try:
                text = sibling_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                continue
            referenced = [match.casefold() for match in re.findall(r'^\s*FILE\s+"([^"]+)"', text, re.I | re.M)]
            if target in {PureWindowsPath(item).name.casefold() for item in referenced}:
                return sibling_path.name
        return None
