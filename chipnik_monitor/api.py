from __future__ import annotations

import json
import os
import calendar
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from pydantic import BaseModel, Field

from pymongo import MongoClient  # type: ignore
from pymongo.collection import Collection  # type: ignore

import chipnik_monitor as monitor

# ML model imports
import numpy as np
import pickle
from prophet import Prophet
from sklearn.preprocessing import StandardScaler

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

app = FastAPI(
    title="Chipnik Monitor API",
    version="1.1.0",
    description="GeoJSON-driven access to HLS reports computed by Chipnik Monitor",
)

_DEFAULT_LOOKBACK_DAYS = 720
_DEFAULT_MAX_CLOUD = 20
_DEFAULT_DATASET = "Both"
_DEFAULT_MODEL = "eurustic"

_OPERATIONS: Dict[str, Dict[str, Any]] = {}
_OPERATIONS_LOCK = threading.Lock()

_MONGO_CLIENT: Optional[MongoClient] = None
_MONGO_REPORTS: Optional[Collection] = None
_MONGO_LOCK = threading.Lock()

_PROFILE_LOOKUP = {profile["name"].lower(): profile for profile in monitor.CROP_PROFILES}
_ALT_PROFILE_NAMES = {
    "potatoe": "potato",
    "tomatoe": "tomato",
}

# ML Model globals
_ML_MODEL: Optional[Prophet] = None
_MODEL_LOCK = threading.Lock()
_MODEL_OUTPUT_DIR = Path(__file__).resolve().parent / "models"


class ReportRequest(BaseModel):
    geojson: Dict[str, Any]
    yield_type: str = Field(..., alias="yieldType")
    field_id: Optional[str] = Field(None, alias="fieldId")

    class Config:
        allow_population_by_field_name = True


def _isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _normalize_yield_key(name: str) -> str:
    key = name.strip().lower().replace("_", " ")
    key = _ALT_PROFILE_NAMES.get(key, key)
    return key


def _get_reports_collection() -> Collection:
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB")
    if not uri or not db_name:
        raise RuntimeError("MONGO_URI and MONGO_DB must be configured")

    global _MONGO_CLIENT, _MONGO_REPORTS

    with _MONGO_LOCK:
        if _MONGO_REPORTS is not None:
            return _MONGO_REPORTS

        try:
            _MONGO_CLIENT = MongoClient(uri)
            database = _MONGO_CLIENT[db_name]
            _MONGO_REPORTS = database["reports"]
        except Exception:
            monitor.logger.exception("Failed to initialize MongoDB connection")
            _MONGO_CLIENT = None
            _MONGO_REPORTS = None
            raise

    return _MONGO_REPORTS


def _mongo_ready_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _serialisable_geojson(payload: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    if isinstance(payload, dict):
        return payload
    try:
        return json.loads(payload)
    except Exception:
        return payload


def _load_ml_model() -> Optional[Prophet]:
    """Load the trained Prophet ML model for NDVI prediction."""
    global _ML_MODEL
    
    with _MODEL_LOCK:
        if _ML_MODEL is not None:
            return _ML_MODEL
        
        # Try to load the saved model
        model_file = _MODEL_OUTPUT_DIR / "ndvi_prophet_model.pkl"
        if not model_file.exists():
            monitor.logger.warning("ML model file not found at %s", model_file)
            return None
        
        try:
            with open(model_file, 'rb') as f:
                _ML_MODEL = pickle.load(f)
            monitor.logger.info("Successfully loaded ML model from %s", model_file)
            return _ML_MODEL
        except Exception as exc:
            monitor.logger.exception("Failed to load ML model: %s", exc)
            return None


def _calculate_vpd(temperature: float, humidity: float) -> float:
    """Calculate Vapor Pressure Deficit (VPD)."""
    try:
        # Saturation vapor pressure (kPa) using Magnus formula
        svp = 0.6112 * np.exp(17.67 * temperature / (temperature + 243.5))
        # Actual vapor pressure (kPa)
        avp = svp * (humidity / 100.0)
        # VPD (kPa)
        return max(0, svp - avp)
    except Exception:
        return 0.0


def _add_growing_season_indicator(df: pd.DataFrame) -> pd.DataFrame:
    """Add growing season indicator based on month."""
    df = df.copy()
    if 'ds' in df.columns:
        df['month'] = pd.to_datetime(df['ds']).dt.month
    elif 'date' in df.columns:
        df['month'] = pd.to_datetime(df['date']).dt.month
    else:
        # Default growing season
        df['is_growing_season'] = 1
        return df
    
    # Growing season: April to September (months 4-9)
    df['is_growing_season'] = ((df['month'] >= 4) & (df['month'] <= 9)).astype(int)
    return df


def _prepare_ml_features(history_data: List[Dict[str, Any]], weather_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for ML model prediction."""
    if not history_data:
        return pd.DataFrame()
    
    # Convert history to DataFrame
    df = pd.DataFrame(history_data)
    df['ds'] = pd.to_datetime(df['date'])
    df['y'] = df['ndvi']
    
    # Remove rows with missing NDVI
    df = df.dropna(subset=['y'])
    
    if df.empty:
        return df
    
    # Add weather features
    if not weather_df.empty:
        weather_daily = weather_df.copy()
        weather_daily['date'] = pd.to_datetime(weather_daily['date']).dt.date
        df['date_only'] = df['ds'].dt.date
        
        # Get available weather columns
        weather_cols = list(weather_daily.columns)
        merge_cols = ['date']
        
        # Add available weather columns to merge
        for col in ['temperature_deg_c', 'humidity_pct', 'cloudcover_pct', 'wind_speed_mps', 'clarity_pct']:
            if col in weather_cols:
                merge_cols.append(col)
        
        # Merge weather data
        df = df.merge(weather_daily[merge_cols], 
                     left_on='date_only', right_on='date', how='left')
        
        # Rename columns to match model expectations with safe access
        df['temperature_mean'] = df.get('temperature_deg_c', pd.Series([20.0] * len(df))).fillna(20.0)
        df['humidity'] = df.get('humidity_pct', pd.Series([60.0] * len(df))).fillna(60.0)
        df['cloudcover_mean'] = df.get('cloudcover_pct', pd.Series([30.0] * len(df))).fillna(30.0)
        df['wind_speed_mean'] = df.get('wind_speed_mps', pd.Series([2.0] * len(df))).fillna(2.0)
        df['clarity_index'] = (df.get('clarity_pct', pd.Series([70.0] * len(df))).fillna(70.0) / 100.0)
        
        # Calculate derived weather variables
        df['vapor_pressure_deficit'] = df.apply(
            lambda row: _calculate_vpd(row['temperature_mean'], row['humidity']),
            axis=1
        )
        df['growing_degree_days'] = df['temperature_mean'].apply(
            lambda x: max(0, x - 10) if pd.notna(x) else 0
        )
        df['precipitation'] = 0.0  # Default value if not available
        
    else:
        # Use default weather values if no weather data
        df['temperature_mean'] = 20.0
        df['humidity'] = 60.0
        df['cloudcover_mean'] = 30.0
        df['wind_speed_mean'] = 2.0
        df['clarity_index'] = 0.7
        df['vapor_pressure_deficit'] = 1.0
        df['growing_degree_days'] = 10.0
        df['precipitation'] = 0.0
    
    # Add regional features (default to primary region)
    df['region_numeric'] = 0
    df['is_northern_region'] = 0
    
    # Add growing season indicator
    df = _add_growing_season_indicator(df)
    
    return df[['ds', 'y', 'temperature_mean', 'humidity', 'cloudcover_mean', 
               'wind_speed_mean', 'clarity_index', 'vapor_pressure_deficit',
               'growing_degree_days', 'precipitation', 'region_numeric', 
               'is_northern_region', 'is_growing_season']]


def _calculate_flowering_start_date_ml(forecast_data: pd.DataFrame, method: str = 'ndvi_threshold') -> Dict[str, Any]:
    """
    Calculate flowering start date based on ML NDVI predictions
    
    Parameters:
    forecast_data (pd.DataFrame): Prophet forecast with 'ds' and 'yhat' columns
    method (str): Method for calculating flowering start
    
    Returns:
    dict: Flowering prediction results
    """
    if forecast_data is None or len(forecast_data) == 0:
        return {'flowering_start_date': None, 'method': method, 'confidence': 0}
    
    # Create a copy and ensure proper date handling
    df = forecast_data.copy()
    df['ds'] = pd.to_datetime(df['ds'])
    df = df.sort_values('ds')
    
    flowering_results = {}
    
    if method == 'ndvi_threshold':
        # Method 1: Flowering starts when NDVI reaches 0.6-0.7
        flowering_threshold = 0.65
        
        # Find first date when NDVI exceeds threshold (during spring growth)
        spring_mask = (df['ds'].dt.month >= 3) & (df['ds'].dt.month <= 6)
        spring_data = df[spring_mask]
        
        if len(spring_data) > 0:
            flowering_candidates = spring_data[spring_data['yhat'] >= flowering_threshold]
            if len(flowering_candidates) > 0:
                flowering_date = flowering_candidates['ds'].iloc[0]
                confidence = min(0.9, 0.5 + (flowering_candidates['yhat'].iloc[0] - flowering_threshold) * 2)
                flowering_results = {
                    'flowering_start_date': flowering_date,
                    'method': 'NDVI Threshold (≥0.65)',
                    'confidence': confidence,
                    'ndvi_at_flowering': flowering_candidates['yhat'].iloc[0],
                    'threshold_used': flowering_threshold
                }
    
    elif method == 'ndvi_acceleration':
        # Method 2: Flowering starts when NDVI growth rate accelerates
        if len(df) >= 3:
            df['ndvi_growth'] = df['yhat'].diff()
            df['ndvi_acceleration'] = df['ndvi_growth'].diff()
            
            spring_mask = (df['ds'].dt.month >= 3) & (df['ds'].dt.month <= 6)
            spring_data = df[spring_mask]
            
            if len(spring_data) > 0:
                max_accel_idx = spring_data['ndvi_acceleration'].idxmax()
                if not pd.isna(max_accel_idx):
                    flowering_date = df.loc[max_accel_idx, 'ds']
                    confidence = min(0.85, 0.6 + abs(df.loc[max_accel_idx, 'ndvi_acceleration']) * 10)
                    flowering_results = {
                        'flowering_start_date': flowering_date,
                        'method': 'NDVI Acceleration Peak',
                        'confidence': confidence,
                        'ndvi_at_flowering': df.loc[max_accel_idx, 'yhat'],
                        'acceleration_value': df.loc[max_accel_idx, 'ndvi_acceleration']
                    }
    
    # Default return if no method worked
    if not flowering_results:
        flowering_results = {
            'flowering_start_date': None,
            'method': method,
            'confidence': 0,
            'error': 'Unable to determine flowering date with selected method'
        }
    
    return flowering_results


def _predict_ndvi_with_ml(history_data: List[Dict[str, Any]], weather_df: pd.DataFrame, 
                         target_year: int) -> Dict[str, Any]:
    """Use ML model to predict NDVI and flowering dates."""
    try:
        model = _load_ml_model()
        if model is None:
            raise ValueError("ML model not available")
        
        # Prepare training data
        training_df = _prepare_ml_features(history_data, weather_df)
        if training_df.empty:
            raise ValueError("No valid training data available")
        
        # Create future dates for prediction (next year)
        current_year = datetime.now().year
        future_start = datetime(target_year, 1, 1)
        future_end = datetime(target_year, 12, 31)
        
        # Create future dataframe with 16-day intervals (satellite revisit cycle)
        future_dates = pd.date_range(start=future_start, end=future_end, freq='16D')
        future_df = pd.DataFrame({'ds': future_dates})
        
        # Add weather features for future dates (use climatology if no forecast available)
        if not weather_df.empty:
            # Use historical weather patterns for future predictions
            # Convert date column to datetime if needed
            weather_df_copy = weather_df.copy()
            weather_df_copy['date'] = pd.to_datetime(weather_df_copy['date'])
            # Select only numeric columns for mean calculation
            numeric_columns = weather_df_copy.select_dtypes(include=[np.number]).columns
            historical_monthly = weather_df_copy.groupby(weather_df_copy['date'].dt.month)[numeric_columns].mean()
            future_df['month'] = future_df['ds'].dt.month
            
            # Map historical weather patterns to future months
            for month in range(1, 13):
                if month in historical_monthly.index:
                    mask = future_df['month'] == month
                    future_df.loc[mask, 'temperature_mean'] = historical_monthly.loc[month, 'temperature_deg_c']
                    future_df.loc[mask, 'humidity'] = historical_monthly.loc[month, 'humidity_pct']
                    future_df.loc[mask, 'cloudcover_mean'] = historical_monthly.loc[month, 'cloudcover_pct']
                    future_df.loc[mask, 'wind_speed_mean'] = historical_monthly.loc[month, 'wind_speed_mps']
                    future_df.loc[mask, 'clarity_index'] = historical_monthly.loc[month, 'clarity_pct'] / 100.0
        else:
            # Use default seasonal patterns
            future_df['temperature_mean'] = 15 + 10 * np.sin(2 * np.pi * (future_df['ds'].dt.dayofyear - 80) / 365)
            future_df['humidity'] = 65.0
            future_df['cloudcover_mean'] = 30.0
            future_df['wind_speed_mean'] = 2.0
            future_df['clarity_index'] = 0.7
        
        # Calculate derived weather variables
        future_df['vapor_pressure_deficit'] = future_df.apply(
            lambda row: _calculate_vpd(row['temperature_mean'], row['humidity']),
            axis=1
        )
        future_df['growing_degree_days'] = future_df['temperature_mean'].apply(
            lambda x: max(0, x - 10)
        )
        future_df['precipitation'] = 0.0
        
        # Add regional features
        future_df['region_numeric'] = 0
        future_df['is_northern_region'] = 0
        
        # Add growing season indicator
        future_df = _add_growing_season_indicator(future_df)
        
        # Fill any remaining NaNs before prediction
        for col in future_df.columns:
            if col != 'ds' and future_df[col].isna().any():
                if col in ['temperature_mean']:
                    future_df[col] = future_df[col].fillna(20.0)
                elif col in ['humidity']:
                    future_df[col] = future_df[col].fillna(60.0)
                elif col in ['cloudcover_mean']:
                    future_df[col] = future_df[col].fillna(30.0)
                elif col in ['wind_speed_mean']:
                    future_df[col] = future_df[col].fillna(2.0)
                elif col in ['clarity_index']:
                    future_df[col] = future_df[col].fillna(0.7)
                elif col in ['vapor_pressure_deficit']:
                    future_df[col] = future_df[col].fillna(1.0)
                elif col in ['growing_degree_days']:
                    future_df[col] = future_df[col].fillna(10.0)
                else:
                    future_df[col] = future_df[col].fillna(0.0)
        
        # Make predictions
        forecast = model.predict(future_df)
        
        # Calculate flowering dates using multiple methods
        methods = ['ndvi_threshold', 'ndvi_acceleration']
        flowering_predictions = {}
        
        for method in methods:
            result = _calculate_flowering_start_date_ml(forecast, method)
            flowering_predictions[method] = result
        
        # Select best prediction (highest confidence)
        best_method = max(flowering_predictions.keys(), 
                         key=lambda x: flowering_predictions[x]['confidence'])
        best_prediction = flowering_predictions[best_method]
        
        # Find NDVI peak from predictions
        ndvi_values = forecast['yhat'].values
        ndvi_peak = np.max(ndvi_values) if len(ndvi_values) > 0 else None
        ndvi_peak_idx = np.argmax(ndvi_values) if len(ndvi_values) > 0 else None
        ndvi_peak_at = None
        
        if ndvi_peak_idx is not None:
            peak_date = forecast.iloc[ndvi_peak_idx]['ds']
            if isinstance(peak_date, pd.Timestamp):
                peak_date = peak_date.to_pydatetime()
            if peak_date.tzinfo is None:
                peak_date = peak_date.replace(tzinfo=timezone.utc)
            ndvi_peak_at = _isoformat_utc(peak_date)
        
        return {
            'ndvi_peak': float(ndvi_peak) if ndvi_peak is not None else None,
            'ndvi_peak_at': ndvi_peak_at,
            'flowering_start_date': best_prediction.get('flowering_start_date'),
            'flowering_confidence': best_prediction.get('confidence', 0),
            'flowering_method': best_prediction.get('method'),
            'model': 'prophet_ml',
            'predictions': forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].to_dict('records')
        }
        
    except Exception as exc:
        monitor.logger.exception("ML prediction failed: %s", exc)
        return {
            'ndvi_peak': None,
            'ndvi_peak_at': None,
            'flowering_start_date': None,
            'flowering_confidence': 0,
            'flowering_method': None,
            'model': 'heuristic_fallback',
            'error': str(exc)
        }


def _persist_report_state(operation_id: str, geojson_payload: Union[str, Dict[str, Any]], yield_type: str,
                          status: str, field_id: Optional[str] = None,
                          history: Optional[List[Dict[str, Any]]] = None,
                          forecast: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None) -> None:
    collection = _get_reports_collection()

    state = _get_operation(operation_id)
    created_at = state.get("created_at") if state else datetime.now(timezone.utc)
    updated_at = state.get("updated_at") if state else datetime.now(timezone.utc)
    resolved_field_id = field_id or (state.get("field_id") if state else None)

    document = {
        "operation_id": operation_id,
        "status": status,
        "created_at": _mongo_ready_datetime(created_at),
        "updated_at": _mongo_ready_datetime(updated_at),
        "yieldType": yield_type,
        "fieldId": resolved_field_id,
        "geojson": _serialisable_geojson(geojson_payload),
        "history": history,
        "forecast": forecast,
        "errorMessage": error_message,
    }

    collection.update_one({"operation_id": operation_id}, {"$set": document}, upsert=True)


def _get_yield_profile(name: str) -> Dict[str, Any]:
    key = _normalize_yield_key(name)
    profile = _PROFILE_LOOKUP.get(key)
    if not profile:
        allowed = sorted(profile_name.title() for profile_name in _PROFILE_LOOKUP.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported yield type '{name}'. Supported types: {', '.join(allowed)}",
        )
    return profile


def _ensure_token() -> str:
    token = monitor.load_token_from_env()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="EARTHDATA_BEARER_TOKEN is not configured; set it in .env or the environment",
        )
    return token


def _geometry_from_geojson(raw_geojson: Union[str, Dict[str, Any]]):
    if isinstance(raw_geojson, str):
        try:
            payload = json.loads(raw_geojson)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid GeoJSON payload: {exc}") from exc
    elif isinstance(raw_geojson, dict):
        payload = raw_geojson
    else:
        raise HTTPException(status_code=400, detail="GeoJSON payload must be an object or JSON string")

    try:
        return monitor.extract_geometry_from_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch_weather_history(lat: float, lon: float, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "hourly": "temperature_2m,relative_humidity_2m,cloudcover,windspeed_10m",
        "timezone": "auto",
    }
    try:
        response = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        monitor.logger.exception("Weather API request failed for lat=%s lon=%s", lat, lon)
        return pd.DataFrame()

    hourly = response.json().get("hourly") or {}
    times = hourly.get("time")
    temps = hourly.get("temperature_2m")
    humidity = hourly.get("relative_humidity_2m")
    cloudcover = hourly.get("cloudcover")
    windspeed = hourly.get("windspeed_10m")
    if not times or not temps or not humidity or not cloudcover:
        monitor.logger.warning("Incomplete weather data returned for lat=%s lon=%s", lat, lon)
        return pd.DataFrame()
    if not windspeed:
        windspeed = [0.0] * len(times)

    weather_df = pd.DataFrame(
        {
            "time": pd.to_datetime(times),
            "temperature_deg_c": pd.to_numeric(temps, errors="coerce"),
            "humidity_pct": pd.to_numeric(humidity, errors="coerce"),
            "cloudcover_pct": pd.to_numeric(cloudcover, errors="coerce"),
            "wind_speed_mps": pd.to_numeric(windspeed, errors="coerce"),
        }
    ).dropna()

    if weather_df.empty:
        return weather_df

    daily = (
        weather_df
        .set_index("time")
        .resample("D")
        .mean()
        .reset_index()
    )
    daily.rename(columns={"time": "date"}, inplace=True)
    daily["clarity_pct"] = 100.0 - daily["cloudcover_pct"].clip(lower=0, upper=100)
    daily["date_only"] = pd.to_datetime(daily["date"]).dt.date
    return daily




def _init_operation(yield_type: str, geojson_payload: Union[str, Dict[str, Any]], field_id: Optional[str] = None) -> str:
    op_id = str(uuid4())
    now = datetime.now(timezone.utc)
    serialised_geojson = _serialisable_geojson(geojson_payload)
    with _OPERATIONS_LOCK:
        _OPERATIONS[op_id] = {
            "status": "processing",
            "created_at": now,
            "updated_at": now,
            "yield_type": yield_type,
            "geojson": serialised_geojson,
            "field_id": field_id,
            "result": None,
            "error": None,
        }
    return op_id

def _update_operation(op_id: str, *, status: Optional[str] = None, result: Optional[Dict[str, Any]] = None,
                      error: Optional[str] = None) -> None:
    with _OPERATIONS_LOCK:
        state = _OPERATIONS.get(op_id)
        if not state:
            return
        if status:
            state["status"] = status
        if result is not None:
            state["result"] = result
        if error is not None:
            state["error"] = error
        state["updated_at"] = datetime.now(timezone.utc)


def _get_operation(op_id: str) -> Optional[Dict[str, Any]]:
    with _OPERATIONS_LOCK:
        state = _OPERATIONS.get(op_id)
        if state is None:
            return None
        return dict(state)


def _get_persisted_operation(op_id: str) -> Optional[Dict[str, Any]]:
    try:
        collection = _get_reports_collection()
    except Exception:
        monitor.logger.exception("Unable to access MongoDB when retrieving operation %s", op_id)
        return None

    document = collection.find_one({"operation_id": op_id})
    if not document:
        return None

    def _ensure_aware(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    history = document.get("history")
    forecast = document.get("forecast")

    state: Dict[str, Any] = {
        "status": document.get("status"),
        "created_at": _ensure_aware(document.get("created_at")),
        "updated_at": _ensure_aware(document.get("updated_at")),
        "yield_type": document.get("yieldType"),
        "field_id": document.get("fieldId"),
        "result": None,
        "error": document.get("errorMessage"),
    }

    if history is not None or forecast is not None:
        state["result"] = {
            "history": history,
            "forecast": forecast,
        }

    return state



def _run_report_job(op_id: str, geojson_payload: Union[str, Dict[str, Any]], yield_profile: Dict[str, Any],
                    field_id: Optional[str] = None) -> None:
    _update_operation(op_id, status="processing")
    try:
        report = _generate_report(geojson_payload, yield_profile)
    except Exception as exc:
        monitor.logger.exception("Report job failed for operation %s", op_id)
        error_message = str(exc)
        _update_operation(op_id, status="error", error=error_message)
        try:
            _persist_report_state(op_id, geojson_payload, yield_profile.get("name", ""), status="error", field_id=field_id, error_message=error_message)
        except Exception:
            monitor.logger.exception("Failed to persist error state for %s", op_id)
        return
    _update_operation(op_id, status="ready", result=report, error=None)
    try:
        _persist_report_state(op_id, geojson_payload, yield_profile.get("name", ""), status="ready", field_id=field_id, history=report.get("history"), forecast=report.get("forecast"))
    except Exception:
        monitor.logger.exception("Failed to persist report state for %s", op_id)

def _generate_report(geojson_payload: Union[str, Dict[str, Any]], yield_profile: Dict[str, Any]) -> Dict[str, Any]:
    geometry = _geometry_from_geojson(geojson_payload)
    bbox = monitor.normalize_bbox(list(geometry.bounds))

    centroid = geometry.centroid if not geometry.is_empty else None
    if centroid and not centroid.is_empty:
        center_lat = float(centroid.y)
        center_lon = float(centroid.x)
    else:
        center_lat = float((bbox[1] + bbox[3]) / 2)
        center_lon = float((bbox[0] + bbox[2]) / 2)

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
    token = _ensure_token()

    data_frame = monitor.search_hls_data(
        bbox=bbox,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        max_cc=_DEFAULT_MAX_CLOUD,
        dataset_type=_DEFAULT_DATASET,
        _token=token,
    )

    if data_frame.empty:
        forecast = {
            "year": end_dt.year,
            "yieldTph": 0.0,
            "ndviPeak": None,
            "ndviPeakAt": None,
            "model": _DEFAULT_MODEL,
            "confidence": 0.0,
            "yieldType": yield_profile["name"],
        }
        return {"history": [], "forecast": forecast}

    rows = list(data_frame.itertuples(index=False))
    index_types = [monitor.IndexType.NDVI, monitor.IndexType.EVI]

    weather_df = _fetch_weather_history(center_lat, center_lon, start_dt, end_dt)
    weather_lookup: Dict[Any, Dict[str, Any]] = {}
    if not weather_df.empty:
        weather_lookup = {
            row["date_only"]: {
                "temperature_deg_c": row["temperature_deg_c"],
                "humidity_pct": row["humidity_pct"],
                "cloudcover_pct": row["cloudcover_pct"],
                "wind_speed_mps": row["wind_speed_mps"],
                "clarity_pct": row["clarity_pct"],
            }
            for _, row in weather_df.iterrows()
        }

    history: List[Dict[str, Any]] = []
    report_records: List[Dict[str, Any]] = []

    for row in rows:
        report = monitor.compute_index_for_row(row, index_types=index_types, bbox=bbox, token=token)
        if not report:
            continue
        report_records.append(report)

        date_value = report.get("date")
        report_dt: Optional[datetime] = None
        if isinstance(date_value, pd.Timestamp):
            report_dt = date_value.to_pydatetime()
        elif isinstance(date_value, datetime):
            report_dt = date_value
        elif date_value is not None:
            try:
                report_dt = pd.to_datetime(date_value).to_pydatetime()
            except Exception:
                report_dt = None
        if report_dt is None:
            continue
        if report_dt.tzinfo is None:
            report_dt = report_dt.replace(tzinfo=timezone.utc)
        else:
            report_dt = report_dt.astimezone(timezone.utc)

        weather = weather_lookup.get(report_dt.date())

        history.append(
            {
                "date": _isoformat_utc(report_dt),
                "ndvi": report.get("mean_NDVI"),
                "cloud_cover": float(row.cloud_cover) if getattr(row, "cloud_cover", None) is not None else None,
                "collection": getattr(row, "collection", None),
                "temperature_deg_c": weather["temperature_deg_c"] if weather else None,
                "humidity_pct": weather["humidity_pct"] if weather else None,
                "cloudcover_pct": weather["cloudcover_pct"] if weather else None,
                "wind_speed_mps": weather["wind_speed_mps"] if weather else None,
                "clarity_pct": weather["clarity_pct"] if weather else None,
            }
        )

    history.sort(key=lambda item: item["date"])

    # Try ML prediction first, fall back to heuristic method
    forecast_year = end_dt.year + 1
    ml_results = _predict_ndvi_with_ml(history, weather_df, forecast_year)
    
    if ml_results.get('model') == 'prophet_ml':
        # Use ML predictions
        monitor.logger.info("Forecast NDVI peak %.3f", ml_results.get('ndvi_peak', 0.0))
        ndvi_peak = ml_results.get('ndvi_peak')
        ndvi_peak_at = ml_results.get('ndvi_peak_at')
        flowering_start_date = ml_results.get('flowering_start_date')
        flowering_confidence = ml_results.get('flowering_confidence', 0)
        model_name = "prophet_ml"
        
        # Calculate yield based on ML predictions
        reference_ndvi = ndvi_peak if ndvi_peak is not None else 0.0
        tolerance = float(yield_profile.get("ndvi_tolerance") or 0.25)
        optimal = float(yield_profile.get("ndvi_optimal") or reference_ndvi)
        if tolerance > 0 and reference_ndvi > 0:
            match_ratio = 1.0 - abs(reference_ndvi - optimal) / tolerance
        else:
            match_ratio = 0.0
        match_ratio = max(0.0, min(1.0, match_ratio))
        min_match = float(yield_profile.get("min_match", 0.0) or 0.0)
        if match_ratio < min_match:
            match_ratio = min(min_match, 1.0)
        
        # Boost confidence if we have flowering prediction
        if flowering_confidence > match_ratio:
            match_ratio = min(1.0, (match_ratio + flowering_confidence) / 2)
            
    else:
        # Fall back to heuristic method
        monitor.logger.info("Using heuristic method as ML prediction failed: %s", ml_results.get('error'))
        
        ndvi_values = [entry["ndvi"] for entry in history if entry["ndvi"] is not None]
        ndvi_peak = max(ndvi_values) if ndvi_values else None
        ndvi_peak_at = None
        flowering_start_date = None
        flowering_confidence = 0
        
        if ndvi_peak is not None:
            for entry in history:
                if entry["ndvi"] == ndvi_peak:
                    ndvi_peak_at = entry["date"]
                    break

        reference_ndvi = ndvi_peak if ndvi_peak is not None else (sum(ndvi_values) / len(ndvi_values) if ndvi_values else 0.0)
        tolerance = float(yield_profile.get("ndvi_tolerance") or 0.25)
        optimal = float(yield_profile.get("ndvi_optimal") or reference_ndvi)
        if tolerance > 0:
            match_ratio = 1.0 - abs(reference_ndvi - optimal) / tolerance
        else:
            match_ratio = 0.0
        match_ratio = max(0.0, min(1.0, match_ratio))
        min_match = float(yield_profile.get("min_match", 0.0) or 0.0)
        if match_ratio < min_match:
            match_ratio = min(min_match, 1.0)

        # Project peak to next year for heuristic method
        future_peak_at: Optional[str] = None
        if ndvi_peak_at:
            try:
                peak_dt = datetime.fromisoformat(ndvi_peak_at.replace("Z", "+00:00"))
                if peak_dt.tzinfo is None:
                    peak_dt = peak_dt.replace(tzinfo=timezone.utc)
                days_in_month = calendar.monthrange(forecast_year, peak_dt.month)[1]
                adjusted_day = min(peak_dt.day, days_in_month)
                future_peak_dt = peak_dt.replace(year=forecast_year, day=adjusted_day)
                future_peak_at = _isoformat_utc(future_peak_dt)
            except Exception:
                future_peak_at = ndvi_peak_at
        ndvi_peak_at = future_peak_at
        model_name = _DEFAULT_MODEL

    yield_per_ha = float(yield_profile.get("yield_t_per_ha") or 0.0)
    yield_tph = yield_per_ha * match_ratio

    # Prepare forecast response with flowering information
    forecast_dict = {
        "year": forecast_year,
        "yieldTph": round(yield_tph, 2),
        "ndviPeak": round(ndvi_peak, 2) if ndvi_peak is not None else None,
        "ndviPeakAt": ndvi_peak_at,
        "model": model_name,
        "confidence": round(match_ratio, 2),
        "yieldType": yield_profile["name"],
    }
    
    # Add flowering information if available
    if flowering_start_date is not None:
        if isinstance(flowering_start_date, pd.Timestamp):
            flowering_start_date = flowering_start_date.to_pydatetime()
        if isinstance(flowering_start_date, datetime):
            if flowering_start_date.tzinfo is None:
                flowering_start_date = flowering_start_date.replace(tzinfo=timezone.utc)
            forecast_dict["floweringStartDate"] = _isoformat_utc(flowering_start_date)
            forecast_dict["floweringConfidence"] = round(flowering_confidence, 2)
            forecast_dict["floweringMethod"] = ml_results.get('flowering_method')

    return {"history": history, "forecast": forecast_dict}


@app.post("/reports", status_code=202)
def create_report(request: ReportRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    profile = _get_yield_profile(request.yield_type)

    operation_id = ""
    try:
        operation_id = _init_operation(profile["name"], request.geojson, request.field_id)
        _persist_report_state(operation_id, request.geojson, profile["name"], status="processing", field_id=request.field_id)
    except Exception as exc:
        monitor.logger.exception("Failed to initialize report operation")
        if operation_id:
            with _OPERATIONS_LOCK:
                _OPERATIONS.pop(operation_id, None)
        raise HTTPException(status_code=500, detail="Failed to initialize report persistence") from exc

    background_tasks.add_task(_run_report_job, operation_id, request.geojson, profile, request.field_id)
    return {"operation_id": operation_id, "status": "accepted"}

@app.get("/reports/{operation_id}")
def get_report(operation_id: str) -> Dict[str, Any]:
    state = _get_operation(operation_id)
    if state is None:
        state = _get_persisted_operation(operation_id)

    if state is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    created_at = state.get("created_at")
    updated_at = state.get("updated_at")

    payload = {
        "operation_id": operation_id,
        "status": state.get("status") or "unknown",
        "created_at": _isoformat_utc(created_at) if created_at else None,
        "updated_at": _isoformat_utc(updated_at) if updated_at else None,
        "yieldType": state.get("yield_type"),
        "fieldId": state.get("field_id"),
        "errorMessage": state.get("error"),
    }
    if state.get("result") is not None:
        payload["result"] = state["result"]
    return jsonable_encoder(payload)
