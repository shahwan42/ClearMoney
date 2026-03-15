// templates.go — Template engine configuration, custom functions, and rendering.
//
// Go's html/template vs Blade (Laravel) vs Jinja2 (Django):
//
// Go uses html/template (part of stdlib) for server-side HTML rendering.
// Unlike Blade or Jinja2, Go templates have minimal logic — by design.
//
// Key differences for Laravel/Django developers:
//
//   Blade/Jinja2:                        Go html/template:
//   @extends('layouts.app')              {{template "base" .}}        (no @extends)
//   @section('content')                  {{define "content"}}...{{end}}
//   @include('partials.card', ['x'=>1])  {{template "card" .}}
//   {{ $user->name }}                    {{.User.Name}}
//   @if($x > 0)                          {{if gt .X 0}}
//   @foreach($items as $item)            {{range .Items}}
//   {{ money($amount) }}                 {{formatEGP .Amount}}
//
// Template inheritance in Go: "Clone-per-page" pattern.
// Go templates don't have @extends. Instead, we:
//   1. Parse a base template set (layout + components)
//   2. Clone it for each page
//   3. Parse the page file on top of the clone
// This lets each page override {{define "content"}} and {{define "title"}} blocks.
//
// Auto-escaping: Go's html/template auto-escapes all output by default (XSS protection).
// To insert raw HTML/CSS, use template.HTML or template.CSS wrapper types.
//
// See: https://pkg.go.dev/html/template
// See: https://pkg.go.dev/html/template#FuncMap (custom functions)
package handler

import (
	"fmt"
	"html/template"
	"io/fs"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

// PageData holds the data passed to every page template.
// Think of it like Laravel's view()->share() data or Django's context dict.
//
// In Go templates, this becomes the "dot" (.) value:
//   {{.ActiveTab}}  — accesses ActiveTab field
//   {{.Data}}       — accesses page-specific data (cast with type assertions in templates)
//
// In Laravel: return view('home', ['activeTab' => 'home', 'data' => $dashData])
// In Django: return render(request, 'home.html', {'active_tab': 'home', 'data': dash_data})
type PageData struct {
	ActiveTab string // which bottom nav tab is active: "home", "reports", "people"
	Data      any    // page-specific data (transactions, accounts, etc.)
}

// TemplateMap holds parsed templates keyed by page name.
// Each page gets its own template set (base layout + components + page content),
// which is how Go handles template inheritance — by cloning a base and adding page blocks.
//
// Usage: templates["home"] returns the fully-assembled template for the home page,
// which includes the base layout, header, nav, and the home-specific content.
type TemplateMap map[string]*template.Template

// TemplateFuncs returns custom template functions available in all templates.
// Like Laravel's Blade directives or Django template filters/tags.
//
// In Go, custom functions are registered via template.FuncMap before parsing.
// Each function name becomes available in templates: {{formatEGP .Amount}}
//
// In Laravel, you'd register Blade directives: Blade::directive('money', ...)
// In Django, you'd create a templatetags module with @register.filter.
//
// See: https://pkg.go.dev/html/template#FuncMap
func TemplateFuncs(loc *time.Location) template.FuncMap {
	funcs := template.FuncMap{
		// formatEGP formats a float as Egyptian Pounds: "EGP 1,234.56"
		"formatEGP": func(amount float64) string {
			return "EGP " + formatNumber(amount)
		},
		// formatNum formats a float with thousand separators, no currency prefix: "1,234.56"
		"formatNum": func(amount float64) string {
			return formatNumber(amount)
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
		// formatDate displays a time.Time as "Jan 2, 2006" in the user's timezone
		"formatDate": func(t time.Time) string {
			return t.In(loc).Format("Jan 2, 2006")
		},
		// formatDateShort displays as "Jan 2" in the user's timezone
		"formatDateShort": func(t time.Time) string {
			return t.In(loc).Format("Jan 2")
		},
		// formatDateISO returns "2006-01-02" in the user's timezone for HTML date inputs
		"formatDateISO": func(t time.Time) string {
			return t.In(loc).Format("2006-01-02")
		},
		// formatDuration converts seconds to a human-readable duration string.
		// Used by the login lockout countdown display.
		"formatDuration": func(seconds int) string {
			if seconds < 60 {
				if seconds == 1 {
					return "1 second"
				}
				return fmt.Sprintf("%d seconds", seconds)
			}
			m := seconds / 60
			s := seconds % 60
			if s == 0 {
				if m == 1 {
					return "1 minute"
				}
				return fmt.Sprintf("%d minutes", m)
			}
			return fmt.Sprintf("%d min %d sec", m, s)
		},
		// deref safely dereferences a string pointer, returning "" if nil
		"deref": func(s *string) string {
			if s == nil {
				return ""
			}
			return *s
		},
		// derefFloat dereferences a *float64 pointer, returning 0 if nil.
		// Used for optional numeric fields like VirtualAccount.TargetAmount.
		"derefFloat": func(f *float64) float64 {
			if f == nil {
				return 0
			}
			return *f
		},
		// derefTime dereferences a *time.Time pointer for use with formatDateShort etc.
		"derefTime": func(t *time.Time) time.Time {
			if t == nil {
				return time.Time{}
			}
			return *t
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
		// formatAccountType converts an account type enum to a human-readable label.
		// e.g., "credit_card" → "Credit Card", "credit_limit" → "Credit Line"
		"formatAccountType": func(t any) string {
			labels := map[string]string{
				"savings":      "Savings",
				"current":      "Current",
				"prepaid":      "Prepaid",
				"credit_card":  "Credit Card",
				"credit_limit": "Credit Line",
				"cash":         "Cash",
			}
			key := fmt.Sprintf("%v", t)
			if label, ok := labels[key]; ok {
				return label
			}
			return key
		},
		// formatType converts a transaction type enum to a human-readable label.
		// e.g., "loan_repayment" → "Loan Repayment", "loan_in" → "Loan Received"
		"formatType": func(t any) string {
			labels := map[string]string{
				"expense":        "Expense",
				"income":         "Income",
				"transfer":       "Transfer",
				"exchange":       "Exchange",
				"loan_out":       "Loan Given",
				"loan_in":        "Loan Received",
				"loan_repayment": "Loan Repayment",
			}
			key := fmt.Sprintf("%v", t)
			if label, ok := labels[key]; ok {
				return label
			}
			return key
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
	// Eliminate negative zero (-0.0) which can result from negating 0.0
	if n == 0 {
		n = 0
	}
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

// ParseTemplates loads all HTML templates using Go's "clone-per-page" inheritance pattern.
//
// Go templates don't have @extends like Blade or {% extends %} like Jinja2.
// Instead, we simulate template inheritance by:
//   1. Parsing the base layout + shared components into a "base" template set
//   2. For each page, cloning the base set (template.Must(base.Clone()))
//   3. Parsing the page-specific file on top of the clone
//
// This lets each page redefine {{define "content"}} and {{define "title"}}
// blocks, overriding the defaults from the base layout — similar to how
// Blade's @section/@yield works, or Django's {% block %}{% endblock %}.
//
// The templateFS parameter is an embedded filesystem (io/fs.FS) containing
// all HTML template files. Go's embed package compiles these files into the
// binary, so there's no filesystem dependency at runtime.
//
// See: https://pkg.go.dev/html/template#Template.Clone
// See: https://pkg.go.dev/io/fs (for embedded filesystems)
func ParseTemplates(templateFS fs.FS, loc *time.Location) (TemplateMap, error) {
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
	base, err := template.New("").Funcs(TemplateFuncs(loc)).ParseFS(templateFS, sharedFiles...)
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
// The page name maps to a file in templates/pages/ (e.g., "home" -> pages/home.html).
// Auth pages (login, setup) use the "bare" layout without header/nav.
//
// This is the Go equivalent of:
//   - Laravel: return view('home', $data);
//   - Django: return render(request, 'pages/home.html', data)
//
// The function looks up the pre-parsed template by page name, selects the layout
// ("base" with header/nav, or "bare" for auth pages), and executes the template
// writing the rendered HTML directly to the ResponseWriter.
//
// ExecuteTemplate(w, "base", data) starts rendering from the "base" named template,
// which in turn calls {{template "content" .}} to render page-specific content.
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

	slog.Debug("rendering page", "page", page, "layout", layout)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := tmpl.ExecuteTemplate(w, layout, data); err != nil {
		http.Error(w, "template error: "+err.Error(), http.StatusInternalServerError)
	}
}
