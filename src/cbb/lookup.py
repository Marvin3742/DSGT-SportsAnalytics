NAME_FIELDS = ("id", "abbreviation", "location", "displayName", "shortDisplayName", "slug")


def find_teams(query, teams, exact=False):
    """Return teams whose id, abbreviation, or names match the query (case-insensitive)."""
    query = query.casefold()
    return [
        team
        for team in teams
        if any(
            (value == query) if exact else (query in value)
            for value in (str(team.get(field, "")).casefold() for field in NAME_FIELDS)
        )
    ]


def resolve_team(query, teams):
    """Return the ESPN id of the single team matching an id, abbreviation, or name."""
    query = str(query)
    if query.isdigit():
        return int(query)
    matches = find_teams(query, teams, exact=True) or find_teams(query, teams)
    if len(matches) != 1:
        names = ", ".join(sorted(t["displayName"] for t in matches)) or "no teams"
        raise ValueError(f"'{query}' matched {names}. Use a more specific name or an ESPN id.")
    return int(matches[0]["id"])
