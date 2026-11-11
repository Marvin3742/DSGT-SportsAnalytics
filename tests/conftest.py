import json
from pathlib import Path

import pytest

from cbb.parse import (
    parse_conferences,
    parse_games,
    parse_player_box,
    parse_players,
    parse_team_games,
    parse_teams,
)
from cbb.pipeline import to_frames

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    """Load a JSON fixture by file name."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def events():
    """Scoreboard events: GT's 2025-26 opener vs UMES, GT at Duke (ACC), and the 2026-27 opener."""
    return _load("scoreboard_events.json")


@pytest.fixture
def summary():
    """Box score for GT's 56-52 OT win over Maryland Eastern Shore on 2025-11-03."""
    return _load("summary_final.json")


@pytest.fixture
def summaries(summary):
    """Summaries keyed by event id; only the UMES game has a box score."""
    return {"401820296": summary}


@pytest.fixture
def frames(events, summaries, summary):
    """Every pipeline table built from the fixtures, with GT, UMES and Duke counted as D1."""
    return to_frames(
        {
            "teams": parse_teams(events, parse_conferences(events), {59, 2379, 150}),
            "games": parse_games(events, summaries),
            "team_games": parse_team_games(events, summaries),
            "player_box": parse_player_box(summary),
            "players": parse_players(_load("roster_athletes.json"), 2026, 59),
        }
    )
