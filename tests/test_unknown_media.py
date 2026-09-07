from app.config import is_unknown_media_candidate


def test_unknown_extension_is_candidate():
    assert is_unknown_media_candidate(".xyz")


def test_companion_media_and_archive_extensions_are_excluded():
    for extension in (".jpg", ".txt", ".iso", ".zip"):
        assert not is_unknown_media_candidate(extension)
