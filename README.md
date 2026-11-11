# DSGT Sports Analytics

Automated data pipeline that collects, processes, and stores NCAA men's basketball data, focused on Georgia Tech, for Power BI dashboards.

## Setup

```bash
conda env create -f environment.yml
conda activate dsgt-sports-analytics
```

## Usage

```bash
cbb update                              # refresh data/processed using cbb.toml
cbb scrape -s 2026 -t "Georgia Tech"    # one-off scrape into data/exports/
cbb teams georgia                       # find team ids
cbb validate                            # check the CSVs
```

## Data

CSVs for Power BI are in `data/processed/`, updated every morning by GitHub Actions. See [docs/data_dictionary.md](docs/data_dictionary.md).
