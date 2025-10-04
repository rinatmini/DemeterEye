package main

import (
	"context"

	"demetereye/models"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type App struct {
	cfg     Config
	mongo   *mongo.Client
	db      *mongo.Database
	users   *mongo.Collection
	fields  *mongo.Collection
	reports *mongo.Collection
}

func newApp(ctx context.Context, cfg Config) (*App, error) {
	client, err := mongo.Connect(ctx, options.Client().ApplyURI(cfg.MongoURI))
	if err != nil {
		return nil, err
	}
	db := client.Database(cfg.MongoDB)

	app := &App{
		cfg:     cfg,
		mongo:   client,
		db:      db,
		users:   db.Collection("users"),
		fields:  db.Collection("fields"),
		reports: db.Collection("reports"),
	}
	// Indexes
	if _, err := app.users.Indexes().CreateOne(ctx, mongo.IndexModel{
		Keys:    bson.D{{Key: "email", Value: 1}},
		Options: options.Index().SetUnique(true),
	}); err != nil {
		return nil, err
	}
	if _, err := app.fields.Indexes().CreateOne(ctx, mongo.IndexModel{
		Keys: bson.D{{Key: "ownerId", Value: 1}, {Key: "createdAt", Value: -1}},
	}); err != nil {
		return nil, err
	}
	// Optional: 2dsphere for future spatial queries
	// _, _ = app.fields.Indexes().CreateOne(ctx, mongo.IndexModel{
	// 	Keys: bson.D{{Key: "geometry", Value: "2dsphere"}},
	// })

	_ = models.User{} // ensure models imported
	return app, nil
}

func (a *App) close(ctx context.Context) { _ = a.mongo.Disconnect(ctx) }
