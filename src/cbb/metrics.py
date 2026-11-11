import pandas as pd

POSSESSION_FT_WEIGHT = 0.475
USAGE_FT_WEIGHT = 0.44
KEYS = ["season", "team_id"]

BOX_COLUMNS = [
    "team_score",
    "fgm",
    "fga",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "oreb",
    "dreb",
    "ast",
    "tov",
]
PLAYER_TOTALS = ["min", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb"]
PLAYER_TOTALS += ["ast", "stl", "blk", "tov", "pf"]

RANKED = {
    "net_rtg": True,
    "ortg": True,
    "drtg": False,
    "pace": True,
    "efg_pct": True,
    "tov_pct": False,
    "orb_pct": True,
    "ft_rate": True,
    "opp_efg_pct": False,
    "opp_tov_pct": True,
    "opp_orb_pct": False,
    "opp_ft_rate": False,
}


def add_game_metrics(team_games):
    """Add possessions, pace, ratings, and both teams' four factors to each team game."""
    games = _with_opponent_stats(team_games)
    metrics = pd.DataFrame(_rates(games), index=games.index).set_axis(team_games.index)
    return team_games.assign(**_rounded(metrics))


def team_seasons(team_games, teams):
    """Aggregate completed team games into season rates per split, ranked among D1 teams."""
    games = _with_opponent_stats(team_games[team_games.completed.fillna(False).astype(bool)])
    games["won"] = games.result == "W"
    has_box = games.fga.notna()
    frames = []
    for split, mask in _split_masks(games).items():
        subset = games[mask]
        record = subset.groupby(KEYS).agg(
            games=("game_id", "size"),
            wins=("won", "sum"),
            points=("team_score", "sum"),
            points_allowed=("opponent_score", "sum"),
        )
        sums = [*BOX_COLUMNS, *(f"opp_{c}" for c in BOX_COLUMNS), "minutes"]
        totals = subset[has_box[mask]].groupby(KEYS)[sums].sum()
        frames.append(record.join(totals).reset_index().assign(split=split))
    d1 = teams.loc[teams.is_d1.fillna(False).astype(bool), [*KEYS, "team", "conference"]]
    df = pd.concat(frames, ignore_index=True).merge(d1, on=KEYS)
    df = df.assign(
        losses=df.games - df.wins,
        ppg=df.points / df.games,
        opp_ppg=df.points_allowed / df.games,
        margin=(df.points - df.points_allowed) / df.games,
        **_rates(df),
    )
    for column, higher_is_better in RANKED.items():
        df[f"{column}_rank"] = (
            df.groupby(["season", "split"])[column]
            .rank(ascending=not higher_is_better, method="min")
            .astype("Int64")
        )
    columns = [*KEYS, "split", "team", "conference", "games", "wins", "losses"]
    columns += ["ppg", "opp_ppg", "margin", *_rate_columns(), *(f"{c}_rank" for c in RANKED)]
    return _rounded(df[columns])


def player_seasons(player_box, team_games):
    """Aggregate player box scores into season totals, per-game averages, and efficiency rates."""
    played = player_box[~player_box.did_not_play.fillna(True).astype(bool)]
    played = played[played["min"].fillna(0) > 0]
    df = played.groupby([*KEYS, "player_id"]).agg(
        player=("player", "last"),
        team=("team", "last"),
        position=("position", "last"),
        games=("game_id", "size"),
        starts=("starter", "sum"),
        **{column: (column, "sum") for column in PLAYER_TOTALS},
    )
    boxed = team_games[team_games.fga.notna() & team_games.completed.fillna(False).astype(bool)]
    team = (
        boxed.assign(minutes=40 + 5 * boxed.overtimes)
        .groupby(KEYS)[["fga", "fta", "tov", "minutes"]]
        .sum()
        .add_prefix("team_")
    )
    df = df.reset_index().merge(team.reset_index(), on=KEYS, how="left")
    minutes = df["min"]
    df = df.assign(
        mpg=minutes / df.games,
        ppg=df.pts / df.games,
        rpg=df.reb / df.games,
        apg=df.ast / df.games,
        spg=df.stl / df.games,
        bpg=df.blk / df.games,
        topg=df.tov / df.games,
        fg_pct=df.fgm / df.fga,
        fg3_pct=df.fg3m / df.fg3a,
        ft_pct=df.ftm / df.fta,
        efg_pct=(df.fgm + 0.5 * df.fg3m) / df.fga,
        ts_pct=df.pts / (2 * (df.fga + USAGE_FT_WEIGHT * df.fta)),
        usage_pct=100
        * (df.fga + USAGE_FT_WEIGHT * df.fta + df.tov)
        * df.team_minutes
        / (minutes * (df.team_fga + USAGE_FT_WEIGHT * df.team_fta + df.team_tov)),
        pts_per40=40 * df.pts / minutes,
        reb_per40=40 * df.reb / minutes,
        ast_per40=40 * df.ast / minutes,
    )
    return _rounded(df.drop(columns=team.columns))


def _with_opponent_stats(team_games):
    """Return team games with the opponent's box score columns (prefixed opp_) and game minutes."""
    opponent = team_games[["game_id", "team_id", *BOX_COLUMNS]].rename(
        columns={"team_id": "opponent_id", **{c: f"opp_{c}" for c in BOX_COLUMNS}}
    )
    games = team_games.merge(opponent, on=["game_id", "opponent_id"], how="left")
    return games.assign(minutes=40 + 5 * games.overtimes)


def _rates(df):
    """Return pace, ratings, four factors, and shooting rates from summed or single-game stats."""
    possessions = (_possessions(df, "") + _possessions(df, "opp_")) / 2
    rates = {
        "possessions": possessions,
        "pace": 40 * possessions / df.minutes,
        "ortg": 100 * df.team_score / possessions,
        "drtg": 100 * df.opp_team_score / possessions,
        "net_rtg": 100 * (df.team_score - df.opp_team_score) / possessions,
    }
    for side, other in (("", "opp_"), ("opp_", "")):
        rates |= {
            f"{side}efg_pct": (df[f"{side}fgm"] + 0.5 * df[f"{side}fg3m"]) / df[f"{side}fga"],
            f"{side}tov_pct": df[f"{side}tov"] / possessions,
            f"{side}orb_pct": df[f"{side}oreb"] / (df[f"{side}oreb"] + df[f"{other}dreb"]),
            f"{side}ft_rate": df[f"{side}fta"] / df[f"{side}fga"],
        }
    return rates | {
        "fg_pct": df.fgm / df.fga,
        "fg3_pct": df.fg3m / df.fg3a,
        "ft_pct": df.ftm / df.fta,
        "fg3a_rate": df.fg3a / df.fga,
        "ast_rate": df.ast / df.fgm,
    }


def _rate_columns():
    """Return the names of the columns _rates produces, in order."""
    columns = ["possessions", "pace", "ortg", "drtg", "net_rtg"]
    for side in ("", "opp_"):
        columns += [f"{side}efg_pct", f"{side}tov_pct", f"{side}orb_pct", f"{side}ft_rate"]
    return columns + ["fg_pct", "fg3_pct", "ft_pct", "fg3a_rate", "ast_rate"]


def _possessions(df, side):
    """Estimate one team's possessions from field goal attempts, rebounds, turnovers and FTs."""
    return (
        df[f"{side}fga"]
        - df[f"{side}oreb"]
        + df[f"{side}tov"]
        + POSSESSION_FT_WEIGHT * df[f"{side}fta"]
    )


def _split_masks(games):
    """Return a boolean mask selecting each split's team games."""
    conference = games.conference_game.fillna(False).astype(bool)
    return {
        "Overall": pd.Series(True, index=games.index),
        "Conference": conference,
        "Non-Conference": ~conference,
        "Home": games.location == "Home",
        "Away": games.location == "Away",
        "Neutral": games.location == "Neutral",
    }


def _rounded(df):
    """Round rates to 3 decimals and ratings, pace, and averages to 1."""
    decimals = {c: 3 for c in df.columns if c.endswith(("_pct", "_rate"))}
    decimals |= {c: 1 for c in df.columns if c.endswith(("rtg", "pg", "per40", "pace"))}
    decimals |= {c: 1 for c in ("possessions", "margin", "usage_pct") if c in df.columns}
    return df.round(decimals)
