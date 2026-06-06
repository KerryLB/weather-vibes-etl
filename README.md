# Weather Vibes ETL Pipeline and Dashboard

An end-to-end data engineering project that extracts 7-day weather forecast data for Louisville, KY from the Open-Meteo API, applies transformation and data quality checks, loads results into a normalized SQLite database, exports analytics-ready CSV files, and powers an interactive Power BI dashboard.

---

## Project Context and Design Decisions

### Database: SQLite vs PostgreSQL

This pipeline uses SQLite as its database backend. Due to project timeline constraints and the iterative nature of this pipeline's development, SQLite was selected in place of PostgreSQL or Supabase. SQLite provides identical schema structure, SQL querying, and SQLAlchemy integration to a hosted PostgreSQL solution, making it a functionally equivalent choice for local development and academic demonstration. The pipeline is architected to support a straightforward migration to PostgreSQL or Supabase by updating the SQLAlchemy connection string alone — no other code changes are required.

### ETL in a Single Script

The complete ETL workflow — extraction, transformation, validation, loading, and CSV export — is implemented in a single Python script. This was an intentional design choice to keep the pipeline self-contained, reproducible, and easy to execute. The script is modular with clearly separated functions for each pipeline stage, following the same organizational principles as a multi-file ETL framework.

### Schema Design: Normalized Database + Star Schema Analytics

The project uses a two-layer schema design reflecting course content on normalized vs star schemas:

**Layer 1 — Normalized database (weather.db):**
- `weather_forecast` — fact table with core daily metrics
- `vibe_dimension` — dimension table with all 11 vibe labels, descriptions, parameters, and emojis
- `fit_recommendations` — dimension table with all 11 outfit and accessory recommendations
- `forecast_vibe` — bridge table linking forecasts to vibes and fits via 3 foreign keys

**Layer 2 — Star schema analytics (Power BI):**
- `forecast_fits.csv` — a flat denormalized join of the current 7-day forecast with explicit `forecast_fits_id` (PK), `vibe_id` (FK), and `fit_id` (FK) columns, plus all weather metrics, vibe fields, and fit fields pre-joined. This is the primary Power BI fact table.
- `vibe_dimension.csv` — dimension table containing all 11 vibes for the full reference card
- `fit_recommendations.csv` — dimension table containing all 11 fits for the full reference card

This approach demonstrates both normalization for data integrity and denormalization for analytics performance.

---

## Project Structure

```
weather-vibes-etl/
├── weather_vibes_app.py          # Main ETL pipeline script
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── CHANGELOG.md                  # Full record of changes from original script
├── .gitignore                    # Excludes data/ directory from version control
├── vibe_guide.txt                # Vibe and fit reference card for Power BI text box
├── docs/
│   ├── Weather_Vibes_ERD.html        # ERD — normalized schema and Power BI star schema
│   ├── Weather_Vibes_ERD.pdf         # PDF version of ERD for BRD
│   ├── weather_vibes_data_flow.pdf   # ETL pipeline data flow diagram
│   ├── Basham_Kerry_DataEngineering_Project_Proposal_UPDATED.docx
│   └── Basham_Kerry_Weather_Vibes_Database_Schema_Documentation_UPDATED.docx
└── data/                         # Auto-created by pipeline — excluded from Git
    ├── weather.db                    # SQLite database
    ├── weather_forecast.csv          # Normalized fact table (DB documentation)
    ├── vibe_dimension.csv            # All 11 vibes — Power BI dimension table
    ├── fit_recommendations.csv       # All 11 fits — Power BI dimension table
    ├── forecast_vibe.csv             # Bridge table (DB documentation)
    └── forecast_fits.csv             # Star schema fact table — primary Power BI source
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/your-username/weather-vibes-etl.git
cd weather-vibes-etl
```

### 2. Create and activate a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Pipeline

```bash
python weather_vibes_app.py
```

The script executes all pipeline stages automatically:

1. **Extract** — Fetches 7-day daily forecast from Open-Meteo API (Louisville, KY) with retry logic and response caching. All outputs written to `data/`.
2. **Transform** — Casts data types, fills NaN values, rounds temperatures to whole numbers, derives `temp_range_f` and `weather_vibe` using dominance-first classification logic
3. **Validate** — Runs 7 named data quality checks with PASS/FAIL logging
4. **Load** — Writes a 4-table normalized schema to `data/weather.db` via SQLAlchemy
5. **Inspect** — Logs table previews to confirm successful load
6. **Export** — Produces 5 CSV files in `data/` including `forecast_fits.csv` with explicit PK and FK columns

---

## Weather Vibe Classification

The pipeline classifies each forecast day into one of 11 weather vibes using dominance-first logic with four inputs: apparent temperature max, precipitation sum, precipitation hours, and max wind speed.

| Vibe | Emoji | Trigger Conditions |
|---|---|---|
| Dramatic Weather Era | ⛈️ | Heavy rain (>= 0.50 in) and wind >= 25 mph |
| Hot Mess Express | 🌧️🥵 | Meaningful rain, wind < 25 mph, temp >= 86F |
| Lo-Fi Chill Day | 🌧️ | Meaningful rain, wind < 25 mph, temp < 86F |
| Unhinged Wind Day | 💨 | No meaningful rain, wind >= 25 mph |
| Offensively Hot | 🥵 | Temp >= 90F, no meaningful rain, wind < 25 mph |
| Almost Too Much | 🫠 | Temp 86 to 89F, no meaningful rain, wind < 25 mph |
| Just Let It Go Day | 🥶 | Temp <= 35F, no meaningful rain, wind >= 20 mph |
| Main Character Energy | 😎 | Temp 72 to 85F, no meaningful rain, wind < 15 mph |
| Soft Launch Day | 🌤️ | Temp 60 to 71F, no meaningful rain, wind < 15 mph |
| Cozy Blanket Day | 🧣 | Temp 35 to 50F, no meaningful rain, wind < 15 mph |
| Existential Meh | 😶 | Fallback — conditions do not match any other vibe |

Meaningful rain = precipitation >= 0.10 inches OR precipitation hours >= 2

---

## Database Schema (Normalized Layer)

### `weather_forecast`
| Column | Type | Description |
|---|---|---|
| forecast_id | INTEGER (PK) | Auto-generated primary key |
| date | TEXT | Forecast date |
| apparent_temperature_max | INTEGER | Max apparent temp (F), rounded to whole number |
| apparent_temperature_min | INTEGER | Min apparent temp (F), rounded to whole number |
| precipitation_sum | REAL | Total precipitation (inches) |
| precipitation_hours | REAL | Hours of precipitation |
| wind_speed_10m_max | REAL | Max wind speed (mph) |
| temp_range_f | INTEGER | Derived daily temp range (F) |
| weather_vibe | TEXT | Assigned vibe label for the day |

### `vibe_dimension`
| Column | Type | Description |
|---|---|---|
| vibe_id | INTEGER (PK) | Auto-generated primary key |
| vibe_name | TEXT UNIQUE | Unique weather vibe label |
| vibe_description | TEXT | Fun personality-driven description |
| vibe_parameters | TEXT | Technical weather conditions that trigger the vibe |
| vibe_emoji | TEXT | Emoji icon for dashboard display |

### `fit_recommendations`
| Column | Type | Description |
|---|---|---|
| fit_id | INTEGER (PK) | Auto-generated primary key |
| vibe_name | TEXT UNIQUE | Vibe label this outfit corresponds to |
| fit | TEXT | Unisex outfit recommendation |
| accessory | TEXT | Accessory callout for the day |
| fit_emoji | TEXT | Emoji icon for dashboard display |

### `forecast_vibe` (bridge table — DB documentation only, not used in Power BI)
| Column | Type | Description |
|---|---|---|
| forecast_id | INTEGER (FK) | References weather_forecast |
| vibe_id | INTEGER (FK) | References vibe_dimension |
| fit_id | INTEGER (FK) | References fit_recommendations |

---

## Analytics Schema (Power BI Star Schema)

### `forecast_fits` (primary Power BI fact table)

A flat joined CSV produced at export time containing only the 7 forecasted days. Includes explicit PK and FK columns for a proper star schema in Power BI.

| Column | Type | Description |
|---|---|---|
| forecast_fits_id | INTEGER (PK) | Surrogate primary key |
| vibe_id | INTEGER (FK) | References vibe_dimension.vibe_id |
| fit_id | INTEGER (FK) | References fit_recommendations.fit_id |
| date | TEXT | Forecast date |
| apparent_temperature_max | INTEGER | Max apparent temp (F) |
| apparent_temperature_min | INTEGER | Min apparent temp (F) |
| temp_range_f | INTEGER | Daily temperature range (F) |
| precipitation_sum | REAL | Total precipitation (inches) |
| precipitation_hours | REAL | Hours of precipitation |
| wind_speed_10m_max | REAL | Max wind speed (mph) |
| weather_vibe | TEXT | Vibe label |
| vibe_emoji | TEXT | Vibe emoji |
| vibe_description | TEXT | Vibe description |
| vibe_parameters | TEXT | Vibe trigger conditions |
| fit | TEXT | Outfit recommendation |
| accessory | TEXT | Accessory callout |
| fit_emoji | TEXT | Fit emoji |

---

## CSV Export Reference

| File | Power BI | Purpose |
|---|---|---|
| `forecast_fits.csv` | Yes — fact table | Primary dashboard source. 7 rows, all fields pre-joined, explicit PK and FK |
| `vibe_dimension.csv` | Yes — dimension | Full 11-vibe reference. Use for the vibe guide card and slicer |
| `fit_recommendations.csv` | Yes — dimension | Full 11-fit reference. Use for the outfit guide card |
| `weather_forecast.csv` | No | Normalized fact table exported for DB documentation |
| `forecast_vibe.csv` | No | Bridge table exported for DB documentation |

---

## Data Quality Checks

| # | Check | Description |
|---|---|---|
| 1 | Null check | No NaN values remain after cleaning |
| 2 | Duplicate check | All dates are unique |
| 3 | Row count | Expects exactly 7 rows |
| 4 | Temperature range | Max temp between -50F and 130F |
| 5 | Precipitation | No negative precipitation values |
| 6 | Schema validation | Temperatures are int64, precipitation and wind are float64 |
| 7 | Vibe completeness | Every row has a weather_vibe label |

---

## Incremental Loading Note

This pipeline uses a full reload strategy by design. Open-Meteo returns a rolling 7-day forecast window where values update with each model run, making a full reload more appropriate than append-only logic. If extended to historical data, an incremental upsert strategy keyed on `date` would be the correct approach.

---

## Loading Data into Power BI

### Import these 3 files only

| File | Role |
|---|---|
| `data/forecast_fits.csv` | Fact table — center of the star schema |
| `data/vibe_dimension.csv` | Dimension table |
| `data/fit_recommendations.csv` | Dimension table |

### Relationships in Model view

- `forecast_fits[vibe_id]` → `vibe_dimension[vibe_id]` — Many to One, Single cross-filter
- `forecast_fits[fit_id]` → `fit_recommendations[fit_id]` — Many to One, Single cross-filter

### Step by step import

1. Open Power BI Desktop
2. Click **Home → Get Data → Text/CSV**
3. Import `forecast_fits.csv`, then repeat for `vibe_dimension.csv` and `fit_recommendations.csv`
4. Go to **Model** view and create the two relationships above using the explicit FK columns
5. Switch to **Report** view and build visuals

### Refreshing data

Re-run `weather_vibes_app.py` to pull a fresh forecast, then click **Home → Refresh** in Power BI.

---

## Documentation Artifacts

| File | Description |
|---|---|
| `docs/Weather_Vibes_ERD.html` | Two-section ERD — Section 1 shows the normalized DB schema with PK/FK indicators; Section 2 shows the Power BI star schema with 3 tables |
| `docs/Weather_Vibes_ERD.pdf` | PDF version for BRD embedding |
| `docs/weather_vibes_data_flow.pdf` | ETL pipeline data flow diagram |

---

## Dashboard Overview

- **Temperature trend** — 7-day line chart showing daily high and low temps with vibe emojis
- **Vibe distribution** — bar chart showing how many days fall into each vibe category
- **KPI cards** — average high temp, average low temp, total precipitation, average wind speed
- **Vibe forecast table** — emoji, vibe name, description, and trigger parameters per day
- **Fit recommendations table** — emoji, vibe name, outfit, and accessory per day
- **Vibe slicer** — filters all visuals dynamically by weather vibe

### Dashboard screenshots

*Screenshot 1: Full 7-day dashboard view*
*Screenshot 2: Dashboard filtered to Lo-Fi Chill Day via the Vibe slicer*
