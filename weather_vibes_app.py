import os
import logging
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
from sqlalchemy import create_engine, text

# -----------------------------------------------
# DIRECTORY SETUP
# -----------------------------------------------
# Ensure the data directory exists before any files are written.
# All outputs — database, CSVs, and cache — are written here.
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Define the database connection string centrally.
# To migrate to PostgreSQL or Supabase, update this string only.
DB_PATH = f"sqlite:///{DATA_DIR}/weather.db"

# -----------------------------------------------
# LOGGING SETUP
# -----------------------------------------------
# Replaces all print() calls with structured, timestamped output.
# Log levels: INFO for normal flow, WARNING for soft issues,
# ERROR for failures, CRITICAL for pipeline termination.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# -----------------------------------------------
# EXTRACT
# -----------------------------------------------
def fetch_weather_data():
    """
    Extracts 7-day daily forecast data from the Open-Meteo API
    for Louisville, KY. Uses a cache session (1-hour TTL) and
    retry logic (5 retries) to handle transient API failures.
    Cache is stored in the data directory alongside other outputs.
    """
    try:
        logger.info("Initializing API session with cache and retry logic...")
        cache_session = requests_cache.CachedSession(
            f'{DATA_DIR}/.cache', expire_after=3600
        )
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        client = openmeteo_requests.Client(session=retry_session)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 38.2542,
            "longitude": -85.7594,
            "daily": [
                "weather_code",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "precipitation_sum",
                "precipitation_hours",
                "wind_speed_10m_max"
            ],
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto"
        }

        logger.info("Sending request to Open-Meteo API...")
        responses = client.weather_api(url, params=params)

        # API response validation: ensure we received a non-empty response
        if not responses or len(responses) == 0:
            raise ValueError("API returned an empty response list.")

        logger.info("API data successfully retrieved.")
        return responses[0]

    except Exception as e:
        logger.error(f"Data extraction failed: {e}")
        raise


# -----------------------------------------------
# TRANSFORM — VIBE DEFINITIONS
# -----------------------------------------------
# Each vibe maps to a description, technical parameters, and emoji.
# Descriptions are loaded into vibe_dimension for Power BI tooltips.
# Parameters are kept separate from descriptions for clean display.
# All 11 vibes are defined here regardless of the current forecast.
VIBE_DEFINITIONS = {
    "Dramatic Weather Era": {
        "description":     "The sky is not okay and it wants you to know it. Rain plus wind means the weather is actively having a crisis. Hold onto your umbrella and your dignity.",
        "vibe_parameters": "Heavy rain (precip >= 0.50 in) and wind >= 25 mph, OR meaningful rain and wind >= 25 mph.",
        "emoji":           "⛈️"
    },
    "Lo-Fi Chill Day": {
        "description":     "The rain showed up but forgot to bring the drama. It is the kind of drizzly day that was made for staying in or pretending you enjoy walking in light rain.",
        "vibe_parameters": "Meaningful rain (precip >= 0.10 in or precip hours >= 2), wind < 25 mph, and max temp < 86F.",
        "emoji":           "🌧️"
    },
    "Hot Mess Express": {
        "description":     "Hot, humid, and raining. Nobody asked for this combination and yet here we are. You will be damp from both directions and there is nothing you can do about it.",
        "vibe_parameters": "Meaningful rain (precip >= 0.10 in or precip hours >= 2), wind < 25 mph, and max temp >= 86F.",
        "emoji":           "🌧️🥵"
    },
    "Unhinged Wind Day": {
        "description":     "Not a cloud in sight but the wind has chosen chaos. Dry and gusty with zero apology. Your hair is on its own today.",
        "vibe_parameters": "No meaningful rain and wind >= 25 mph.",
        "emoji":           "💨"
    },
    "Offensively Hot": {
        "description":     "The sun is too close and too confident. Hot, dry, and absolutely relentless. Hydration is not optional.",
        "vibe_parameters": "Max temp >= 90F, no meaningful rain, wind < 25 mph.",
        "emoji":           "🥵"
    },
    "Almost Too Much": {
        "description":     "Warm enough to question every decision you made getting dressed. Not quite suffering but you are aware of the sun at all times.",
        "vibe_parameters": "Max temp 86 to 89F, no meaningful rain, wind < 25 mph.",
        "emoji":           "🫠"
    },
    "Just Let It Go Day": {
        "description":     "Cold and blustery with something to prove. This is the weather that makes you question why you live here and then immediately remember the food scene.",
        "vibe_parameters": "Max temp <= 35F, no meaningful rain, wind >= 20 mph.",
        "emoji":           "🥶"
    },
    "Main Character Energy": {
        "description":     "The weather is doing everything right and so are you. Warm, dry, breezy enough to feel alive but not enough to ruin anything. Go outside.",
        "vibe_parameters": "Max temp 72 to 85F, no meaningful rain, wind < 15 mph.",
        "emoji":           "😎"
    },
    "Soft Launch Day": {
        "description":     "Pleasant without being showy about it. The kind of day that eases you in gently and asks very little of you. A solid B plus weather day.",
        "vibe_parameters": "Max temp 60 to 71F, no meaningful rain, wind < 15 mph.",
        "emoji":           "🌤️"
    },
    "Cozy Blanket Day": {
        "description":     "Cool, calm, and quietly delightful. The air has a bite but nothing a good layer cannot fix. Soup weather. Thermos weather. Good book weather.",
        "vibe_parameters": "Max temp 35 to 50F, no meaningful rain, wind < 15 mph.",
        "emoji":           "🧣"
    },
    "Existential Meh": {
        "description":     "Not bad, not good, just kind of... there. Temps are middling, wind is meh, sky has no strong opinions.",
        "vibe_parameters": "Fallback. Conditions do not match any other vibe category.",
        "emoji":           "😶"
    },
}


# -----------------------------------------------
# TRANSFORM — FIT RECOMMENDATIONS
# -----------------------------------------------
# Each vibe maps to a unisex outfit, accessory callout, and emoji.
# All 11 vibes are defined here regardless of the current forecast.
# Loaded into fit_recommendations table and fit_recommendations.csv.
FIT_RECOMMENDATIONS = {
    "Dramatic Weather Era": {
        "fit":       "Waterproof shell jacket, rain boots, dark jeans. Prepared but make it fashion.",
        "accessory": "Umbrella and a waterproof bag.",
        "emoji":     "☂️"
    },
    "Lo-Fi Chill Day": {
        "fit":       "Oversized hoodie or tee, joggers or shorts, comfy shoes. Cozy with low effort.",
        "accessory": "Headphones and your favorite drink.",
        "emoji":     "🎧"
    },
    "Hot Mess Express": {
        "fit":       "Lightweight shorts, a moisture-wicking tee, waterproof sandals. There is no winning outfit today, just damage control.",
        "accessory": "A compact umbrella and the acceptance that your hair is not going to cooperate.",
        "emoji":     "☔"
    },
    "Unhinged Wind Day": {
        "fit":       "Fitted athletic wear, windbreaker, baseball cap pulled low. Aerodynamic on purpose.",
        "accessory": "Cap and lip balm.",
        "emoji":     "🧢"
    },
    "Offensively Hot": {
        "fit":       "Linen shorts, breathable tee, sandals, sunglasses. Surrender to the heat gracefully.",
        "accessory": "Sunglasses and SPF 50.",
        "emoji":     "🕶️"
    },
    "Almost Too Much": {
        "fit":       "Lightweight shorts, a loose breathable tee, slip-on sneakers. Minimal layers and maximum airflow.",
        "accessory": "Water bottle and some ice cream just in case.",
        "emoji":     "💧"
    },
    "Just Let It Go Day": {
        "fit":       "Puffer jacket, thermal underlayer, beanie, boots. Full armor.",
        "accessory": "Gloves and hand warmers.",
        "emoji":     "🧤"
    },
    "Main Character Energy": {
        "fit":       "Light wash jeans, tucked-in tee, clean sneakers. You look good and you know it.",
        "accessory": "Fresh kicks and your favorite playlist.",
        "emoji":     "🎵"
    },
    "Soft Launch Day": {
        "fit":       "Relaxed trousers or straight-leg pants, a light crewneck, clean shoes. Quietly put together.",
        "accessory": "A light jacket tied around the waist just in case.",
        "emoji":     "🧥"
    },
    "Cozy Blanket Day": {
        "fit":       "Fleece pullover, corduroy pants, chunky knit beanie. Warm without trying too hard.",
        "accessory": "Scarf and a thermos.",
        "emoji":     "🧣"
    },
    "Existential Meh": {
        "fit":       "Whatever is clean. No one including the weather has strong feelings today.",
        "accessory": "A bag because you probably have somewhere to be.",
        "emoji":     "🎒"
    },
}


# -----------------------------------------------
# TRANSFORM — VIBE LOGIC
# -----------------------------------------------
def get_weather_vibe(temp_max, precip_sum, precip_hours, wind_max):
    """
    Classifies a day's weather vibe using dominance-first rules.
    The strongest weather condition wins outright.

    Inputs:
        temp_max      — apparent temperature max (F), integer
        precip_sum    — total precipitation (inches)
        precip_hours  — hours of precipitation
        wind_max      — max wind speed (mph)

    Meaningful rain = precip_sum >= 0.10 in OR precip_hours >= 2
    Heavy rain      = precip_sum >= 0.50 in
    """
    # Safety: coerce NaN to neutral defaults before comparison
    temp_max     = float(temp_max)     if pd.notna(temp_max)     else 0.0
    precip_sum   = float(precip_sum)   if pd.notna(precip_sum)   else 0.0
    precip_hours = float(precip_hours) if pd.notna(precip_hours) else 0.0
    wind_max     = float(wind_max)     if pd.notna(wind_max)     else 0.0

    # Derived condition flags
    meaningful_rain = (precip_sum >= 0.10) or (precip_hours >= 2)
    heavy_rain      = precip_sum >= 0.50
    windy           = wind_max >= 25

    # Dominance-first rule order:
    # 1) Stormy — heavy rain AND wind wins outright
    if heavy_rain and windy:
        return "Dramatic Weather Era"
    # 2) Extreme heat dominates on dry calm days
    if (temp_max >= 90) and (not meaningful_rain) and (wind_max < 25):
        return "Offensively Hot"
    # 3) Meaningful rain with strong wind
    if meaningful_rain and windy:
        return "Dramatic Weather Era"
    # 4) Hot rainy days get their own vibe, not Lo-Fi Chill Day
    if meaningful_rain and (temp_max >= 86):
        return "Hot Mess Express"
    # 5) Meaningful rain, calmer wind, cooler temp
    if meaningful_rain:
        return "Lo-Fi Chill Day"
    # 6) Wind dominates on dry days
    if (not meaningful_rain) and (wind_max >= 25):
        return "Unhinged Wind Day"
    # 7) Cold and windy
    if (temp_max <= 35) and (wind_max >= 20):
        return "Just Let It Go Day"
    # 8) Warm but not quite Offensively Hot — closes the 86-89F gap
    if (86 <= temp_max <= 89) and (not meaningful_rain) and (wind_max < 25):
        return "Almost Too Much"
    # 9) Comfort vibes — dry and calm
    if (72 <= temp_max <= 85) and (wind_max < 15):
        return "Main Character Energy"
    if (60 <= temp_max <= 71) and (wind_max < 15):
        return "Soft Launch Day"
    if (35 <= temp_max <= 50) and (wind_max < 15):
        return "Cozy Blanket Day"
    # 10) Fallback
    return "Existential Meh"


# -----------------------------------------------
# TRANSFORM — MAIN TRANSFORMATION FUNCTION
# -----------------------------------------------
def transform_weather_data(response):
    """
    Transforms the raw API response into a clean pandas DataFrame.

    Steps:
        1. Extract 6 daily variables from the API response object
        2. Cast all numeric columns to float64 (API returns float32)
        3. Detect and log NaN values, then fill with safe defaults
        4. Round temperatures to whole integers for clean display
        5. Derive temp_range_f (daily temperature swing)
        6. Assign weather_vibe using dominance-first classification
    """
    try:
        logger.info("Beginning data transformation...")
        daily = response.Daily()

        daily_data = {
            "date": pd.date_range(
                start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=daily.Interval()),
                inclusive="left"
            ).tz_convert(response.Timezone().decode())
        }

        daily_data["apparent_temperature_max"] = daily.Variables(1).ValuesAsNumpy()
        daily_data["apparent_temperature_min"] = daily.Variables(2).ValuesAsNumpy()
        daily_data["precipitation_sum"]        = daily.Variables(3).ValuesAsNumpy()
        daily_data["precipitation_hours"]      = daily.Variables(4).ValuesAsNumpy()
        daily_data["wind_speed_10m_max"]       = daily.Variables(5).ValuesAsNumpy()

        df = pd.DataFrame(daily_data)

        # Cast all numeric columns to float64 for consistent schema.
        # The Open-Meteo API returns float32 by default — standardizing
        # to float64 ensures downstream validation and DB loading are predictable.
        numeric_cols = [
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max"
        ]
        df[numeric_cols] = df[numeric_cols].astype("float64")
        logger.info("Numeric columns cast to float64.")

        # NaN detection: log any missing values before cleaning
        nan_counts = df.isnull().sum()
        if nan_counts.any():
            logger.warning(f"NaN values detected before cleaning:\n{nan_counts[nan_counts > 0]}")
        else:
            logger.info("No NaN values detected in raw data.")

        # NaN handling:
        # Precipitation and wind default to 0 (no event = no value)
        # Temperatures use forward-fill to preserve the nearest valid reading
        df["precipitation_sum"]        = df["precipitation_sum"].fillna(0)
        df["precipitation_hours"]      = df["precipitation_hours"].fillna(0)
        df["wind_speed_10m_max"]       = df["wind_speed_10m_max"].fillna(0)
        df["apparent_temperature_max"] = df["apparent_temperature_max"].ffill()
        df["apparent_temperature_min"] = df["apparent_temperature_min"].ffill()

        # Round temperatures to whole numbers for clean Power BI display.
        # Precipitation and wind retain decimals (precision matters there).
        df["apparent_temperature_max"] = df["apparent_temperature_max"].round(0).astype(int)
        df["apparent_temperature_min"] = df["apparent_temperature_min"].round(0).astype(int)
        df["precipitation_sum"]        = df["precipitation_sum"].round(2)
        df["wind_speed_10m_max"]       = df["wind_speed_10m_max"].round(1)

        # Derived metric: daily temperature range (max minus min)
        df["temp_range_f"] = (
            df["apparent_temperature_max"] - df["apparent_temperature_min"]
        ).round(0).astype(int)

        # Derived metric: weather vibe label using dominance-first logic.
        # Passes precipitation_hours as a second rain signal for accuracy.
        df["weather_vibe"] = df.apply(
            lambda row: get_weather_vibe(
                row["apparent_temperature_max"],
                row["precipitation_sum"],
                row["precipitation_hours"],
                row["wind_speed_10m_max"]
            ),
            axis=1
        )

        logger.info(f"Transformation complete. {len(df)} rows ready for validation.")
        return df

    except Exception as e:
        logger.error(f"Data transformation failed: {e}")
        raise


# -----------------------------------------------
# DATA QUALITY & VALIDATION
# -----------------------------------------------
def validate_dataframe(df):
    """
    Runs 7 named data quality checks on the transformed DataFrame.
    Each check logs a clear PASS or FAIL result with detail.
    Pipeline raises RuntimeError and halts if any check fails.

    Checks:
        1. Null value check
        2. Duplicate date detection
        3. Row count verification (expects 7)
        4. Temperature range validation (-50F to 130F)
        5. Precipitation non-negative check
        6. Schema / datatype validation
        7. Vibe completeness check
    """
    logger.info("--- Running Data Quality Validation ---")
    failures = []

    # CHECK 1: Null value check
    null_counts = df.isnull().sum()
    if null_counts.any():
        msg = f"FAIL | Null check: NaN values remain after cleaning:\n{null_counts[null_counts > 0]}"
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info("PASS | Null check: No NaN values found in any column.")

    # CHECK 2: Duplicate date detection
    duplicate_dates = df["date"].duplicated().sum()
    if duplicate_dates > 0:
        msg = f"FAIL | Duplicate check: {duplicate_dates} duplicate date(s) found."
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info(f"PASS | Duplicate check: All {len(df)} dates are unique.")

    # CHECK 3: Row count verification (Open-Meteo returns 7 days by default)
    expected_rows = 7
    if len(df) != expected_rows:
        msg = f"FAIL | Row count check: Expected {expected_rows} rows, got {len(df)}."
        logger.warning(msg)
        failures.append(msg)
    else:
        logger.info(f"PASS | Row count check: {len(df)} rows as expected.")

    # CHECK 4: Temperature range validation (-50F to 130F covers all realistic conditions)
    temp_out_of_range = df[
        (df["apparent_temperature_max"] < -50) | (df["apparent_temperature_max"] > 130)
    ]
    if not temp_out_of_range.empty:
        msg = f"FAIL | Temperature range check: {len(temp_out_of_range)} out-of-range value(s) found."
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info("PASS | Temperature range check: All max temps within -50F to 130F.")

    # CHECK 5: Precipitation non-negative check
    negative_precip = df[df["precipitation_sum"] < 0]
    if not negative_precip.empty:
        msg = f"FAIL | Precipitation check: {len(negative_precip)} negative precipitation value(s) found."
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info("PASS | Precipitation check: All precipitation values are non-negative.")

    # CHECK 6: Schema / datatype validation
    # Temperatures are int64 after whole-number rounding.
    # Precipitation and wind remain float64.
    expected_types = {
        "apparent_temperature_max": "int64",
        "apparent_temperature_min": "int64",
        "precipitation_sum":        "float64",
        "wind_speed_10m_max":       "float64",
        "temp_range_f":             "int64",
        "weather_vibe":             "object"
    }
    type_mismatches = {
        col: str(df[col].dtype)
        for col, expected in expected_types.items()
        if col in df.columns and str(df[col].dtype) != expected
    }
    if type_mismatches:
        msg = f"FAIL | Schema check: Unexpected dtypes: {type_mismatches}"
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info("PASS | Schema check: All columns match expected data types.")

    # CHECK 7: Weather vibe completeness — no unlabeled rows
    missing_vibes = df["weather_vibe"].isnull().sum()
    if missing_vibes > 0:
        msg = f"FAIL | Vibe completeness check: {missing_vibes} row(s) missing a weather_vibe label."
        logger.error(msg)
        failures.append(msg)
    else:
        logger.info("PASS | Vibe completeness check: All rows have a weather_vibe label.")

    # Final result
    if failures:
        logger.error(f"Validation completed with {len(failures)} failure(s). Pipeline halted.")
        raise RuntimeError(f"Data quality validation failed with {len(failures)} error(s).")
    else:
        logger.info("--- All validation checks passed. Proceeding to load. ---")


# -----------------------------------------------
# LOAD — 4-TABLE NORMALIZED SCHEMA
# -----------------------------------------------
#
# INCREMENTAL LOADING NOTE:
# A true incremental load appends only new records on each run,
# using a date key or timestamp to avoid re-inserting existing rows.
#
# This pipeline uses a full reload strategy by design because:
#   1. Open-Meteo returns a rolling 7-day FORECAST window. Previous
#      forecasts are replaced by updated model runs on each call.
#   2. Forecast values for any given date can change between pipeline
#      runs as the model refines predictions, making append-only logic
#      potentially stale.
#   3. The dataset is small (7 rows), so the cost of a full reload
#      is negligible compared to the complexity of upsert logic.
#
# If extended to historical/archive data, an incremental strategy
# using INSERT OR IGNORE or ON CONFLICT DO UPDATE keyed on the
# date column would be the correct approach.
#
def load_to_sqlite(df):
    """
    Loads the transformed DataFrame into a 4-table normalized SQLite schema:
        - weather_forecast:   core forecast metrics with weather_vibe column
        - vibe_dimension:     dimension table — all 11 vibes with descriptions,
                              parameters, and emojis (current forecast only)
        - fit_recommendations: dimension table — all 11 outfit and accessory
                              recommendations
        - forecast_vibe:      bridge table linking forecast_id, vibe_id, fit_id
                              via 3 foreign keys

    Full reload strategy used intentionally — see incremental loading note above.
    All files written to DATA_DIR (data/).
    """
    try:
        logger.info(f"Connecting to SQLite database at {DB_PATH}...")
        engine = create_engine(DB_PATH)

        with engine.connect() as conn:

            # Drop in reverse dependency order to respect foreign keys
            logger.info("Dropping existing tables for full reload...")
            conn.execute(text("DROP TABLE IF EXISTS forecast_vibe;"))
            conn.execute(text("DROP TABLE IF EXISTS fit_recommendations;"))
            conn.execute(text("DROP TABLE IF EXISTS vibe_dimension;"))
            conn.execute(text("DROP TABLE IF EXISTS weather_forecast;"))

            # --- TABLE 1: weather_forecast ---
            logger.info("Creating and loading weather_forecast table...")
            conn.execute(text("""
                CREATE TABLE weather_forecast (
                    forecast_id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    date                     TEXT,
                    apparent_temperature_max INTEGER,
                    apparent_temperature_min INTEGER,
                    precipitation_sum        REAL,
                    precipitation_hours      REAL,
                    wind_speed_10m_max       REAL,
                    temp_range_f             INTEGER,
                    weather_vibe             TEXT
                );
            """))
            df.copy().to_sql("weather_forecast", engine, if_exists="append", index=False)
            logger.info(f"Loaded {len(df)} rows into weather_forecast.")

            # --- TABLE 2: vibe_dimension ---
            logger.info("Creating and loading vibe_dimension table...")
            conn.execute(text("""
                CREATE TABLE vibe_dimension (
                    vibe_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    vibe_name       TEXT UNIQUE,
                    vibe_description TEXT,
                    vibe_parameters TEXT,
                    vibe_emoji      TEXT
                );
            """))
            unique_vibe_names = df["weather_vibe"].unique()
            unique_vibes = pd.DataFrame({
                "vibe_name":        unique_vibe_names,
                "vibe_description": [VIBE_DEFINITIONS.get(v, {}).get("description", "")      for v in unique_vibe_names],
                "vibe_parameters":  [VIBE_DEFINITIONS.get(v, {}).get("vibe_parameters", "")  for v in unique_vibe_names],
                "vibe_emoji":       [VIBE_DEFINITIONS.get(v, {}).get("emoji", "")            for v in unique_vibe_names]
            })
            unique_vibes.to_sql("vibe_dimension", engine, if_exists="append", index=False)
            logger.info(f"Loaded {len(unique_vibes)} unique vibe(s) into vibe_dimension.")

            # --- TABLE 3: fit_recommendations ---
            logger.info("Creating and loading fit_recommendations table...")
            conn.execute(text("""
                CREATE TABLE fit_recommendations (
                    fit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    vibe_name  TEXT UNIQUE,
                    fit        TEXT,
                    accessory  TEXT,
                    fit_emoji  TEXT
                );
            """))
            fit_rows = pd.DataFrame([
                {
                    "vibe_name": vibe,
                    "fit":       FIT_RECOMMENDATIONS[vibe]["fit"],
                    "accessory": FIT_RECOMMENDATIONS[vibe]["accessory"],
                    "fit_emoji": FIT_RECOMMENDATIONS[vibe]["emoji"]
                }
                for vibe in FIT_RECOMMENDATIONS
            ])
            fit_rows.to_sql("fit_recommendations", engine, if_exists="append", index=False)
            logger.info(f"Loaded {len(fit_rows)} fit recommendations into fit_recommendations.")

            # --- TABLE 4: forecast_vibe (bridge) ---
            logger.info("Creating and loading forecast_vibe bridge table...")
            conn.execute(text("""
                CREATE TABLE forecast_vibe (
                    forecast_id INTEGER,
                    vibe_id     INTEGER,
                    fit_id      INTEGER,
                    FOREIGN KEY (forecast_id) REFERENCES weather_forecast(forecast_id),
                    FOREIGN KEY (vibe_id)     REFERENCES vibe_dimension(vibe_id),
                    FOREIGN KEY (fit_id)      REFERENCES fit_recommendations(fit_id)
                );
            """))
            # Pull all three tables back to build the bridge rows
            forecast_table = pd.read_sql("SELECT * FROM weather_forecast;",     engine)
            vibe_table     = pd.read_sql("SELECT * FROM vibe_dimension;",       engine)
            fit_table      = pd.read_sql("SELECT * FROM fit_recommendations;",  engine)

            # weather_vibe is already on forecast_table — merge directly to vibe and fit
            merged = forecast_table.merge(vibe_table, left_on="weather_vibe", right_on="vibe_name")
            merged = merged.merge(fit_table[["fit_id", "vibe_name"]], on="vibe_name")

            forecast_vibe_df = merged[["forecast_id", "vibe_id", "fit_id"]]
            forecast_vibe_df.to_sql("forecast_vibe", engine, if_exists="append", index=False)
            logger.info(f"Loaded {len(forecast_vibe_df)} row(s) into forecast_vibe bridge table.")

        logger.info("4-table normalized schema loaded successfully into data/weather.db.")

    except Exception as e:
        logger.error(f"Database load failed: {e}")
        raise


# -----------------------------------------------
# INSPECT DATABASE
# -----------------------------------------------
def inspect_database():
    """
    Reads back all four loaded tables and logs previews to confirm
    successful database population before CSV export.
    """
    try:
        logger.info("Inspecting loaded database tables...")
        engine = create_engine(DB_PATH)

        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", engine)
        logger.info(f"Tables in database: {tables['name'].tolist()}")

        forecast = pd.read_sql("SELECT * FROM weather_forecast LIMIT 5;", engine)
        logger.info(f"\nweather_forecast preview:\n{forecast.to_string(index=False)}")

        vibe = pd.read_sql("SELECT * FROM vibe_dimension;", engine)
        logger.info(f"\nvibe_dimension preview:\n{vibe.to_string(index=False)}")

        bridge = pd.read_sql("SELECT * FROM forecast_vibe LIMIT 5;", engine)
        logger.info(f"\nforecast_vibe preview:\n{bridge.to_string(index=False)}")

        fits = pd.read_sql("SELECT * FROM fit_recommendations;", engine)
        logger.info(f"\nfit_recommendations preview:\n{fits.to_string(index=False)}")

    except Exception as e:
        logger.error(f"Database inspection failed: {e}")
        raise


# -----------------------------------------------
# EXPORT TO CSV
# -----------------------------------------------
def export_to_csv():
    """
    Exports all four database tables to CSV files in the data/ directory
    for use in Power BI or Plotly Dash dashboards.

    Also produces forecast_fits.csv — a flat joined analytics table scoped to
    only the 7 days in the current forecast window. Includes:
        - forecast_fits_id (PK) — surrogate primary key from weather_forecast.forecast_id
        - vibe_id (FK)          — references vibe_dimension.vibe_id
        - fit_id (FK)           — references fit_recommendations.fit_id
        - all weather metrics, vibe fields, and fit fields pre-joined

    This is the primary Power BI data source. With explicit PK and FK columns,
    it forms a clean star schema with vibe_dimension and fit_recommendations
    without needing the forecast_vibe bridge table on the dashboard side.

    Files written to data/:
        weather_forecast.csv      — core forecast metrics (DB documentation)
        vibe_dimension.csv        — all 11 vibes with descriptions, parameters, emojis
        fit_recommendations.csv   — all 11 outfit and accessory recommendations
        forecast_vibe.csv         — bridge table (DB documentation only)
        forecast_fits.csv         — star schema fact table, primary Power BI source
    """
    try:
        logger.info(f"Exporting tables to CSV in {DATA_DIR}/...")
        engine = create_engine(DB_PATH)

        pd.read_sql("SELECT * FROM weather_forecast;",    engine).to_csv(f"{DATA_DIR}/weather_forecast.csv",    index=False)
        pd.read_sql("SELECT * FROM vibe_dimension;",      engine).to_csv(f"{DATA_DIR}/vibe_dimension.csv",      index=False)
        pd.read_sql("SELECT * FROM fit_recommendations;", engine).to_csv(f"{DATA_DIR}/fit_recommendations.csv", index=False)
        pd.read_sql("SELECT * FROM forecast_vibe;",       engine).to_csv(f"{DATA_DIR}/forecast_vibe.csv",       index=False)

        # forecast_fits: flat analytics join scoped to current forecast only.
        # Includes forecast_fits_id as a surrogate PK and vibe_id/fit_id as
        # explicit FK references to dimension tables — giving this CSV a proper
        # star schema structure for Power BI without needing the bridge table.
        # LEFT JOINs ensure no unmatched rows from the full lookup tables bleed in.
        forecast_fits_query = """
            SELECT
                wf.forecast_id          AS forecast_fits_id,
                vd.vibe_id              AS vibe_id,
                fr.fit_id               AS fit_id,
                wf.date,
                wf.apparent_temperature_max,
                wf.apparent_temperature_min,
                wf.temp_range_f,
                wf.precipitation_sum,
                wf.precipitation_hours,
                wf.wind_speed_10m_max,
                wf.weather_vibe,
                vd.vibe_emoji,
                vd.vibe_description,
                vd.vibe_parameters,
                fr.fit,
                fr.accessory,
                fr.fit_emoji
            FROM weather_forecast wf
            LEFT JOIN vibe_dimension      vd ON wf.weather_vibe = vd.vibe_name
            LEFT JOIN fit_recommendations fr ON wf.weather_vibe = fr.vibe_name
            ORDER BY wf.date ASC;
        """
        forecast_fits = pd.read_sql(forecast_fits_query, engine)
        forecast_fits.to_csv(f"{DATA_DIR}/forecast_fits.csv", index=False)
        logger.info(f"forecast_fits.csv exported with {len(forecast_fits)} rows — forecast_fits_id PK, vibe_id FK, fit_id FK included.")

        logger.info(f"All CSV files exported to {DATA_DIR}/: weather_forecast.csv, vibe_dimension.csv, fit_recommendations.csv, forecast_vibe.csv, forecast_fits.csv (star schema fact table with PK and FK columns)")

    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        raise


# -----------------------------------------------
# MAIN PIPELINE
# -----------------------------------------------
def run_pipeline():
    """
    Orchestrates the full ETL pipeline in 6 stages:
        1. Extract  — fetch 7-day forecast from Open-Meteo API
        2. Transform — clean, cast, round, derive vibe and temp_range_f
        3. Validate  — run 7 named data quality checks
        4. Load      — write 4-table normalized schema to data/weather.db
        5. Inspect   — log table previews to confirm successful load
        6. Export    — produce 5 CSV files in data/ for Power BI
    """
    logger.info("========================================")
    logger.info("  Weather Vibes ETL Pipeline — Start")
    logger.info("========================================")

    try:
        response = fetch_weather_data()
        df       = transform_weather_data(response)
        validate_dataframe(df)
        load_to_sqlite(df)
        inspect_database()
        export_to_csv()
        logger.info("========================================")
        logger.info("  Pipeline completed successfully.")
        logger.info(f"  Outputs written to: {DATA_DIR}/")
        logger.info("========================================")

    except Exception as e:
        logger.critical(f"Pipeline terminated with error: {e}")
        raise


# -----------------------------------------------
# ENTRY POINT
# -----------------------------------------------
if __name__ == "__main__":
    run_pipeline()
