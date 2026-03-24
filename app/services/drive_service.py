from __future__ import annotations

import ctypes
import logging
import string
from ctypes import wintypes
from pathlib import Path

from app.models.drive import DriveInfo

LOGGER = logging.getLogger(__name__)

DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3


class DriveService:
    def list_external_drives(self) -> list[DriveInfo]:
        drives: list[DriveInfo] = []
        system_drive = Path.home().drive.upper()

        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
            if drive_type not in (DRIVE_REMOVABLE, DRIVE_FIXED):
                continue
            if f"{letter}:".upper() == system_drive:
                continue

            info = self._get_volume_info(root)
            if info is None:
                continue
            label, serial, filesystem = info
            drives.append(
                DriveInfo(
                    letter=f"{letter}:",
                    label=label,
                    volume_serial=serial,
                    filesystem=filesystem,
                )
            )

        return drives

    def _get_volume_info(self, root: str) -> tuple[str, str, str] | None:
        volume_name = ctypes.create_unicode_buffer(261)
        filesystem_name = ctypes.create_unicode_buffer(261)
        serial_number = wintypes.DWORD()
        max_component_len = wintypes.DWORD()
        filesystem_flags = wintypes.DWORD()

        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            volume_name,
            ctypes.sizeof(volume_name),
            ctypes.byref(serial_number),
            ctypes.byref(max_component_len),
            ctypes.byref(filesystem_flags),
            filesystem_name,
            ctypes.sizeof(filesystem_name),
        )
        if not ok:
            LOGGER.warning("Could not read volume information for %s", root)
            return None

        serial_hex = f"{serial_number.value:08X}"
        return volume_name.value, serial_hex, filesystem_name.value
