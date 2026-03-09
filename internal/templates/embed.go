// Package templates embeds all HTML template files into the compiled binary.
//
// # go:embed — Compile-Time File Embedding (for Laravel/Django developers)
//
// In Laravel, template files (Blade files in resources/views/) are loaded from
// disk at runtime. You deploy the PHP code AND the template files together.
// If a template file is missing on the server, you get a runtime error.
//
// In Django, templates (in templates/) are also loaded from disk at runtime,
// configured via TEMPLATES['DIRS'] in settings.py. Same issue — missing
// templates cause runtime errors.
//
// Go takes a different approach with the //go:embed directive (added in Go 1.16).
// It tells the compiler to READ the files at build time and EMBED their contents
// directly into the compiled binary. The result:
//
//   - The binary is self-contained — no template files to deploy separately
//   - Missing templates cause COMPILE-TIME errors, not runtime errors
//   - The binary is larger (includes all template content), but deployment is simpler
//   - Templates cannot be modified without recompiling (no live editing in production)
//
// This is similar to:
//   - Laravel Mix/Vite bundling JS/CSS into a single file
//   - Webpack's raw-loader embedding files into the JS bundle
//   - Docker multi-stage builds that copy files into the final image
//
// # How embed.FS Works
//
// embed.FS implements the io/fs.FS interface — Go's virtual filesystem abstraction.
// Any code that accepts an fs.FS can work with embedded files OR real disk files
// interchangeably. This makes testing easy (use real files) while production
// uses embedded files.
//
// The //go:embed directive supports glob patterns:
//   - layouts/*.html     → all .html files in the layouts/ subdirectory
//   - components/*.html  → all .html files in the components/ subdirectory
//   - pages/*.html       → all .html files in the pages/ subdirectory
//   - partials/*.html    → all .html files in the partials/ subdirectory
//
// These paths are relative to this Go source file's directory.
//
// See: https://pkg.go.dev/embed (official embed package documentation)
// See: https://pkg.go.dev/io/fs#FS (the filesystem interface embed.FS implements)
// See: https://go.dev/blog/go1.16 (blog post introducing go:embed)
package templates

import "embed"

// FS contains all HTML template files embedded at compile time.
//
// The //go:embed directive on the NEXT LINE (it must be a comment directly
// above the variable) tells the Go compiler which files to include. Multiple
// patterns are space-separated. The variable must be of type string, []byte,
// or embed.FS. We use embed.FS because we need to access multiple files
// (html/template.ParseFS reads from an fs.FS).
//
// Usage in the application (in internal/handler/):
//
//	tmpl, err := template.ParseFS(templates.FS, "layouts/base.html", "pages/home.html")
//
// This is like Blade's @extends('layouts.base') + @section('content'), but
// the template resolution happens through Go's template engine instead of
// Blade's compiler. Django's equivalent would be {% extends "base.html" %}.
//
//go:embed layouts/*.html components/*.html pages/*.html partials/*.html
var FS embed.FS
