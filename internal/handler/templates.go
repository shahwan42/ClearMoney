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
	funcs := template.FuncMap{
		// formatEGP formats a float as Egyptian Pounds: "EGP 1,234.56"
		"formatEGP": func(amount float64) string {
			return "EGP " + formatNumber(amount)
		},
		// formatUSD formats a float as US Dollars: "$1,234.56"
		"formatUSD": func(amount float64) string {
			return "$" + formatNumber(amount)
		},
		// formatCurrency formats an amount with the appropriate currency symbol.
		// Accepts any string-like type (including models.Currency).
		"formatCurrency": func(amount float64, currency any) string {
			cur := strings.ToUpper(fmt.Sprintf("%v", currency))
			switch cur {
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
		// deref safely dereferences a string pointer, returning "" if nil
		"deref": func(s *string) string {
			if s == nil {
				return ""
			}
			return *s
		},
		// derefFloat dereferences a *float64 pointer, returning 0 if nil.
		// Used for optional numeric fields like VirtualFund.TargetAmount.
		"derefFloat": func(f *float64) float64 {
			if f == nil {
				return 0
			}
			return *f
		},
		// string converts any value to string (for use in template comparisons)
		"string": func(v any) string {
			return fmt.Sprintf("%v", v)
		},
		// percentage computes (part / total) * 100 for progress bars
		"percentage": func(part, total int) float64 {
			if total == 0 {
				return 0
			}
			return float64(part) / float64(total) * 100
		},
		// neg negates a float64 (for displaying absolute values of negative numbers)
		"neg": func(v float64) float64 {
			return -v
		},
		// addFloat adds two float64 values (for template arithmetic)
		"addFloat": func(a, b float64) float64 {
			return a + b
		},
		// dict creates a map[string]any from key-value pairs.
		// Used to pass multiple values to sub-templates (like Laravel's @include with data):
		//   {{template "chart-sparkline" (dict "Values" .Values "Color" "#0d9488")}}
		// In Django, similar to {% include "partial.html" with key=value %}
		"dict": func(values ...any) map[string]any {
			d := make(map[string]any)
			for i := 0; i < len(values)-1; i += 2 {
				key, ok := values[i].(string)
				if ok {
					d[key] = values[i+1]
				}
			}
			return d
		},
	}

	// Merge chart template functions (conicGradient, sparklinePoints, chartColor, etc.)
	// These power CSS-only data visualization — see charts.go for details.
	for name, fn := range ChartFuncs() {
		funcs[name] = fn
	}

	return funcs
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
	// Shared files: layouts + components + partials (parsed once, cloned per page)
	sharedFiles := []string{
		"layouts/base.html",
		"layouts/bare.html",
		"components/header.html",
		"components/bottom-nav.html",
	}

	// Add all partial files dynamically
	partialFiles, err := fs.Glob(templateFS, "partials/*.html")
	if err != nil {
		return nil, fmt.Errorf("finding partial templates: %w", err)
	}
	sharedFiles = append(sharedFiles, partialFiles...)

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

// barePages lists pages that use the "bare" layout (no header/nav) — like login and setup.
var barePages = map[string]bool{
	"login": true,
	"setup": true,
}

// RenderPage renders a named page template with the given data.
// The page name maps to a file in templates/pages/ (e.g., "home" → pages/home.html).
// Auth pages (login, setup) use the "bare" layout without header/nav.
func RenderPage(templates TemplateMap, w http.ResponseWriter, page string, data PageData) {
	tmpl, ok := templates[page]
	if !ok {
		http.Error(w, "page not found: "+page, http.StatusNotFound)
		return
	}

	layout := "base"
	if barePages[page] {
		layout = "bare"
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := tmpl.ExecuteTemplate(w, layout, data); err != nil {
		http.Error(w, "template error: "+err.Error(), http.StatusInternalServerError)
	}
}
