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
  center = [50, 30],
  zoom = 12,
  className = "w-full h-[70vh] rounded-xl border",
}) {
  const fgRef = useRef(null);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.clearLayers();
    if (value) {
      const gj = L.geoJSON({ type: "Feature", geometry: value });
      gj.eachLayer((l) => fg.addLayer(l));
    }
  }, [value]);

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

  return (
    <MapContainer
      center={center}
      zoom={zoom}
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
          draw={{
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
          }}
          onCreated={onCreated}
          onEdited={onEdited}
          onDeleted={onDeleted}
        />
      </FeatureGroup>
    </MapContainer>
  );
}
