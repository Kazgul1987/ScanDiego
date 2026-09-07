from app.models.content import ContentDetectionResult, MediaContentType
from app.services.content_association_service import ContentAssociationService


def detection(title="Game", base_id=None):
    return ContentDetectionResult(MediaContentType.DLC, title, base_content_id=base_id, confidence=.9)


def test_same_title_and_platform_associates():
    result = ContentAssociationService().associate(detection(), "Switch", [{"id": 1, "title": "Game", "platform": "Switch", "has_base": 1}])
    assert result.parent_game_id == 1


def test_platform_conflict_and_ambiguous_parent_are_not_associated():
    service = ContentAssociationService()
    assert service.associate(detection(), "Switch", [{"id": 1, "title": "Game", "platform": "PS2"}]).parent_game_id is None
    result = service.associate(detection(), "Switch", [
        {"id": 1, "title": "Game", "platform": "Switch", "has_base": 1},
        {"id": 2, "title": "Game", "platform": "Switch", "has_base": 1},
    ])
    assert result.parent_game_id is None and result.ambiguous


def test_exact_technical_id_wins_and_manual_lock_is_preserved():
    games = [
        {"id": 1, "title": "Wrong", "platform": "Switch", "content_id": "0100A"},
        {"id": 2, "title": "Game", "platform": "Switch", "content_id": "other"},
    ]
    service = ContentAssociationService()
    assert service.associate(detection(base_id="0100A"), "Switch", games).parent_game_id == 1
    locked = service.associate(detection(base_id="0100A"), "Switch", games,
                               {"id": 4, "game_id": 2, "content_locked": 1})
    assert locked.parent_game_id == 2 and locked.reason == "manual"
