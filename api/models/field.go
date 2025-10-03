package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// FieldStatus is a soft enum stored as string in MongoDB.
type FieldStatus string

const (
	FieldStatusProcessing FieldStatus = "processing"
	FieldStatusReady      FieldStatus = "ready"
	FieldStatusError      FieldStatus = "error"
)

// Field — main field card with geometry, metadata and daily history.
type Field struct {
	ID        primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	OwnerID   primitive.ObjectID `bson:"ownerId"      json:"ownerId"`
	Name      string             `bson:"name"         json:"name"`
	Geometry  map[string]any     `bson:"geometry"     json:"geometry"` // GeoJSON Polygon/MultiPolygon
	CreatedAt time.Time          `bson:"createdAt"    json:"createdAt"`

	// Visual and lifecycle
	Photo        string      `bson:"photo,omitempty"  json:"photo,omitempty"`  // URL to field avatar/photo
	Status       FieldStatus `bson:"status,omitempty" json:"status,omitempty"` // processing | ready | error
	ErrorMessage string      `bson:"errorMessage,omitempty" json:"errorMessage,omitempty"`

	// Farmer-facing metadata
	Meta *FieldMeta `bson:"meta,omitempty" json:"meta,omitempty"`

	// Daily history (sparse). Each item is one day.
	History []HistoryDaily `bson:"history,omitempty" json:"history,omitempty"`

	// Farmer-provided yields by year
	Yields []YieldEntry `bson:"yields,omitempty" json:"yields,omitempty"`

	// Forecast for the current season
	Forecast *FieldForecast `bson:"forecast,omitempty" json:"forecast,omitempty"`

	// Phenology baseline and current-season deltas (optional, can be filled by a processor)
	Norm    *PhenologyNorm `bson:"norm,omitempty"    json:"norm,omitempty"`
	Current *PhenologyYear `bson:"current,omitempty" json:"current,omitempty"`
}

// FieldMeta — field metadata provided/edited by the farmer.
type FieldMeta struct {
	AreaHa *float64 `bson:"areaHa,omitempty" json:"areaHa,omitempty"` // area in hectares
	Notes  string   `bson:"notes,omitempty"  json:"notes,omitempty"`
	Crop   string   `bson:"crop,omitempty"   json:"crop,omitempty"` // crop type - wheat | corn | soybeans | etc.
}

// HistoryDaily — one daily observation. Field names match the incoming data exactly.
type HistoryDaily struct {
	Date            time.Time `bson:"date"                   json:"date"` // ISO date
	NDVI            *float64  `bson:"ndvi,omitempty"         json:"ndvi,omitempty"`
	CloudCover      *int      `bson:"cloud_cover,omitempty"  json:"cloud_cover,omitempty"` // HLS cloud mask (0..100?)
	Collection      string    `bson:"collection,omitempty"   json:"collection,omitempty"`  // e.g., "HLSS30_2.0"
	TemperatureDegC *float64  `bson:"temperature_deg_c,omitempty" json:"temperature_deg_c,omitempty"`
	HumidityPct     *float64  `bson:"humidity_pct,omitempty"      json:"humidity_pct,omitempty"`
	CloudcoverPct   *float64  `bson:"cloudcover_pct,omitempty"    json:"cloudcover_pct,omitempty"` // weather cloud cover
	WindSpeedMps    *float64  `bson:"wind_speed_mps,omitempty"    json:"wind_speed_mps,omitempty"`
	ClarityPct      *float64  `bson:"clarity_pct,omitempty"       json:"clarity_pct,omitempty"` // clear-sky fraction if provided
}

// ---- Optional analytics types (kept for phenology/forecast) ----

type PhenologyYear struct {
	SOS       *time.Time          `bson:"sos,omitempty"      json:"sos,omitempty"`        // Start of Season
	PeakDate  *time.Time          `bson:"peakDate,omitempty" json:"peakDate,omitempty"`   // NDVI peak date
	EOS       *time.Time          `bson:"eos,omitempty"      json:"eos,omitempty"`        // End of Season
	LOS       *int                `bson:"los,omitempty"      json:"los,omitempty"`        // Length Of Season (days)
	PeakNDVI  *float64            `bson:"peakNdvi,omitempty" json:"peakNdvi,omitempty"`   // NDVI peak value
	Deviation *PhenologyDeviation `bson:"deviation,omitempty" json:"deviation,omitempty"` // deltas vs baseline
}

type PhenologyDeviation struct {
	DaysSOS  *int     `bson:"daysSOS,omitempty"  json:"daysSOS,omitempty"`
	DaysPeak *int     `bson:"daysPeak,omitempty" json:"daysPeak,omitempty"`
	DaysEOS  *int     `bson:"daysEOS,omitempty"  json:"daysEOS,omitempty"`
	DaysLOS  *int     `bson:"daysLOS,omitempty"  json:"daysLOS,omitempty"`
	PeakNDVI *float64 `bson:"peakNdvi,omitempty" json:"peakNdvi,omitempty"`
}

type PhenologyNorm struct {
	SOSAvgDOY   *int     `bson:"sosAvgDOY,omitempty"   json:"sosAvgDOY,omitempty"`
	PeakAvgDOY  *int     `bson:"peakAvgDOY,omitempty"  json:"peakAvgDOY,omitempty"`
	EOSAvgDOY   *int     `bson:"eosAvgDOY,omitempty"   json:"eosAvgDOY,omitempty"`
	LOSAvgDays  *int     `bson:"losAvgDays,omitempty"  json:"losAvgDays,omitempty"`
	PeakNDVIAvg *float64 `bson:"peakNdviAvg,omitempty" json:"peakNdviAvg,omitempty"`
}

type YieldEntry struct {
	Year     int      `bson:"year"               json:"year"`
	ValueTph *float64 `bson:"valueTph,omitempty" json:"valueTph,omitempty"` // tons/ha
	Unit     string   `bson:"unit,omitempty"     json:"unit,omitempty"`     // default "t/ha"
	Notes    string   `bson:"notes,omitempty"    json:"notes,omitempty"`
}

type FieldForecast struct {
	Year       int        `bson:"year"                 json:"year"`
	YieldTph   *float64   `bson:"yieldTph,omitempty"   json:"yieldTph,omitempty"`
	NDVIPeak   *float64   `bson:"ndviPeak,omitempty"   json:"ndviPeak,omitempty"`
	NDVIPeakAt *time.Time `bson:"ndviPeakAt,omitempty" json:"ndviPeakAt,omitempty"`
	Model      string     `bson:"model,omitempty"      json:"model,omitempty"`      // model id/version
	Confidence *float64   `bson:"confidence,omitempty" json:"confidence,omitempty"` // 0..1
	UpdatedAt  time.Time  `bson:"updatedAt"            json:"updatedAt"`
}
