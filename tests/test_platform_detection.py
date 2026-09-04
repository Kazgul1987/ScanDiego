import pytest
from app.models.platform import Platform
from app.services.platform_detection_service import PlatformDetectionService


@pytest.mark.parametrize(("path", "expected"), [
    (r"D:\ROMs\PS2\Gran Turismo 4.iso", Platform.PLAYSTATION_2),
    (r"E:\Games\Switch\Zelda.xci", Platform.SWITCH),
    (r"F:\ROMs\GameCube\Metroid Prime.rvz", Platform.GAMECUBE),
    (r"F:\ROMs\Super Famicom\Mario.sfc", Platform.SNES),
    (r"F:\unsorted\Pokemon.gba", Platform.GAME_BOY_ADVANCE),
    (r"F:\unsorted\mystery.iso", Platform.UNKNOWN),
])
def test_detect(path, expected):
    assert PlatformDetectionService().detect(path) == expected
