# config.py

import os

# YouTube API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Maximum number of playlists to fetch per query
MAX_RESULTS_PER_QUERY = 25

# Preserve the old import-time constant for callers that still expect it,
# while keeping a runtime fallback for request-time lookups.
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()


def get_youtube_api_key() -> str:
    api_key = YOUTUBE_API_KEY or os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY not set. Please set it as an environment variable."
        )
    return api_key
