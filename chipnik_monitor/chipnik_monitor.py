from enum import Enum
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
from pystac_client import Client
import rasterio
from rasterio.warp import transform_bounds
try:
    from rasterio.session import AWSSession  # type: ignore
except ImportError:
    AWSSession = None  # type: ignore
else:
    try:
        import boto3  # type: ignore  # noqa: F401
    except ImportError:
        AWSSession = None  # type: ignore
from shapely.geometry import shape, box, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from pathlib import Path
from collections import OrderedDict
from functools import partial
import requests
import hashlib
import json
import logging
import concurrent.futures
import math
import calendar
import os
import time
from typing import List, Tuple, Optional, Union, Dict, Any
import warnings
warnings.filterwarnings("ignore")
# Configure logger
logger = logging.getLogger('chipnik_monitor')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(handler)

_CLOUD_RUN_SERVICE = os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT')
logger.setLevel(logging.INFO if _CLOUD_RUN_SERVICE else logging.DEBUG)

def log_progress(message: str) -> None:
    logger.log(logging.INFO, message)

DEFAULT_CENTER_LON = -122.09261814845487
DEFAULT_CENTER_LAT = 47.60464601773639
DEFAULT_CORNER_HALF_WIDTH_DEG = 0.055
DEFAULT_MIN_LON = DEFAULT_CENTER_LON - DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MAX_LON = DEFAULT_CENTER_LON + DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MIN_LAT = DEFAULT_CENTER_LAT - DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MAX_LAT = DEFAULT_CENTER_LAT + DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_RADIUS_KM = 6.0

ENABLE_EVI = os.getenv("ENABLE_EVI", "").strip().lower() in {"1", "true", "yes", "on"}

DEFAULT_DAYS_BACK_LIMIT = 730
_days_back_raw = os.getenv("DAYS_BACK_LIMIT", "").strip()
if _days_back_raw:
    try:
        DAYS_BACK_LIMIT = int(_days_back_raw)
    except ValueError:
        logger.warning("Invalid DAYS_BACK_LIMIT=%s; falling back to default", _days_back_raw)
        DAYS_BACK_LIMIT = DEFAULT_DAYS_BACK_LIMIT
else:
    DAYS_BACK_LIMIT = DEFAULT_DAYS_BACK_LIMIT
DAYS_BACK_LIMIT = max(1, min(4500, DAYS_BACK_LIMIT))

APP_NAME = "HLS Crop Monitor"
APP_LOGO_PATH = Path("media") / "small_logo.png"

def extract_geometry_from_geojson(geojson_obj: dict) -> BaseGeometry:
    geojson_type = (geojson_obj or {}).get("type") if isinstance(geojson_obj, dict) else None
    if geojson_type == "Feature":
        geometry = geojson_obj.get("geometry")
        if geometry is None:
            raise ValueError("Feature is missing geometry")
        return shape(geometry)
    if geojson_type == "FeatureCollection":
        features = geojson_obj.get("features") or []
        geometries = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry")
            if geometry:
                geometries.append(shape(geometry))
        if not geometries:
            raise ValueError("FeatureCollection contains no valid geometries")
        return unary_union(geometries)
    if isinstance(geojson_obj, dict) and geojson_type:
        return shape(geojson_obj)
    raise ValueError("Unsupported GeoJSON structure; expected Feature, FeatureCollection, or geometry")

def find_existing_secrets() -> bool:
    candidate_paths = (
        Path.home() / '.streamlit/secrets.toml',
        Path.cwd() / '.streamlit/secrets.toml',
    )
    return any(path.exists() for path in candidate_paths)

def geometry_to_polygons(geometry: BaseGeometry) -> List[List[List[float]]]:
    if geometry is None or geometry.is_empty:
        return []
    geojson = mapping(geometry)
    geo_type = geojson.get("type")
    if geo_type == "Polygon":
        return [geojson["coordinates"]]
    if geo_type == "MultiPolygon":
        return list(geojson["coordinates"])
    if geo_type == "GeometryCollection":
        polygons: List[List[List[float]]] = []
        for geom in geometry.geoms:  # type: ignore[attr-defined]
            polygons.extend(geometry_to_polygons(geom))
        return polygons
    return []

GEOJSON_DIR = Path("geojsons")

def list_geojson_files(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    candidates: List[Path] = []
    for pattern in ("*.geojson", "*.GeoJSON", "*.json", "*.JSON"):
        candidates.extend(directory.glob(pattern))
    unique = {}
    for file_path in candidates:
        unique[file_path.name] = file_path
    return sorted(unique.values(), key=lambda f: f.name.lower())

def _determine_cache_root() -> Path:
    override = os.getenv("CACHE_ROOT")
    if override:
        return Path(override)
    if _CLOUD_RUN_SERVICE:
        return Path("/tmp/chipnik_cache")
    return Path(".cache")

CACHE_ROOT = _determine_cache_root()
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
INDEX_CACHE_VERSION = "1"

# HLS products have 30 m ground sampling distance; used to convert pixels to area.
HLS_PIXEL_RESOLUTION_METERS = 30.0
HLS_PIXEL_AREA_SQM = HLS_PIXEL_RESOLUTION_METERS ** 2
# Treat NDVI >= 0.35 as photosynthetically active canopy (crop/biomass) coverage.
CROP_NDVI_THRESHOLD = 0.35

CROP_PROFILES = (
    {
        "name": "Potato",
        "ndvi_optimal": 0.65,
        "ndvi_tolerance": 0.25,
        "yield_t_per_ha": 45.0,
    },
    {
        "name": "Soybean",
        "ndvi_optimal": 0.60,
        "ndvi_tolerance": 0.25,
        "yield_t_per_ha": 3.5,
    },
    {
        "name": "Wheat",
        "ndvi_optimal": 0.55,
        "ndvi_tolerance": 0.20,
        "yield_t_per_ha": 6.0,
    },
    {
        "name": "Tomato",
        "ndvi_optimal": 0.68,
        "ndvi_tolerance": 0.30,
        "yield_t_per_ha": 70.0,
        "min_match": 0.05,
    },
    {
        "name": "Sugar beet",
        "ndvi_optimal": 0.65,
        "ndvi_tolerance": 0.35,
        "yield_t_per_ha": 55.0,
        "min_match": 0.05,
    },
)

class IndexType(Enum):
    NDVI = 1
    EVI = 2

def get_index_cache_path(index_type: IndexType, red_url: str, blue_url: str, nir_url: str, bbox: List[float]) -> Path:
    payload = json.dumps(
        {
            "red": red_url,
            "blue": blue_url,
            "nir": nir_url,
            "bbox": [round(float(coord), 6) for coord in bbox],
            "version": INDEX_CACHE_VERSION
        },
        sort_keys=True
    )
    cache_dir = CACHE_ROOT / index_type.name
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.npz"

STAC_CACHE_DIR = CACHE_ROOT / "stac"
STAC_CACHE_VERSION = "1"

STAC_PAGE_SIZE = 200
STAC_MAX_ITEMS = 2000
_STAC_MEMORY_CACHE_MAX_ENTRIES = 32
_STAC_RESULTS_CACHE: "OrderedDict[Tuple[Any, ...], Tuple[Dict[str, Any], ...]]" = OrderedDict()


STAC_CACHE_TTL_SECONDS = 3600 * 24 * 7

def get_stac_cache_path(bbox: List[float], start: str, end: str, max_cc: int,
                        dataset_type: str, token: str) -> Path:
    payload = {
        "bbox": [round(float(coord), 6) for coord in bbox],
        "start": start,
        "end": end,
        "max_cc": int(max_cc),
        "dataset": dataset_type,
        "token": hashlib.sha256(token.encode("utf-8")).hexdigest() if token else "",
        "version": STAC_CACHE_VERSION
    }
    cache_dir = STAC_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.json"

def load_stac_cache(cache_path: Path) -> Optional[pd.DataFrame]:
    if not cache_path.exists():
        return None
    try:
        if STAC_CACHE_TTL_SECONDS > 0:
            age = time.time() - cache_path.stat().st_mtime
            if age > STAC_CACHE_TTL_SECONDS:
                try:
                    cache_path.unlink()
                except FileNotFoundError:
                    pass
                return None
    except OSError:
        logger.exception("Failed to inspect STAC cache at %s", cache_path)
        return None

    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read STAC cache from %s", cache_path)
        try:
            cache_path.unlink()
        except FileNotFoundError:
            pass
        return None

    records = raw.get("records", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
    return df

def store_stac_cache(cache_path: Path, records: List[dict]) -> None:
    try:
        serialisable: List[dict] = []
        for record in records:
            cloud_cover = record.get("cloud_cover")
            if cloud_cover is not None:
                try:
                    cloud_cover = float(cloud_cover)
                except (TypeError, ValueError):
                    cloud_cover = None

            dt_value = record.get("datetime")
            if isinstance(dt_value, (datetime, pd.Timestamp)):
                dt_serialised = dt_value.isoformat()
            elif dt_value is not None:
                dt_serialised = str(dt_value)
            else:
                dt_serialised = None

            serialisable.append({
                "id": record.get("id"),
                "datetime": dt_serialised,
                "cloud_cover": cloud_cover,
                "collection": record.get("collection"),
                "nir_url": record.get("nir_url"),
                "red_url": record.get("red_url"),
                "blue_url": record.get("blue_url"),
            })

        cache_path.write_text(json.dumps({"records": serialisable}), encoding="utf-8")
    except Exception:
        logger.exception("Failed to persist STAC cache at %s", cache_path)

def load_token_from_env() -> str:
    token = os.getenv("EARTHDATA_BEARER_TOKEN")
    if token:
        return token.strip()

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("EARTHDATA_BEARER_TOKEN"):
                _, _, value = stripped.partition("=")
                token = value.strip().strip('"').strip("'")
                os.environ["EARTHDATA_BEARER_TOKEN"] = token
                return token
    return ""

def normalize_bbox(bbox: List[float]) -> List[float]:
    if not bbox or len(bbox) != 4:
        raise ValueError("AOI must contain four coordinates (min lon, min lat, max lon, max lat).")

    min_lon, min_lat, max_lon, max_lat = bbox
    min_lon, max_lon = sorted([float(min_lon), float(max_lon)])
    min_lat, max_lat = sorted([float(min_lat), float(max_lat)])

    if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
        raise ValueError("Longitude values must fall between -180 and 180 degrees.")
    if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        raise ValueError("Latitude values must fall between -90 and 90 degrees.")
    if min_lon == max_lon or min_lat == max_lat:
        raise ValueError("AOI must span a non-zero area.")

    normalised = [min_lon, min_lat, max_lon, max_lat]
    logger.debug("Normalised bbox=%s", normalised)
    return normalised



def ensure_datetime(value: Union[datetime, date]) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())

# Page configuration
st.set_page_config(
    page_title=f"{APP_NAME} - HLS Analytics",
    page_icon=str(APP_LOGO_PATH) if APP_LOGO_PATH.exists() else ":potato:",
    layout="wide"
)

if APP_LOGO_PATH.exists():
    st.image(str(APP_LOGO_PATH), width=96)

# Page title
st.title(f"{APP_NAME} - NDVI Analysis")
st.markdown("**Assess crop canopy vigor with HLS (Harmonized Landsat Sentinel-2) imagery**")

# Sidebar controls

earthdata_token = load_token_from_env()
bbox = None
aoi_geometry: Optional[BaseGeometry] = None
bbox_error = None

with st.sidebar:
    st.header("Settings")

    # NASA Earthdata token input
    if earthdata_token:
        st.success("NASA Earthdata token loaded from .env")
    else:
        st.warning("Set EARTHDATA_BEARER_TOKEN in your .env file to enable authenticated downloads.")

    st.markdown("---")

    # Area of interest coordinates
    st.subheader("Area of interest (AOI)")

    geojson_files = list_geojson_files(GEOJSON_DIR)
    input_method = st.radio(
        "Input method",
        ["Corner coordinates", "Center + radius", "GeoJSON"],
        index=2 if geojson_files else 0
    )

    if input_method == "Corner coordinates":
        col1, col2 = st.columns(2)
        with col1:
            min_lon = st.number_input("Min Longitude", value=round(DEFAULT_MIN_LON, 4), format="%.4f")
            min_lat = st.number_input("Min Latitude", value=round(DEFAULT_MIN_LAT, 4), format="%.4f")
        with col2:
            max_lon = st.number_input("Max Longitude", value=round(DEFAULT_MAX_LON, 4), format="%.4f")
            max_lat = st.number_input("Max Latitude", value=round(DEFAULT_MAX_LAT, 4), format="%.4f")
        try:
            bbox = normalize_bbox([min_lon, min_lat, max_lon, max_lat])
            aoi_geometry = box(bbox[0], bbox[1], bbox[2], bbox[3])
        except ValueError as exc:
            bbox_error = str(exc)
            bbox = None
            aoi_geometry = None
            st.error(bbox_error)

    elif input_method == "Center + radius":
        center_lon = st.number_input("Center longitude", value=round(DEFAULT_CENTER_LON, 4), format="%.4f")
        center_lat = st.number_input("Center latitude", value=round(DEFAULT_CENTER_LAT, 4), format="%.4f")
        radius_km = st.number_input("Radius (km)", value=float(DEFAULT_RADIUS_KM), min_value=0.1, max_value=100.0)

        # Rough conversion from kilometres to degrees
        lat_offset = radius_km / 111.0
        lon_offset = radius_km / (111.0 * np.cos(np.radians(center_lat)))

        try:
            bbox = normalize_bbox([
                center_lon - lon_offset,
                center_lat - lat_offset,
                center_lon + lon_offset,
                center_lat + lat_offset
            ])
            aoi_geometry = box(bbox[0], bbox[1], bbox[2], bbox[3])
        except ValueError as exc:
            bbox_error = str(exc)
            bbox = None
            aoi_geometry = None
            st.error(bbox_error)

    else:  # GeoJSON
        selected_geojson_path: Optional[Path] = None
        selected_geojson_text = ""
        if geojson_files:
            geojson_display_names = [path.name for path in geojson_files]
            selected_geojson_name = st.selectbox(
                "GeoJSON file",
                geojson_display_names,
                index=0,
                help="Files discovered in the geojsons directory"
            )
            selected_geojson_path = next(
                (candidate for candidate in geojson_files if candidate.name == selected_geojson_name),
                None
            )
            if selected_geojson_path is not None:
                try:
                    selected_geojson_text = selected_geojson_path.read_text(encoding="utf-8")
                except Exception as exc:
                    st.error(f"Failed to read {selected_geojson_path.name}: {exc}")
                    selected_geojson_text = ""
        else:
            st.info("No GeoJSON files found. Add files to the geojsons directory or paste one below.")
        geojson_input = st.text_area(
            "Paste a GeoJSON polygon",
            value=selected_geojson_text,
            height=150,
            help="Polygon geometry or Feature with Polygon geometry"
        )
        if selected_geojson_path is not None:
            st.caption(f"Loaded from `geojsons/{selected_geojson_path.name}`")
        if geojson_input:
            try:
                geojson_data = json.loads(geojson_input)
                geom = extract_geometry_from_geojson(geojson_data)
                aoi_geometry = geom
                raw_bbox = list(geom.bounds)
                bbox = normalize_bbox(raw_bbox)
            except ValueError as exc:
                bbox_error = str(exc)
                bbox = None
                aoi_geometry = None
                st.error(bbox_error)
            except Exception as e:
                st.error(f"Failed to parse GeoJSON: {e}")

    st.markdown("---")

    # Time window
    st.subheader("Time range")

    end_date = st.date_input(
        "End date",
        value=datetime.now(),
        max_value=datetime.now()
    )

    max_days_back = DAYS_BACK_LIMIT
    slider_step = 1 if max_days_back <= 30 else 30
    slider_min = min(100, max_days_back - slider_step)
    if slider_min < 0:
        slider_min = 0
    if slider_min >= max_days_back:
        slider_min = max(0, max_days_back - slider_step)
    days_back = st.slider(
        "Days back",
        min_value=slider_min,
        max_value=max_days_back,
        value=max_days_back,
        step=slider_step
    )

    start_date = end_date - timedelta(days=days_back)

    st.markdown("---")

    # Filtering parameters
    st.subheader("Filters")

    max_cloud_cover = st.slider(
        "Max cloud cover (%)",
        min_value=0,
        max_value=100,
        value=20,
        step=5
    )

    dataset = st.selectbox(
        "HLS dataset",
        ["Both", "HLSS30.v2.0", "HLSL30.v2.0"],
        index=0,
        help="S=Sentinel-2, L=Landsat"
    )

    st.markdown("---")

    search_button = st.button("Search scenes", type="primary", use_container_width=True)

if bbox:
    logger.debug("Active bbox for queries: %s", bbox)

# HLS helper functions
def estimate_crop_size_ranking(mean_ndvi: float, reference_area_ha: float) -> pd.DataFrame:
    """Estimate feasible crop areas for multiple crop types using NDVI heuristics."""

    if reference_area_ha <= 0 or math.isnan(reference_area_ha) or math.isnan(mean_ndvi):
        return pd.DataFrame()

    rows = []
    for profile in CROP_PROFILES:
        tolerance = profile.get('ndvi_tolerance', 0.25)
        yield_t_per_ha = profile.get('yield_t_per_ha')
        if tolerance <= 0:
            continue
        match_ratio = 1.0 - abs(mean_ndvi - profile['ndvi_optimal']) / tolerance
        match_ratio = max(0.0, min(1.0, match_ratio))
        min_match = float(profile.get('min_match', 0.0) or 0.0)
        floor_applied = False
        if min_match > 0 and match_ratio < min_match:
            match_ratio = min(min_match, 1.0)
            floor_applied = True
        estimated_area = reference_area_ha * match_ratio
        if not yield_t_per_ha or yield_t_per_ha <= 0:
            continue
        estimated_yield = estimated_area * yield_t_per_ha
        rows.append({
            'Crop': profile['name'],
            'Match': match_ratio,
            'Estimated area (ha)': estimated_area,
            'Estimated yield (t)': estimated_yield,
            'Match floor': 'Yes' if floor_applied else 'No',
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.sort_values(by='Estimated yield (t)', ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_yearly_crop_rankings(ndvi_df: pd.DataFrame, crop_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate crop rankings into multi-year averages."""

    if ndvi_df.empty or crop_df.empty:
        return pd.DataFrame()

    ndvi_yearly = (
        ndvi_df.assign(year=pd.to_datetime(ndvi_df['date']).dt.year)
        .groupby('year')['mean_NDVI']
        .mean()
        .dropna()
    )

    crop_area_yearly = (
        crop_df.assign(year=pd.to_datetime(crop_df['date']).dt.year)
        .groupby('year')['crop_area_hectares']
        .mean()
        .dropna()
    )

    common_years = sorted(set(ndvi_yearly.index).intersection(crop_area_yearly.index))
    if not common_years:
        return pd.DataFrame()

    per_year_rankings: List[pd.DataFrame] = []
    for year in common_years:
        mean_ndvi_year = float(ndvi_yearly.loc[year])
        reference_area_year = float(crop_area_yearly.loc[year])
        if reference_area_year <= 0 or math.isnan(reference_area_year) or math.isnan(mean_ndvi_year):
            continue
        ranking = estimate_crop_size_ranking(mean_ndvi_year, reference_area_year)
        if ranking.empty:
            continue
        ranking.insert(0, 'Year', int(year))
        per_year_rankings.append(ranking)

    if not per_year_rankings:
        return pd.DataFrame()

    per_year_df = pd.concat(per_year_rankings, ignore_index=True)

    summary = (
        per_year_df
        .groupby('Crop')
        .agg({
            'Estimated area (ha)': 'mean',
            'Estimated yield (t)': 'mean',
            'Match': 'mean',
            'Match floor': lambda col: 'Yes' if (col == 'Yes').any() else 'No',
            'Year': lambda col: sorted(set(int(v) for v in col)),
        })
        .reset_index()
    )

    if summary.empty:
        return summary

    summary['Years included'] = summary['Year'].apply(lambda years: ', '.join(str(y) for y in years))
    summary['Year count'] = summary['Year'].apply(len)
    summary = summary.drop(columns=['Year'])
    summary = summary.rename(columns={
        'Match': 'NDVI match',
        'Match floor': 'Match floor applied',
    })

    summary['Match floor applied'] = summary['Match floor applied'].astype(str)
    summary.sort_values(by='Estimated yield (t)', ascending=False, inplace=True)
    summary.reset_index(drop=True, inplace=True)
    return summary




def _stac_token_fingerprint(token: str) -> str:
    if not token:
        return "anon"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_stac_memory_cache_key(
    bbox: Tuple[float, float, float, float],
    start: str,
    end: str,
    max_cc: int,
    dataset_type: str,
    token: str,
) -> Tuple[Any, ...]:
    rounded_bbox = tuple(round(float(coord), 6) for coord in bbox)
    return (rounded_bbox, start, end, int(max_cc), dataset_type, _stac_token_fingerprint(token))


def _get_stac_records_from_memory(cache_key: Tuple[Any, ...]) -> Optional[List[Dict[str, Any]]]:
    cached = _STAC_RESULTS_CACHE.get(cache_key)
    if cached is None:
        return None
    _STAC_RESULTS_CACHE.move_to_end(cache_key)
    return [dict(record) for record in cached]


def _set_stac_records_in_memory(cache_key: Tuple[Any, ...], records: List[Dict[str, Any]]) -> None:
    _STAC_RESULTS_CACHE[cache_key] = tuple(dict(record) for record in records)
    _STAC_RESULTS_CACHE.move_to_end(cache_key)
    if len(_STAC_RESULTS_CACHE) > _STAC_MEMORY_CACHE_MAX_ENTRIES:
        _STAC_RESULTS_CACHE.popitem(last=False)


def _fetch_stac_records(
    bbox: Tuple[float, float, float, float],
    start: str,
    end: str,
    max_cc: int,
    dataset_type: str,
    token: str,
) -> List[Dict[str, Any]]:
    cache_key = _make_stac_memory_cache_key(bbox, start, end, max_cc, dataset_type, token)
    cached_records = _get_stac_records_from_memory(cache_key)
    if cached_records is not None:
        logger.debug(
            "STAC in-memory cache hit: bbox=%s start=%s end=%s dataset=%s",
            bbox,
            start,
            end,
            dataset_type,
        )
        return cached_records

    logger.debug(
        "STAC in-memory cache miss: bbox=%s start=%s end=%s dataset=%s",
        bbox,
        start,
        end,
        dataset_type,
    )

    catalog = Client.open(
        "https://cmr.earthdata.nasa.gov/stac/LPCLOUD",
        headers={"Authorization": f"Bearer {token}"} if token else {},
    )

    if dataset_type == "HLSS30.v2.0":
        collections = ["HLSS30.v2.0"]
    elif dataset_type == "HLSL30.v2.0":
        collections = ["HLSL30.v2.0"]
    else:
        collections = ["HLSS30.v2.0", "HLSL30.v2.0"]

    logger.debug("Collections to query: %s", collections)

    records: List[Dict[str, Any]] = []
    normalised_bbox = list(bbox)

    for collection in collections:
        search = catalog.search(
            collections=[collection],
            bbox=normalised_bbox,
            datetime=f"{start}/{end}",
            max_items=STAC_MAX_ITEMS,
            limit=STAC_PAGE_SIZE,
        )
        collected: List[Any] = []
        for item in search.items():
            collected.append(item)
            if len(collected) >= STAC_MAX_ITEMS:
                logger.warning(
                    "Reached STAC max items (%s) for %s; results truncated",
                    STAC_MAX_ITEMS,
                    collection,
                )
                break
        logger.debug("Collection %s returned %s items before filtering", collection, len(collected))

        for item in collected:
            props = item.properties
            cloud_cover = props.get("eo:cloud_cover", 100)
            if cloud_cover > max_cc:
                logger.debug(
                    "Skipping item %s: cloud cover %.2f exceeds threshold %s",
                    item.id,
                    cloud_cover,
                    max_cc,
                )
                continue

            nir_asset = item.assets.get("B8A") or item.assets.get("B05")
            red_asset = item.assets.get("B04")
            blue_asset = item.assets.get("B02")

            nir_url = getattr(nir_asset, "href", None)
            red_url = getattr(red_asset, "href", None)
            blue_url = getattr(blue_asset, "href", None)
            if not nir_url or not red_url or not blue_url:
                logger.debug(
                    "Skipping item %s: missing required bands (red=%s, nir=%s, blue=%s)",
                    item.id,
                    bool(red_url),
                    bool(nir_url),
                    bool(blue_url),
                )
                continue

            records.append(
                {
                    "id": item.id,
                    "datetime": pd.to_datetime(props["datetime"]),
                    "cloud_cover": float(cloud_cover),
                    "collection": item.collection_id,
                    "nir_url": nir_url,
                    "red_url": red_url,
                    "blue_url": blue_url,
                }
            )
            logger.debug("Kept item %s (collection=%s)", item.id, item.collection_id)

    _set_stac_records_in_memory(cache_key, records)
    return records

@st.cache_data(ttl=3600 * 24 * 7)
def search_hls_data(bbox: List[float], start: str, end: str, max_cc: int,
                    dataset_type: str, _token: str) -> pd.DataFrame:
    """Search HLS scenes via the STAC API"""

    logger.info("search_hls_data: bbox=%s start=%s end=%s max_cc=%s dataset=%s token_provided=%s", bbox, start, end, max_cc, dataset_type, bool(_token))
    bbox = normalize_bbox(bbox)

    cache_path = get_stac_cache_path(bbox, start, end, max_cc, dataset_type, _token)
    cached_df = load_stac_cache(cache_path)
    if cached_df is not None:
        logger.debug("search_hls_data: returning %s cached items from %s", len(cached_df), cache_path.name)
        return cached_df

    try:
        records = _fetch_stac_records(tuple(bbox), start, end, max_cc, dataset_type, _token)
    except Exception as e:
        logger.exception("search_hls_data failed")
        st.error(f"Search error: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    logger.info("search_hls_data: %s items after filtering", len(df))
    if not df.empty:
        df = df.sort_values("datetime")
    store_stac_cache(cache_path, records)
    logger.debug("search_hls_data: cached %s items at %s", len(df), cache_path.name)
    return df


def summarise_ndvi_stats(ndvi: Optional[np.ma.MaskedArray], mean_ndvi: float) -> Dict[str, float]:
    """Derive crop-cover metrics from an NDVI raster."""

    if ndvi is None or getattr(ndvi, 'size', 0) == 0:
        return {
            'mean_ndvi': mean_ndvi,
            'crop_fraction': float('nan'),
            'crop_percent': float('nan'),
            'crop_area_hectares': float('nan'),
            'total_area_hectares': float('nan'),
        }

    valid_values = ndvi.compressed()
    valid_pixels = int(valid_values.size)
    if valid_pixels == 0:
        return {
            'mean_ndvi': mean_ndvi,
            'crop_fraction': float('nan'),
            'crop_percent': float('nan'),
            'crop_area_hectares': float('nan'),
            'total_area_hectares': float('nan'),
        }

    crop_pixels = int(np.count_nonzero(valid_values >= CROP_NDVI_THRESHOLD))
    crop_fraction = crop_pixels / valid_pixels if valid_pixels else float('nan')
    crop_area_hectares = (crop_pixels * HLS_PIXEL_AREA_SQM) / 10000.0
    total_area_hectares = (valid_pixels * HLS_PIXEL_AREA_SQM) / 10000.0

    return {
        'mean_ndvi': mean_ndvi,
        'crop_fraction': crop_fraction,
        'crop_percent': crop_fraction * 100.0,
        'crop_area_hectares': crop_area_hectares,
        'total_area_hectares': total_area_hectares,
    }


def calculate_index_from_urls(index_type: IndexType, red_url: str, blue_url: str, nir_url: str, bbox: List[float],
                             token: str) -> Tuple[Optional[np.ma.MaskedArray], Optional[float], Optional[Dict[str, float]]]:
    """Compute vegetation index from COG assets and derive NDVI statistics when applicable."""

    logger.info(
        "calculate_index_from_urls: red_url=%s blue_url=%s nir_url=%s bbox=%s token_provided=%s",
        red_url,
        blue_url,
        nir_url,
        bbox,
        bool(token)
    )

    try:
        bbox = normalize_bbox(bbox)
    except ValueError:
        logger.exception("Vegetation index calculation received invalid bbox")
        st.warning("Vegetation index calculation error: invalid bounding box")
        return None, None, None

    cache_path = get_index_cache_path(index_type, red_url, blue_url, nir_url, bbox)

    if cache_path.exists():
        try:
            with np.load(cache_path, allow_pickle=False) as cached:
                index_data = cached[index_type.name]
                mask = cached['mask']
                mean_index = float(cached['mean'].item())
            masked_data = np.ma.array(index_data, mask=mask)
            stats = summarise_ndvi_stats(masked_data, mean_index) if index_type is IndexType.NDVI else None
            logger.debug("Loaded index data from cache for %s", cache_path.name)
            return masked_data, mean_index, stats
        except Exception:
            logger.exception("Failed to load index data cache from %s", cache_path)
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass

    try:
        env_kwargs: dict[str, object] = {}
        session = None
        if token:
            env_kwargs['GDAL_HTTP_HEADERS'] = f"Authorization: Bearer {token}"
            env_kwargs['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
            env_kwargs['GDAL_HTTP_MULTIRANGE'] = 'YES'
            logger.debug("Attempting to create AWSSession for provided NASA token")
            if AWSSession is not None:
                try:
                    session = AWSSession(
                        aws_access_key_id='',
                        aws_secret_access_key='',
                        aws_session_token=token
                    )
                    logger.debug("AWSSession created: %s", session)
                except AttributeError:
                    logger.warning("boto3 is not available; falling back to GDAL HTTP headers only.")
                except Exception:
                    logger.exception("Failed to create AWSSession; continuing with GDAL HTTP headers")
                else:
                    env_kwargs['session'] = session
            else:
                logger.debug("AWSSession class unavailable; using GDAL HTTP headers only.")
        else:
            logger.debug("No NASA token supplied; using default rasterio session")

        def _window_from_bbox(src_obj: rasterio.io.DatasetReader):
            try:
                left, bottom, right, top = transform_bounds(
                    'EPSG:4326',
                    src_obj.crs,
                    bbox[0],
                    bbox[1],
                    bbox[2],
                    bbox[3],
                    densify_pts=21
                )
            except Exception:
                logger.exception("Failed to transform AOI %s into %s", bbox, src_obj.crs)
                raise

            left = max(left, src_obj.bounds.left)
            right = min(right, src_obj.bounds.right)
            bottom = max(bottom, src_obj.bounds.bottom)
            top = min(top, src_obj.bounds.top)

            if not (left < right and bottom < top):
                logger.warning(
                    "AOI %s does not intersect raster bounds %s for %s",
                    bbox,
                    src_obj.bounds,
                    src_obj.name
                )
                return None

            window = src_obj.window(left, bottom, right, top)
            window = window.round_offsets(op=math.floor).round_shape(op=math.ceil)

            if window.width <= 0 or window.height <= 0:
                logger.warning(
                    "AOI %s produced empty window against raster %s",
                    bbox,
                    src_obj.name
                )
                return None

            return window

        with rasterio.Env(**env_kwargs):
            logger.debug("Opening red band %s", red_url)
            with rasterio.open(red_url) as red_src:
                red_window = _window_from_bbox(red_src)
                if red_window is None:
                    return None, None, None
                red = red_src.read(1, window=red_window, masked=True)
                logger.debug("Read red band with shape %s", getattr(red, 'shape', None))

            logger.debug("Opening blue band %s", blue_url)
            with rasterio.open(blue_url) as blue_src:
                blue_window = _window_from_bbox(blue_src)
                if blue_window is None:
                    return None, None, None
                blue = blue_src.read(1, window=blue_window, masked=True)
                logger.debug("Read blue band with shape %s", getattr(blue, 'shape', None))

            logger.debug("Opening NIR band %s", nir_url)
            with rasterio.open(nir_url) as nir_src:
                nir_window = _window_from_bbox(nir_src)
                if nir_window is None:
                    return None, None, None
                nir = nir_src.read(1, window=nir_window, masked=True)
                logger.debug("Read NIR band with shape %s", getattr(nir, 'shape', None))

        if red.size == 0 or nir.size == 0:
            logger.warning("AOI read returned empty arrays (red=%s, nir=%s)", red.size, nir.size)
            return None, None, None

        if red.shape != nir.shape or red.shape != blue.shape:
            logger.warning(
                "Band windows differ in shape for %s vs %s vs %s: %s vs %s vs %s",
                red_url,
                blue_url,
                nir_url,
                red.shape,
                blue.shape,
                nir.shape
            )
            return None, None, None

        red_data = red.astype('float32')
        blue_data = blue.astype('float32')
        nir_data = nir.astype('float32')

        match index_type:
            case IndexType.NDVI:
                with np.errstate(divide='ignore', invalid='ignore'):
                    ndvi = (nir_data - red_data) / (nir_data + red_data)
                combined_mask = np.ma.getmaskarray(red) | np.ma.getmaskarray(nir)
                masked_data = np.ma.array(ndvi, mask=combined_mask)
            case IndexType.EVI:
                with np.errstate(divide='ignore', invalid='ignore'):
                    evi = 2.5 * (nir_data - red_data) / (nir_data + 6 * red_data - 7.5 * blue_data + 1)
                combined_mask = (
                    np.ma.getmaskarray(red)
                    | np.ma.getmaskarray(blue)
                    | np.ma.getmaskarray(nir)
                )
                masked_data = np.ma.array(evi, mask=combined_mask)

        if masked_data.count() == 0:
            logger.warning("Vegetation index computation has no valid pixels for %s", red_url)
            return None, None, None

        mean_index = float(masked_data.mean())
        logger.info("calculate_index_from_urls: mean index=%.4f", mean_index)

        stats = summarise_ndvi_stats(masked_data, mean_index) if index_type is IndexType.NDVI else None

        try:
            index_data_to_store = masked_data.filled(np.nan).astype('float32')
            mask_to_store = np.ma.getmaskarray(masked_data)
            data_to_save = {
                index_type.name: index_data_to_store,
                'mask': mask_to_store,
                'mean': np.array([mean_index], dtype='float32'),
            }
            np.savez_compressed(cache_path, **data_to_save)
            logger.debug("Cached Vegetation index result at %s", cache_path)
        except Exception:
            logger.exception("Failed to persist Vegetation index cache at %s", cache_path)

        return masked_data, mean_index, stats

    except Exception as e:
        logger.exception("Vegetation index calculation failed")
        st.warning(f"Vegetation index calculation error: {e}")
        return None, None, None


def compute_index_for_row(row: Tuple, index_types: List[IndexType], bbox: List[float], token: str) -> Dict[str, Any]:
    if hasattr(row, "_asdict"):
        data = row._asdict()
    elif isinstance(row, dict):
        data = row
    else:
        keys = ["id", "datetime", "cloud_cover", "collection", "nir_url", "red_url", "blue_url"]
        data: Dict[str, Any] = {}
        for idx, key in enumerate(keys):
            if isinstance(row, (list, tuple)) and idx < len(row):
                data[key] = row[idx]

    scene_id = data.get("id")
    red_url = data.get("red_url")
    blue_url = data.get("blue_url")
    nir_url = data.get("nir_url")

    if not red_url or not nir_url or not blue_url:
        logger.debug("Skipping scene %s due to missing band URLs", scene_id)
        return {}

    logger.debug("Submitting NDVI task for scene=%s", scene_id)

    result: Dict[str, Any] = {
        "date": data.get("datetime"),
        "cloud_cover": data.get("cloud_cover"),
        "collection": data.get("collection"),
    }

    for index_type in index_types:
        index_data, mean_index, stats = calculate_index_from_urls(index_type, red_url, blue_url, nir_url, bbox, token)
        if index_data is None or mean_index is None:
            continue

        result[f"mean_{index_type.name}"] = mean_index

        if index_type is IndexType.NDVI and stats:
            result["crop_fraction"] = stats.get("crop_fraction")
            result["crop_percent"] = stats.get("crop_percent")
            result["crop_area_hectares"] = stats.get("crop_area_hectares")
            result["total_area_hectares"] = stats.get("total_area_hectares")

    return result


def fetch_weather_history(lat: float, lon: float, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_str,
        "end_date": end_str,
        "hourly": "temperature_2m,relative_humidity_2m,cloudcover,windspeed_10m",
        "timezone": "auto",
    }
    try:
        response = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.exception("Weather API request failed")
        st.warning(f"Weather data unavailable: {exc}")
        return pd.DataFrame()

    payload = response.json()
    hourly = payload.get("hourly") or {}
    times = hourly.get("time")
    temps = hourly.get("temperature_2m")
    humidity = hourly.get("relative_humidity_2m")
    cloudcover = hourly.get("cloudcover")
    windspeed = hourly.get("windspeed_10m")
    if not times or not temps or not humidity or not cloudcover:
        logger.warning("Incomplete weather data returned for lat=%s lon=%s", lat, lon)
        return pd.DataFrame()
    if not windspeed:
        logger.warning("Wind speed missing for lat=%s lon=%s; substituting zeros", lat, lon)
        windspeed = [0.0] * len(times)

    weather_df = pd.DataFrame(
        {
            "time": pd.to_datetime(times),
            "temperature_c": pd.to_numeric(temps, errors="coerce"),
            "humidity_pct": pd.to_numeric(humidity, errors="coerce"),
            "cloudcover_pct": pd.to_numeric(cloudcover, errors="coerce"),
            "wind_speed": pd.to_numeric(windspeed, errors="coerce"),
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
    daily.rename(columns={
        "time": "date",
        "temperature_c": "temperature_mean",
        "humidity_pct": "humidity_mean",
        "cloudcover_pct": "cloudcover_mean",
        "wind_speed": "wind_speed_mean",
    }, inplace=True)
    daily["clarity_index"] = 100.0 - daily["cloudcover_mean"].clip(lower=0, upper=100)
    return daily


# Main interface logic

if search_button:
    if not earthdata_token:
        st.warning("Please set EARTHDATA_BEARER_TOKEN in your .env file.")
        st.info("""
        **How to obtain a token:**
        1. Create an account at https://urs.earthdata.nasa.gov/
        2. Open Profile -> Generate Token
        3. Copy the Bearer Token into your .env file as EARTHDATA_BEARER_TOKEN
        """)
    elif not bbox:
        st.error(bbox_error or "Please provide an area of interest")
    else:
        center_latitude: Optional[float] = None
        center_longitude: Optional[float] = None
        if aoi_geometry is not None and not aoi_geometry.is_empty:
            centroid = aoi_geometry.centroid
            center_latitude = centroid.y
            center_longitude = centroid.x
        elif bbox:
            center_latitude = (bbox[1] + bbox[3]) / 2
            center_longitude = (bbox[0] + bbox[2]) / 2

        start_dt = ensure_datetime(start_date)
        end_dt = ensure_datetime(end_date)

        with st.spinner("Searching HLS scenes..."):
            df = search_hls_data(
                bbox=bbox,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                max_cc=max_cloud_cover,
                dataset_type=dataset,
                _token=earthdata_token
            )

        if df.empty:
            st.warning("No scenes found. Try adjusting your filters.")
        else:
            st.success(f"Found {len(df)} HLS scenes")

            # Output tabs
            tab1, tab2, tab3 = st.tabs(["NDVI time series", "Map", "Data table"])

            with tab1:
                st.subheader("NDVI time series")

                progress_bar = st.progress(0)
                status_text = st.empty()

                results: List[Dict[str, Any]] = []
                row_tuples = list(df.itertuples(index=False))
                index_types = [IndexType.NDVI]
                if ENABLE_EVI:
                    index_types.append(IndexType.EVI)
                
                if row_tuples:
                    worker = partial(compute_index_for_row, index_types=index_types, bbox=bbox, token=earthdata_token)
                    default_worker_cap = 1 if _CLOUD_RUN_SERVICE else 8
                    worker_cap_raw = os.getenv("WORKER_CAP", "").strip()
                    if worker_cap_raw:
                        try:
                            worker_cap = max(1, int(worker_cap_raw))
                            logger.info(f"WORKER_CAP={worker_cap_raw}")
                        except ValueError:
                            logger.warning("Invalid WORKER_CAP=%s; falling back to default", worker_cap_raw)
                            worker_cap = default_worker_cap
                    else:
                        worker_cap = default_worker_cap
                    max_workers = min(worker_cap, len(row_tuples))
                    max_workers = max(1, max_workers)
                    logger.debug("NDVI worker pool size=%s", max_workers)
                    try:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                            future_to_index = {executor.submit(worker, row): idx for idx, row in enumerate(row_tuples)}
                            completed = 0
                            for future in concurrent.futures.as_completed(future_to_index):
                                idx = future_to_index[future]
                                completed += 1
                                try:
                                    result = future.result()
                                    if result:
                                        results.append(result)
                                except Exception:
                                    logger.exception("NDVI worker failed for index %s", idx)
                                scene_info = df.iloc[idx]
                                scene_id = scene_info.get('id') if hasattr(scene_info, 'get') else getattr(scene_info, 'id', None)
                                date_value = scene_info.get('datetime') if hasattr(scene_info, 'get') else getattr(scene_info, 'datetime', None)
                                date_label = date_value.strftime('%Y-%m-%d') if hasattr(date_value, 'strftime') else str(date_value)
                                message = f"Processing scene {completed}/{len(row_tuples)}"
                                if scene_id:
                                    message += f" ({scene_id})"
                                message += f": {date_label}"
                                status_text.text(message)
                                progress_bar.progress(completed / len(row_tuples))
                                log_progress(message)
                    except Exception:
                        logger.exception("Parallel NDVI processing failed; falling back to sequential execution")
                        results = []

                    if not results:
                        logger.info("Parallel NDVI returned no results; retrying sequential execution")
                        progress_bar.progress(0.0)
                        for idx, row in enumerate(row_tuples):
                            scene_info = df.iloc[idx]
                            scene_id = scene_info.get('id') if hasattr(scene_info, 'get') else getattr(scene_info, 'id', None)
                            date_value = scene_info.get('datetime') if hasattr(scene_info, 'get') else getattr(scene_info, 'datetime', None)
                            date_label = date_value.strftime('%Y-%m-%d') if hasattr(date_value, 'strftime') else str(date_value)
                            message = f"Processing scene {idx + 1}/{len(row_tuples)}"
                            if scene_id:
                                message += f" ({scene_id})"
                            message += f": {date_label}"
                            status_text.text(message)
                            result = worker(row)
                            if result:
                                results.append(result)
                            progress_bar.progress((idx + 1) / len(row_tuples))
                            log_progress(message)

                status_text.empty()
                progress_bar.empty()

                if results:
                    ndvi_df = pd.DataFrame(results).sort_values('date')

                    weather_df = pd.DataFrame()
                    if center_latitude is not None and center_longitude is not None:
                        weather_df = fetch_weather_history(center_latitude, center_longitude, start_dt, end_dt)

                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(
                        go.Scatter(
                            x=ndvi_df['date'],
                            y=ndvi_df['mean_NDVI'],
                            mode="lines+markers",
                            name="NDVI",
                            line=dict(color="green", width=2),
                            marker=dict(size=8),
                            hovertemplate="<b>Date:</b> %{x}<br><b>NDVI:</b> %{y:.3f}<extra></extra>",
                        ),
                        secondary_y=False,
                    )

                    if ENABLE_EVI and 'mean_EVI' in ndvi_df:
                        fig.add_trace(
                            go.Scatter(
                                x=ndvi_df['date'],
                                y=ndvi_df['mean_EVI'],
                                mode="lines+markers",
                                name="EVI",
                                line=dict(color="blue", width=2),
                                marker=dict(size=8),
                                hovertemplate="<b>Date:</b> %{x}<br><b>EVI:</b> %{y:.3f}<extra></extra>",
                            ),
                            secondary_y=False,
                        )

                    fig.add_hline(
                        y=0.3,
                        line_dash="dash",
                        line_color="orange",
                        annotation_text="Early canopy target",
                    )
                    fig.add_hline(
                        y=0.6,
                        line_dash="dash",
                        line_color="darkgreen",
                        annotation_text="Peak foliage target",
                    )

                    if not weather_df.empty:
                        fig.add_trace(
                            go.Scatter(
                                x=weather_df['date'],
                                y=weather_df['clarity_index'],
                                name="Clarity index (%)",
                                line=dict(color="#1b9e77"),
                                visible='legendonly'
                            ),
                            secondary_y=True,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=weather_df['date'],
                                y=weather_df['humidity_mean'],
                                name="Humidity (%)",
                                line=dict(color="#d95f02", dash="dash"),
                            ),
                            secondary_y=True,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=weather_df['date'],
                                y=weather_df['temperature_mean'],
                                name="Temperature (deg C)",
                                line=dict(color="#7570b3", dash="dot"),
                            ),
                            secondary_y=True,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=weather_df['date'],
                                y=weather_df['wind_speed_mean'],
                                name="Wind speed (m/s)",
                                line=dict(color="#66a61e", dash="dashdot"),
                                visible='legendonly'
                            ),
                            secondary_y=True,
                        )

                    fig.update_yaxes(title_text="NDVI", secondary_y=False)
                    fig.update_yaxes(title_text="Weather metrics", secondary_y=True)
                    fig.update_layout(
                        title="NDVI and weather overview",
                        xaxis_title="Date",
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        height=520,
                    )

                    st.plotly_chart(fig, use_container_width=True)
                    if not weather_df.empty:
                        st.caption("Weather source: Open-Meteo archive (daily means).")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Mean NDVI", f"{ndvi_df['mean_NDVI'].mean():.3f}")
                    with col2:
                        st.metric("Max NDVI", f"{ndvi_df['mean_NDVI'].max():.3f}")
                    with col3:
                        st.metric("Min NDVI", f"{ndvi_df['mean_NDVI'].min():.3f}")
                    with col4:
                        st.metric("Std. dev.", f"{ndvi_df['mean_NDVI'].std():.3f}")

                    if ndvi_df['mean_NDVI'].min() < 0:
                        st.info("Negative NDVI values typically indicate open water, clouds, or other non-vegetation surfaces within the AOI.")

                    mean_ndvi = float(ndvi_df['mean_NDVI'].mean()) if not ndvi_df.empty else float('nan')

                    monthly_ndvi = (
                        ndvi_df.assign(month_number=pd.to_datetime(ndvi_df['date']).dt.month)
                        .groupby('month_number')['mean_NDVI']
                        .agg(['mean', 'median'])
                        .reset_index()
                        .sort_values('month_number')
                    )
                    if not monthly_ndvi.empty:
                        monthly_ndvi['month_name'] = monthly_ndvi['month_number'].apply(lambda m: calendar.month_abbr[m])
                        monthly_fig = go.Figure()
                        monthly_fig.add_trace(
                            go.Scatter(
                                x=monthly_ndvi['month_name'],
                                y=monthly_ndvi['mean'],
                                name="Monthly mean NDVI",
                                mode="lines+markers",
                                marker=dict(size=8),
                                line=dict(color="#2c7fb8", width=2),
                                hovertemplate="<b>Month:</b> %{x}<br><b>Mean NDVI:</b> %{y:.3f}<extra></extra>",
                            )
                        )
                        monthly_fig.add_trace(
                            go.Scatter(
                                x=monthly_ndvi['month_name'],
                                y=monthly_ndvi['median'],
                                name="Monthly median NDVI",
                                mode="lines+markers",
                                marker=dict(size=8),
                                line=dict(color="#7fcdbb", width=2, dash="dash"),
                                hovertemplate="<b>Month:</b> %{x}<br><b>Median NDVI:</b> %{y:.3f}<extra></extra>",
                            )
                        )
                        monthly_fig.update_layout(
                            title="Monthly NDVI summary",
                            xaxis_title="Month",
                            yaxis_title="NDVI",
                            height=420,
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        )
                        monthly_fig.update_xaxes(
                            categoryorder="array",
                            categoryarray=[calendar.month_abbr[m] for m in range(1, 13)]
                        )
                        st.plotly_chart(monthly_fig, use_container_width=True)

                    crop_df = pd.DataFrame()
                    if 'crop_percent' in ndvi_df.columns:
                        crop_df = ndvi_df.dropna(subset=['crop_percent'])

                    if not crop_df.empty:
                        crop_fig = go.Figure()
                        crop_fig.add_trace(
                            go.Bar(
                                x=crop_df['date'],
                                y=crop_df['crop_percent'],
                                name="Crop cover (%)",
                                marker_color="#228B22",
                                hovertemplate="<b>Date:</b> %{x}<br><b>Crop cover:</b> %{y:.1f}%<extra></extra>",
                            )
                        )
                        crop_fig.update_yaxes(title_text="Crop cover (% of AOI)", range=[0, 100])
                        crop_fig.update_layout(
                            title="Estimated crop-covered area",
                            xaxis_title="Date",
                            height=420,
                            showlegend=False,
                        )
                        st.plotly_chart(crop_fig, use_container_width=True)

                        latest_crop = crop_df.iloc[-1]
                        latest_timestamp = pd.to_datetime(latest_crop['date']) if pd.notna(latest_crop['date']) else None
                        latest_date_str = latest_timestamp.strftime("%Y-%m-%d") if latest_timestamp is not None else "N/A"
                        crop_area = latest_crop.get('crop_area_hectares')
                        total_area = latest_crop.get('total_area_hectares')
                        if pd.notna(crop_area) and pd.notna(total_area):
                            st.caption(
                                f"Estimated crop biomass footprint on {latest_date_str}: {crop_area:.1f} ha "
                                f"({latest_crop['crop_percent']:.1f}% of {total_area:.1f} ha AOI)."
                            )

                        yearly_rankings = build_yearly_crop_rankings(ndvi_df, crop_df)
                        if not yearly_rankings.empty:
                            area_source = yearly_rankings.sort_values('Estimated area (ha)', ascending=False)
                            area_fig = go.Figure()
                            area_fig.add_trace(
                                go.Bar(
                                    y=area_source['Crop'],
                                    x=area_source['Estimated area (ha)'],
                                    orientation='h',
                                    marker_color="#2e8b57",
                                    customdata=area_source[['NDVI match', 'Estimated yield (t)', 'Years included', 'Year count', 'Match floor applied']].to_numpy(),
                                    hovertemplate=(
                                        "<b>Crop:</b> %{y}<br>Average area: %{x:.1f} ha"
                                        "<br>Average NDVI match: %{customdata[0]:.0%}"
                                        "<br>Average yield: %{customdata[1]:.1f} t"
                                        "<br>Years included: %{customdata[2]} (%{customdata[3]} yrs)"
                                        "<br>Match floor applied: %{customdata[4]}<extra></extra>"
                                    ),
                                )
                            )
                            area_fig.update_layout(
                                title="Average crop size ranking (area)",
                                xaxis_title="Average feasible area (ha)",
                                yaxis_title="Crop",
                                height=420,
                                margin=dict(l=120, r=40, t=80, b=60),
                                showlegend=False,
                            )
                            st.plotly_chart(area_fig, use_container_width=True)

                            yield_source = yearly_rankings.sort_values('Estimated yield (t)', ascending=False)
                            yield_fig = go.Figure()
                            yield_fig.add_trace(
                                go.Bar(
                                    y=yield_source['Crop'],
                                    x=yield_source['Estimated yield (t)'],
                                    orientation='h',
                                    marker_color="#556b2f",
                                    customdata=yield_source[['NDVI match', 'Estimated area (ha)', 'Years included', 'Year count', 'Match floor applied']].to_numpy(),
                                    hovertemplate=(
                                        "<b>Crop:</b> %{y}<br>Average yield: %{x:.1f} t"
                                        "<br>Average NDVI match: %{customdata[0]:.0%}"
                                        "<br>Average area basis: %{customdata[1]:.1f} ha"
                                        "<br>Years included: %{customdata[2]} (%{customdata[3]} yrs)"
                                        "<br>Match floor applied: %{customdata[4]}<extra></extra>"
                                    ),
                                )
                            )
                            yield_fig.update_layout(
                                title="Average crop yield ranking (heuristic)",
                                xaxis_title="Average yield (t)",
                                yaxis_title="Crop",
                                height=420,
                                margin=dict(l=120, r=40, t=80, b=60),
                                showlegend=False,
                            )
                            st.plotly_chart(yield_fig, use_container_width=True)

                            with st.expander("Average crop ranking details", expanded=False):
                                pretty_df = yearly_rankings.copy()
                                pretty_df['NDVI match'] = pretty_df['NDVI match'].map(lambda v: f"{v:.0%}")
                                for column in ('Estimated area (ha)', 'Estimated yield (t)'):
                                    pretty_df[column] = pretty_df[column].map(lambda v: f"{v:.1f}")
                                display_columns = ['Crop', 'Estimated area (ha)', 'Estimated yield (t)', 'NDVI match', 'Match floor applied', 'Years included', 'Year count']
                                st.dataframe(pretty_df[display_columns], hide_index=True, use_container_width=True)
                        else:
                            st.info("Multi-year crop rankings are unavailable - insufficient NDVI or crop area data across years.")

                    if not math.isnan(mean_ndvi):
                        if mean_ndvi < 0.2:
                            st.error("**Severely stressed canopy** - bare soil, standing water, or senescing vegetation")
                        elif mean_ndvi < 0.4:
                            st.warning("**Early canopy development** - sparse foliage; monitor crop inputs closely")
                        elif mean_ndvi < 0.6:
                            st.success("**Healthy canopy** - vigorous vegetative growth and photosynthesis")
                        else:
                            st.info("**Very dense canopy** - peak foliage; watch for lodging, pests, or late-season disease pressure")

                else:
                    st.error("Could not compute NDVI for the retrieved scenes")

            with tab2:
                st.subheader("AOI map")

                polygons = geometry_to_polygons(aoi_geometry) if aoi_geometry else []
                if not polygons and bbox:
                    polygons = [[
                        [bbox[0], bbox[1]],
                        [bbox[2], bbox[1]],
                        [bbox[2], bbox[3]],
                        [bbox[0], bbox[3]],
                        [bbox[0], bbox[1]],
                    ]]

                map_center_lat = center_latitude if center_latitude is not None else DEFAULT_CENTER_LAT
                map_center_lon = center_longitude if center_longitude is not None else DEFAULT_CENTER_LON

                layers = []
                if polygons:
                    polygon_data = [{"polygon": poly} for poly in polygons]
                    layers.append(
                        pdk.Layer(
                            "PolygonLayer",
                            polygon_data,
                            get_polygon="polygon",
                            get_fill_color=[34, 139, 34, 80],
                            get_line_color=[34, 139, 34],
                            line_width_min_pixels=2,
                        )
                    )

                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=[{"position": [map_center_lon, map_center_lat]}],
                        get_position="position",
                        get_radius=750,
                        get_fill_color=[255, 215, 0, 180],
                        get_line_color=[0, 100, 0],
                        line_width_min_pixels=1,
                    )
                )

                mapbox_token = os.getenv("MAPBOX_API_KEY")
                if not mapbox_token and find_existing_secrets():
                    try:
                        mapbox_token = st.secrets.get("mapbox_api_key")  # type: ignore[attr-defined]
                    except Exception:
                        mapbox_token = None

                if mapbox_token:
                    pdk.settings.mapbox_api_key = mapbox_token
                    map_style = "mapbox://styles/mapbox/satellite-streets-v12"
                else:
                    map_style = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

                deck = pdk.Deck(
                    map_style=map_style,
                    initial_view_state=pdk.ViewState(
                        latitude=map_center_lat,
                        longitude=map_center_lon,
                        zoom=9,
                        pitch=0,
                    ),
                    layers=layers,
                    tooltip={"text": "AOI"},
                )
                st.pydeck_chart(deck)

                st.info(f"""
                **AOI summary:**
                - South-west corner: {bbox[1]:.4f} deg N, {bbox[0]:.4f} deg E
                - North-east corner: {bbox[3]:.4f} deg N, {bbox[2]:.4f} deg E
                - Approximate area: ~{((bbox[2] - bbox[0]) * 111 * (bbox[3] - bbox[1]) * 111):.1f} km^2
                """)

            with tab3:
                st.subheader("Data table")

                display_df = df[["datetime", "collection", "cloud_cover"]].copy()
                display_df["datetime"] = display_df["datetime"].dt.strftime("%Y-%m-%d %H:%M")
                display_df.columns = ["Date & time", "Collection", "Cloud cover (%)"]

                st.dataframe(display_df, use_container_width=True)

                # Export button
                csv_table = display_df.to_csv(index=False)
                st.download_button(
                    label="Download table as CSV",
                    data=csv_table,
                    file_name=f"hls_table_{start_dt.date()}_{end_dt.date()}.csv",
                    mime="text/csv",
                )

                if results:
                    weather_export = weather_df.copy() if not weather_df.empty else pd.DataFrame()
                    export_df = pd.DataFrame(results).sort_values('date')
                    if not weather_export.empty:
                        # Normalize dates to timezone-naive and date-only for proper matching
                        export_df['date_normalized'] = pd.to_datetime(export_df['date']).dt.tz_localize(None).dt.date
                        weather_export['date_normalized'] = pd.to_datetime(weather_export['date']).dt.date
                        
                        weather_export = weather_export.rename(columns={
                            'temperature_mean': 'temperature_deg_c',
                            'humidity_mean': 'humidity_pct',
                            'cloudcover_mean': 'cloudcover_pct',
                            'wind_speed_mean': 'wind_speed_mps',
                            'clarity_index': 'clarity_pct',
                        })
                        
                        export_df = export_df.merge(
                            weather_export.drop(columns=['date']), 
                            left_on='date_normalized', 
                            right_on='date_normalized', 
                            how='left'
                        )
                        export_df = export_df.drop(columns=['date_normalized'])
                    csv_results = export_df.to_csv(index=False)
                    st.download_button(
                        label="Download NDVI + weather (CSV)",
                        data=csv_results,
                        file_name=f"hls_ndvi_weather_{start_dt.date()}_{end_dt.date()}.csv",
                        mime="text/csv",
                    )
else:
    # First-run instructions
    st.info("""
    ### Welcome to HLS Crop Monitor!

    **What you can do with this app:**
    - Retrieve HLS (Harmonized Landsat Sentinel-2) imagery at 30 m resolution
    - Analyse NDVI time series to track canopy vigor
    - Compare management zones across multiple observation dates

    **To get started:**
    1. Request a free token at https://urs.earthdata.nasa.gov/
    2. Provide the area of interest in the sidebar
    3. Choose the time range
    4. Select "Search scenes"

    **NDVI interpretation guidance:**
    - < 0.2: Bare soil, standing water, or senescing vegetation
    - 0.2-0.4: Emerging canopy or stressed plants
    - 0.4-0.6: Healthy vegetative growth
    - > 0.6: Peak foliage; monitor for disease and nutrient demand
    """)

    # Example AOIs
    st.markdown("### Sample AOIs to try")

    st.markdown("""
    **Sun Valley Potatoes (ID, USA)**  
    - Use the bundled `geojsons/sun_valley_potatoes.json`
    - Suggested season: May-August
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Snake River Plain Center Pivots (ID, USA)**  
        Large irrigated potato blocks near American Falls
        - Center: 42.7730 deg N, -112.8480 deg W
        - Suggested radius: 6 km
        """)

    with col2:
        st.markdown("""
        **Red River Valley Fields (ND/MN, USA)**  
        Loamy soils with intensive potato production
        - Center: 47.8100 deg N, -96.8200 deg W
        - Suggested radius: 6 km
        """)
# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>HLS Crop Monitor v1.0 | Data source: NASA HLS v2.0 | Built with Streamlit</p>
    <p><small>Data provided by NASA LP DAAC via the CMR-STAC API</small></p>
</div>
""", unsafe_allow_html=True)
