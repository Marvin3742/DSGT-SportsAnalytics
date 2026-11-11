import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from cbb.espn import EspnClient
from cbb.metrics import add_game_metrics, player_seasons, team_seasons
from cbb.parse import (
    parse_conferences,
    parse_games,
    parse_player_box,
    parse_players,
    parse_team_games,
    parse_teams,
)

log = logging.getLogger(__name__)

TABLES = ("teams", "games", "team_games", "player_box", "players")


def build(seasons, team_ids=None, roster_team_ids=(), client=None, workers=4):
    """Scrape seasons (all of Division I unless team_ids is given) into DataFrames by table."""
    client = client or EspnClient()
    d1_team_ids = {int(team["id"]) for team in client.teams()}
    tables = {name: [] for name in TABLES}
    for season in seasons:
        season_tables = build_season(
            client,
            season,
            team_ids,
            set(roster_team_ids) | (team_ids or set()),
            d1_team_ids,
            workers,
        )
        for name, rows in season_tables.items():
            tables[name].extend(rows)
    return to_frames(tables)


def to_frames(tables):
    """Turn rows keyed by table name into DataFrames and add the derived metric tables."""
    frames = {name: pd.DataFrame(rows).convert_dtypes() for name, rows in tables.items()}
    frames["team_games"] = add_game_metrics(frames["team_games"])
    frames["team_seasons"] = team_seasons(frames["team_games"], frames["teams"]).convert_dtypes()
    frames["player_seasons"] = player_seasons(
        frames["player_box"], frames["team_games"]
    ).convert_dtypes()
    return frames


def build_season(client, season, team_ids, roster_team_ids, d1_team_ids, workers):
    """Scrape one season and return its rows keyed by table name."""
    dates = client.calendar(season)
    boards = _parallel(lambda date: client.scoreboard(date, season), dates, workers)
    all_events = list({event["id"]: event for board in boards for event in board}.values())
    events = [e for e in all_events if team_ids is None or _event_team_ids(e) & team_ids]
    final_ids = [e["id"] for e in events if e["competitions"][0]["status"]["type"]["completed"]]
    log.info("%s season: %d games, %d final", season, len(events), len(final_ids))
    fetched = _parallel(
        lambda game_id: _summary_or_none(client, game_id, season),
        final_ids,
        workers,
        label=f"{season} box scores",
    )
    summaries = {game_id: s for game_id, s in zip(final_ids, fetched, strict=True) if s}
    player_box = [row for s in summaries.values() for row in parse_player_box(s)]
    players = [
        row
        for team_id in sorted(roster_team_ids)
        for row in _team_players(client, team_id, season, player_box)
    ]
    return {
        "teams": parse_teams(events, parse_conferences(all_events), d1_team_ids),
        "games": parse_games(events, summaries),
        "team_games": parse_team_games(events, summaries),
        "player_box": player_box,
        "players": players,
    }


def write_tables(tables, out_dir):
    """Write each table to <out_dir>/<name>.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(out_dir / f"{name}.csv", index=False)


def _team_players(client, team_id, season, player_box):
    """Return players rows for a team's roster plus anyone in its box scores missing from it."""
    athletes = client.roster(team_id, season).get("athletes", [])
    on_roster = {int(a["id"]) for a in athletes}
    missing = {r["player_id"] for r in player_box if r["team_id"] == team_id} - on_roster
    athletes += [client.athlete(player_id, season) for player_id in sorted(missing)]
    return parse_players(athletes, season, team_id)


def _summary_or_none(client, game_id, season):
    """Fetch a summary, skipping games ESPN rejects; network failures still abort the run."""
    try:
        return client.summary(game_id, season)
    except requests.HTTPError as error:
        log.warning("Skipping box score for game %s: %s", game_id, error)
        return None


def _event_team_ids(event):
    """Return the set of team ids playing in an event."""
    return {int(c["id"]) for c in event["competitions"][0]["competitors"]}


def _parallel(fn, items, workers, label=None):
    """Apply fn to items on a thread pool, preserving order, logging progress, failing fast."""
    results = []
    with ThreadPoolExecutor(workers) as pool:
        try:
            for done, result in enumerate(pool.map(fn, items), 1):
                results.append(result)
                if label and done % 500 == 0:
                    log.info("%s: %d/%d", label, done, len(items))
        except BaseException:
            pool.shutdown(cancel_futures=True)
            raise
    return results
