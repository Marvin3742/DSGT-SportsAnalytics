import tomllib
from pathlib import Path

SITE_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
CORE_API_URL = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
)
DIVISION_I_GROUP = 50
LOCAL_TZ = "America/New_York"

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "cbb.toml"
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
EXPORTS_DIR = ROOT_DIR / "data" / "exports"


def load_settings(path=CONFIG_PATH):
    """Read the seasons, teams, and roster teams that `cbb update` scrapes."""
    with open(path, "rb") as file:
        return tomllib.load(file)
