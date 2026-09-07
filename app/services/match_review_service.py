from app.models.metadata import MetadataStatus

class MatchReviewService:
    """Backend used by both Match prüfen and Match ändern."""
    def __init__(self, db, provider, matcher): self.db, self.provider, self.matcher = db, provider, matcher
    def candidates(self, game_id): return self.db.list_candidates(game_id)
    def search(self, game_id: int, text: str):
        local = self.db._conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
        ranked = self.matcher.rank(text, local["platform"], self.provider.search_game(text, local["platform"]), local["release_year"])
        self.db.save_candidates(game_id, self.provider.name, ranked)
        return self.candidates(game_id)
    def apply(self, game_id: int, external_id: str, score: float = 100):
        external = self.provider.get_game(external_id)
        self.db.apply_candidate_manually(game_id, external, self.provider.name, score)
    def no_match(self, game_id: int):
        self.db.set_metadata_status(game_id, MetadataStatus.NO_MATCH)
        self.db.save_candidates(game_id, self.provider.name, [])
