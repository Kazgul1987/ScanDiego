import json

from app.models.content import MediaContentType
from app.services.switch_content_detection_service import FIXTURE_MAGIC, SwitchContentDetectionService


def fixture(tmp_path, title_id, **extra):
    path = tmp_path / "fixture.nsp"
    path.write_bytes(b"PFS0" + FIXTURE_MAGIC + json.dumps({"title_id": title_id, **extra}).encode() + b"\0payload")
    return path


def test_switch_title_id_relationships():
    classify = SwitchContentDetectionService.classify_title_id
    assert classify("0100ABCD12345000") == (MediaContentType.BASE_GAME, "0100ABCD12345000")
    assert classify("0100ABCD12345800") == (MediaContentType.UPDATE, "0100ABCD12345000")
    assert classify("0100ABCD12346001") == (MediaContentType.DLC, "0100ABCD12345000")


def test_clear_bounded_switch_metadata(tmp_path):
    result = SwitchContentDetectionService().parse(fixture(tmp_path, "0100ABCD12345800", title="Game", version="2.0", region="EU"))
    assert result.readable and result.content_type is MediaContentType.UPDATE
    assert result.base_content_id == "0100ABCD12345000"
    assert (result.title, result.version, result.region) == ("Game", "2.0", "EU")


def test_unreadable_and_missing_container_do_not_raise(tmp_path):
    path = tmp_path / "encrypted.xci"; path.write_bytes(b"HEAD" * 100)
    result = SwitchContentDetectionService().parse(path)
    assert result.supported and not result.readable and result.warnings
    missing = SwitchContentDetectionService().parse(tmp_path / "missing.nsp")
    assert missing.supported and not missing.readable
