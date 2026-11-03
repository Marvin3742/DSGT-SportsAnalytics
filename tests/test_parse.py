import json
from pathlib import Path

import pandas as pd
import pytest

from cbb.lookup import resolve_team
from cbb.parse import (
    parse_conferences,
    parse_games,
    parse_player_box,
    parse_players,
    parse_team_games,
    parse_teams,
)
from cbb.validate import validate

FIXTURES = Path(__file__).parent / "fixtures"
GT, UMES, DUKE = 59, 2379, 150
UMES_GAME, DUKE_GAME = 401820296, 401820636


def load(name):
    """Load a JSON fixture by file name."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def events():
    """Scoreboard events: GT's 2025-26 opener vs UMES, GT at Duke (ACC), and the 2026-27 opener."""
    return load("scoreboard_events.json")


@pytest.fixture
def summary():
    """Box score for GT's 56-52 OT win over Maryland Eastern Shore on 2025-11-03."""
    return load("summary_final.json")


@pytest.fixture
def summaries(summary):
    """Summaries keyed by event id; only the UMES game has a box score."""
    return {str(UMES_GAME): summary}


def by_id(rows, **keys):
    """Return the single row whose columns match keys."""
    (row,) = [r for r in rows if all(r[k] == v for k, v in keys.items())]
    return row


def test_final_game(events, summaries):
    game = by_id(parse_games(events, summaries), game_id=UMES_GAME)
    assert game["game_date"] == "2025-11-03"
    assert (game["home_team"], game["away_team"]) == ("Georgia Tech", "Maryland Eastern Shore")
    assert (game["home_score"], game["away_score"], game["winner_team_id"]) == (56, 52, GT)
    assert game["overtimes"] == 1
    assert game["has_box_score"]
    assert not game["conference_game"]


def test_upcoming_game_has_no_result(events, summaries):
    game = parse_games(events, summaries)[2]
    assert not game["completed"]
    assert game["away_team"] == "Hampton"
    assert game["home_score"] is None and game["winner_team_id"] is None
    assert not game["has_box_score"]


def test_team_games_are_one_row_per_side(events, summaries):
    rows = parse_team_games(events, summaries)
    assert len(rows) == 6
    gt = by_id(rows, game_id=UMES_GAME, team_id=GT)
    umes = by_id(rows, game_id=UMES_GAME, team_id=UMES)
    assert (gt["location"], gt["result"], gt["margin"]) == ("Home", "W", 4)
    assert (umes["location"], umes["result"], umes["margin"]) == ("Away", "L", -4)
    assert (gt["fgm"], gt["fga"], gt["fg_pct"]) == (21, 60, 0.35)
    assert umes["tov"] == 19


def test_team_games_without_box_score_have_empty_stats(events, summaries):
    duke_game = by_id(parse_team_games(events, summaries), game_id=DUKE_GAME, team_id=GT)
    assert duke_game["conference_game"]
    assert duke_game["team_score"] is not None
    assert duke_game["fgm"] is None and duke_game["fg_pct"] is None


def test_running_records(events, summaries):
    rows = parse_team_games(events, summaries)
    opener = by_id(rows, game_id=UMES_GAME, team_id=GT)
    assert (opener["wins"], opener["losses"], opener["conf_wins"], opener["conf_losses"]) == (
        1,
        0,
        0,
        0,
    )
    duke_game = by_id(rows, game_id=DUKE_GAME, team_id=GT)
    won = duke_game["result"] == "W"
    assert (duke_game["wins"], duke_game["losses"]) == ((2, 0) if won else (1, 1))
    assert (duke_game["conf_wins"], duke_game["conf_losses"]) == ((1, 0) if won else (0, 1))
    assert rows[-1]["wins"] is None


def test_player_box_matches_team_totals(summary):
    players = parse_player_box(summary)
    for team_id, points in ((GT, 56), (UMES, 52)):
        played = [p for p in players if p["team_id"] == team_id and not p["did_not_play"]]
        assert sum(p["pts"] for p in played) == points
    assert {p["opponent_id"] for p in players if p["team_id"] == GT} == {UMES}


def test_player_box_dnp_rows_have_no_stats(summary):
    dnps = [p for p in parse_player_box(summary) if p["did_not_play"]]
    assert len(dnps) == 7
    assert all(p["pts"] is None and p["min"] is None for p in dnps)


def test_teams_get_season_conferences(events):
    conferences = parse_conferences(events)
    assert conferences[2] == "ACC"
    teams = {r["team_id"]: r for r in parse_teams(events, conferences, {GT, DUKE})}
    assert teams[GT]["conference"] == "ACC"
    assert teams[DUKE]["is_d1"] and not teams[UMES]["is_d1"]


def test_players():
    rows = parse_players(load("roster_athletes.json"), 2026, GT)
    assert rows[0]["team_id"] == GT
    assert rows[0]["height_in"] > 60 and rows[0]["weight_lb"] > 100


def test_resolve_team():
    teams = [
        {
            "id": "59",
            "abbreviation": "GT",
            "location": "Georgia Tech",
            "displayName": "Georgia Tech",
        },
        {"id": "61", "abbreviation": "UGA", "location": "Georgia", "displayName": "Georgia"},
        {"id": "290", "abbreviation": "GASO", "location": "Georgia Southern", "displayName": "GS"},
        {"id": "2247", "abbreviation": "GAST", "location": "Georgia State", "displayName": "GSU"},
    ]
    assert resolve_team("georgia tech", teams) == GT
    assert resolve_team("GT", teams) == GT
    assert resolve_team("59", teams) == GT
    assert resolve_team("Georgia", teams) == 61
    with pytest.raises(ValueError, match="Georgia S"):
        resolve_team("Georgia S", teams)


def test_validate_catches_bad_scores(events, summaries):
    tables = {
        "teams": parse_teams(events, parse_conferences(events), set()),
        "games": parse_games(events, summaries),
        "team_games": parse_team_games(events, summaries),
        "player_box": parse_player_box(summaries[str(UMES_GAME)]),
        "players": [],
    }
    frames = {name: pd.DataFrame(rows).convert_dtypes() for name, rows in tables.items()}
    frames["players"] = pd.DataFrame(columns=["player_id", "season", "team_id"])
    assert validate(frames) == ([], [])
    frames["team_games"].loc[0, "team_score"] = 99
    errors, _ = validate(frames)
    assert any("team scores differ" in error for error in errors)


def test_player_box_skips_athletes_without_ids(summary):
    group = summary["boxscore"]["players"][0]["statistics"][0]
    group["athletes"].append(
        {
            "athlete": {"shortName": "L. Moser"},
            "starter": False,
            "didNotPlay": True,
            "ejected": False,
            "stats": [],
        }
    )
    assert all(p["player"] != "L. Moser" for p in parse_player_box(summary))
    assert len(parse_player_box(summary)) == len(group["athletes"]) - 1 + len(
        summary["boxscore"]["players"][1]["statistics"][0]["athletes"]
    )
