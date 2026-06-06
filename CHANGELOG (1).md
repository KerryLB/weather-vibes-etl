# Weather Vibes ETL Pipeline — Changelog

A full record of every change made from the original `weather_vibes_app.py` submission to the final version, organized by category.

---

## Original Script Summary

The original pipeline included:
- Open-Meteo API extraction for Louisville, KY (7-day forecast)
- Basic transformation using `apparent_temperature_max`, `precipitation_sum`, and `wind_speed_10m_max`
- A `get_weather_vibe()` function with 9 vibe labels using simple if/elif logic
- A 3-table SQLite schema: `weather_forecast`, `vibe_dimension`, `forecast_vibe`
- CSV export for Power BI
- Raw `print()` statements for output
- No logging, no error handling, no data validation

---

## Changes by Category

---

### 1. Logging and Error Handling

**What changed:**
- Replaced all `print()` statements with Python's built-in `logging` module
- Added `logging.basicConfig()` at the top of the file with timestamp formatting and log levels (`INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- Wrapped every major function (`fetch_weather_data`, `transform_weather_data`, `load_to_sqlite`, `inspect_database`, `export_to_csv`) in `try/except` blocks
- Added `logger.critical()` in `run_pipeline()` to catch and report any top-level pipeline failure

**Why:**
- Raw `print()` is not considered professional engineering practice
- Structured logging gives timestamps, severity levels, and consistent formatting
- Error handling prevents silent failures and produces informative messages when something goes wrong

---

### 2. Data Extraction Improvements

**What changed:**
- Added API response validation: raises `ValueError` if the API returns an empty response list
- Added `precipitation_hours` to the extracted variables (`daily.Variables(4)`) — it was already in the API `params` list in the original but was never pulled into the DataFrame

**Why:**
- API response validation catches connectivity or quota issues early before bad data propagates downstream
- `precipitation_hours` is used by the improved vibe logic as a second rain signal

---

### 3. Data Type Standardization

**What changed:**
- Added explicit `.astype("float64")` cast for all numeric columns immediately after the DataFrame is built
- The Open-Meteo API returns `float32` by default; standardizing to `float64` prevents schema validation failures downstream

**Why:**
- Inconsistent dtypes caused the schema validation check to fail with a `FAIL` log on the first run
- Casting at the source ensures all downstream logic operates on a consistent type

---

### 4. NaN Handling

**What changed:**
- Added detection and logging of NaN values before cleaning (`logger.warning` if any found)
- `precipitation_sum` and `wind_speed_10m_max` filled with `0` (no event = no value)
- `precipitation_hours` filled with `0`
- `apparent_temperature_max` and `apparent_temperature_min` forward-filled using `.ffill()`

**Why:**
- The original script had no NaN handling; missing API values would propagate silently into the database
- Forward-fill for temperature preserves the most recent valid reading rather than defaulting to zero, which would corrupt vibe classification

---

### 5. Temperature and Numeric Rounding

**What changed:**
- `apparent_temperature_max` and `apparent_temperature_min` rounded to whole numbers using `.round(0).astype(int)`, producing clean integer values (e.g. 87 instead of 87.3124817)
- `temp_range_f` rounded to whole number integer as well
- `wind_speed_10m_max` rounded to 1 decimal place
- `precipitation_sum` rounded to 2 decimal places

**Why:**
- Raw API values return many decimal places which display poorly in Power BI cards and tables
- Whole number temperatures are more intuitive and readable on a dashboard
- Precipitation and wind retain decimals since a difference of 0.25 inches of rain or 1.5 mph of wind is meaningfully different

---

### 6. Vibe Logic Improvements

**What changed:**
- `get_weather_vibe()` signature updated from `(temp, precip, wind)` to `(temp_max, precip_sum, precip_hours, wind_max)`
- Added `meaningful_rain` flag: `precipitation_sum >= 0.10 OR precipitation_hours >= 2`
- Added `heavy_rain` flag: `precipitation_sum >= 0.50`
- Added `windy` flag: `wind_max >= 25`
- Switched from simple if/elif chain to dominance-first rule ordering so the strongest condition always wins
- Added NaN safety handling inside the function itself (`pd.notna()` checks)
- Added new vibe **Almost Too Much** for 86 to 89F dry calm days, closing the gap that caused those temperatures to incorrectly fall through to `Existential Meh`

**Why:**
- The original logic used a single precipitation threshold (`precip > 0`) which is too sensitive — light dew or trace amounts would trigger rain vibes
- `precipitation_hours` provides a more reliable secondary rain signal
- The 86 to 89F range had no matching rule in the original logic, causing warm sunny days to be labeled `Existential Meh` — incorrect and misleading on a dashboard

---

### 7. Derived Metrics

**What changed:**
- Added `temp_range_f` column: `apparent_temperature_max - apparent_temperature_min`, rounded to a whole number integer
- `weather_vibe` column added directly to `weather_forecast` table (not just the bridge table) for direct Power BI use
- `precipitation_hours` added to `weather_forecast` table so the data driving vibe classification is visible alongside the label

**Why:**
- `temp_range_f` is a useful analytics metric for showing daily temperature variability on a dashboard
- Having `weather_vibe` directly on `weather_forecast` means Power BI can build visuals from a single table without needing to navigate relationships

---

### 8. Data Validation

**What changed:**
- Added a full `validate_dataframe()` function with 7 named checks, each logging a clear `PASS` or `FAIL` message:
  1. Null value check
  2. Duplicate date detection
  3. Row count verification (expects 7 rows)
  4. Temperature range validation (-50F to 130F)
  5. Precipitation non-negative check
  6. Schema and datatype validation — expects `int64` for temperature columns and `temp_range_f` (after whole-number rounding), and `float64` for precipitation and wind
  7. Weather vibe completeness check
- Pipeline raises `RuntimeError` and halts if any check fails

**Why:**
- The original script had zero validation
- The assignment rubric explicitly requires multiple meaningful validation checks with informative output
- Halting on failure prevents bad data from being written to the database
- Schema check expected types were updated to reflect `int64` for temperature columns after whole-number rounding was introduced, keeping validation in sync with actual data types

---

### 9. Incremental Loading Documentation

**What changed:**
- Added a detailed comment block directly above `load_to_sqlite()` explaining why a full reload strategy is used instead of incremental loading

**Why:**
- The assignment rubric requires either implementation of incremental loading or a clear explanation of why it was not used
- The reasoning is sound: Open-Meteo returns a rolling 7-day forecast where values update with each model run, making a full reload more appropriate than append-only logic

---

### 10. Database Schema Expansion

**What changed:**
- `weather_forecast` table: added `precipitation_hours`, `temp_range_f`, and `weather_vibe` columns
- `vibe_dimension` table: added `vibe_description` and `vibe_emoji` columns
- Added new `fit_recommendations` table (Table 3) with `vibe_name`, `fit`, `accessory`, and `fit_emoji` columns
- `forecast_vibe` bridge table is now Table 4

**Why:**
- Richer schema gives Power BI more to work with directly without requiring calculated columns or DAX workarounds
- `vibe_emoji` and `fit_emoji` render natively in Power BI tables, cards, and tooltips
- `fit_recommendations` is a standalone lookup table that adds a fun and practical layer to the dashboard

---

### 11. VIBE_DEFINITIONS and FIT_RECOMMENDATIONS Constants

**What changed:**
- Added `VIBE_DEFINITIONS` as a module-level dict mapping each vibe to a `description` and `emoji`
- Added `FIT_RECOMMENDATIONS` as a module-level dict mapping each vibe to a `fit`, `accessory`, and `emoji`
- All text fields written without dashes (`—` or `-`) to prevent CSV rendering issues

**Why:**
- Centralizing definitions in module-level constants makes them easy to update without touching function logic
- Descriptions and emojis load directly into the database from these dicts, keeping the data and the code in sync
- Dashes caused formatting issues when the strings were written to CSV and opened in Excel or Power BI

---

### 12. New Vibe: Almost Too Much

**What changed:**
- Added `Almost Too Much` as the 10th vibe label
- Triggers when `86 <= temp_max <= 89` and conditions are dry and calm
- Description: "Warm enough to question every decision you made getting dressed. Not quite suffering but you are aware of the sun at all times."
- Emoji: 🫠
- Fit: Lightweight shorts, a loose breathable tee, slip-on sneakers. Minimal layers and maximum airflow.
- Accessory: Water bottle and some ice cream $$ just in case. 💧

**Why:**
- The original logic had a dead zone between Main Character Energy (72 to 85F) and Offensively Hot (>=90F)
- Days in the 86 to 89F range with no rain and calm wind were incorrectly falling through to `Existential Meh`

---

### 13. Fit Recommendation Refinements

**What changed:**
- All fit and accessory descriptions rewritten to be fully unisex (no gendered language)
- Duplicate 🎒 emoji resolved: Soft Launch Day updated to 🧥, Existential Meh kept 🎒
- Main Character Energy emoji updated from 👟 to 🎵 to reflect accessory change
- Individual accessory and fit updates per vibe:
  - Almost Too Much: accessory changed to "Water bottle and some ice cream $$ just in case"
  - Main Character Energy: accessory changed to "Fresh kicks and your favorite playlist"
  - Soft Launch Day: fit updated to "Relaxed trousers or straight-leg pants, a light crewneck, clean shoes. Quietly put together."
  - Cozy Blanket Day: fit updated to "Fleece pullover, corduroy pants, chunky knit beanie. Warm without trying too hard."

**Why:**
- Original descriptions contained gendered references (e.g. "hair tie", "cottagecore") that did not fit the unisex intent of the project
- Duplicate emojis on the dashboard would make it harder to distinguish vibes at a glance

---

### 14. CSV Export Updates

**What changed:**
- Added `fit_recommendations.csv` to the export
- All four tables now exported: `weather_forecast.csv`, `vibe_dimension.csv`, `fit_recommendations.csv`, `forecast_vibe.csv`

**Why:**
- Power BI needs all tables as CSVs since it does not natively support SQLite without an ODBC driver
- `fit_recommendations` is a standalone table that needs its own file for Power BI import

---

### 15. Supporting Files Added

**What changed:**
- Added `requirements.txt` listing all dependencies with pinned versions
- Added `README.md` with setup instructions, schema documentation, validation check descriptions, incremental loading rationale, and a step-by-step Power BI loading guide

**Why:**
- The assignment submission checklist explicitly requires both files
- The README documents the Power BI workflow so the project is reproducible end-to-end

---

### 16. Vibe Descriptions Rewritten

**What changed:**
- All 10 vibe descriptions rewritten in a fun, personality-driven tone consistent with the project's creative theme
- `vibe_parameters` added as a new field in `VIBE_DEFINITIONS` separating the technical weather conditions from the human-readable description
- `vibe_parameters` added as a column in the `vibe_dimension` table and CSV so Power BI can display conditions separately from the vibe description

**Why:**
- Original descriptions were dry and technical (e.g. "Rainy day with strong winds (precipitation > 0 and wind >= 25 mph)") and did not match the fun tone of the project
- Separating parameters from descriptions keeps the dashboard clean — a card can show the fun description as a headline and the parameters as fine print

---

### 17. Bridge Table Expanded

**What changed:**
- `fit_id` added as a third column in the `forecast_vibe` bridge table with a foreign key referencing `fit_recommendations(fit_id)`
- Merge logic updated to pull `fit_id` by joining on `vibe_name` after the vibe dimension merge

**Why:**
- The original bridge table only linked `forecast_id` to `vibe_id`, leaving `fit_recommendations` as an unconnected dimension
- Adding `fit_id` to the bridge table makes the relational model complete — any forecast day is now fully connected to its weather data, vibe label, and outfit recommendation in one join

---

### 18. forecast_fits.csv — Flat Joined Analytics Export

**What changed:**
- Added `forecast_fits.csv` as a fifth export produced by a SQL JOIN inside `export_to_csv()`
- Joins `weather_forecast` to `vibe_dimension` and `fit_recommendations` on `weather_vibe = vibe_name`
- Contains only the 7 days in the current forecast window — no unmatched vibe rows from the full lookup tables
- Includes all weather metrics, vibe label, vibe emoji, vibe description, vibe parameters, fit, accessory, and fit emoji in one flat file

**Why:**
- `fit_recommendations` contains all 10 vibes as a static lookup table, which caused all 10 outfits to appear in Power BI even when only 3 or 4 vibes were forecasted that week
- A flat joined export scoped to the current forecast solves this without requiring Power BI relationship filters
- Simplifies dashboard building significantly — one table covers all visuals without navigation through relationships
- Recommended as the primary Power BI data source going forward

---

### 19. Hot Mess Express — New Vibe

**What changed:**
- Added `Hot Mess Express` as the 11th vibe label
- Triggers when meaningful rain is present, wind < 25 mph, and max temp >= 86F
- `Lo-Fi Chill Day` updated with a max temp ceiling of < 86F to prevent hot humid days from being misclassified
- Description: "Hot, humid, and raining. Nobody asked for this combination and yet here we are. You will be damp from both directions and there is nothing you can do about it."
- Emoji: 🌧️🥵
- Fit: Lightweight shorts, a moisture-wicking tee, waterproof sandals. There is no winning outfit today, just damage control.
- Accessory: A compact umbrella and the acceptance that your hair is not going to cooperate. ☔
- Added to `VIBE_DEFINITIONS`, `FIT_RECOMMENDATIONS`, vibe logic, and `vibe_guide.txt`

**Why:**
- A 94F rainy day was being classified as `Lo-Fi Chill Day` because the original logic had no temperature ceiling for rainy vibes
- Hot and humid with rain is a fundamentally different experience from a cool drizzly day and deserves its own identity
- The 86F boundary aligns cleanly with the existing vibe temperature boundaries (Almost Too Much starts at 86F on dry days)

---

### 20. ERD and Data Flow Diagrams Updated

**What changed:**
- `Weather_Vibes_ERD.html` rebuilt from scratch as a fully updated entity relationship diagram including:
  - All 5 tables: `weather_forecast`, `vibe_dimension`, `fit_recommendations`, `forecast_vibe`, and `forecast_fits`
  - Primary key (PK) rows highlighted and labeled in each table
  - Foreign key (FK) rows highlighted and labeled in the bridge table
  - All new columns added since the original ERD: `precipitation_hours`, `temp_range_f`, `weather_vibe`, `vibe_description`, `vibe_parameters`, `vibe_emoji`, `fit_emoji`
  - Dashed gray lines showing normalized FK relationships with 1 and * cardinality labels
  - Green dashed lines showing the denormalized join paths into `forecast_fits`
  - Legend explaining line types and PK/FK color coding
- `weather_vibes_data_flow.html` updated to include `forecast_fits` in the export section, labeled as the primary Power BI data source
- Both files added to the project structure in README.md
- New Documentation Artifacts section added to README.md describing both diagram files

**Why:**
- The original ERD was outdated, showing only 3 tables with no PK/FK indicators and missing all columns added during development
- The data flow diagram was missing `forecast_fits.csv` which is now the primary Power BI data source
- Both diagrams are needed for BRD documentation and GitHub repository completeness

---

## Summary Table

| # | Change | Original | Final |
|---|---|---|---|
| 1 | Logging | `print()` only | `logging` module with timestamps and levels |
| 2 | Error handling | None | `try/except` in every function |
| 3 | API validation | None | Empty response check |
| 4 | `precipitation_hours` | In params but never extracted | Extracted and used in vibe logic |
| 5 | Data types | `float32` from API | Cast to `float64` |
| 6 | NaN handling | None | Fill and forward-fill with logging |
| 7 | Rounding | None | Temps and temp_range_f to whole integers, wind to 1dp, precip to 2dp |
| 8 | Vibe logic | Simple if/elif, 3 inputs | Dominance-first, 4 inputs, NaN-safe |
| 9 | Vibe count | 9 | 10 (Almost Too Much added) |
| 10 | Validation | None | 7 named checks with PASS/FAIL logging |
| 11 | Incremental loading | Full reload, unexplained | Full reload with detailed justification comment |
| 12 | `weather_forecast` columns | 5 | 8 (added precipitation_hours, temp_range_f, weather_vibe) |
| 13 | `vibe_dimension` columns | 1 | 3 (added vibe_description, vibe_emoji) |
| 14 | Tables in DB | 3 | 4 (fit_recommendations added) |
| 15 | CSVs exported | 3 | 4 (fit_recommendations.csv added) |
| 16 | VIBE_DEFINITIONS | None | Module-level dict with description and emoji per vibe |
| 17 | FIT_RECOMMENDATIONS | None | Module-level dict with fit, accessory, and emoji per vibe |
| 18 | Supporting files | None | requirements.txt and README.md |
| 19 | Schema validation expected types | N/A | Updated to int64 for temp columns after whole-number rounding |
| 20 | Fit descriptions | Gendered language in some fields | Rewritten to be unisex across all 10 vibes |
| 21 | Fit and vibe emojis | Duplicate bag emoji on Soft Launch Day and Existential Meh | Soft Launch Day updated to jacket emoji, Main Character Energy updated to music note emoji |
| 22 | Vibe descriptions | Dry technical descriptions | Rewritten in fun personality-driven tone across all 10 vibes |
| 23 | vibe_parameters field | N/A | Added to VIBE_DEFINITIONS and vibe_dimension table to separate conditions from descriptions |
| 24 | forecast_vibe bridge table | forecast_id and vibe_id only | Added fit_id as third column with foreign key to fit_recommendations |
| 25 | forecast_fits.csv | N/A | New flat joined export with only current 7-day forecast vibes and fits, purpose-built for Power BI |
| 26 | README | Outdated schema, 3 CSVs, old Power BI steps | Fully rewritten with updated schema, 5 CSV descriptions, recommended import strategy, business insights section |
| 27 | Hot Mess Express vibe | N/A | New vibe for hot rainy days (>= 86F with meaningful rain and wind < 25 mph) |
| 28 | Lo-Fi Chill Day temp ceiling | No temperature limit | Added max temp < 86F to prevent hot humid days from being labeled chill |
| 29 | ERD | Outdated 3-table diagram, no PK/FK indicators | Rebuilt with all 5 tables, PK/FK labels, cardinality, new columns, and two schema layers |
| 30 | Data flow diagram | Missing forecast_fits in export section | Updated to include forecast_fits as primary Power BI source |
| 31 | README project structure | Missing diagram files | Added Weather_Vibes_ERD.html and weather_vibes_data_flow.html |
| 32 | README documentation artifacts | N/A | New section describing both diagram files and how to export them |
