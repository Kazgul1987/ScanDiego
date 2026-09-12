from __future__ import annotations

import re
from pathlib import PurePath, PureWindowsPath

from app.models.platform import Platform


class PlatformDetectionService:
    _aliases = {
        Platform.PLAYSTATION_5: ("ps5", "playstation5", "playstation 5"),
        Platform.PLAYSTATION_4: ("ps4", "playstation4", "playstation 4"),
        Platform.PLAYSTATION_3: ("ps3", "playstation3", "playstation 3"),
        Platform.PLAYSTATION_2: ("ps2", "playstation2", "playstation 2"),
        Platform.PLAYSTATION: ("ps1", "psx", "playstation", "playstation 1"),
        Platform.PSP: ("psp", "playstation portable"),
        Platform.PS_VITA: ("vita", "psvita", "ps vita"),
        Platform.XBOX_SERIES: ("xbox series", "series x", "series s"),
        Platform.XBOX_ONE: ("xbox one", "xboxone"),
        Platform.XBOX_360: ("xbox 360", "xbox360", "x360"),
        Platform.XBOX: ("xbox", "original xbox"),
        Platform.SWITCH: ("switch", "nintendo switch"),
        Platform.NINTENDO_3DS: ("3ds", "nintendo 3ds"),
        Platform.NINTENDO_DS: ("nds", "nintendo ds"),
        Platform.GAME_BOY_ADVANCE: ("gba", "game boy advance", "gameboy advance"),
        Platform.GAME_BOY_COLOR: ("gbc", "game boy color", "gameboy color"),
        Platform.GAME_BOY: ("game boy", "gameboy"),
        Platform.GAMECUBE: ("gamecube", "game cube", "ngc"),
        Platform.WII_U: ("wii u", "wiiu"),
        Platform.WII: ("wii",),
        Platform.NINTENDO_64: ("n64", "nintendo 64"),
        Platform.SNES: ("snes", "super nintendo", "super famicom"),
        Platform.NES: ("nes", "nintendo entertainment system", "famicom"),
        Platform.MEGA_DRIVE: ("mega drive", "megadrive", "genesis"),
        Platform.SEGA_CD: ("sega cd", "segacd", "mega cd", "megacd"),
        Platform.SATURN: ("saturn", "sega saturn"),
        Platform.DREAMCAST: ("dreamcast", "sega dreamcast"),
        Platform.PC: ("pc", "windows", "win", "pc games", "windows games"),
    }
    _extensions = {
        ".xci": Platform.SWITCH, ".nsp": Platform.SWITCH, ".nsz": Platform.SWITCH,
        ".xcz": Platform.SWITCH, ".3ds": Platform.NINTENDO_3DS,
        ".cia": Platform.NINTENDO_3DS, ".nds": Platform.NINTENDO_DS,
        ".gba": Platform.GAME_BOY_ADVANCE, ".gbc": Platform.GAME_BOY_COLOR,
        ".gb": Platform.GAME_BOY, ".n64": Platform.NINTENDO_64,
        ".z64": Platform.NINTENDO_64, ".v64": Platform.NINTENDO_64,
        ".sfc": Platform.SNES, ".smc": Platform.SNES,
        ".gen": Platform.MEGA_DRIVE, ".md": Platform.MEGA_DRIVE,
        ".wbfs": Platform.WII,
    }

    def detect(self, path: str | PurePath) -> Platform:
        contextual = self.detect_context(path)
        if contextual != Platform.UNKNOWN:
            return contextual
        raw = str(path)
        suffix = PureWindowsPath(raw).suffix.lower()
        return self._extensions.get(suffix, Platform.UNKNOWN)

    def detect_context(self, path: str | PurePath, max_directory_depth: int | None = None) -> Platform:
        """Detect an explicit platform folder, without inferring from the extension.

        ``max_directory_depth`` is relative to the supplied path and lets callers
        distinguish collection folders near a scan root from deeply nested data.
        """
        raw = str(path)
        parts = PureWindowsPath(raw).parts if "\\" in raw else PurePath(raw).parts
        directories = parts[:-1]
        if max_directory_depth is not None:
            directories = directories[:max_directory_depth]
        for part in reversed(directories):
            normalized = re.sub(r"[-_.]+", " ", part).strip().casefold()
            compact = normalized.replace(" ", "")
            for platform, aliases in self._aliases.items():
                if any(normalized == alias or compact == alias.replace(" ", "") for alias in aliases):
                    return platform
        return Platform.UNKNOWN

    @staticmethod
    def normalize_external(name: str) -> str:
        """Map provider platform labels through one conservative central mapping."""
        value = re.sub(r"[-_.]+", " ", name).strip().casefold()
        if value in {"pc", "windows", "win", "pc (microsoft windows)"}:
            return "PC"
        if value.startswith("playstation") or value in {"ps1", "ps2", "ps3", "ps4", "ps5", "ps vita", "psp"}:
            return "PlayStation"
        if value.startswith("xbox"):
            return "Xbox"
        if (value.startswith("nintendo") or value.startswith("wii") or value in
                {"switch", "gamecube", "game boy", "game boy color", "game boy advance", "nes", "snes"}):
            return "Nintendo"
        if any(token in value for token in ("sega", "dreamcast", "saturn", "mega drive", "genesis")):
            return "Sega"
        return "Unknown"

    @staticmethod
    def family(name: str) -> str:
        """Return the broad ScanDiego family used for metadata comparison."""
        value = name.casefold()
        if value == "pc" or value in {"windows", "win", "pc (microsoft windows)"}: return "PC"
        if "playstation" in value or value.startswith("ps"): return "PlayStation"
        if "xbox" in value: return "Xbox"
        if any(x in value for x in ("nintendo", "switch", "wii", "gamecube", "game boy", "snes", "nes")): return "Nintendo"
        if any(x in value for x in ("sega", "dreamcast", "saturn", "mega drive", "genesis")): return "Sega"
        return "Unknown"
