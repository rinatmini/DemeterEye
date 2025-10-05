// src/components/FieldDrawMap.jsx
import { useEffect, useRef, useState, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  FeatureGroup,
  LayersControl,
  LayerGroup,
  GeoJSON,
  Pane,
} from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import L from "leaflet";

export default function FieldDrawMap({
  value, // GeoJSON geometry: Polygon | MultiPolygon
  onChange,
  initialCenter = [47.4554598, -122.2208032],
  initialZoom = 14,
  rememberView = true,
  fitToGeometry = true,
  className = "w-full h-[70vh] rounded-xl border",
  mode = "view", // "view" | "edit" | "draw"
}) {
  const fgRef = useRef(null);
  const mapRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const LSKEY = "demetereye.mapView";

  // Seed FG with current geometry and fit bounds when map is ready
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;

    fg.clearLayers();
    if (value) {
      const gj = L.geoJSON({ type: "Feature", geometry: value });
      gj.eachLayer((l) => fg.addLayer(l));

      if (fitToGeometry && mapRef.current) {
        const b = gj.getBounds();
        if (b.isValid()) {
          mapRef.current.fitBounds(b, { padding: [24, 24] });
        }
      }
    }
  }, [value, fitToGeometry, mapReady]);

  const onMapCreated = (map) => {
    mapRef.current = map;

    // restore saved view; actual fit to geometry will happen in the effect above
    let center = initialCenter;
    let zoom = initialZoom;

    if (rememberView) {
      try {
        const saved = JSON.parse(localStorage.getItem(LSKEY) || "null");
        if (saved?.center && typeof saved.zoom === "number") {
          center = saved.center;
          zoom = saved.zoom;
        }
      } catch {}
    }
    map.setView(center, zoom);

    if (rememberView) {
      map.on("moveend", () => {
        const c = map.getCenter();
        localStorage.setItem(
          LSKEY,
          JSON.stringify({ center: [c.lat, c.lng], zoom: map.getZoom() })
        );
      });
    }

    // Fix layout race on first paint
    setTimeout(() => map.invalidateSize(), 0);
    setMapReady(true);
  };

  const reportFromGroup = () => {
    const fg = fgRef.current;
    if (!fg) return onChange?.(null);
    const layers = fg.getLayers();
    if (!layers.length) return onChange?.(null);
    onChange?.(layers[0].toGeoJSON().geometry);
  };

  const onCreated = (e) => {
    fgRef.current.clearLayers();
    fgRef.current.addLayer(e.layer);
    reportFromGroup();
  };
  const onEdited = () => reportFromGroup();
  const onDeleted = () => onChange?.(null);

  // Toolbar options by mode
  const editControlExtra =
    mode === "view"
      ? {
          edit: false,
          remove: false,
          selectedPathOptions: { maintainColor: true },
        }
      : { selectedPathOptions: { maintainColor: true } };

  const drawOptions =
    mode === "draw"
      ? {
          polygon: {
            allowIntersection: false,
            showArea: true,
            shapeOptions: { color: "#10b981" },
          },
          marker: false,
          circle: false,
          circlemarker: false,
          rectangle: false,
          polyline: false,
        }
      : {
          polygon: false,
          marker: false,
          circle: false,
          circlemarker: false,
          rectangle: false,
          polyline: false,
        };

  // Force re-render of GeoJSON overlay when geometry changes
  const geojsonKey = useMemo(
    () => (value ? JSON.stringify(value).slice(0, 200) : "empty"),
    [value]
  );

  return (
    <MapContainer
      center={initialCenter}
      zoom={initialZoom}
      whenCreated={onMapCreated}
      className={className}
      scrollWheelZoom
    >
      <LayersControl position="topright">
        <LayersControl.BaseLayer name="Streets (OSM)">
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        </LayersControl.BaseLayer>

        <LayersControl.BaseLayer name="Satellite (Esri)" checked>
          <LayerGroup>
            <TileLayer
              attribution="Tiles &copy; Esri — Sources: Esri, Maxar, Earthstar Geographics, USDA, USGS, AeroGRID, IGN, and the GIS User Community"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
            <TileLayer
              url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              opacity={0.8}
            />
          </LayerGroup>
        </LayersControl.BaseLayer>
      </LayersControl>

      {/* Always draw current geometry on top (view & edit) */}
      {value && (
        <Pane name="vector-top" style={{ zIndex: 650 }}>
          <GeoJSON
            key={geojsonKey}
            data={{ type: "Feature", geometry: value }}
            style={{ color: "#10b981", weight: 2, fillOpacity: 0.2 }}
          />
        </Pane>
      )}

      <FeatureGroup ref={fgRef}>
        <EditControl
          position="topleft"
          draw={drawOptions}
          onCreated={onCreated}
          onEdited={onEdited}
          onDeleted={onDeleted}
          {...editControlExtra}
        />
      </FeatureGroup>
    </MapContainer>
  );
}
