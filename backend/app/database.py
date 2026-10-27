from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    api_key = settings.supabase_secret_key or settings.supabase_key
    return create_client(
        settings.supabase_url,
        api_key,
    )


supabase: Client = get_supabase_client()
