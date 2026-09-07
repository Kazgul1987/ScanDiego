class MetadataCompletenessService:
    """Single policy for matched versus incomplete provider records."""
    @staticmethod
    def status(game) -> str:
        present = sum(bool(value) for value in (
            game.title, game.release_date or game.release_year, game.publisher, game.developer
        ))
        return "matched" if present >= 3 else "incomplete"
