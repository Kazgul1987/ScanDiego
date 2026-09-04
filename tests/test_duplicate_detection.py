from app.services.duplicate_detection_service import DuplicateDetectionService, DuplicateStatus


def entry(**changes):
    value = {"title": "Game", "platform": "PC", "file_size": 100, "file_hash": None, "hash_type": None}
    value.update(changes)
    return value


def test_same_title_platform_and_size_is_probable():
    assert DuplicateDetectionService().compare(entry(), entry()) == DuplicateStatus.PROBABLE


def test_same_title_on_other_platform_is_not_duplicate():
    assert DuplicateDetectionService().compare(entry(), entry(platform="Xbox")) == DuplicateStatus.NONE


def test_different_size_is_possible():
    assert DuplicateDetectionService().compare(entry(), entry(file_size=200)) == DuplicateStatus.POSSIBLE


def test_identical_hash_is_confirmed():
    assert DuplicateDetectionService().compare(entry(file_hash="abc", hash_type="sha256"), entry(file_hash="abc", hash_type="sha256")) == DuplicateStatus.CONFIRMED
