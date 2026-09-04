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
        Platform.SATURN: ("saturn", "sega saturn"),
        Platform.DREAMCAST: ("dreamcast", "sega dreamcast"),
        Platform.PC: ("pc games", "windows games"),
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
        raw = str(path)
        parts = PureWindowsPath(raw).parts if "\\" in raw else PurePath(raw).parts
        for part in reversed(parts[:-1]):
            normalized = re.sub(r"[-_.]+", " ", part).strip().casefold()
            compact = normalized.replace(" ", "")
            for platform, aliases in self._aliases.items():
                if any(normalized == alias or compact == alias.replace(" ", "") for alias in aliases):
                    return platform
        suffix = PureWindowsPath(raw).suffix.lower()
        return self._extensions.get(suffix, Platform.UNKNOWN)

