package main

import (
	"context"
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"time"

	"demetereye/models"

	"github.com/go-chi/chi/v5"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// handleCreateField inserts a new field with basic GeoJSON validation.
func (a *App) handleCreateField(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)

	var req createFieldReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.Name) == "" || len(req.Geometry) == 0 {
		http.Error(w, "name and geometry are required", http.StatusBadRequest)
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
		Status:    models.FieldStatusProcessing,
	}
	if req.AreaHa != nil {
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

	if err == nil {
		// send update to processor
		a.PostProcessorReports(ctx, processorReportReq{
			GeoJSON:   req.Geometry,
			YieldType: req.Crop,
			Yields:    req.Yields,
		})
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
	_ = json.NewEncoder(w).Encode(f)
}

// handleUpdateField updates name/geometry and meta.areaHa if provided.
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
		set["status"] = models.FieldStatusProcessing
	}
	if req.AreaHa != nil {
		set["meta.areaHa"] = req.AreaHa // store under nested meta
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
	_ = json.NewEncoder(w).Encode(out)

	if err == nil {
		// send update to processor
		a.PostProcessorReports(ctx, processorReportReq{
			GeoJSON:   req.Geometry,
			YieldType: req.Crop,
			Yields:    req.Yields,
		})
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

// handleIngestFieldData upserts daily history by date and optionally sets a forecast.
// It merges per-day records by date key (UTC date), preferring non-nil incoming values.
// If a forecast is provided, status defaults to "ready" unless explicitly overridden.
func (a *App) handleIngestFieldData(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	idStr := chi.URLParam(r, "id")
	oid, err := primitive.ObjectIDFromHex(idStr)
	if err != nil {
		http.Error(w, "bad id", http.StatusBadRequest)
		return
	}

	var req ingestFieldReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()

	// Load existing history to merge. We only need history, status, forecast.
	var existing struct {
		History  []models.HistoryDaily `bson:"history"`
		Status   models.FieldStatus    `bson:"status"`
		Forecast *models.FieldForecast `bson:"forecast"`
	}
	find := a.fields.FindOne(ctx,
		bson.M{"_id": oid, "ownerId": uid},
		options.FindOne().SetProjection(bson.M{"history": 1, "status": 1, "forecast": 1}),
	)
	if err := find.Err(); err != nil {
		// If document not found, FindOne.Err() is non-nil as well.
		if err == context.DeadlineExceeded {
			http.Error(w, "timeout", http.StatusGatewayTimeout)
			return
		}
	}
	if err := find.Decode(&existing); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	// Build a map of existing history keyed by date (YYYY-MM-DD in UTC).
	hmap := make(map[string]models.HistoryDaily, len(existing.History))
	for _, d := range existing.History {
		key := dateKeyUTC(d.Date)
		// Normalize stored date to 00:00:00Z to keep one-per-day.
		d.Date = dateOnlyUTC(d.Date)
		hmap[key] = d
	}

	// Merge incoming rows: upsert by date, overriding only non-nil fields.
	for _, in := range req.History {
		key := dateKeyUTC(in.Date)
		in.Date = dateOnlyUTC(in.Date)
		if curr, ok := hmap[key]; ok {
			hmap[key] = mergeDaily(curr, in)
		} else {
			// Insert as-is.
			hmap[key] = in
		}
	}

	// Flatten and sort by date ascending for deterministic storage.
	merged := make([]models.HistoryDaily, 0, len(hmap))
	for _, v := range hmap {
		merged = append(merged, v)
	}
	sort.Slice(merged, func(i, j int) bool { return merged[i].Date.Before(merged[j].Date) })

	// Prepare $set payload.
	set := bson.M{
		"history": merged,
	}

	// Apply forecast if provided.
	if req.Forecast != nil {
		req.Forecast.UpdatedAt = time.Now().UTC()
		set["forecast"] = req.Forecast
	}

	// Decide status:
	set["status"] = models.FieldStatusReady

	// Update and return the full document.
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
	_ = json.NewEncoder(w).Encode(out)
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
func mergeDaily(curr models.HistoryDaily, in models.HistoryDaily) models.HistoryDaily {
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
	if in.TemperatureDegC != nil {
		out.TemperatureDegC = in.TemperatureDegC
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
