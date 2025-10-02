package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"demetereye/models"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"golang.org/x/crypto/bcrypt"
)

// handleRegister creates a new user with bcrypt-hashed password.
func (a *App) handleRegister(w http.ResponseWriter, r *http.Request) {
	var req registerReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if req.Username == "" || req.Email == "" || req.Password == "" {
		http.Error(w, "username, email, password are required", http.StatusBadRequest)
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		http.Error(w, "hash error", http.StatusInternalServerError)
		return
	}
	u := models.User{
		Username:     req.Username,
		Email:        strings.ToLower(req.Email),
		PasswordHash: string(hash),
		CreatedAt:    time.Now(),
	}

	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	if _, err = a.users.InsertOne(ctx, &u); err != nil {
		if mongo.IsDuplicateKeyError(err) {
			http.Error(w, "email already registered", http.StatusConflict)
			return
		}
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(bson.M{"ok": true})
}

// handleLogin verifies credentials and returns a JWT token.
func (a *App) handleLogin(w http.ResponseWriter, r *http.Request) {
	var req loginReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	var u models.User
	if err := a.users.FindOne(ctx, bson.M{"email": strings.ToLower(req.Email)}).Decode(&u); err != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}
	if bcrypt.CompareHashAndPassword([]byte(u.PasswordHash), []byte(req.Password)) != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}

	tok, err := signJWT(a.cfg.JWTSecret, u.ID)
	if err != nil {
		http.Error(w, "jwt error", http.StatusInternalServerError)
		return
	}
	_ = json.NewEncoder(w).Encode(tokenResp{Token: tok})
}

// handleMe returns the current user's profile (without password hash).
func (a *App) handleMe(w http.ResponseWriter, r *http.Request) {
	uid := mustUserID(r)
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	var u models.User
	if err := a.users.FindOne(ctx, bson.M{"_id": uid}).Decode(&u); err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	u.PasswordHash = ""
	_ = json.NewEncoder(w).Encode(u)
}
