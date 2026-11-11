from datetime import datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from cbb.config import LOCAL_TZ

UNRANKED = 99
SEASON_TYPES = {1: "Preseason", 2: "Regular Season", 3: "Postseason"}
RECORD_COLUMNS = ("wins", "losses", "conf_wins", "conf_losses")

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
    """Build one row per game from scoreboard events and box score summaries keyed by event id."""
    rows = []
    for event in events:
        comp = event["competitions"][0]
        home, away = _home_away(comp)
        done = comp["status"]["type"]["completed"]
        tipoff = _tipoff(event)
        winner = next((c for c in comp["competitors"] if c.get("winner")), None)
        venue = comp.get("venue", {})
        rows.append(
            {
                "game_id": int(event["id"]),
                **_season_columns(event),
                "game_date": tipoff.date().isoformat(),
                "tipoff_et": tipoff.strftime("%Y-%m-%d %H:%M"),
                "status": comp["status"]["type"]["description"],
                "completed": done,
                "neutral_site": comp.get("neutralSite"),
                "conference_game": comp.get("conferenceCompetition"),
                "event_note": next(
                    (n["headline"] for n in comp.get("notes", []) if n.get("headline")), None
                ),
                "home_team_id": int(home["id"]),
                "home_team": home["team"]["location"],
                "away_team_id": int(away["id"]),
                "away_team": away["team"]["location"],
                "home_score": _score(home, done),
                "away_score": _score(away, done),
                "winner_team_id": int(winner["id"]) if done and winner else None,
                "overtimes": max(len(home.get("linescores", [])) - 2, 0) if done else None,
                "venue": venue.get("fullName"),
                "venue_city": venue.get("address", {}).get("city"),
                "venue_state": venue.get("address", {}).get("state"),
                "attendance": comp.get("attendance") or None,
                "has_box_score": _has_box_score(summaries.get(event["id"])),
            }
        )
    return rows


def parse_team_games(events, summaries):
    """Build one row per team per game from that team's perspective, with box score stats."""
    rows = []
    for event in events:
        comp = event["competitions"][0]
        done = comp["status"]["type"]["completed"]
        box = _team_box_stats(summaries.get(event["id"]))
        for team, opponent in permutations(comp["competitors"]):
            team_score, opponent_score = _score(team, done), _score(opponent, done)
            row = {
                "game_id": int(event["id"]),
                "season": event["season"]["year"],
                "season_type": SEASON_TYPES.get(event["season"]["type"]),
                "game_date": _tipoff(event).date().isoformat(),
                "completed": done,
                "team_id": int(team["id"]),
                "team": team["team"]["location"],
                "opponent_id": int(opponent["id"]),
                "opponent": opponent["team"]["location"],
                "location": "Neutral" if comp.get("neutralSite") else team["homeAway"].title(),
                "conference_game": comp.get("conferenceCompetition"),
                "result": ("W" if team.get("winner") else "L") if done else None,
                "team_score": team_score,
                "opponent_score": opponent_score,
                "margin": team_score - opponent_score if done else None,
                "overtimes": max(len(team.get("linescores", [])) - 2, 0) if done else None,
                "rank": _rank(team),
                "opponent_rank": _rank(opponent),
                **_stat_columns(box.get(int(team["id"]), {}), TEAM_STATS),
            }
            rows.append(row | _percentages(row))
    return _add_records(rows)


def parse_player_box(summary):
    """Build one row per player per team from a finished game's box score, including DNPs."""
    game_id, season = int(summary["header"]["id"]), summary["header"]["season"]["year"]
    team_ids = [int(c["id"]) for c in summary["header"]["competitions"][0]["competitors"]]
    rows = []
    for team in summary["boxscore"].get("players", []):
        team_id = int(team["team"]["id"])
        group = team["statistics"][0]
        for entry in group["athletes"]:
            athlete = entry["athlete"]
            if "id" not in athlete:
                continue
            stats = dict(zip(group["keys"], entry["stats"], strict=False))
            rows.append(
                {
                    "game_id": game_id,
                    "season": season,
                    "team_id": team_id,
                    "team": team["team"]["location"],
                    "opponent_id": next(other for other in team_ids if other != team_id),
                    "player_id": int(athlete["id"]),
                    "player": athlete["displayName"],
                    "jersey": athlete.get("jersey"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "starter": entry["starter"],
                    "did_not_play": entry["didNotPlay"],
                    "ejected": entry["ejected"],
                    **_stat_columns(stats, PLAYER_STATS),
                }
            )
    return rows


def parse_conferences(events):
    """Map conference ids to short names using the conference games in scoreboard events."""
    conferences = {}
    for event in events:
        group = event["competitions"][0].get("groups")
        if group and group.get("isConference"):
            conferences[int(group["id"])] = group.get("shortName") or group.get("name")
    return conferences


def parse_teams(events, conferences, d1_team_ids):
    """Build one row per team per season from the teams appearing in scoreboard events."""
    teams = {}
    for event in events:
        season = event["season"]["year"]
        for competitor in event["competitions"][0]["competitors"]:
            team = competitor["team"]
            team_id = int(team["id"])
            conference_id = _to_int(team.get("conferenceId"))
            teams[(team_id, season)] = {
                "team_id": team_id,
                "season": season,
                "team": team["location"],
                "nickname": team.get("name"),
                "display_name": team.get("displayName"),
                "abbreviation": team.get("abbreviation"),
                "conference_id": conference_id,
                "conference": conferences.get(conference_id),
                "is_d1": team_id in d1_team_ids,
                "color": team.get("color"),
                "alt_color": team.get("alternateColor"),
                "logo_url": team.get("logo"),
            }
    return list(teams.values())


def parse_players(athletes, season, team_id):
    """Build one row per player on a team's roster for a season from roster or bio payloads."""
    return [
        {
            "player_id": int(a["id"]),
            "season": season,
            "team_id": team_id,
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


def _add_records(rows):
    """Add each team's running season record after every completed game."""
    tallies = {}
    for row in sorted(rows, key=lambda r: (r["game_date"], r["game_id"])):
        tally = tallies.setdefault((row["season"], row["team_id"]), [0, 0, 0, 0])
        if row["result"]:
            won = row["result"] == "W"
            tally[0 if won else 1] += 1
            if row["conference_game"]:
                tally[2 if won else 3] += 1
        row.update(zip(RECORD_COLUMNS, tally if row["result"] else [None] * 4, strict=True))
    return rows


def _home_away(comp):
    """Return the (home, away) competitors of a competition."""
    by_side = {c["homeAway"]: c for c in comp["competitors"]}
    return by_side["home"], by_side["away"]


def _tipoff(event):
    """Return an event's start time in US Eastern time."""
    return datetime.fromisoformat(event["date"]).astimezone(ZoneInfo(LOCAL_TZ))


def _season_columns(event):
    """Return season, season_label (e.g. 2025-26), and season_type for an event."""
    year = event["season"]["year"]
    return {
        "season": year,
        "season_label": f"{year - 1}-{year % 100:02d}",
        "season_type": SEASON_TYPES.get(event["season"]["type"]),
    }


def _score(competitor, done):
    """Return a competitor's final score, or None before the game is over."""
    return _to_int(competitor.get("score")) if done else None


def _has_box_score(summary):
    """Return True if a summary includes player box score stats."""
    return bool(summary and summary["boxscore"].get("players"))


def _team_box_stats(summary):
    """Map team id to its raw box score stats ({name: displayValue}) for a summary."""
    if not summary:
        return {}
    return {
        int(team["team"]["id"]): {s["name"]: s["displayValue"] for s in team["statistics"]}
        for team in summary["boxscore"].get("teams", [])
    }


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
    """Return a competitor's AP rank at game time, or None when unranked."""
    rank = competitor.get("curatedRank", {}).get("current")
    return rank if rank and rank != UNRANKED else None


def _to_int(value):
    """Convert an ESPN value to int, returning None for blanks and placeholders."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
