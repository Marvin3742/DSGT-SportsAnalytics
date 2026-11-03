# Data Dictionary

CSVs in `data/processed/`, covering every NCAA Division I men's basketball game for the 2025-26 and 2026-27 seasons. Source: ESPN.

## Quick start for Power BI

- Georgia Tech is `team_id = 59`. Filter `team_games` on it for GT's schedule, results, and team stats.
- `season` is the year the season **ends**: `2026` = 2025-26, `2027` = 2026-27.
- Game times are US Eastern.
- Blank cells mean "not available": games not played yet, or small-school games ESPN has no box score for.

### Relationships

| From | To | Key |
|---|---|---|
| `team_games` | `games` | `game_id` |
| `player_box` | `games` | `game_id` |
| `team_games` | `teams` | `team_id` + `season` |
| `player_box` | `team_games` | `game_id` + `team_id` |
| `player_box` | `players` | `player_id` + `season` + `team_id` |

Power BI relationships use one column, so for two-column keys create a combined key column, for example `team_season = team_id & "-" & season`.

## teams.csv

One row per team per season. Includes non-Division I opponents.

| Column | Description |
|---|---|
| team_id | ESPN team id |
| season | Season end year |
| team | School name, e.g. `Georgia Tech` |
| nickname | e.g. `Yellow Jackets` |
| display_name | e.g. `Georgia Tech Yellow Jackets` |
| abbreviation | e.g. `GT` |
| conference_id, conference | Conference that season, e.g. `ACC` |
| is_d1 | Division I team |
| color, alt_color | Team colors as hex without `#`, e.g. `b3a369` |
| logo_url | Team logo image |

## games.csv

One row per game, including games not played yet.

| Column | Description |
|---|---|
| game_id | ESPN game id |
| season, season_label | `2026`, `2025-26` |
| season_type | `Regular Season` or `Postseason` |
| game_date | Date (Eastern) |
| tipoff_et | Start time (Eastern), `YYYY-MM-DD HH:MM` |
| status | `Final`, `Scheduled`, `Postponed`, `Canceled`, ... |
| completed | Game is finished |
| neutral_site | Played at a neutral site |
| conference_game | Conference game |
| event_note | Tournament label, e.g. `NCAA Men's Basketball Championship - East Region - 1st Round` |
| home_team_id, home_team, away_team_id, away_team | Teams (ESPN still lists a home and away team at neutral sites) |
| home_score, away_score | Final score |
| winner_team_id | Winning team |
| overtimes | Number of overtime periods |
| venue, venue_city, venue_state | Arena |
| attendance | Attendance, when reported |
| has_box_score | ESPN has player stats for this game |

## team_games.csv

One row per team per game, from that team's point of view. Every game appears twice, once for each team. This is the main table for team performance.

| Column | Description |
|---|---|
| game_id, season, season_type, game_date, completed | As in `games` |
| team_id, team | The team this row is about |
| opponent_id, opponent | The other team |
| location | `Home`, `Away`, or `Neutral` |
| conference_game | Conference game |
| result | `W` or `L` |
| team_score, opponent_score, margin | Points scored, allowed, and the difference |
| rank, opponent_rank | AP poll rank at game time (blank if unranked) |
| fgm, fga, fg_pct | Field goals made, attempted, percentage |
| fg3m, fg3a, fg3_pct | Three-pointers |
| ftm, fta, ft_pct | Free throws |
| oreb, dreb, reb | Offensive, defensive, total rebounds |
| ast, stl, blk | Assists, steals, blocks |
| tov, team_tov | Turnovers (total, and those credited to the team rather than a player) |
| pf, tech_fouls, flagrant_fouls | Fouls |
| pts_off_tov, fast_break_pts, paint_pts | Points off turnovers, fast-break points, points in the paint |
| largest_lead | Largest lead in the game |
| wins, losses, conf_wins, conf_losses | The team's season record **after** this game |

## player_box.csv

One row per player per game, for both teams. Includes players who didn't play (`did_not_play = True`, stats blank).

| Column | Description |
|---|---|
| game_id, season | As in `games` |
| team_id, team, opponent_id | Player's team and opponent |
| player_id, player | ESPN player id and name |
| jersey, position | Jersey number; position `G`, `F`, or `C` |
| starter, did_not_play, ejected | Flags |
| min, pts | Minutes and points |
| fgm, fga, fg3m, fg3a, ftm, fta | Shooting |
| oreb, dreb, reb, ast, stl, blk, tov, pf | Other stats |

## players.csv

One row per player per season for the teams listed in `roster_teams` in `cbb.toml` (currently Georgia Tech only). Includes players who left mid-season, so every GT player in `player_box` has a row here.

| Column | Description |
|---|---|
| player_id, season, team_id | Key |
| player, first_name, last_name | Name |
| jersey, position | As listed on the roster |
| height_in, height | Height in inches, and as text (`6' 7"`) |
| weight_lb | Weight in pounds |
| class | `Freshman`, `Sophomore`, `Junior`, `Senior`, ... |
| hometown | e.g. `Atlanta, GA` |
| headshot_url | Player photo |

## Things to watch for

- **Season percentages:** sum makes and attempts, then divide. Averaging the per-game `fg_pct` gives the wrong answer.
- **Rebounds:** team `reb` is often a few higher than the sum of player rebounds, because ESPN credits some rebounds to the team.
- **Box scores:** almost every finished game has one. The rare exception has a final score but no box score (`has_box_score = False`).
- **ESPN data errors:** in about 0.1% of team box scores, the player points don't add up to the team score, usually by 2. None involve Georgia Tech.
