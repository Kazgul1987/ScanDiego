from __future__ import annotations

import re
from pathlib import Path


class TitleNormalizationService:
    """Conservative, composable cleanup for ROM/image filenames."""

    _parenthetical = re.compile(
        r"\s*\((?:USA|Europe|Japan|World|Germany|En|De|Fr|Es|It|"
        r"Rev(?:ision)?\s*\d+|v(?:ersion)?\s*\d+(?:\.\d+)*)\)", re.I
    )
    _bracket_tags = re.compile(r"\s*\[(?:!|b|bad|v\d+(?:\.\d+)*)\]", re.I)
    _version = re.compile(r"\s+(?:v|version)\s*\d+(?:\.\d+)*(?:\.\d+)?\s*$", re.I)

    def normalize(self, filename: str) -> str:
        value = Path(filename).stem
        value = value.replace("_", " ")
        value = self._parenthetical.sub("", value)
        value = self._bracket_tags.sub("", value)
        value = self._version.sub("", value)
        value = re.sub(r"(?<=\w)\.(?=\w)", " ", value)
        return re.sub(r"\s+", " ", value).strip(" .-_")
