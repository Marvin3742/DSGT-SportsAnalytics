# Data Dictionary

CSVs in `data/processed/`, covering every NCAA Division I men's basketball game for the 2025-26 and 2026-27 seasons. Source: ESPN.

## Quick start for Power BI

- Georgia Tech is `team_id = 59`. Filter `team_games` on it for GT's schedule, results, and team stats.
- For season numbers and D1 rankings, use `team_seasons` and `player_seasons`. Their rates are computed from season totals, so they are correct as-is; don't average per-game percentages.
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
| `team_seasons` | `teams` | `team_id` + `season` |
| `player_seasons` | `players` | `player_id` + `season` + `team_id` |

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
| overtimes | Number of overtime periods |
| wins, losses, conf_wins, conf_losses | The team's season record **after** this game |
| possessions | Estimated possessions in the game (average of both teams' estimates) |
| pace | Possessions per 40 minutes |
| ortg, drtg, net_rtg | Points scored and allowed per 100 possessions, and the difference |
| efg_pct | Effective FG%: field goal percentage with threes counted as 1.5 makes |
| tov_pct | Turnovers per possession |
| orb_pct | Share of the team's missed shots it rebounded |
| ft_rate | Free throw attempts per field goal attempt |
| opp_efg_pct, opp_tov_pct, opp_orb_pct, opp_ft_rate | The same four stats for the opponent (the team's defense) |
| fg3a_rate | Share of field goal attempts that were threes |
| ast_rate | Share of made field goals that were assisted |

The last group is blank for games without a box score.

## team_seasons.csv

One row per Division I team per season per split. Includes every completed game, so totals match official stats.

| Column | Description |
|---|---|
| team_id, season, team, conference | Team |
| split | `Overall`, `Conference`, `Non-Conference`, `Home`, `Away`, or `Neutral` |
| games, wins, losses | Record in this split |
| ppg, opp_ppg, margin | Points per game scored and allowed, and average margin |
| possessions | Total possessions |
| pace, ortg, drtg, net_rtg | As in `team_games`, over the whole split |
| efg_pct, tov_pct, orb_pct, ft_rate | Offensive four factors |
| opp_efg_pct, opp_tov_pct, opp_orb_pct, opp_ft_rate | Defensive four factors |
| fg_pct, fg3_pct, ft_pct, fg3a_rate, ast_rate | Shooting and passing |
| *_rank | Rank among D1 teams for the same season and split, where 1 is best. Lower is better for `drtg`, `tov_pct` and the opponent shooting stats. Available for net_rtg, ortg, drtg, pace (1 = fastest) and the eight four-factor columns |

These are raw stats, not adjusted for opponent strength.

## player_seasons.csv

One row per player per team per season, for every D1 player who played.

| Column | Description |
|---|---|
| season, team_id, player_id | Key |
| player, team, position | Player |
| games, starts | Games played and started |
| min, pts, fgm, fga, fg3m, fg3a, ftm, fta, oreb, dreb, reb, ast, stl, blk, tov, pf | Season totals |
| mpg, ppg, rpg, apg, spg, bpg, topg | Per-game averages |
| fg_pct, fg3_pct, ft_pct | Shooting percentages |
| efg_pct | Effective FG% |
| ts_pct | True shooting %: points per shooting attempt, counting free throws |
| usage_pct | Share of the team's possessions the player used while on the court (0-100; about 20 is average) |
| pts_per40, reb_per40, ast_per40 | Per 40 minutes |

Filter on `min` (for example 100+) before ranking players, so a few lucky minutes don't top the list.

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

