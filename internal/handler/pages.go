package handler

import (
	"net/http"
)

// PageHandler serves full HTML pages (as opposed to JSON API endpoints).
// Think of it like Laravel's web routes vs API routes — same data, different format.
type PageHandler struct {
	templates TemplateMap
}

func NewPageHandler(templates TemplateMap) *PageHandler {
	return &PageHandler{templates: templates}
}

// Home renders the dashboard page.
// GET /
func (h *PageHandler) Home(w http.ResponseWriter, r *http.Request) {
	RenderPage(h.templates, w, "home", PageData{ActiveTab: "home"})
}
