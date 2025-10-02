package main

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

// signJWT creates an HS256 token with 24h expiration.
func signJWT(secret string, userID primitive.ObjectID) (string, error) {
	claims := jwt.MapClaims{
		"sub": userID.Hex(),
		"exp": time.Now().Add(24 * time.Hour).Unix(),
		"iat": time.Now().Unix(),
		"iss": "demetereye",
	}
	t := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return t.SignedString([]byte(secret))
}

// parseJWT validates token and returns subject as ObjectID.
func parseJWT(secret, tokenStr string) (primitive.ObjectID, error) {
	tok, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(secret), nil
	})
	if err != nil || !tok.Valid {
		return primitive.NilObjectID, errors.New("invalid token")
	}
	if claims, ok := tok.Claims.(jwt.MapClaims); ok {
		if sub, ok := claims["sub"].(string); ok {
			return primitive.ObjectIDFromHex(sub)
		}
	}
	return primitive.NilObjectID, errors.New("no subject")
}
