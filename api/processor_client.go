// file: processor_client.go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// PostProcessorReports calls POST {ProcessorURI}/reports with given payload.
func (a *App) PostProcessorReports(ctx context.Context, in processorReportReq) (*processorReportResp, error) {
	// Defensive: basic validation
	if len(in.GeoJSON) == 0 {
		return nil, fmt.Errorf("empty geojson")
	}

	// Marshal request
	body, err := json.Marshal(in)
	if err != nil {
		return nil, fmt.Errorf("marshal processor req: %w", err)
	}

	// HTTP client with sane timeouts
	client := &http.Client{
		Timeout: 25 * time.Second,
	}

	url := a.cfg.ProcessorURI
	if url == "" || url == "local" {
		url = "http://127.0.0.1:8000"
	}
	url = url + "/reports"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("processor call failed: %w", err)
	}
	defer resp.Body.Close()

	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("processor non-2xx: %s, body: %s", resp.Status, string(data))
	}

	var out processorReportResp
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("decode processor resp: %w", err)
	}
	return &out, nil
}
