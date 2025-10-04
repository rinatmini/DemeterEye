package models

import "time"

// ReportStatus mirrors processor operation states.
type ReportStatus string

const (
	ReportStatusProcessing ReportStatus = "processing"
	ReportStatusReady      ReportStatus = "ready"
	ReportStatusError      ReportStatus = "error"
)

// Report mirrors documents persisted by the processor into the "reports" collection.
// Field names and tags match processor persistence exactly.
type Report struct {
	OperationID  string          `bson:"operation_id"              json:"operation_id"`
	Status       ReportStatus    `bson:"status"                    json:"status"`     // processing | ready | error
	CreatedAt    time.Time       `bson:"created_at"                json:"created_at"` // naive UTC in Mongo
	UpdatedAt    time.Time       `bson:"updated_at"                json:"updated_at"` // naive UTC in Mongo
	YieldType    string          `bson:"yieldType"                 json:"yieldType"`  // e.g., "Potato"
	FieldID      string          `bson:"fieldId,omitempty"         json:"fieldId,omitempty"`
	GeoJSON      map[string]any  `bson:"geojson,omitempty"         json:"geojson,omitempty"` // processor may store object/string; we normalize to object
	History      []ReportDaily   `bson:"history,omitempty"         json:"history,omitempty"`
	Forecast     *ReportForecast `bson:"forecast,omitempty"        json:"forecast,omitempty"`
	ErrorMessage string          `bson:"errorMessage,omitempty"    json:"errorMessage,omitempty"`
}

// ReportDaily — one daily observation as written by the processor.
type ReportDaily struct {
	Date           time.Time `bson:"date"                   json:"date"` // RFC3339 stored as time in Go
	NDVI           *float64  `bson:"ndvi,omitempty"         json:"ndvi,omitempty"`
	CloudCover     *int      `bson:"cloud_cover,omitempty"  json:"cloud_cover,omitempty"` // HLS cloud mask (0..100?)
	Collection     string    `bson:"collection,omitempty"   json:"collection,omitempty"`  // e.g., "HLSS30_2.0"
	TemperatureDeg *float64  `bson:"temperature_deg_c,omitempty" json:"temperature_deg_c,omitempty"`
	HumidityPct    *float64  `bson:"humidity_pct,omitempty"      json:"humidity_pct,omitempty"`
	CloudcoverPct  *float64  `bson:"cloudcover_pct,omitempty"    json:"cloudcover_pct,omitempty"`
	WindSpeedMps   *float64  `bson:"wind_speed_mps,omitempty"    json:"wind_speed_mps,omitempty"`
	ClarityPct     *float64  `bson:"clarity_pct,omitempty"       json:"clarity_pct,omitempty"`

	Type int `bson:"type,omitempty" json:"type,omitempty"` // 0: actual, 1: forecast
}

// ReportForecast — forecast section produced by the processor.
type ReportForecast struct {
	Year       int        `bson:"year"                 json:"year"`
	YieldTph   *float64   `bson:"yieldTph,omitempty"   json:"yieldTph,omitempty"`
	NDVIPeak   *float64   `bson:"ndviPeak,omitempty"   json:"ndviPeak,omitempty"`
	NDVIPeakAt *time.Time `bson:"ndviPeakAt,omitempty" json:"ndviPeakAt,omitempty"`
	Model      string     `bson:"model,omitempty"      json:"model,omitempty"`
	Confidence *float64   `bson:"confidence,omitempty" json:"confidence,omitempty"`
}
