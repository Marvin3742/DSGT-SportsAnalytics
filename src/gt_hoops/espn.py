import json
import time

import requests

from gt_hoops.config import ESPN_BASE_URL, ESPN_CORE_URL, GT_TEAM_ID, RAW_DIR

REGULAR_SEASON = 2
POSTSEASON = 3


class EspnClient:
    """Client for ESPN's public men's college basketball API that caches raw JSON locally."""

    def __init__(self, raw_dir=RAW_DIR, delay=0.5, session=None):
        self.raw_dir = raw_dir
        self.delay = delay
        self.session = session or requests.Session()

    def schedule(self, season):
        """Return GT's regular season and postseason events for a season."""
        events = []
        for season_type in (REGULAR_SEASON, POSTSEASON):
            data = self._get(
                f"{ESPN_BASE_URL}/teams/{GT_TEAM_ID}/schedule",
                season=season,
                seasontype=season_type,
            )
            self._save(data, season, f"schedule_{season_type}.json")
            events.extend(data.get("events", []))
        return events

    def roster(self, season):
        """Return GT's roster payload for a season."""
        data = self._get(f"{ESPN_BASE_URL}/teams/{GT_TEAM_ID}/roster", season=season)
        self._save(data, season, "roster.json")
        return data

    def summary(self, game_id, season):
        """Return a game summary, reusing the cached copy once the game is final."""
        cached = self._load(season, f"games/{game_id}.json")
        if cached:
            return cached
        data = self._get(f"{ESPN_BASE_URL}/summary", event=game_id)
        if is_final(data):
            self._save(data, season, f"games/{game_id}.json")
        return data

    def athlete(self, player_id, season):
        """Return a player's bio for a season, for players missing from the roster endpoint."""
        name = f"athletes/{player_id}.json"
        cached = self._load(season, name)
        if cached:
            return cached
        data = self._get(f"{ESPN_CORE_URL}/seasons/{season}/athletes/{player_id}")
        self._save(data, season, name)
        return data

    def _get(self, url, retries=3, **params):
        """GET a URL, retrying on rate limits and server errors."""
        for attempt in range(retries):
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code != 429 and response.status_code < 500:
                break
            time.sleep(2 ** (attempt + 1))
        response.raise_for_status()
        time.sleep(self.delay)
        return response.json()

    def _load(self, season, name):
        """Return a cached raw payload, or None if it isn't cached."""
        path = self.raw_dir / str(season) / name
        return json.loads(path.read_text()) if path.exists() else None

    def _save(self, data, season, name):
        """Write a raw payload under data/raw/<season>/."""
        path = self.raw_dir / str(season) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))


def is_final(summary):
    """Return True if the summary's game has finished."""
    return summary["header"]["competitions"][0]["status"]["type"]["completed"]
