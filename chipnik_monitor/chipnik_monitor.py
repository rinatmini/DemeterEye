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
from shapely.geometry import shape, box, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from pathlib import Path
from functools import partial
import requests
import hashlib
import json
import logging
import concurrent.futures
import math
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
logger.setLevel(logging.DEBUG)

DEFAULT_CENTER_LON = -122.09261814845487
DEFAULT_CENTER_LAT = 47.60464601773639
DEFAULT_CORNER_HALF_WIDTH_DEG = 0.055
DEFAULT_MIN_LON = DEFAULT_CENTER_LON - DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MAX_LON = DEFAULT_CENTER_LON + DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MIN_LAT = DEFAULT_CENTER_LAT - DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_MAX_LAT = DEFAULT_CENTER_LAT + DEFAULT_CORNER_HALF_WIDTH_DEG
DEFAULT_RADIUS_KM = 6.0

APP_NAME = "Potato Crop Monitor"
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

CACHE_ROOT = Path(".cache")
NDVI_CACHE_DIR = CACHE_ROOT / "ndvi"
NDVI_CACHE_VERSION = "1"

def get_ndvi_cache_path(red_url: str, nir_url: str, bbox: List[float]) -> Path:
    payload = json.dumps(
        {
            "red": red_url,
            "nir": nir_url,
            "bbox": [round(float(coord), 6) for coord in bbox],
            "version": NDVI_CACHE_VERSION
        },
        sort_keys=True
    )
    cache_dir = NDVI_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.npz"

STAC_CACHE_DIR = CACHE_ROOT / "stac"
STAC_CACHE_VERSION = "1"

STAC_PAGE_SIZE = 200
STAC_MAX_ITEMS = 2000

STAC_CACHE_TTL_SECONDS = 3600

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
                "red_url": record.get("red_url")
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
st.title(f"{APP_NAME} - HLS NDVI Analysis")
st.markdown("**Assess potato crop health with HLS (Harmonized Landsat Sentinel-2) imagery**")

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

    days_back = st.slider(
        "Days back",
        min_value=7,
        max_value=1800,
        value=90,
        step=7
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
        ["HLSS30.v2.0", "HLSL30.v2.0", "Both"],
        help="S=Sentinel-2, L=Landsat"
    )

    st.markdown("---")

    search_button = st.button("Search scenes", type="primary", use_container_width=True)

if bbox:
    logger.debug("Active bbox for queries: %s", bbox)

# HLS helper functions
@st.cache_data(ttl=3600)
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
        # Connect to LP DAAC STAC
        catalog = Client.open(
            "https://cmr.earthdata.nasa.gov/stac/LPCLOUD",
            headers={"Authorization": f"Bearer {_token}"} if _token else {}
        )

        # Determine which collections to query
        if dataset_type == "HLSS30.v2.0":
            collections = ["HLSS30.v2.0"]
        elif dataset_type == "HLSL30.v2.0":
            collections = ["HLSL30.v2.0"]
        else:
            collections = ["HLSS30.v2.0", "HLSL30.v2.0"]

        logger.debug("Collections to query: %s", collections)
        all_items = []
        for collection in collections:
            search = catalog.search(
                collections=[collection],
                bbox=bbox,
                datetime=f"{start}/{end}",
                max_items=STAC_MAX_ITEMS,
                limit=STAC_PAGE_SIZE
            )
            collected = []
            for item in search.items():
                collected.append(item)
                if len(collected) >= STAC_MAX_ITEMS:
                    logger.warning("Reached STAC max items (%s) for %s; results truncated", STAC_MAX_ITEMS, collection)
                    break
            logger.debug("Collection %s returned %s items before filtering", collection, len(collected))
            all_items.extend(collected)

        # Convert results into a DataFrame
        records = []
        for item in all_items:
            props = item.properties
            logger.debug("Evaluating item %s (cloud %.2f)", item.id, props.get('eo:cloud_cover', float('nan')))

            # Cloud cover filter
            cloud_cover = props.get('eo:cloud_cover', 100)
            if cloud_cover > max_cc:
                logger.debug("Skipping item %s: cloud cover %.2f exceeds threshold %s", item.id, cloud_cover, max_cc)
                continue

            nir_asset = item.assets.get('B8A') or item.assets.get('B05')
            red_asset = item.assets.get('B04')

            nir_url = getattr(nir_asset, 'href', None)
            red_url = getattr(red_asset, 'href', None)
            if not nir_url or not red_url:
                logger.debug("Skipping item %s: missing required bands (red=%s, nir=%s)", item.id, bool(red_url), bool(nir_url))
                continue

            records.append({
                "id": item.id,
                "datetime": pd.to_datetime(props['datetime']),
                "cloud_cover": float(cloud_cover),
                "collection": item.collection_id,
                "nir_url": nir_url,
                "red_url": red_url
            })
            logger.debug("Kept item %s (collection=%s)", item.id, item.collection_id)

        df = pd.DataFrame(records)
        logger.info("search_hls_data: %s items after filtering", len(df))
        if not df.empty:
            df = df.sort_values("datetime")
        store_stac_cache(cache_path, records)
        logger.debug("search_hls_data: cached %s items at %s", len(df), cache_path.name)
        return df

    except Exception as e:
        logger.exception("search_hls_data failed")
        st.error(f"Search error: {e}")
        return pd.DataFrame()

def calculate_ndvi_from_urls(red_url: str, nir_url: str, bbox: List[float],
                             token: str) -> Tuple[np.ndarray, float]:
    """Compute NDVI from two COG asset URLs"""

    logger.info(
        "calculate_ndvi_from_urls: red_url=%s nir_url=%s bbox=%s token_provided=%s",
        red_url,
        nir_url,
        bbox,
        bool(token)
    )

    try:
        bbox = normalize_bbox(bbox)
    except ValueError:
        logger.exception("NDVI calculation received invalid bbox")
        st.warning("NDVI calculation error: invalid bounding box")
        return None, None

    cache_path = get_ndvi_cache_path(red_url, nir_url, bbox)

    if cache_path.exists():
        try:
            with np.load(cache_path, allow_pickle=False) as cached:
                ndvi_data = cached["ndvi"]
                mask = cached["mask"]
                mean_ndvi = float(cached["mean"].item())
            ndvi = np.ma.array(ndvi_data, mask=mask)
            logger.debug("Loaded NDVI from cache for %s", cache_path.name)
            return ndvi, mean_ndvi
        except Exception:
            logger.exception("Failed to load NDVI cache from %s", cache_path)
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass

    try:
        env_kwargs: dict[str, object] = {}
        session = None
        if token:
            env_kwargs["GDAL_HTTP_HEADERS"] = f"Authorization: Bearer {token}"
            env_kwargs["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
            env_kwargs["GDAL_HTTP_MULTIRANGE"] = "YES"
            logger.debug("Attempting to create AWSSession for provided NASA token")
            if AWSSession is not None:
                try:
                    session = AWSSession(
                        aws_access_key_id="",
                        aws_secret_access_key="",
                        aws_session_token=token
                    )
                    logger.debug("AWSSession created: %s", session)
                except AttributeError:
                    logger.warning("boto3 is not available; falling back to GDAL HTTP headers only.")
                except Exception:
                    logger.exception("Failed to create AWSSession; continuing with GDAL HTTP headers")
                else:
                    env_kwargs["session"] = session
            else:
                logger.debug("AWSSession class unavailable; using GDAL HTTP headers only.")
        else:
            logger.debug("No NASA token supplied; using default rasterio session")

        def _window_from_bbox(src_obj: rasterio.io.DatasetReader):
            try:
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326",
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
                    return None, None
                red = red_src.read(1, window=red_window, masked=True)
                logger.debug("Read red band with shape %s", getattr(red, 'shape', None))

            logger.debug("Opening NIR band %s", nir_url)
            with rasterio.open(nir_url) as nir_src:
                nir_window = _window_from_bbox(nir_src)
                if nir_window is None:
                    return None, None
                nir = nir_src.read(1, window=nir_window, masked=True)
                logger.debug("Read NIR band with shape %s", getattr(nir, 'shape', None))

        if red.size == 0 or nir.size == 0:
            logger.warning(
                "AOI read returned empty arrays (red=%s, nir=%s)",
                red.size,
                nir.size
            )
            return None, None

        if red.shape != nir.shape:
            logger.warning(
                "Band windows differ in shape for %s vs %s: %s vs %s",
                red_url,
                nir_url,
                red.shape,
                nir.shape
            )
            return None, None

        red_data = red.astype("float32")
        nir_data = nir.astype("float32")

        with np.errstate(divide='ignore', invalid='ignore'):
            ndvi = (nir_data - red_data) / (nir_data + red_data)

        combined_mask = np.ma.getmaskarray(red) | np.ma.getmaskarray(nir)
        ndvi = np.ma.array(ndvi, mask=combined_mask)
        if ndvi.count() == 0:
            logger.warning("NDVI computation has no valid pixels for %s", red_url)
            return None, None

        mean_ndvi = float(ndvi.mean())
        logger.info("calculate_ndvi_from_urls: mean NDVI=%.4f", mean_ndvi)

        try:
            ndvi_to_store = ndvi.filled(np.nan).astype("float32")
            mask_to_store = np.ma.getmaskarray(ndvi)
            np.savez_compressed(
                cache_path,
                ndvi=ndvi_to_store,
                mask=mask_to_store,
                mean=np.array([mean_ndvi], dtype="float32")
            )
            logger.debug("Cached NDVI result at %s", cache_path)
        except Exception:
            logger.exception("Failed to persist NDVI cache at %s", cache_path)

        return ndvi, mean_ndvi

    except Exception as e:
        logger.exception("NDVI calculation failed")
        st.warning(f"NDVI calculation error: {e}")
        return None, None




def compute_ndvi_for_row(row: Tuple, bbox: List[float], token: str) -> Dict[str, Any]:
    if hasattr(row, "_asdict"):
        data = row._asdict()
    elif isinstance(row, dict):
        data = row
    else:
        keys = ["id", "datetime", "cloud_cover", "collection", "nir_url", "red_url"]
        data = {}
        for idx, key in enumerate(keys):
            if isinstance(row, (list, tuple)) and idx < len(row):
                data[key] = row[idx]

    scene_id = data.get("id")
    red_url = data.get("red_url")
    nir_url = data.get("nir_url")

    if not red_url or not nir_url:
        logger.debug("Skipping scene %s due to missing band URLs", scene_id)
        return {}

    logger.debug("Submitting NDVI task for scene=%s", scene_id)

    _, mean_ndvi = calculate_ndvi_from_urls(red_url, nir_url, bbox, token)
    if mean_ndvi is None:
        return {}

    return {
        "date": data.get("datetime"),
        "ndvi": mean_ndvi,
        "cloud_cover": data.get("cloud_cover"),
        "collection": data.get("collection"),
    }
@st.cache_data(ttl=3600)
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
                if row_tuples:
                    worker = partial(compute_ndvi_for_row, bbox=bbox, token=earthdata_token)
                    max_workers = min(8, len(row_tuples))
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
                                status_text.text(
                                    f"Processing {completed}/{len(row_tuples)}: {df.iloc[idx]['datetime'].strftime('%Y-%m-%d')}"
                                )
                                progress_bar.progress(completed / len(row_tuples))
                    except Exception:
                        logger.exception("Parallel NDVI processing failed; falling back to sequential execution")
                        results = []

                    if not results:
                        logger.info("Parallel NDVI returned no results; retrying sequential execution")
                        progress_bar.progress(0.0)
                        for idx, row in enumerate(row_tuples):
                            status_text.text(
                                f"Processing {idx + 1}/{len(row_tuples)}: {df.iloc[idx]['datetime'].strftime('%Y-%m-%d')}"
                            )
                            result = worker(row)
                            if result:
                                results.append(result)
                            progress_bar.progress((idx + 1) / len(row_tuples))

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
                            y=ndvi_df['ndvi'],
                            mode="lines+markers",
                            name="NDVI",
                            line=dict(color="green", width=2),
                            marker=dict(size=8),
                            hovertemplate="<b>Date:</b> %{x}<br><b>NDVI:</b> %{y:.3f}<extra></extra>",
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
                        st.metric("Mean NDVI", f"{ndvi_df['ndvi'].mean():.3f}")
                    with col2:
                        st.metric("Max NDVI", f"{ndvi_df['ndvi'].max():.3f}")
                    with col3:
                        st.metric("Min NDVI", f"{ndvi_df['ndvi'].min():.3f}")
                    with col4:
                        st.metric("Std. dev.", f"{ndvi_df['ndvi'].std():.3f}")

                    if ndvi_df['ndvi'].min() < 0:
                        st.info("Negative NDVI values typically indicate open water, clouds, or other non-vegetation surfaces within the AOI.")

                    mean_ndvi = ndvi_df['ndvi'].mean()
                    if mean_ndvi < 0.2:
                        st.error("**Severely stressed potatoes** - bare soil, standing water, or senescing vines")
                    elif mean_ndvi < 0.4:
                        st.warning("**Early canopy development** - emergence or sparse foliage; monitor inputs closely")
                    elif mean_ndvi < 0.6:
                        st.success("**Healthy potato canopy** - vigorous vegetative growth and photosynthesis")
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
    ### Welcome to Potato Crop Monitor!

    **What you can do with this app:**
    - Retrieve HLS (Harmonized Landsat Sentinel-2) imagery at 30 m resolution
    - Analyse NDVI time series to track potato canopy vigor
    - Compare management zones across multiple observation dates

    **To get started:**
    1. Request a free token at https://urs.earthdata.nasa.gov/
    2. Provide the area of interest in the sidebar
    3. Choose the time range
    4. Select "Search scenes"

    **NDVI interpretation for potatoes:**
    - < 0.2: Bare soil, standing water, or senescing vines
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
    <p>Potato Crop Monitor v1.0 | Data source: NASA HLS v2.0 | Built with Streamlit</p>
    <p><small>Data provided by NASA LP DAAC via the CMR-STAC API</small></p>
</div>
""", unsafe_allow_html=True)
