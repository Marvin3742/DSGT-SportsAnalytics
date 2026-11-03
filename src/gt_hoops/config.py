from pathlib import Path

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
ESPN_CORE_URL = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
)
GT_TEAM_ID = 59
SEASONS = [2026, 2027]
LOCAL_TZ = "America/New_York"

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
