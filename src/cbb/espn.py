import gzip
import json
import time

import requests

from cbb.config import CORE_API_URL, DIVISION_I_GROUP, RAW_DIR, SITE_API_URL


class EspnClient:
    """Client for ESPN's public men's college basketball API that caches finished data locally."""

    def __init__(self, raw_dir=RAW_DIR, delay=0.25, session=None):
        self.raw_dir = raw_dir
        self.delay = delay
        self.session = session or requests.Session()

    def teams(self):
        """Return ESPN's current list of Division I teams."""
        data = self._get(f"{SITE_API_URL}/teams", groups=DIVISION_I_GROUP, limit=500)
        return [entry["team"] for entry in data["sports"][0]["leagues"][0]["teams"]]

    def calendar(self, season):
        """Return a season's game dates as YYYYMMDD strings."""
        data = self._get(
            f"{SITE_API_URL}/scoreboard", dates=f"{season}0115", groups=DIVISION_I_GROUP, limit=1
        )
        return [day[:10].replace("-", "") for day in data["leagues"][0]["calendar"]]

    def scoreboard(self, date, season):
        """Return a day's Division I events, caching the day once every game is over."""
        name = f"scoreboards/{date}.json.gz"
        cached = self._load(season, name)
        if cached is not None:
            return cached
        events = self._get(
            f"{SITE_API_URL}/scoreboard", dates=date, groups=DIVISION_I_GROUP, limit=500
        )["events"]
        if all(e["competitions"][0]["status"]["type"]["state"] == "post" for e in events):
            self._save(events, season, name)
        return events

    def summary(self, game_id, season):
        """Return a game's header and box score, caching play-by-play separately once final."""
        name = f"games/{game_id}.json.gz"
        cached = self._load(season, name)
        if cached is not None:
            return cached
        data = self._get(f"{SITE_API_URL}/summary", event=game_id)
        game = {key: data.get(key) for key in ("header", "boxscore", "gameInfo")}
        if is_final(game):
            self._save(game, season, name)
            plays = {key: data.get(key) for key in ("plays", "winprobability")}
            self._save(plays, season, f"plays/{game_id}.json.gz")
        return game

    def roster(self, team_id, season):
        """Return a team's roster payload for a season."""
        data = self._get(f"{SITE_API_URL}/teams/{team_id}/roster", season=season)
        self._save(data, season, f"rosters/{team_id}.json.gz")
        return data

    def athlete(self, player_id, season):
        """Return a player's bio for a season, for players missing from the roster endpoint."""
        name = f"athletes/{player_id}.json.gz"
        cached = self._load(season, name)
        if cached is not None:
            return cached
        data = self._get(f"{CORE_API_URL}/seasons/{season}/athletes/{player_id}")
        self._save(data, season, name)
        return data

    def _get(self, url, retries=4, **params):
        """GET a URL, retrying on connection failures, rate limits, and server errors."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == retries - 1:
                    raise
            else:
                if response.status_code != 429 and response.status_code < 500:
                    break
            time.sleep(2 ** (attempt + 1))
        response.raise_for_status()
        time.sleep(self.delay)
        return response.json()

    def _load(self, season, name):
        """Return a cached payload, or None if it isn't cached."""
        path = self.raw_dir / str(season) / name
        if not path.exists():
            return None
        with gzip.open(path, "rt") as file:
            return json.load(file)

    def _save(self, data, season, name):
        """Write a payload under data/raw/<season>/, replacing any previous copy atomically."""
        path = self.raw_dir / str(season) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".partial")
        with gzip.open(partial, "wt") as file:
            json.dump(data, file)
        partial.replace(path)


def is_final(summary):
    """Return True if the summary's game has finished."""
    return summary["header"]["competitions"][0]["status"]["type"]["completed"]
