# Chipnik Monitor
![](media/logo.png)
Chipnik Monitor provides both a Streamlit dashboard and a FastAPI service for analysing Harmonized Landsat Sentinel (HLS) data and crop health metrics.

## Requirements
- Python 3.10 or newer
- GDAL/rasterio prerequisites (varies by OS)
- Access credentials for NASA Earthdata and a MongoDB database

## Installation
1. Optional: create and activate a virtual environment.
2. Install dependencies from the project directory:
   ```bash
   pip install -r requirements.txt
   ```
3. Populate `.env` in `chipnik_monitor/` with the following keys:
   - `EARTHDATA_BEARER_TOKEN`
   - `MONGO_URI`
   - `MONGO_DB`
   - `DAYS_BACK_LIMIT` (optional, defaults to 2000)

## Running the Streamlit App
From the `chipnik_monitor/` directory run:
```bash
streamlit run chipnik_monitor.py
```

## Running the FastAPI Service
From the same directory start Uvicorn:
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
The interactive docs are available at `http://127.0.0.1:8000/docs` once the server is up.

## API Examples
Submit a report request:
```bash
curl -X POST "http://127.0.0.1:8000/reports" \
     -H "Content-Type: application/json" \
     -d '{
          "geojson": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "coordinates": [
                    [
                        [
                            -113.7370959660704,
                            42.56966951323284
                        ],
                        [
                            -113.58840072392796,
                            42.67550031213827
                        ],
                        [
                            -113.59032588587989,
                            42.7770471032151
                        ],
                        [
                            -113.8917929547514,
                            42.84287717991728
                        ],
                        [
                            -113.90279587828836,
                            42.56892463282091
                        ],
                        [
                            -113.7370959660704,
                            42.56966951323284
                        ]
                    ]
                ],
                "type": "Polygon"
            }
        },
          "yieldType": "Potato"
        }'
```

Check operation status/results:
```bash
curl "http://127.0.0.1:8000/reports/<operation_id>"
```
