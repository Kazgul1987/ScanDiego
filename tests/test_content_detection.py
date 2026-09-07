from pathlib import Path

import pytest

from app.models.content import MediaContentType
from app.services.content_detection_service import ContentDetectionService
from app.services.version_detection_service import VersionDetectionService


@pytest.mark.parametrize("name,kind,title,version", [
    ("Super Smash Bros Ultimate.nsp", MediaContentType.BASE_GAME, "Super Smash Bros Ultimate", None),
    ("Super Smash Bros Ultimate Update 13.0.2.nsp", MediaContentType.UPDATE, "Super Smash Bros Ultimate", "13.0.2"),
    ("Super Smash Bros Ultimate Joker DLC.nsp", MediaContentType.DLC, "Super Smash Bros Ultimate", None),
    ("The Sims 4 Seasons Expansion Pack.nsp", MediaContentType.DLC, "The Sims 4", None),
    ("Resident Evil 4 Demo.nsp", MediaContentType.DEMO, "Resident Evil 4", None),
    ("The Last of Us Part II.nsp", MediaContentType.BASE_GAME, "The Last of Us Part II", None),
])
def test_filename_content_detection(tmp_path, name, kind, title, version):
    path = tmp_path / name
    path.write_bytes(b"unreadable-container")
    result = ContentDetectionService().detect(path)
    assert result.content_type is kind
    assert result.title == title
    assert result.version == version


@pytest.mark.parametrize("value,expected", [
    ("Game v1.2.0", "1.2.0"), ("Game Version 1.4", "1.4"),
    ("Game Patch 2.1", "2.1"), ("Game [v65536]", "65536"),
])
def test_version_detection(value, expected):
    assert VersionDetectionService().detect(value) == expected
