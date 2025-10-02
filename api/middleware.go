package main

import (
	"context"
	"net/http"
	"strings"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

type ctxKey string

const userIDKey ctxKey = "userID"

// authMiddleware extracts and validates Bearer token and injects userID into context.
func (a *App) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authz := r.Header.Get("Authorization")
		if !strings.HasPrefix(authz, "Bearer ") {
			http.Error(w, "missing bearer token", http.StatusUnauthorized)
			return
		}
		raw := strings.TrimPrefix(authz, "Bearer ")
		uid, err := parseJWT(a.cfg.JWTSecret, raw)
		if err != nil {
			http.Error(w, "invalid token", http.StatusUnauthorized)
			return
		}
		ctx := context.WithValue(r.Context(), userIDKey, uid)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// mustUserID returns the userID from context or NilObjectID if missing.
func mustUserID(r *http.Request) primitive.ObjectID {
	val := r.Context().Value(userIDKey)
	if val == nil {
		return primitive.NilObjectID
	}
	return val.(primitive.ObjectID)
}
