package main

import (
	"encoding/json"
	"time"
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

// Payload we send to Processor /reports
type processorReportReq struct {
	FieldID   string          `json:"fieldId"`             // field id
	GeoJSON   json.RawMessage `json:"geojson"`             // entire Feature or Geometry
	YieldType string          `json:"yieldType,omitempty"` // e.g., "Potato"
	Yields    []YieldEntry    `json:"yields,omitempty"`
}

type processorReportResp struct {
	OperationID string `json:"operation_id,omitempty"` // if processor returns a task id
	Status      string `json:"status,omitempty"`       // e.g., "queued"
}

type reportDoc struct {
	Status       string           `bson:"status"`
	CreatedAt    time.Time        `bson:"created_at"`
	UpdatedAt    time.Time        `bson:"updated_at"`
	YieldType    string           `bson:"yieldType"`
	FieldID      string           `bson:"fieldId"`
	History      []map[string]any `bson:"history"`
	Forecast     map[string]any   `bson:"forecast"`
	ErrorMessage *string          `bson:"errorMessage"`
}
