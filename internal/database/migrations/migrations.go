// Package migrations embeds SQL migration files into the compiled Go binary.
//
// In Laravel, migration files live in database/migrations/ and are read from disk
// at runtime. In Django, migrations are Python files discovered by the framework.
//
// Go takes a different approach: the //go:embed directive below tells the Go compiler
// to bundle all .sql files in this directory INTO the binary itself at compile time.
// The result is a single executable that carries its own migrations — no need to
// ship a migrations folder alongside the binary in production.
//
// The embed.FS type acts like a read-only virtual filesystem. Other packages
// (like migrate.go) read from it as if reading from disk.
package migrations

// "embed" is a standard library package that enables the //go:embed directive.
// You don't call any functions from it directly — just importing it unlocks
// the //go:embed compiler directive below.
import "embed"

// The "//go:embed" below is a compiler directive (not a regular comment).
// The "//go:" prefix is special in Go — it instructs the compiler to do something
// at build time. Here, "//go:embed *.sql" means: "take every .sql file in this
// directory and bake them into the FS variable."
//
// FS is exported (uppercase) so other packages can access it.
// It satisfies the fs.FS interface, so any code expecting a filesystem can use it.
//go:embed *.sql
var FS embed.FS
