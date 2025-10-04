package main

import (
	"os"
)

type Config struct {
	MongoURI     string
	MongoDB      string
	ProcessorURI string
	JWTSecret    string
	Port         string
}

func mustConfig() Config {
	cfg := Config{
		MongoURI:     getenv("MONGO_URI", "mongodb://localhost:27017"),
		MongoDB:      getenv("MONGO_DB", "demetereye"),
		ProcessorURI: getenv("PROCESSOR_URL", "http://127.0.0.1:8000"),
		JWTSecret:    getenv("JWT_SECRET", "change_me"),
		Port:         getenv("PORT", "8080"),
	}

	return cfg
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
