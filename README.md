# DSGT Sports Analytics

Automated data pipeline that collects, processes, and stores Georgia Tech NCAA men's basketball data for Power BI dashboards.

## Setup

```bash
conda env create -f environment.yml
conda activate dsgt-sports-analytics
```

## Update the data

```bash
python -m gt_hoops.pipeline
```

## Data

CSVs for Power BI are in `data/processed/`:

- `games.csv`: one row per GT game
- `team_box.csv`: team box score per game (GT and opponent)
- `player_box.csv`: player box score per game (GT and opponent)
- `players.csv`: GT roster per season

`season` is the year the season ends (2026 = 2025-26).
