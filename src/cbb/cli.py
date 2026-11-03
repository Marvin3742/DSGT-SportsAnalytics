import logging
from pathlib import Path
from typing import Annotated

import typer

from cbb.config import EXPORTS_DIR, PROCESSED_DIR, load_settings
from cbb.espn import EspnClient
from cbb.lookup import find_teams, resolve_team
from cbb.pipeline import build, write_tables
from cbb.validate import load_tables
from cbb.validate import validate as find_problems

app = typer.Typer(
    help="Scrape NCAA men's basketball data from ESPN.", no_args_is_help=True, add_completion=False
)

Workers = Annotated[int, typer.Option(help="Parallel requests to ESPN.")]


@app.callback()
def main():
    """Configure logging for every command."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")


@app.command()
def update(workers: Workers = 4):
    """Scrape the seasons and teams in cbb.toml into data/processed, then validate."""
    settings = load_settings()
    client = EspnClient()
    d1_teams = client.teams()
    team_ids = _resolve(settings.get("teams", []), d1_teams) or None
    roster_ids = _resolve(settings.get("roster_teams", []), d1_teams)
    tables = build(settings["seasons"], team_ids, roster_ids, client, workers)
    write_tables(tables, PROCESSED_DIR)
    _report(tables)
    validate(PROCESSED_DIR)


@app.command()
def scrape(
    season: Annotated[
        list[int],
        typer.Option("--season", "-s", help="Season end year (2026 = 2025-26). Repeatable."),
    ],
    team: Annotated[
        list[str] | None,
        typer.Option(
            "--team", "-t", help="Team name, abbreviation, or ESPN id. Repeatable. Omit for all D1."
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Output folder. Default: data/exports/<teams>_<seasons>.")
    ] = None,
    workers: Workers = 4,
):
    """Scrape specific seasons and teams into a separate folder, leaving data/processed alone."""
    client = EspnClient()
    d1_teams = client.teams()
    team_ids = _resolve(team or [], d1_teams) or None
    tables = build(season, team_ids, (), client, workers)
    slugs = sorted(t["slug"] for t in d1_teams if int(t["id"]) in (team_ids or ())) or ["all"]
    out = out or EXPORTS_DIR / f"{'-'.join(slugs)}_{'-'.join(map(str, season))}"
    write_tables(tables, out)
    _report(tables)
    typer.echo(f"Wrote {out}")


@app.command()
def teams(
    query: Annotated[str | None, typer.Argument(help="Filter by name or abbreviation.")] = None,
):
    """List Division I teams with their ESPN ids."""
    d1_teams = EspnClient().teams()
    for team in sorted(find_teams(query, d1_teams) if query else d1_teams, key=_display_name):
        typer.echo(f"{team['id']:>6}  {team['abbreviation']:<6}  {team['displayName']}")


@app.command()
def validate(
    data_dir: Annotated[Path, typer.Argument(help="Folder of pipeline CSVs.")] = PROCESSED_DIR,
):
    """Check pipeline CSVs for duplicates and box score consistency; exits with 1 on errors."""
    errors, warnings = find_problems(load_tables(data_dir))
    for warning in warnings:
        typer.echo(f"WARN  {warning}", err=True)
    for error in errors:
        typer.echo(f"FAIL  {error}", err=True)
    if errors:
        raise typer.Exit(1)
    typer.echo("All checks passed." if not warnings else "Passed with warnings.")


def _resolve(queries, d1_teams):
    """Turn team names, abbreviations, or ids into a set of ESPN ids."""
    try:
        return {resolve_team(query, d1_teams) for query in queries}
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _report(tables):
    """Print row counts per table."""
    for name, frame in tables.items():
        typer.echo(f"{name}: {len(frame):,} rows")


def _display_name(team):
    """Sort key for teams."""
    return team["displayName"]
