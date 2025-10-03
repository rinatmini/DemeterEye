// src/components/FieldDrawMap.jsx
import React, { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  FeatureGroup,
  LayersControl,
  LayerGroup,
} from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import L from "leaflet";

export default function FieldDrawMap({
  value,
  onChange,
  initialCenter = [47.4554598, -122.2208032],
  initialZoom = 14,
  rememberView = true,
  fitToGeometry = true,
  className = "w-full h-[70vh] rounded-xl border",
  mode = "draw",
}) {
  const fgRef = useRef(null);
  const mapRef = useRef(null);
  const LSKEY = "demetereye.mapView";

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.clearLayers();
    if (value) {
      const gj = L.geoJSON({ type: "Feature", geometry: value });
      gj.eachLayer((l) => fg.addLayer(l));
      if (fitToGeometry && mapRef.current) {
        mapRef.current.fitBounds(gj.getBounds(), { padding: [24, 24] });
      }
    }
  }, [value, fitToGeometry]);

  const onMapCreated = (map) => {
    mapRef.current = map;

    let center = initialCenter,
      zoom = initialZoom;
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

  const FieldDrawMapOptions = mode !== "draw" && {
    edit: false,
    remove: false,
    selectedPathOptions: { maintainColor: true },
  };

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

      <FeatureGroup ref={fgRef}>
        <EditControl
          position="topleft"
          draw={
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
                }
          }
          onCreated={onCreated}
          onEdited={onEdited}
          onDeleted={onDeleted}
          {...FieldDrawMapOptions}
        />
      </FeatureGroup>
    </MapContainer>
  );
}
