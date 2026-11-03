import pandas as pd

from gt_hoops.config import PROCESSED_DIR, SEASONS
from gt_hoops.espn import EspnClient, is_final
from gt_hoops.parse import parse_games, parse_player_box, parse_players, parse_team_box


def build_season(client, season):
    """Scrape one season and return its rows keyed by table name."""
    events = client.schedule(season)
    summaries = {event["id"]: client.summary(event["id"], season) for event in events}
    finals = [s for s in summaries.values() if is_final(s)]
    player_box = [row for s in finals for row in parse_player_box(s)]
    athletes = client.roster(season)["athletes"]
    on_roster = {int(a["id"]) for a in athletes}
    missing = {row["player_id"] for row in player_box if row["is_gt"]} - on_roster
    athletes += [client.athlete(player_id, season) for player_id in sorted(missing)]
    return {
        "games": parse_games(events, summaries),
        "team_box": [row for s in finals for row in parse_team_box(s)],
        "player_box": player_box,
        "players": parse_players(athletes, season),
    }


def run(seasons=SEASONS, client=None, out_dir=PROCESSED_DIR):
    """Scrape every season and write one CSV per table, replacing previous output."""
    client = client or EspnClient()
    tables = {}
    for season in seasons:
        for name, rows in build_season(client, season).items():
            tables.setdefault(name, []).extend(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        pd.DataFrame(rows).convert_dtypes().to_csv(out_dir / f"{name}.csv", index=False)
    return tables


def main():
    """Run the pipeline and print row counts per table."""
    for name, rows in run().items():
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
