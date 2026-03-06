package handler

import (
	"fmt"
	"html/template"
	"io/fs"
	"net/http"
	"strings"
	"time"
)

// PageData holds the data passed to every page template.
// Think of it like Laravel's view()->share() data or Django's context dict.
type PageData struct {
	ActiveTab string // which bottom nav tab is active: "home", "reports", "people"
	Data      any    // page-specific data (transactions, accounts, etc.)
}

// TemplateMap holds parsed templates keyed by page name.
// Each page gets its own template set (base layout + components + page content),
// which is how Go handles template inheritance — by cloning a base and adding page blocks.
type TemplateMap map[string]*template.Template

// TemplateFuncs returns custom template functions available in all templates.
// Like Laravel's Blade directives or Django template filters.
func TemplateFuncs() template.FuncMap {
	return template.FuncMap{
		// formatEGP formats a float as Egyptian Pounds: "EGP 1,234.56"
		"formatEGP": func(amount float64) string {
			return "EGP " + formatNumber(amount)
		},
		// formatUSD formats a float as US Dollars: "$1,234.56"
		"formatUSD": func(amount float64) string {
			return "$" + formatNumber(amount)
		},
		// formatCurrency formats an amount with the appropriate currency symbol
		"formatCurrency": func(amount float64, currency string) string {
			switch strings.ToUpper(currency) {
			case "USD":
				return "$" + formatNumber(amount)
			default:
				return "EGP " + formatNumber(amount)
			}
		},
		// formatDate displays a time.Time as "Jan 2, 2006"
		"formatDate": func(t time.Time) string {
			return t.Format("Jan 2, 2006")
		},
		// formatDateShort displays as "Jan 2"
		"formatDateShort": func(t time.Time) string {
			return t.Format("Jan 2")
		},
	}
}

// formatNumber adds thousand separators and 2 decimal places.
// 1234567.89 → "1,234,567.89"
func formatNumber(n float64) string {
	s := fmt.Sprintf("%.2f", n)
	parts := strings.Split(s, ".")
	intPart := parts[0]
	decPart := parts[1]

	prefix := ""
	if intPart[0] == '-' {
		prefix = "-"
		intPart = intPart[1:]
	}

	var result []byte
	for i, c := range intPart {
		if i > 0 && (len(intPart)-i)%3 == 0 {
			result = append(result, ',')
		}
		result = append(result, byte(c))
	}

	return prefix + string(result) + "." + decPart
}

// ParseTemplates loads all HTML templates using Go's template inheritance pattern.
//
// Go templates don't have @extends like Blade. Instead, we:
// 1. Parse the base layout + components as a "base" template set
// 2. For each page, clone the base and parse the page file on top
//
// This lets each page redefine {{define "content"}} and {{define "title"}}
// blocks, overriding the defaults from the base layout.
func ParseTemplates(templateFS fs.FS) (TemplateMap, error) {
	// Shared files: layout + components (parsed once, cloned per page)
	sharedFiles := []string{
		"layouts/base.html",
		"components/header.html",
		"components/bottom-nav.html",
	}

	// Parse shared templates
	base, err := template.New("").Funcs(TemplateFuncs()).ParseFS(templateFS, sharedFiles...)
	if err != nil {
		return nil, fmt.Errorf("parsing base templates: %w", err)
	}

	// Find all page files
	pageFiles, err := fs.Glob(templateFS, "pages/*.html")
	if err != nil {
		return nil, fmt.Errorf("finding page templates: %w", err)
	}

	templates := make(TemplateMap)
	for _, pageFile := range pageFiles {
		// Extract page name: "pages/home.html" → "home"
		name := strings.TrimPrefix(pageFile, "pages/")
		name = strings.TrimSuffix(name, ".html")

		// Clone the base template set and add the page-specific blocks
		pageTemplate, err := template.Must(base.Clone()).ParseFS(templateFS, pageFile)
		if err != nil {
			return nil, fmt.Errorf("parsing page %s: %w", name, err)
		}
		templates[name] = pageTemplate
	}

	return templates, nil
}

// RenderPage renders a named page template with the given data.
// The page name maps to a file in templates/pages/ (e.g., "home" → pages/home.html).
func RenderPage(templates TemplateMap, w http.ResponseWriter, page string, data PageData) {
	tmpl, ok := templates[page]
	if !ok {
		http.Error(w, "page not found: "+page, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := tmpl.ExecuteTemplate(w, "base", data); err != nil {
		http.Error(w, "template error: "+err.Error(), http.StatusInternalServerError)
	}
}
