SUPPORTED_MEDIA_EXTENSIONS = frozenset({
    ".iso", ".nsp", ".xci", ".bin", ".cue", ".img", ".chd", ".cso",
    ".rvz", ".wbfs", ".wia", ".gcz", ".nsz", ".xcz", ".3ds", ".cia",
    ".gba", ".gbc", ".gb", ".nds", ".n64", ".z64", ".v64", ".sfc",
    ".smc", ".gen", ".md",
})
ARCHIVE_EXTENSIONS = frozenset({".rar", ".zip", ".7z"})
# Files commonly stored next to games are deliberately not treated as unknown media.
COMPANION_FILE_EXTENSIONS = frozenset({
    ".txt", ".nfo", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".xml", ".json", ".md", ".pdf", ".sfv", ".sha1", ".sha256",
    ".log", ".ini", ".cfg",
})
SCAN_BATCH_SIZE = 250
APP_VERSION = "0.6.0"


def is_unknown_media_candidate(extension: str) -> bool:
    """Return whether a file in an explicit Games/ROMs root merits review."""
    normalized = extension.casefold()
    return bool(normalized and normalized not in SUPPORTED_MEDIA_EXTENSIONS
                and normalized not in ARCHIVE_EXTENSIONS
                and normalized not in COMPANION_FILE_EXTENSIONS)
