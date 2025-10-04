package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// Field — main field card with geometry and farmer-provided metadata.
// Processor-derived time series and forecasts are NOT stored here anymore.
// They live in the "reports" collection (see models/report.go).
type Field struct {
	ID        primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	OwnerID   primitive.ObjectID `bson:"ownerId"      json:"ownerId"`
	Name      string             `bson:"name"         json:"name"`
	Geometry  map[string]any     `bson:"geometry"     json:"geometry"` // GeoJSON Polygon/MultiPolygon
	CreatedAt time.Time          `bson:"createdAt"    json:"createdAt"`

	// Injected-only (NOT stored in Mongo):
	Status   ReportStatus    `bson:"-" json:"status"`
	Forecast *ReportForecast `bson:"-" json:"forecast,omitempty"`
	History  []ReportDaily   `bson:"-" json:"history,omitempty"`

	// Visual
	Photo string `bson:"photo,omitempty" json:"photo,omitempty"` // URL to field avatar/photo

	// Farmer-facing metadata
	Meta *FieldMeta `bson:"meta,omitempty" json:"meta,omitempty"`

	// Farmer-provided yields by year (stays with Field)
	Yields []YieldEntry `bson:"yields,omitempty" json:"yields,omitempty"`

	// Optional analytics for phenology (if you still want to keep them at Field level)
	Norm    *PhenologyNorm `bson:"norm,omitempty"    json:"norm,omitempty"`
	Current *PhenologyYear `bson:"current,omitempty" json:"current,omitempty"`

	// Error message is kept here only for UI notes not related to processor runs.
	// If it was used exclusively for processor status/errors, consider removing it.
	ErrorMessage string `bson:"errorMessage,omitempty" json:"errorMessage,omitempty"`
}

type FieldMeta struct {
	AreaHa *float64 `bson:"areaHa,omitempty" json:"areaHa,omitempty"` // area in hectares
	Notes  string   `bson:"notes,omitempty"  json:"notes,omitempty"`
	Crop   string   `bson:"crop,omitempty"   json:"crop,omitempty"` // crop type - wheat | corn | soybeans | etc.
}

type YieldEntry struct {
	Year     int      `bson:"year"               json:"year"`
	ValueTph *float64 `bson:"valueTph,omitempty" json:"valueTph,omitempty"` // tons/ha
	Unit     string   `bson:"unit,omitempty"     json:"unit,omitempty"`     // default "t/ha"
	Notes    string   `bson:"notes,omitempty"    json:"notes,omitempty"`
}

// ---- Optional analytics types (kept for phenology UI) ----

type PhenologyYear struct {
	SOS       *time.Time          `bson:"sos,omitempty"      json:"sos,omitempty"`      // Start of Season
	PeakDate  *time.Time          `bson:"peakDate,omitempty" json:"peakDate,omitempty"` // NDVI peak date
	EOS       *time.Time          `bson:"eos,omitempty"      json:"eos,omitempty"`      // End of Season
	LOS       *int                `bson:"los,omitempty"      json:"los,omitempty"`      // Length Of Season (days)
	PeakNDVI  *float64            `bson:"peakNdvi,omitempty" json:"peakNdvi,omitempty"` // NDVI peak value
	Deviation *PhenologyDeviation `bson:"deviation,omitempty" json:"deviation,omitempty"`
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
