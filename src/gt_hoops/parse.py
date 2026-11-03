from datetime import datetime
from zoneinfo import ZoneInfo

from gt_hoops.config import GT_TEAM_ID, LOCAL_TZ

UNRANKED = 99

SHOOTING_PAIRS = {
    "fieldGoalsMade-fieldGoalsAttempted": ("fgm", "fga"),
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted": ("fg3m", "fg3a"),
    "freeThrowsMade-freeThrowsAttempted": ("ftm", "fta"),
}

TEAM_STATS = {
    **SHOOTING_PAIRS,
    "offensiveRebounds": "oreb",
    "defensiveRebounds": "dreb",
    "totalRebounds": "reb",
    "assists": "ast",
    "steals": "stl",
    "blocks": "blk",
    "totalTurnovers": "tov",
    "teamTurnovers": "team_tov",
    "fouls": "pf",
    "technicalFouls": "tech_fouls",
    "flagrantFouls": "flagrant_fouls",
    "turnoverPoints": "pts_off_tov",
    "fastBreakPoints": "fast_break_pts",
    "pointsInPaint": "paint_pts",
    "largestLead": "largest_lead",
}

PLAYER_STATS = {
    "minutes": "min",
    "points": "pts",
    **SHOOTING_PAIRS,
    "offensiveRebounds": "oreb",
    "defensiveRebounds": "dreb",
    "rebounds": "reb",
    "assists": "ast",
    "steals": "stl",
    "blocks": "blk",
    "turnovers": "tov",
    "fouls": "pf",
}


def parse_games(events, summaries):
    """Build one row per GT game from schedule events and their summaries keyed by event id."""
    return [_game_row(event, summaries[event["id"]]) for event in events]


def parse_team_box(summary):
    """Build one row per team from a finished game's box score."""
    game_id, season = _game_keys(summary)
    competitors = {int(c["id"]): c for c in summary["header"]["competitions"][0]["competitors"]}
    rows = []
    for team in summary["boxscore"]["teams"]:
        team_id = int(team["team"]["id"])
        stats = {s["name"]: s["displayValue"] for s in team["statistics"]}
        row = {
            "game_id": game_id,
            "season": season,
            "team_id": team_id,
            "team": team["team"]["location"],
            "is_gt": team_id == GT_TEAM_ID,
            "opponent_id": next(other for other in competitors if other != team_id),
            "home_away": team["homeAway"],
            "pts": _to_int(competitors[team_id]["score"]),
            **_stat_columns(stats, TEAM_STATS),
        }
        rows.append(row | _percentages(row))
    return rows


def parse_player_box(summary):
    """Build one row per player per team from a finished game's box score, including DNPs."""
    game_id, season = _game_keys(summary)
    rows = []
    for team in summary["boxscore"].get("players", []):
        team_id = int(team["team"]["id"])
        group = team["statistics"][0]
        for entry in group["athletes"]:
            athlete = entry["athlete"]
            rows.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "team_id": team_id,
                    "team": team["team"]["location"],
                    "is_gt": team_id == GT_TEAM_ID,
                    "player_id": int(athlete["id"]),
                    "player": athlete["displayName"],
                    "jersey": athlete.get("jersey"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "starter": entry["starter"],
                    "did_not_play": entry["didNotPlay"],
                    "ejected": entry["ejected"],
                    **_stat_columns(
                        dict(zip(group["keys"], entry["stats"], strict=False)), PLAYER_STATS
                    ),
                }
            )
    return rows


def parse_players(athletes, season):
    """Build one row per GT player for a season from roster or athlete bio payloads."""
    return [
        {
            "player_id": int(a["id"]),
            "season": season,
            "player": a["displayName"],
            "first_name": a.get("firstName"),
            "last_name": a.get("lastName"),
            "jersey": a.get("jersey"),
            "position": a.get("position", {}).get("abbreviation"),
            "height_in": _to_int(a.get("height")),
            "height": a.get("displayHeight"),
            "weight_lb": _to_int(a.get("weight")),
            "class": a.get("experience", {}).get("displayValue"),
            "hometown": a.get("birthPlace", {}).get("displayText"),
            "headshot_url": a.get("headshot", {}).get("href"),
        }
        for a in athletes
    ]


def _game_row(event, summary):
    """Flatten one schedule event and its summary into a games row."""
    comp = event["competitions"][0]
    gt, opp = sorted(comp["competitors"], key=lambda c: int(c["id"]) != GT_TEAM_ID)
    status = comp["status"]["type"]
    done = status["completed"]
    tipoff = datetime.fromisoformat(event["date"]).astimezone(ZoneInfo(LOCAL_TZ))
    header = summary["header"]["competitions"][0]
    gt_header = next(c for c in header["competitors"] if int(c["id"]) == GT_TEAM_ID)
    gt_score = int(gt["score"]["value"]) if done else None
    opp_score = int(opp["score"]["value"]) if done else None
    return {
        "game_id": int(event["id"]),
        "season": event["season"]["year"],
        "season_label": event["season"]["displayName"],
        "season_type": event["seasonType"]["name"],
        "game_date": tipoff.date().isoformat(),
        "tipoff_et": tipoff.strftime("%Y-%m-%d %H:%M"),
        "status": status["description"],
        "completed": done,
        "opponent_id": int(opp["id"]),
        "opponent": opp["team"]["location"],
        "opponent_abbr": opp["team"]["abbreviation"],
        "opponent_logo_url": next(iter(opp["team"].get("logos", [])), {}).get("href"),
        "location": "Neutral" if comp["neutralSite"] else gt["homeAway"].title(),
        "conference_game": header.get("conferenceCompetition"),
        "venue": comp.get("venue", {}).get("fullName"),
        "venue_city": comp.get("venue", {}).get("address", {}).get("city"),
        "venue_state": comp.get("venue", {}).get("address", {}).get("state"),
        "gt_rank": _rank(gt),
        "opponent_rank": _rank(opp),
        "gt_score": gt_score,
        "opponent_score": opp_score,
        "result": ("W" if gt["winner"] else "L") if done else None,
        "margin": gt_score - opp_score if done else None,
        "overtimes": max(len(gt_header.get("linescores", [])) - 2, 0) if done else None,
        "gt_record": _record(gt, "total"),
        "gt_conf_record": _record(gt, "vsconf"),
        "attendance": comp.get("attendance") or None,
    }


def _game_keys(summary):
    """Return the (game_id, season) pair for a summary."""
    return int(summary["header"]["id"]), summary["header"]["season"]["year"]


def _stat_columns(values, mapping):
    """Map ESPN stat names to columns, splitting 'made-attempted' strings into two ints."""
    row = {}
    for name, column in mapping.items():
        value = values.get(name)
        if isinstance(column, tuple):
            made, attempted = value.split("-") if value and "-" in value else (None, None)
            row[column[0]], row[column[1]] = _to_int(made), _to_int(attempted)
        else:
            row[column] = _to_int(value)
    return row


def _percentages(row):
    """Return FG, 3PT and FT percentages as 0-1 decimals."""
    return {
        f"{prefix}_pct": round(row[f"{prefix}m"] / row[f"{prefix}a"], 3)
        if row[f"{prefix}a"]
        else None
        for prefix in ("fg", "fg3", "ft")
    }


def _rank(competitor):
    """Return a competitor's AP rank, or None when unranked."""
    rank = competitor.get("curatedRank", {}).get("current")
    return rank if rank and rank != UNRANKED else None


def _record(competitor, record_type):
    """Return a competitor's record string of the given type after the game."""
    records = competitor.get("record") or []
    return next((r["displayValue"] for r in records if r["type"] == record_type), None)


def _to_int(value):
    """Convert an ESPN stat value to int, returning None for blanks and placeholders."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
