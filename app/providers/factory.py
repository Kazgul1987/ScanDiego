from app.providers.igdb import IGDBProvider
from app.providers.steamgriddb import SteamGridDBProvider

class UnknownProviderError(ValueError): pass

def create_metadata_provider(settings):
    if settings.metadata_provider == "igdb":
        return IGDBProvider(settings.igdb_client_id, settings.igdb_client_secret)
    raise UnknownProviderError(f"Unbekannter Metadata-Provider: {settings.metadata_provider}")

def create_artwork_provider(settings):
    if settings.artwork_provider == "steamgriddb":
        return SteamGridDBProvider(settings.steamgriddb_api_key)
    raise UnknownProviderError(f"Unbekannter Artwork-Provider: {settings.artwork_provider}")
