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

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

app = FastAPI(
    title="Chipnik Monitor API",
    version="1.1.0",
    description="GeoJSON-driven access to HLS reports computed by Chipnik Monitor",
)

_DEFAULT_LOOKBACK_DAYS = 4500
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

    ndvi_values = [entry["ndvi"] for entry in history if entry["ndvi"] is not None]
    ndvi_peak = max(ndvi_values) if ndvi_values else None
    ndvi_peak_at = None
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

    yield_per_ha = float(yield_profile.get("yield_t_per_ha") or 0.0)
    yield_tph = yield_per_ha * match_ratio

    forecast_year = end_dt.year + 1

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

    forecast = {
        "year": forecast_year,
        "yieldTph": round(yield_tph, 2),
        "ndviPeak": round(ndvi_peak, 2) if ndvi_peak is not None else None,
        "ndviPeakAt": future_peak_at,
        "model": _DEFAULT_MODEL,
        "confidence": round(match_ratio, 2),
        "yieldType": yield_profile["name"],
    }

    return {"history": history, "forecast": forecast}


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
