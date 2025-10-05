package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"log"
	"math"

	"demetereye/models"

	"github.com/go-chi/chi/v5"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo/options"
)

func toFloatPtr(v any) *float64 {
	switch t := v.(type) {
	case float64:
		return &t
	case float32:
		f := float64(t)
		return &f
	case int32:
		f := float64(t)
		return &f
	case int64:
		f := float64(t)
		return &f
	case int:
		f := float64(t)
		return &f
	default:
		return nil
	}
}

func toIntPtr(v any) *int {
	switch t := v.(type) {
	case int:
		return &t
	case int32:
		i := int(t)
		return &i
	case int64:
		i := int(t)
		return &i
	case float64:
		i := int(math.Round(t))
		return &i
	default:
		return nil
	}
}

func parseRFC3339Ptr(s any) *time.Time {
	str, ok := s.(string)
	if !ok || strings.TrimSpace(str) == "" {
		return nil
	}
	if dt, err := time.Parse(time.RFC3339, str); err == nil {
		return &dt
	}
	return nil
}

func enrichFieldWithLatestReport(ctx context.Context, a *App, f *models.Field) {
	var doc reportDoc
	// find the latest report for the field
	err := a.reports.FindOne(
		ctx,
		bson.M{"fieldId": f.ID.Hex()},
		options.FindOne().SetSort(bson.D{{Key: "updated_at", Value: -1}}),
	).Decode(&doc)
	if err != nil {
		return
	}

	switch doc.Status {
	case "processing":
		f.Status = models.ReportStatusProcessing
	case "ready":
		f.Status = models.ReportStatusReady
	case "error":
		f.Status = models.ReportStatusError
	}

	if len(doc.History) > 0 {
		h := make([]models.ReportDaily, 0, len(doc.History))
		for _, it := range doc.History {
			var d time.Time
			if ds, ok := it["date"].(string); ok {
				if dt, err := time.Parse(time.RFC3339, ds); err == nil {
					d = dt
				}
			}
			if d.IsZero() {
				continue
			}

			entry := models.ReportDaily{
				Date:           d,
				NDVI:           toFloatPtr(it["ndvi"]),
				CloudCover:     toIntPtr(it["cloud_cover"]),
				Collection:     strOrEmpty(it["collection"]),
				TemperatureDeg: toFloatPtr(it["temperature_deg_c"]),
				HumidityPct:    toFloatPtr(it["humidity_pct"]),
				CloudcoverPct:  toFloatPtr(it["cloudcover_pct"]),
				WindSpeedMps:   toFloatPtr(it["wind_speed_mps"]),
				ClarityPct:     toFloatPtr(it["clarity_pct"]),
			}

			// Populate point type for the UI safely: 0 = actual, 1 = forecast
			if tv, ok := it["type"]; ok && tv != nil {
				switch t := tv.(type) {
				case int:
					entry.Type = t
				case int32:
					entry.Type = int(t)
				case int64:
					entry.Type = int(t)
				case float64:
					entry.Type = int(math.Round(t))
				default:
					entry.Type = 0
				}
			} else if isFc, ok := it["isForecast"].(bool); ok && isFc {
				entry.Type = 1
			} else if isFc2, ok := it["isForcast"].(bool); ok && isFc2 {
				entry.Type = 1
			} else {
				entry.Type = 0
			}
			h = append(h, entry)
		}
		if len(h) > 0 {
			f.History = h
		}
	}

	if doc.Forecast != nil && len(doc.Forecast) > 0 {
		ff := &models.ReportForecast{}
		// year
		if y, ok := doc.Forecast["year"].(int32); ok {
			ff.Year = int(y)
		}
		if y, ok := doc.Forecast["year"].(int); ok {
			ff.Year = y
		}
		if y, ok := doc.Forecast["year"].(int64); ok {
			ff.Year = int(y)
		}
		if y, ok := doc.Forecast["year"].(float64); ok {
			ff.Year = int(y)
		}

		if y, ok := doc.Forecast["yieldTph"].(float64); ok {
			ff.YieldTph = toFloatPtr(y)
		}
		if y, ok := doc.Forecast["yieldConfidence"].(float64); ok {
			ff.YieldConfidence = toFloatPtr(y)
		}

		if y, ok := doc.Forecast["ndviPeak"].(float64); ok {
			ff.NDVIPeak = toFloatPtr(y)
		}
		if y, ok := doc.Forecast["ndviPeakAt"].(string); ok {
			ff.NDVIPeakAt = parseRFC3339Ptr(y)
		}
		if y, ok := doc.Forecast["ndviModel"].(string); ok {
			ff.NDVIModel = y
		}
		if y, ok := doc.Forecast["ndviStartAt"].(string); ok {
			ff.NDVIStartAt = parseRFC3339Ptr(y)
		}
		if y, ok := doc.Forecast["ndviStartConfidence"].(float64); ok {
			ff.NDVIStartConfidence = toFloatPtr(y)
		}
		if y, ok := doc.Forecast["ndviStartMethod"].(string); ok {
			ff.NDVIStartMethod = y
		}
		if y, ok := doc.Forecast["ndviConfidence"].(float64); ok {
			ff.NDVIConfidence = toFloatPtr(y)
		}
		// ff.NDVIEndAt = parseRFC3339Ptr(doc.Forecast["ndviEndAt"])

		f.Forecast = ff
	}

	if doc.Anomalies != nil && len(doc.Anomalies) > 0 {
		anomalies := make([]models.Anomaly, len(doc.Anomalies))
		for i, a := range doc.Anomalies {
			anomalies[i] = models.Anomaly{
				Key:        a["key"].(string),
				Title:      a["title"].(string),
				Triggered:  a["triggered"].(bool),
				Severity:   a["severity"].(string),
				DetectedAt: parseRFC3339Ptr(a["detectedAt"]),
				// Details:    a["details"].(map[string]any),
			}
		}
		f.Anomalies = anomalies
	}
}

func strOrEmpty(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

// handleCreateField inserts a new field with basic GeoJSON validation.
func (a *App) handleCreateField(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)

	var req createFieldReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.Name) == "" || strings.TrimSpace(req.Crop) == "" || len(req.Geometry) == 0 {
		http.Error(w, "name, crop and geometry are required", http.StatusBadRequest)
		return
	}

	// Minimal GeoJSON check (type + coordinates).
	var geom bson.M
	if err := json.Unmarshal(req.Geometry, &geom); err != nil {
		http.Error(w, "invalid geometry json", http.StatusBadRequest)
		return
	}
	gt, _ := geom["type"].(string)
	if gt != "Polygon" && gt != "MultiPolygon" {
		http.Error(w, "geometry.type must be Polygon or MultiPolygon", http.StatusBadRequest)
		return
	}

	f := models.Field{
		OwnerID:   uid,
		Name:      req.Name,
		Geometry:  geom,
		CreatedAt: time.Now(),
		Status:    models.ReportStatusProcessing,
	}
	// Create meta if any of its fields are provided
	if req.AreaHa != nil || strings.TrimSpace(req.Notes) != "" || strings.TrimSpace(req.Crop) != "" {
		f.Meta = &models.FieldMeta{AreaHa: req.AreaHa, Notes: req.Notes, Crop: req.Crop}
	}

	if req.Photo != "" {
		f.Photo = req.Photo
	}

	if len(req.Yields) > 0 {
		f.Yields = make([]models.YieldEntry, len(req.Yields))
		for i, y := range req.Yields {
			f.Yields[i] = models.YieldEntry{Year: y.Year, ValueTph: y.ValueTph, Unit: y.Unit, Notes: y.Notes}
		}
	}

	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	res, err := a.fields.InsertOne(ctx, &f)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}
	f.ID = res.InsertedID.(primitive.ObjectID)
	_ = json.NewEncoder(w).Encode(f)

	// send update to processor only if we know the crop/yield type
	yt := strings.TrimSpace(req.Crop)
	if yt != "" {
		if _, perr := a.PostProcessorReports(ctx, processorReportReq{
			FieldID:   f.ID.Hex(),
			GeoJSON:   req.Geometry,
			YieldType: yt,
			Yields:    req.Yields,
		}); perr != nil {
			log.Println("processor error (create)", perr)
		}
	}
}

// handleListFields returns the current user's fields.
func (a *App) handleListFields(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
	defer cancel()

	cur, err := a.fields.Find(ctx, bson.M{"ownerId": uid}, options.Find().SetSort(bson.D{{Key: "createdAt", Value: -1}}))
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}
	defer cur.Close(ctx)

	var out []models.Field
	if err := cur.All(ctx, &out); err != nil {
		http.Error(w, "decode error", http.StatusInternalServerError)
		return
	}
	for i := range out {
		enrichFieldWithLatestReport(ctx, a, &out[i])
	}
	_ = json.NewEncoder(w).Encode(out)
}

// handleGetField returns a single field by id (owned by the user).
func (a *App) handleGetField(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	idStr := chi.URLParam(r, "id")
	oid, err := primitive.ObjectIDFromHex(idStr)
	if err != nil {
		http.Error(w, "bad id", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	var f models.Field
	if err := a.fields.FindOne(ctx, bson.M{"_id": oid, "ownerId": uid}).Decode(&f); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	enrichFieldWithLatestReport(ctx, a, &f)
	_ = json.NewEncoder(w).Encode(f)
}

// handleUpdateField updates name/geometry/yields and meta.areaHa if provided.
func (a *App) handleUpdateField(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	idStr := chi.URLParam(r, "id")
	oid, err := primitive.ObjectIDFromHex(idStr)
	if err != nil {
		http.Error(w, "bad id", http.StatusBadRequest)
		return
	}

	var req createFieldReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}

	set := bson.M{}
	if req.Name != "" {
		set["name"] = req.Name
	}
	if len(req.Geometry) > 0 {
		var geom bson.M
		if err := json.Unmarshal(req.Geometry, &geom); err != nil {
			http.Error(w, "invalid geometry json", http.StatusBadRequest)
			return
		}
		gt, _ := geom["type"].(string)
		if gt != "Polygon" && gt != "MultiPolygon" {
			http.Error(w, "geometry.type must be Polygon or MultiPolygon", http.StatusBadRequest)
			return
		}
		set["geometry"] = geom
		set["status"] = models.ReportStatusProcessing
	}
	if req.AreaHa != nil {
		set["meta.areaHa"] = req.AreaHa // store under nested meta
	}
	if strings.TrimSpace(req.Notes) != "" {
		set["meta.notes"] = req.Notes
	}
	if strings.TrimSpace(req.Crop) != "" {
		set["meta.crop"] = req.Crop
	}
	if len(req.Yields) > 0 {
		// Convert to models.YieldEntry so correct bson field names are used
		ys := make([]models.YieldEntry, len(req.Yields))
		for i, y := range req.Yields {
			ys[i] = models.YieldEntry{Year: y.Year, ValueTph: y.ValueTph, Unit: y.Unit, Notes: y.Notes}
		}
		set["yields"] = ys
	}
	if len(set) == 0 {
		http.Error(w, "nothing to update", http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	res := a.fields.FindOneAndUpdate(
		ctx,
		bson.M{"_id": oid, "ownerId": uid},
		bson.M{"$set": set},
		options.FindOneAndUpdate().SetReturnDocument(options.After),
	)

	var out models.Field
	if err := res.Decode(&out); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	enrichFieldWithLatestReport(ctx, a, &out)
	_ = json.NewEncoder(w).Encode(out)

	// send update to processor only if geometry is provided and we know yieldType
	yt2 := strings.TrimSpace(req.Crop)
	if yt2 == "" && out.Meta != nil {
		yt2 = strings.TrimSpace(out.Meta.Crop)
	}
	if len(req.Geometry) > 0 && yt2 != "" {
		if _, perr := a.PostProcessorReports(ctx, processorReportReq{
			FieldID:   out.ID.Hex(),
			GeoJSON:   req.Geometry,
			YieldType: yt2,
			Yields:    req.Yields,
		}); perr != nil {
			log.Println("processor error (update)", perr)
		}
	} else {
		log.Println("skip PostProcessorReports: missing geometry or yieldType")
	}
}

// handleDeleteField removes a field by id.
func (a *App) handleDeleteField(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	idStr := chi.URLParam(r, "id")
	oid, err := primitive.ObjectIDFromHex(idStr)
	if err != nil {
		http.Error(w, "bad id", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	res, err := a.fields.DeleteOne(ctx, bson.M{"_id": oid, "ownerId": uid})
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}
	if res.DeletedCount == 0 {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	_ = json.NewEncoder(w).Encode(bson.M{"ok": true})
}

// ---- helpers ----

// dateOnlyUTC normalizes a timestamp to 00:00:00 UTC (one bucket per day).
func dateOnlyUTC(t time.Time) time.Time {
	tt := t.UTC()
	return time.Date(tt.Year(), tt.Month(), tt.Day(), 0, 0, 0, 0, time.UTC)
}

// dateKeyUTC formats a timestamp as "YYYY-MM-DD" in UTC to serve as a map key.
func dateKeyUTC(t time.Time) string {
	tt := t.UTC()
	return tt.Format("2006-01-02")
}

// mergeDaily overlays non-nil values from 'in' onto 'curr' (same date).
// Strings: only overwrite when non-empty. Numeric pointers: overwrite when non-nil.
func mergeDaily(curr models.ReportDaily, in models.ReportDaily) models.ReportDaily {
	out := curr
	out.Date = in.Date // normalized already

	if in.NDVI != nil {
		out.NDVI = in.NDVI
	}
	if in.CloudCover != nil {
		out.CloudCover = in.CloudCover
	}
	if in.Collection != "" {
		out.Collection = in.Collection
	}
	if in.TemperatureDeg != nil {
		out.TemperatureDeg = in.TemperatureDeg
	}
	if in.HumidityPct != nil {
		out.HumidityPct = in.HumidityPct
	}
	if in.CloudcoverPct != nil {
		out.CloudcoverPct = in.CloudcoverPct
	}
	if in.WindSpeedMps != nil {
		out.WindSpeedMps = in.WindSpeedMps
	}
	if in.ClarityPct != nil {
		out.ClarityPct = in.ClarityPct
	}
	return out
}
