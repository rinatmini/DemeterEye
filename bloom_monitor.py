import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from pystac_client import Client
import rasterio
from rasterio.warp import transform_bounds
try:
    from rasterio.session import AWSSession  # type: ignore
except ImportError:
    AWSSession = None  # type: ignore
from shapely.geometry import shape
from pathlib import Path
import json
import logging
import math
import os
from typing import List, Tuple
import warnings
warnings.filterwarnings("ignore")
# Configure logger
logger = logging.getLogger('bloom_monitor')
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

# Page configuration
st.set_page_config(
    page_title="Bloom Monitor - HLS Analytics",
    page_icon=":seedling:",
    layout="wide"
)

# Page title
st.title("Bloom Monitor - HLS NDVI Analysis")
st.markdown("**Monitor algal blooms with HLS (Harmonized Landsat Sentinel-2) imagery**")

# Sidebar controls

earthdata_token = load_token_from_env()
bbox = None
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

    input_method = st.radio(
        "Input method",
        ["Corner coordinates", "Center + radius", "GeoJSON"]
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
        except ValueError as exc:
            bbox_error = str(exc)
            bbox = None
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
        except ValueError as exc:
            bbox_error = str(exc)
            bbox = None
            st.error(bbox_error)

    else:  # GeoJSON
        geojson_input = st.text_area(
            "Paste a GeoJSON polygon",
            height=150,
            help="Polygon geometry or Feature with Polygon geometry"
        )
        if geojson_input:
            try:
                geojson_data = json.loads(geojson_input)
                if geojson_data.get('type') == 'Feature':
                    geom = shape(geojson_data['geometry'])
                else:
                    geom = shape(geojson_data)
                raw_bbox = list(geom.bounds)
                bbox = normalize_bbox(raw_bbox)
            except ValueError as exc:
                bbox_error = str(exc)
                bbox = None
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
        max_value=365,
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
                max_items=100
            )
            items = list(search.items())
            logger.debug("Collection %s returned %s items before filtering", collection, len(items))
            all_items.extend(items)

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
                "cloud_cover": cloud_cover,
                "collection": item.collection_id,
                "nir_url": nir_url,
                "red_url": red_url,
                "item": item
            })
            logger.debug("Kept item %s (collection=%s)", item.id, item.collection_id)

        df = pd.DataFrame(records)
        logger.info("search_hls_data: %s items after filtering", len(df))
        if not df.empty:
            df = df.sort_values("datetime")
        return df

    except Exception as e:
        logger.exception("search_hls_data failed")
        st.error(f"Search error: {e}")
        return pd.DataFrame()


def calculate_ndvi_from_urls(red_url: str, nir_url: str, bbox: List[float],
                             token: str) -> Tuple[np.ndarray, float]:
    """Compute NDVI from two COG asset URLs"""

    logger.info("calculate_ndvi_from_urls: red_url=%s nir_url=%s bbox=%s token_provided=%s", red_url, nir_url, bbox, bool(token))

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

        # Read both bands inside a single rasterio environment
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
        return ndvi, mean_ndvi

    except Exception as e:
        logger.exception("NDVI calculation failed")
        st.warning(f"NDVI calculation error: {e}")
        return None, None



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
        with st.spinner("Searching HLS scenes..."):
            # Run the search
            df = search_hls_data(
                bbox=bbox,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
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

                # Calculate NDVI metrics per scene
                ndvi_data = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, row in df.iterrows():
                    status_text.text(
                        f"Processing {idx + 1}/{len(df)}: {row['datetime'].strftime('%Y-%m-%d')}"
                    )
                    logger.debug("Row %s: scene=%s red=%s nir=%s", idx, row.get('id'), row.get('red_url'), row.get('nir_url'))

                    if row["red_url"] and row["nir_url"]:
                        _, mean_ndvi = calculate_ndvi_from_urls(
                            row["red_url"],
                            row["nir_url"],
                            bbox,
                            earthdata_token
                        )
                        if mean_ndvi is not None:
                            ndvi_data.append({
                                "date": row["datetime"],
                                "ndvi": mean_ndvi,
                                "cloud_cover": row["cloud_cover"],
                                "collection": row["collection"]
                            })
                            logger.debug("Appended NDVI result for scene %s: %.4f", row.get('id'), mean_ndvi)
                        else:
                            logger.debug("NDVI computation returned None for scene %s", row.get('id'))
                    else:
                        logger.debug("Skipping scene %s due to missing band URLs", row.get('id'))

                    progress_bar.progress((idx + 1) / len(df))

                status_text.empty()
                progress_bar.empty()

                if ndvi_data:
                    ndvi_df = pd.DataFrame(ndvi_data)

                    # Time-series chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=ndvi_df["date"],
                        y=ndvi_df["ndvi"],
                        mode="lines+markers",
                        name="NDVI",
                        line=dict(color="green", width=2),
                        marker=dict(size=8),
                        hovertemplate="<b>Date:</b> %{x}<br><b>NDVI:</b> %{y:.3f}<extra></extra>"
                    ))

                    # Reference thresholds for interpretation
                    fig.add_hline(
                        y=0.3,
                        line_dash="dash",
                        line_color="orange",
                        annotation_text="Vegetation threshold"
                    )
                    fig.add_hline(
                        y=0.6,
                        line_dash="dash",
                        line_color="darkgreen",
                        annotation_text="Dense vegetation"
                    )

                    fig.update_layout(
                        title="NDVI time series",
                        xaxis_title="Date",
                        yaxis_title="NDVI",
                        hovermode="x unified",
                        height=500
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Summary statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Mean NDVI", f"{ndvi_df['ndvi'].mean():.3f}")
                    with col2:
                        st.metric("Max NDVI", f"{ndvi_df['ndvi'].max():.3f}")
                    with col3:
                        st.metric("Min NDVI", f"{ndvi_df['ndvi'].min():.3f}")
                    with col4:
                        st.metric("Std. dev.", f"{ndvi_df['ndvi'].std():.3f}")

                    # Interpretation
                    st.markdown("---")
                    st.subheader("Interpreting results")

                    mean_ndvi = ndvi_df['ndvi'].mean()
                    if mean_ndvi < 0.2:
                        st.info("**Low vegetation or water surface** - likely open water or minimal vegetation")
                    elif mean_ndvi < 0.4:
                        st.warning("**Moderate vegetation** - early signs of vegetation or bloom activity")
                    elif mean_ndvi < 0.6:
                        st.success("**Active vegetation** - likely active algal bloom")
                    else:
                        st.error("**Dense vegetation** - very high biomass, possible intense bloom")
                else:
                    st.error("Could not compute NDVI for the retrieved scenes")

            with tab2:
                st.subheader("AOI map")

                # Build a simple map around the AOI
                center_lat = (bbox[1] + bbox[3]) / 2
                center_lon = (bbox[0] + bbox[2]) / 2

                map_data = pd.DataFrame({"lat": [center_lat], "lon": [center_lon]})
                st.map(map_data, zoom=8)

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
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"hls_data_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )
else:
    # First-run instructions
    st.info("""
    ### Welcome to Bloom Monitor!

    **What you can do with this app:**
    - Retrieve HLS (Harmonized Landsat Sentinel-2) imagery at 30 m resolution
    - Analyse NDVI time series to monitor blooms
    - Visualise vegetation change over time

    **To get started:**
    1. Request a free token at https://urs.earthdata.nasa.gov/
    2. Provide the area of interest in the sidebar
    3. Choose the time range
    4. Select "Search scenes"

    **NDVI interpretation:**
    - < 0.2: Water, bare ground, or snow
    - 0.2-0.4: Sparse vegetation
    - 0.4-0.6: Moderate vegetation
    - > 0.6: Dense vegetation
    """)

    # Example AOIs
    st.markdown("### Sample AOIs to try")

    st.markdown("""
    **Default AOI - Lake Sammamish (WA, USA)**\n    - Center: 47.6046 deg N, -122.0926 deg W\n    - Suggested radius: 6 km\n    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Discovery Park (Seattle, WA, USA)**  
        Coastal bluffs and nearshore waters on Puget Sound
        - Center: 47.6658 deg N, -122.4386 deg W
        - Suggested radius: 5 km
        """)

    with col2:
        st.markdown("""
        **Deception Pass (WA, USA)**  
        Dynamic coastal waters with frequent bloom activity
        - Center: 48.4063 deg N, -122.6754 deg W
        - Suggested radius: 5 km
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Bloom Monitor v1.0 | Data source: NASA HLS v2.0 | Built with Streamlit</p>
    <p><small>Data provided by NASA LP DAAC via the CMR-STAC API</small></p>
</div>
""", unsafe_allow_html=True)

