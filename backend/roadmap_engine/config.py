from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "opportunities.db"
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
EVIDENCE_FETCH_TIMEOUT_SECONDS = 8
EVIDENCE_CACHE_TTL_HOURS = 24

