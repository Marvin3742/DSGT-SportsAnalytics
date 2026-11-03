import pandas as pd

KEYS = {
    "teams": ["team_id", "season"],
    "games": ["game_id"],
    "team_games": ["game_id", "team_id"],
    "player_box": ["game_id", "team_id", "player_id"],
    "players": ["player_id", "season", "team_id"],
}
MAX_BOX_SCORE_MISMATCH_RATE = 0.01


def load_tables(data_dir):
    """Read every pipeline CSV in a folder into DataFrames keyed by table name."""
    return {name: pd.read_csv(data_dir / f"{name}.csv", low_memory=False) for name in KEYS}


def validate(tables):
    """Return (errors, warnings) for the tables; errors mean the pipeline output is broken.

    Box scores whose player totals don't match the team totals are warnings, since ESPN's own data
    has a few of these, unless they exceed MAX_BOX_SCORE_MISMATCH_RATE.
    """
    errors = []
    for name, keys in KEYS.items():
        duplicates = tables[name].duplicated(keys).sum()
        if duplicates:
            errors.append(f"{name}: {duplicates} duplicate rows on {keys}")

    games, team_games = tables["games"], tables["team_games"]
    if len(team_games) != 2 * len(games):
        errors.append(f"team_games has {len(team_games)} rows for {len(games)} games")

    unknown = set(team_games.team_id) - set(tables["teams"].team_id)
    if unknown:
        errors.append(f"team_games: {len(unknown)} team ids missing from teams")

    scores = team_games.merge(games, on="game_id")
    expected = scores.home_score.where(scores.team_id == scores.home_team_id, scores.away_score)
    mismatched = (scores.team_score.fillna(-1) != expected.fillna(-1)).sum()
    if mismatched:
        errors.append(f"team_games: {mismatched} team scores differ from games")

    warnings = []
    boxed = team_games[team_games.fga.notna()].set_index(["game_id", "team_id"])
    totals = (
        tables["player_box"].groupby(["game_id", "team_id"])[["pts", "fgm", "fga"]].sum()
    ).add_suffix("_players")
    joined = boxed.join(totals, how="inner")
    for team_column, player_column in (("team_score", "pts"), ("fgm", "fgm"), ("fga", "fga")):
        bad = joined[joined[team_column] != joined[f"{player_column}_players"]]
        if bad.empty:
            continue
        message = (
            f"{len(bad)} of {len(joined)} team box scores where player {player_column} "
            f"don't add up to the team's {team_column} (games: "
            f"{', '.join(map(str, bad.index.get_level_values('game_id')[:5]))}"
            f"{', ...' if len(bad) > 5 else ''})"
        )
        rate = len(bad) / len(joined)
        (errors if rate > MAX_BOX_SCORE_MISMATCH_RATE else warnings).append(message)
    return errors, warnings
