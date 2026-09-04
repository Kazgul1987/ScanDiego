import pytest
from app.services.title_normalization_service import TitleNormalizationService


@pytest.mark.parametrize(("filename", "expected"), [
    ("The_Legend_of_Zelda_Tears_of_the_Kingdom.xci", "The Legend of Zelda Tears of the Kingdom"),
    ("Gran.Turismo.4 (USA) (Rev 1).iso", "Gran Turismo 4"),
    ("Metroid Prime [!] [b].rvz", "Metroid Prime"),
    ("Game__Name (Europe) v1.2.nsp", "Game Name"),
])
def test_normalize(filename, expected):
    assert TitleNormalizationService().normalize(filename) == expected
