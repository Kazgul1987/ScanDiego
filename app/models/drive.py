from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DriveInfo:
    letter: str
    label: str
    volume_serial: str
    filesystem: str

    @property
    def display_name(self) -> str:
        return f"{self.letter} ({self.label or 'Ohne Label'})"
