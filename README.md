# Weather Vibes ETL Pipeline and Dashboard

An end-to-end data engineering project that extracts 7-day weather forecast data for Louisville, KY from the Open-Meteo API, applies transformation and data quality checks, loads results into a normalized SQLite database, exports analytics-ready CSV files, and powers an interactive Power BI dashboard.

---

## Project Context and Design Decisions

### Database: SQLite vs PostgreSQL

This pipeline uses SQLite as its database backend. Due to project timeline constraints and the iterative nature of this pipeline's development, SQLite was selected in place of PostgreSQL or Supabase. SQLite provides identical schema structure, SQL querying, and SQLAlchemy integration to a hosted PostgreSQL solution, making it a functionally equivalent choice for local development and academic demonstration. The pipeline is architected to support a straightforward migration to PostgreSQL or Supabase by updating the SQLAlchemy connection string alone — no other code changes are required.

### ETL in a Single Script

The complete ETL workflow — extraction, transformation, validation, loading, and CSV export — is implemented in a single Python script. This was an intentional design choice to keep the pipeline self-contained, reproducible, and easy to execute. The script is modular with clearly separated functions for each pipeline stage, following the same organizational principles as a multi-file ETL framework.

### Schema Design: Normalized to Star

The database schema was designed in two layers, reflecting the course content on normalized vs star schemas:

**Normalized layer (database storage):**
- `weather_forecast` — fact table with core metrics
- `vibe_dimension` — dimension table with vibe labels, descriptions, parameters, and emojis
- `fit_recommendations` — dimension table with outfit and accessory recommendations
- `forecast_vibe` — bridge table linking forecasts to vibes and fits via foreign keys

**Star schema layer (analytics):**
- `forecast_fits.csv` — a flat denormalized join of the current 7-day forecast with all vibe and fit fields pre-joined. This is the primary Power BI data source and functions as the center of the star schema in the dashboard data model.

This approach demonstrates both normalization concepts for data integrity and denormalization for analytics performance — a deliberate architectural decision rather than a limitation.

---

## Project Structure

```
weather-vibes-etl/
├── weather_vibes_app.py      # Main ETL pipeline script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── CHANGELOG.md              # Full record of changes from original script
├── vibe_guide.txt            # Vibe and fit reference card for Power BI text box
├── weather.db                # SQLite database (auto-created on first run)
├── weather_forecast.csv      # Core forecast metrics table
├── vibe_dimension.csv        # All 11 vibe labels, descriptions, parameters, and emojis
├── fit_recommendations.csv   # All 11 outfit and accessory recommendations
├── forecast_vibe.csv         # Bridge table linking forecasts to vibes and fits
└── forecast_fits.csv         # Flat joined table — primary Power BI data source
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

1. **Extract** — Fetches 7-day daily forecast from Open-Meteo API (Louisville, KY) with retry logic and response caching
2. **Transform** — Casts data types, fills NaN values, rounds temperatures to whole numbers, derives `temp_range_f` and `weather_vibe` using dominance-first classification logic
3. **Validate** — Runs 7 named data quality checks with PASS/FAIL logging
4. **Load** — Writes a 4-table normalized schema to `weather.db` via SQLAlchemy
5. **Inspect** — Logs table previews to confirm successful load
6. **Export** — Produces 5 CSV files including `forecast_fits.csv`, a flat joined analytics table

---

## Weather Vibe Classification

The pipeline classifies each forecast day into one of 11 weather vibes using dominance-first logic. The classification uses four inputs: apparent temperature max, precipitation sum, precipitation hours, and max wind speed.

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

## Database Schema

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
| vibe_name | TEXT | Unique weather vibe label |
| vibe_description | TEXT | Fun personality-driven description |
| vibe_parameters | TEXT | Technical weather conditions that trigger the vibe |
| vibe_emoji | TEXT | Emoji icon for dashboard display |

### `fit_recommendations`
| Column | Type | Description |
|---|---|---|
| fit_id | INTEGER (PK) | Auto-generated primary key |
| vibe_name | TEXT | Vibe label this outfit corresponds to |
| fit | TEXT | Unisex outfit recommendation |
| accessory | TEXT | Accessory callout for the day |
| fit_emoji | TEXT | Emoji icon for dashboard display |

### `forecast_vibe` (bridge table)
| Column | Type | Description |
|---|---|---|
| forecast_id | INTEGER (FK) | References weather_forecast |
| vibe_id | INTEGER (FK) | References vibe_dimension |
| fit_id | INTEGER (FK) | References fit_recommendations |

### `forecast_fits` (flat analytics export)
A joined CSV produced at export time. Contains only the 7 forecasted days with all weather metrics, vibe label, vibe description, vibe parameters, outfit, accessory, and emojis in one flat file. This is the primary Power BI data source.

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

### Recommended import strategy

Import only these three files:

| File | Role | Purpose |
|---|---|---|
| `forecast_fits.csv` | Fact table | Primary dashboard table — current 7-day forecast with vibe and fit pre-joined |
| `vibe_dimension.csv` | Dimension table | Full 11-vibe reference including vibes not in the current forecast |
| `fit_recommendations.csv` | Dimension table | Full 11-fit reference for the outfit guide |

### Power BI data model (star schema)

After importing, set up two relationships in Model view:

- `forecast_fits[weather_vibe]` → `vibe_dimension[vibe_name]` — Many to One, Single cross-filter direction
- `forecast_fits[weather_vibe]` → `fit_recommendations[vibe_name]` — Many to One, Single cross-filter direction

This produces a clean 3-table star schema with `forecast_fits` as the center fact table.

### Step by step import

1. Open Power BI Desktop
2. Click **Home → Get Data → Text/CSV**
3. Import `forecast_fits.csv`, then repeat for `vibe_dimension.csv` and `fit_recommendations.csv`
4. Go to **Model** view and create the two relationships above
5. Switch to **Report** view and build visuals

### Refreshing data

Re-run `weather_vibes_app.py` to pull a fresh forecast, then click **Home → Refresh** in Power BI to update all visuals.

---

## Dashboard Overview

The Power BI dashboard communicates the following business insights:

- **Temperature trend** — 7-day line chart showing daily high and low temps with vibe emojis as data point labels
- **Vibe distribution** — bar chart showing how many days this week fall into each vibe category
- **KPI cards** — average high temp, average low temp, total precipitation, and average wind speed
- **Vibe forecast table** — emoji, vibe name, description, and trigger parameters for each day in the forecast
- **Fit recommendations table** — emoji, vibe name, outfit, and accessory for each day
- **Vibe slicer** — filters all visuals dynamically by weather vibe

### Dashboard screenshots

*Screenshot 1: Full 7-day dashboard view*
*Screenshot 2: Dashboard filtered to Lo-Fi Chill Day via the Vibe slicer*


#   w e a t h e r - v i b e s - e t l  
 