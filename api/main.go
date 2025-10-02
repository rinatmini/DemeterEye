package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"time"
)

func main() {
	cfg := mustConfig()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	app, err := newApp(ctx, cfg)
	if err != nil {
		log.Fatal("mongo connect error: ", err)
	}
	defer app.close(context.Background())

	port := cfg.Port
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           app.routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Println("DemeterEye API listening on :" + port)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}
