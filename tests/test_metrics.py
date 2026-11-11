import pandas as pd
import pytest

GT, UMES = 59, 2379
UMES_GAME = 401820296


def row(df, **keys):
    """Return the single DataFrame row whose columns match keys."""
    match = df
    for column, value in keys.items():
        match = match[match[column] == value]
    assert len(match) == 1
    return match.iloc[0]


def possessions(team, opponent):
    """Average of both teams' possession estimates for a game."""
    estimate = lambda r: r.fga - r.oreb + r.tov + 0.475 * r.fta  # noqa: E731
    return (estimate(team) + estimate(opponent)) / 2


def test_game_metrics_use_both_teams(frames):
    games = frames["team_games"]
    gt = row(games, game_id=UMES_GAME, team_id=GT)
    umes = row(games, game_id=UMES_GAME, team_id=UMES)
    expected = possessions(gt, umes)
    assert gt.possessions == umes.possessions == pytest.approx(expected, abs=0.05)
    assert gt.pace == pytest.approx(40 * expected / 45, abs=0.05)
    assert gt.ortg == pytest.approx(100 * 56 / expected, abs=0.05)
    assert gt.drtg == umes.ortg
    assert gt.net_rtg == -umes.net_rtg
    assert gt.efg_pct == pytest.approx((gt.fgm + 0.5 * gt.fg3m) / gt.fga, abs=0.0005)
    assert gt.orb_pct == pytest.approx(gt.oreb / (gt.oreb + umes.dreb), abs=0.0005)
    assert gt.opp_efg_pct == umes.efg_pct
    assert gt.opp_tov_pct == umes.tov_pct


def test_game_without_box_score_has_no_metrics(frames):
    games = frames["team_games"]
    duke_game = games[(games.team_id == GT) & (games.game_id != UMES_GAME) & games.completed]
    assert duke_game.possessions.isna().all() and duke_game.ortg.isna().all()


def test_team_seasons_record_and_rates(frames):
    seasons = frames["team_seasons"]
    games = frames["team_games"]
    overall = row(seasons, team_id=GT, season=2026, split="Overall")
    conference = row(seasons, team_id=GT, season=2026, split="Conference")
    opener = row(games, game_id=UMES_GAME, team_id=GT)
    assert overall.games == 2 and overall.wins + overall.losses == 2
    assert overall.ortg == opener.ortg
    assert conference.games == 1 and pd.isna(conference.ortg)


def test_team_season_ranks_point_the_right_way(frames):
    overall = frames["team_seasons"].query("season == 2026 and split == 'Overall'")
    gt = row(overall, team_id=GT)
    umes = row(overall, team_id=UMES)
    assert gt.net_rtg > umes.net_rtg
    assert (gt.net_rtg_rank, umes.net_rtg_rank) == (1, 2)
    assert gt.drtg < umes.drtg
    assert (gt.drtg_rank, umes.drtg_rank) == (1, 2)


def test_player_usage_adds_up_to_about_100(frames):
    players = frames["player_seasons"]
    gt = players[(players.team_id == GT) & (players.season == 2026)]
    played = frames["player_box"].query("team_id == @GT and not did_not_play")
    assert len(gt) == len(played)
    minutes_weighted = (gt.usage_pct * gt["min"]).sum() / 45
    assert 95 <= minutes_weighted <= 100.5
    top = gt.sort_values("pts").iloc[-1]
    assert top.ts_pct == pytest.approx(top.pts / (2 * (top.fga + 0.44 * top.fta)), abs=0.0005)
