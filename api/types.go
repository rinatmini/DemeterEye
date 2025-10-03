package main

import (
	"demetereye/models"
	"encoding/json"
)

// Request/response DTOs. Keep them minimal and explicit.

type registerReq struct {
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

type loginReq struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type tokenResp struct {
	Token string `json:"token"`
}

type createFieldReq struct {
	Name     string          `json:"name"`
	Geometry json.RawMessage `json:"geometry"`         // GeoJSON Polygon/MultiPolygon
	AreaHa   *float64        `json:"areaHa,omitempty"` // stored under meta.areaHa
	Notes    string          `json:"notes,omitempty"`
	Crop     string          `json:"crop,omitempty"`
	Photo    string          `json:"photo,omitempty"`

	Yields []YieldEntry `json:"yields,omitempty"`
}

type YieldEntry struct {
	Year     int      `json:"year"`
	ValueTph *float64 `json:"valueTph,omitempty"`
	Unit     string   `json:"unit,omitempty"`
	Notes    string   `json:"notes,omitempty"`
}

// ingestFieldReq is used by the processor to submit daily history and an optional forecast.
type ingestFieldReq struct {
	// Daily history rows to upsert by date (matching models.HistoryDaily fields).
	History []models.HistoryDaily `json:"history"`

	// Optional forecast to set for the current season. UpdatedAt is set server-side.
	Forecast *models.FieldForecast `json:"forecast,omitempty"`
}

// Payload we send to Processor /reports
type processorReportReq struct {
	GeoJSON   json.RawMessage `json:"geojson"`             // entire Feature or Geometry
	YieldType string          `json:"yieldType,omitempty"` // e.g., "Potato"
	Yields    []YieldEntry    `json:"yields,omitempty"`
}

type processorReportResp struct {
	OperationID string `json:"operation_id,omitempty"` // if processor returns a task id
	Status      string `json:"status,omitempty"`       // e.g., "queued"
}
