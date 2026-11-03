import json
from pathlib import Path

import pytest

from gt_hoops.config import GT_TEAM_ID
from gt_hoops.parse import parse_games, parse_player_box, parse_players, parse_team_box

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    """Load a JSON fixture by file name."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def summary():
    """Box score summary for GT's 56-52 OT win over Maryland Eastern Shore on 2025-11-03."""
    return load("summary_final.json")


@pytest.fixture
def games(summary):
    """Games rows for one final and one upcoming game."""
    events = load("schedule_events.json")
    final, upcoming = events
    summaries = {final["id"]: summary, upcoming["id"]: load("summary_upcoming_header.json")}
    return parse_games(events, summaries)


def test_final_game(games):
    game = games[0]
    assert game["game_date"] == "2025-11-03"
    assert game["opponent"] == "Maryland Eastern Shore"
    assert (game["gt_score"], game["opponent_score"], game["result"]) == (56, 52, "W")
    assert game["margin"] == 4
    assert game["overtimes"] == 1
    assert game["location"] == "Home"
    assert game["gt_record"] == "1-0"


def test_upcoming_game_has_no_result(games):
    game = games[1]
    assert not game["completed"]
    assert game["opponent"] == "Hampton"
    assert game["gt_score"] is None
    assert game["result"] is None
    assert game["overtimes"] is None


def test_team_box(summary):
    rows = {row["team_id"]: row for row in parse_team_box(summary)}
    gt = rows[GT_TEAM_ID]
    assert gt["is_gt"] and gt["opponent_id"] == 2379
    assert (gt["pts"], gt["fgm"], gt["fga"], gt["fg3m"], gt["fg3a"]) == (56, 21, 60, 5, 26)
    assert gt["fg_pct"] == 0.35
    assert rows[2379]["tov"] == 19


def test_player_box_matches_team_totals(summary):
    players = parse_player_box(summary)
    teams = {row["team_id"]: row for row in parse_team_box(summary)}
    for team_id, team in teams.items():
        played = [p for p in players if p["team_id"] == team_id and not p["did_not_play"]]
        assert sum(p["pts"] for p in played) == team["pts"]
        assert sum(p["fga"] for p in played) == team["fga"]


def test_player_box_dnp_rows_have_no_stats(summary):
    dnps = [p for p in parse_player_box(summary) if p["did_not_play"]]
    assert len(dnps) == 7
    assert all(p["pts"] is None and p["min"] is None for p in dnps)


def test_players():
    rows = parse_players(load("roster_athletes.json"), 2026)
    assert rows[0]["player"] == "Eric Chatfield Jr."
    assert rows[0]["season"] == 2026
    assert (rows[0]["height_in"], rows[0]["weight_lb"]) == (72, 160)
