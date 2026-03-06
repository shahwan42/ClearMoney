// Package templates embeds all HTML template files into the binary.
// This is like Laravel's views directory, but compiled into the executable
// so there's no need to deploy template files separately.
package templates

import "embed"

// FS contains all HTML template files embedded at compile time.
// The //go:embed directive tells the Go compiler to include these files
// in the binary — similar to how Laravel Mix bundles assets.
//
//go:embed layouts/*.html components/*.html pages/*.html
var FS embed.FS
