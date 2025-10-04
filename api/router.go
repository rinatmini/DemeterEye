package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/cors"
)

// routes wires middlewares and endpoints. Adjust CORS for your frontend hosts.
func (a *App) routes() http.Handler {
	r := chi.NewRouter()

	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		ExposedHeaders:   []string{"Link"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	r.Route("/api", func(api chi.Router) {
		api.Post("/auth/register", a.handleRegister)
		api.Post("/auth/login", a.handleLogin)

		api.Group(func(pr chi.Router) {
			pr.Use(a.authMiddleware)
			pr.Get("/me", a.handleMe)

			pr.Route("/fields", func(fr chi.Router) {
				fr.Get("/", a.handleListFields)
				fr.Post("/", a.handleCreateField)
				fr.Get("/{id}", a.handleGetField)
				fr.Put("/{id}", a.handleUpdateField)
				fr.Delete("/{id}", a.handleDeleteField)
			})
		})
	})

	return r
}
