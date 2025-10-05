from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_VOLATILITY_WINDOW = 45
_VOLATILITY_MIN_PERIODS = 10
_EARLY_SENESCENCE_THRESHOLD = 0.4
_EARLY_SENESCENCE_LOOKBACK = 30
_EARLY_SENESCENCE_LEAD_DAYS = 14
_LATE_GREENING_THRESHOLD = 0.3
_LATE_GREENING_DELAY_DAYS = 14
_LATE_GREENING_CONFIRM_WINDOW = 4
_LATE_GREENING_CONFIRM_COUNT = 3
_NDVI_DROP_THRESHOLD = 0.1
_RECENT_WINDOW_DAYS = 60

_ANOMALY_META = {
    "ndvi_volatility": "NDVI Volatility Spike",
    "early_senescence": "Early Senescence",
    "late_greenup": "Delayed Greenup",
    "weatherless_drop": "NDVI Drop Without Weather Driver",
}

def _base_result(key: str) -> Dict[str, Any]:
    return {
        "key": key,
        "title": _ANOMALY_META.get(key, key),
        "triggered": False,
        "severity": "info",
        "detectedAt": None,
        "details": {},
    }


def _isoformat(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        timestamp = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    if timestamp is None or pd.isna(timestamp):
        return None
    if not isinstance(timestamp, pd.Timestamp):
        return None
    return timestamp.isoformat().replace("+00:00", "Z")


def _normalize_ndvi_frame(ndvi_df: pd.DataFrame) -> pd.DataFrame:
    if ndvi_df is None or ndvi_df.empty:
        return pd.DataFrame(columns=["date", "ndvi"])
    df = ndvi_df.copy()
    if "type" in df.columns:
        df = df[df["type"] == 0].copy()
    value_col: Optional[str] = None
    for candidate in ("ndvi", "mean_NDVI", "mean_ndvi"):
        if candidate in df.columns:
            value_col = candidate
            break
    if value_col is None:
        raise ValueError("NDVI column not found in dataframe")
    if "date" not in df.columns:
        raise ValueError("date column not found in dataframe")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=["date", value_col])
    if df.empty:
        return pd.DataFrame(columns=["date", "ndvi"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df = df[["date", value_col]].rename(columns={value_col: "ndvi"})
    return df


def _build_daily_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    series = df.set_index("date")["ndvi"].sort_index()
    daily = series.resample("D").mean()
    daily = daily.interpolate(limit=7, limit_direction="both")
    return daily


def _normalize_weather(weather_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if weather_df is None or weather_df.empty:
        return pd.DataFrame()
    df = weather_df.copy()
    date_col: Optional[str] = None
    for candidate in ("date", "date_only", "datetime"):
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("weather dataframe missing date column")
    df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
    df = df.dropna(subset=[date_col])
    rename_map = {
        "temperature_mean": "temperature",
        "temperature_deg_c": "temperature",
        "temp_c": "temperature",
        "humidity_mean": "humidity",
        "humidity_pct": "humidity",
        "cloudcover_mean": "cloudcover",
        "cloudcover_pct": "cloudcover",
        "wind_speed_mean": "wind_speed",
        "wind_speed_mps": "wind_speed",
        "clarity_index": "clarity",
        "clarity_pct": "clarity",
    }
    for column, alias in rename_map.items():
        if column in df.columns:
            df[alias] = pd.to_numeric(df[column], errors="coerce")
    base_cols = [col for col in ("temperature", "humidity", "cloudcover", "wind_speed", "clarity") if col in df.columns]
    df = df[[date_col] + base_cols]
    df["date"] = df[date_col].dt.normalize()
    grouped = df.groupby("date")[base_cols].mean().reset_index()
    return grouped


def _detect_volatility(daily_series: pd.Series) -> Tuple[Dict[str, Any], pd.DataFrame]:
    result = _base_result("ndvi_volatility")
    if daily_series.dropna().shape[0] < _VOLATILITY_MIN_PERIODS:
        result["details"]["reason"] = "insufficient_history"
        return result, pd.DataFrame(columns=["date", "rollingStd", "threshold"])
    rolling_std = daily_series.rolling(window=_VOLATILITY_WINDOW, min_periods=_VOLATILITY_MIN_PERIODS).std()
    chart_df = pd.DataFrame({
        "date": rolling_std.index,
        "rollingStd": rolling_std.values,
    })
    valid_std = rolling_std.dropna()
    if valid_std.empty:
        result["details"]["reason"] = "no_variability"
        chart_df["threshold"] = np.nan
        return result, chart_df
    threshold = float(np.nanpercentile(valid_std, 95))
    chart_df["threshold"] = threshold
    flagged = valid_std[valid_std >= threshold]
    if not flagged.empty:
        detected_at = flagged.index.max()
        result["detectedAt"] = _isoformat(detected_at)
        recent_date = daily_series.dropna().index.max()
        if recent_date is not None and (recent_date - detected_at).days <= _RECENT_WINDOW_DAYS:
            result["triggered"] = True
            result["severity"] = "warning"
    result["details"].update({
        "windowDays": _VOLATILITY_WINDOW,
        "threshold": threshold,
        "latestRollingStd": float(valid_std.iloc[-1]),
        "flaggedCount": int((rolling_std >= threshold).sum()),
    })
    return result, chart_df


def _detect_early_senescence(daily_series: pd.Series) -> Tuple[Dict[str, Any], pd.DataFrame]:
    result = _base_result("early_senescence")
    chart_df = pd.DataFrame(columns=["year", "dropDate", "isCurrent"])
    if daily_series.dropna().empty:
        result["details"]["reason"] = "insufficient_history"
        return result, chart_df
    drop_dates: List[Tuple[int, pd.Timestamp]] = []
    for year, series in daily_series.groupby(daily_series.index.year):
        series = series.dropna()
        if series.empty:
            continue
        for current_date, value in series.items():
            if value >= _EARLY_SENESCENCE_THRESHOLD:
                continue
            start = current_date - pd.Timedelta(days=_EARLY_SENESCENCE_LOOKBACK)
            window = series.loc[start:current_date]
            if window.empty or len(window) == 1:
                continue
            previous = window.iloc[:-1]
            if previous.empty:
                continue
            if previous.max() >= _EARLY_SENESCENCE_THRESHOLD:
                drop_dates.append((year, current_date))
                break
    if not drop_dates:
        result["details"]["reason"] = "no_drop_found"
        return result, chart_df
    chart_df = pd.DataFrame(drop_dates, columns=["year", "dropDate"])
    chart_df["isCurrent"] = chart_df["year"] == chart_df["year"].max()
    current_year = int(chart_df["year"].max())
    current_row = chart_df[chart_df["year"] == current_year]
    baseline_rows = chart_df[chart_df["year"] < current_year]
    if current_row.empty or baseline_rows.empty:
        result["details"]["reason"] = "no_baseline"
        return result, chart_df
    current_ts = pd.to_datetime(current_row.iloc[0]["dropDate"], utc=True)
    current_doy = int(current_ts.timetuple().tm_yday)
    baseline_days = [int(pd.to_datetime(val, utc=True).timetuple().tm_yday) for val in baseline_rows["dropDate"].tolist()]
    if not baseline_days:
        result["details"]["reason"] = "no_baseline"
        return result, chart_df
    baseline_doy = int(np.median(baseline_days))
    days_early = baseline_doy - current_doy
    result["details"].update({
        "baselineDayOfYear": baseline_doy,
        "currentDayOfYear": current_doy,
        "daysEarly": days_early,
        "threshold": _EARLY_SENESCENCE_THRESHOLD,
    })
    if days_early >= _EARLY_SENESCENCE_LEAD_DAYS:
        result["triggered"] = True
        result["severity"] = "warning"
        result["detectedAt"] = _isoformat(current_ts)
    else:
        result["detectedAt"] = _isoformat(current_ts)
    return result, chart_df


def _detect_late_greenup(daily_series: pd.Series) -> Tuple[Dict[str, Any], pd.DataFrame]:
    result = _base_result("late_greenup")
    chart_df = pd.DataFrame(columns=["year", "greenupDate", "isCurrent"])
    if daily_series.dropna().empty:
        result["details"]["reason"] = "insufficient_history"
        return result, chart_df
    greenup_dates: List[Tuple[int, pd.Timestamp]] = []
    for year, series in daily_series.groupby(daily_series.index.year):
        series = series.dropna()
        if series.empty:
            continue
        above = (series >= _LATE_GREENING_THRESHOLD).astype(float)
        rolling_hits = above.rolling(window=_LATE_GREENING_CONFIRM_WINDOW, min_periods=_LATE_GREENING_CONFIRM_WINDOW).sum()
        candidates = rolling_hits[rolling_hits >= _LATE_GREENING_CONFIRM_COUNT]
        if candidates.empty:
            continue
        candidate_date = candidates.index[0]
        greenup_dates.append((year, candidate_date))
    if not greenup_dates:
        result["details"]["reason"] = "no_greenup_detected"
        return result, chart_df
    chart_df = pd.DataFrame(greenup_dates, columns=["year", "greenupDate"])
    chart_df["isCurrent"] = chart_df["year"] == chart_df["year"].max()
    current_year = int(chart_df["year"].max())
    current_rows = chart_df[chart_df["year"] == current_year]
    baseline_rows = chart_df[chart_df["year"] < current_year]
    if baseline_rows.empty:
        result["details"]["reason"] = "no_baseline"
        return result, chart_df
    baseline_days = [int(pd.to_datetime(val, utc=True).timetuple().tm_yday) for val in baseline_rows["greenupDate"].tolist()]
    baseline_doy = int(np.median(baseline_days)) if baseline_days else None
    latest_observed = daily_series.dropna().index.max()
    if not current_rows.empty:
        current_ts = pd.to_datetime(current_rows.iloc[0]["greenupDate"], utc=True)
        current_doy = int(current_ts.timetuple().tm_yday)
        delay_days = current_doy - baseline_doy if baseline_doy is not None else None
        result["details"].update({
            "baselineDayOfYear": baseline_doy,
            "currentDayOfYear": current_doy,
            "delayDays": delay_days,
            "threshold": _LATE_GREENING_THRESHOLD,
        })
        result["detectedAt"] = _isoformat(current_ts)
        if delay_days is not None and delay_days >= _LATE_GREENING_DELAY_DAYS:
            result["triggered"] = True
            result["severity"] = "warning"
    else:
        if baseline_doy is not None and latest_observed is not None:
            latest_doy = int(latest_observed.timetuple().tm_yday)
            delay_days = latest_doy - baseline_doy
            result["details"].update({
                "baselineDayOfYear": baseline_doy,
                "currentDayOfYear": None,
                "delayDays": delay_days,
                "threshold": _LATE_GREENING_THRESHOLD,
                "status": "not_observed",
            })
            if delay_days >= _LATE_GREENING_DELAY_DAYS:
                result["triggered"] = True
                result["severity"] = "warning"
                result["detectedAt"] = _isoformat(latest_observed)
    return result, chart_df


def _detect_weatherless_drop(observed_df: pd.DataFrame, weather_df: pd.DataFrame) -> Tuple[Dict[str, Any], pd.DataFrame]:
    result = _base_result("weatherless_drop")
    chart_df = pd.DataFrame(columns=["date", "ndvi", "delta", "flagged"])
    if observed_df.empty or observed_df["ndvi"].count() < 2:
        result["details"]["reason"] = "insufficient_history"
        return result, chart_df
    obs = observed_df.copy()
    obs["date"] = pd.to_datetime(obs["date"], utc=True, errors="coerce")
    obs = obs.dropna(subset=["date"])
    obs = obs.sort_values("date").reset_index(drop=True)
    obs["ndvi"] = pd.to_numeric(obs["ndvi"], errors="coerce")
    obs = obs.dropna(subset=["ndvi"])
    if obs.shape[0] < 2:
        result["details"]["reason"] = "insufficient_history"
        return result, chart_df
    obs["delta"] = obs["ndvi"].diff()
    obs["date_only"] = obs["date"].dt.normalize()
    obs["prev_ndvi"] = obs["ndvi"].shift(1)
    obs["days_since_prev"] = obs["date"].diff().dt.days
    if weather_df is None or weather_df.empty:
        result["details"]["reason"] = "missing_weather"
        chart_df = obs[["date", "ndvi", "delta"]]
        chart_df["flagged"] = False
        return result, chart_df
    merged = obs.merge(weather_df, how="left", on="date")
    percentiles: Dict[str, Tuple[float, float]] = {}
    for column in ("temperature", "wind_speed", "cloudcover", "clarity"):
        if column in weather_df.columns:
            values = weather_df[column].dropna()
            if values.empty:
                continue
            percentiles[column] = (
                float(np.nanpercentile(values, 10)),
                float(np.nanpercentile(values, 90)),
            )
    flagged_indices: List[int] = []
    latest_event: Optional[Dict[str, Any]] = None
    for idx, row in merged.iterrows():
        if not np.isfinite(row.get("delta", np.nan)) or row["delta"] >= -_NDVI_DROP_THRESHOLD:
            continue
        if row.get("days_since_prev") is not None and row.get("days_since_prev") and row.get("days_since_prev") > 30:
            continue
        is_extreme = False
        temp_val = row.get("temperature")
        if "temperature" in percentiles and temp_val is not None and np.isfinite(temp_val):
            low, high = percentiles["temperature"]
            if temp_val <= low or temp_val >= high:
                is_extreme = True
        wind_val = row.get("wind_speed")
        if "wind_speed" in percentiles and wind_val is not None and np.isfinite(wind_val):
            _, wind_high = percentiles["wind_speed"]
            if wind_val >= wind_high:
                is_extreme = True
        cloud_val = row.get("cloudcover")
        if "cloudcover" in percentiles and cloud_val is not None and np.isfinite(cloud_val):
            _, cloud_high = percentiles["cloudcover"]
            if cloud_val >= cloud_high:
                is_extreme = True
        clarity_val = row.get("clarity")
        if "clarity" in percentiles and clarity_val is not None and np.isfinite(clarity_val):
            clarity_low, _ = percentiles["clarity"]
            if clarity_val <= clarity_low:
                is_extreme = True
        if is_extreme:
            continue
        flagged_indices.append(idx)
        latest_event = {
            "date": row["date"],
            "ndvi": row["ndvi"],
            "delta": row["delta"],
            "previous_ndvi": row.get("prev_ndvi"),
            "temperature": temp_val,
            "wind_speed": wind_val,
            "cloudcover": cloud_val,
            "clarity": clarity_val,
        }
    chart_df = merged[["date", "ndvi", "delta"]].copy()
    chart_df["flagged"] = chart_df.index.isin(flagged_indices)
    if latest_event:
        result["detectedAt"] = _isoformat(latest_event["date"])
        latest_sample = obs["date"].max()
        if latest_sample is not None and (latest_sample - latest_event["date"]).days <= _RECENT_WINDOW_DAYS:
            result["triggered"] = True
            result["severity"] = "warning"
        result["details"].update({
            "dropMagnitude": float(abs(latest_event["delta"])),
            "currentNdvi": float(latest_event["ndvi"]),
            "previousNdvi": float(latest_event.get("previous_ndvi")) if latest_event.get("previous_ndvi") is not None else None,
            "temperature": float(latest_event.get("temperature")) if latest_event.get("temperature") is not None else None,
            "windSpeed": float(latest_event.get("wind_speed")) if latest_event.get("wind_speed") is not None else None,
            "cloudcover": float(latest_event.get("cloudcover")) if latest_event.get("cloudcover") is not None else None,
            "clarity": float(latest_event.get("clarity")) if latest_event.get("clarity") is not None else None,
            "threshold": _NDVI_DROP_THRESHOLD,
        })
    else:
        result["details"]["reason"] = "no_drop_detected"
    return result, chart_df


def detect_anomalies(ndvi_df: pd.DataFrame, weather_df: Optional[pd.DataFrame] = None) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
    """Compute NDVI anomaly signals and return structured results and chart contexts."""
    normalized_ndvi = _normalize_ndvi_frame(ndvi_df)
    daily_series = _build_daily_series(normalized_ndvi)
    weather_norm = _normalize_weather(weather_df)

    anomalies: List[Dict[str, Any]] = []
    charts: Dict[str, pd.DataFrame] = {}

    volatility_result, volatility_chart = _detect_volatility(daily_series)
    anomalies.append(volatility_result)
    charts["volatility"] = volatility_chart

    senescence_result, senescence_chart = _detect_early_senescence(daily_series)
    anomalies.append(senescence_result)
    charts["early_senescence"] = senescence_chart

    greenup_result, greenup_chart = _detect_late_greenup(daily_series)
    anomalies.append(greenup_result)
    charts["late_greenup"] = greenup_chart

    weatherless_result, weatherless_chart = _detect_weatherless_drop(normalized_ndvi, weather_norm)
    anomalies.append(weatherless_result)
    charts["weatherless_drop"] = weatherless_chart

    if daily_series.empty:
        ndvi_daily_df = pd.DataFrame(columns=["date", "ndvi"])
    else:
        ndvi_daily_df = daily_series.reset_index()
        ndvi_daily_df.columns = ["date", "ndvi"]
    charts["ndvi_daily"] = ndvi_daily_df

    for chart_key, frame in charts.items():
        if not frame.empty and "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    return anomalies, charts
