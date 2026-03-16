// Package models defines the domain structs shared across all layers.
//
// Laravel analogy: This is like your app/Models/ directory — each struct here
// is equivalent to an Eloquent model class. However, unlike Eloquent, Go structs
// are plain data containers with NO ORM magic. There are no $fillable, $casts,
// $hidden, or relationship methods baked in. Instead, the repository layer handles
// all database operations (see internal/repository/).
//
// Django analogy: Similar to models.py, but without the Meta class, managers, or
// querysets. Go separates data definition (here) from data access (repository layer).
//
// Key Go conventions for someone coming from PHP/Python:
//
//   - Struct tags (`json:"..." db:"..."`) are metadata annotations placed after
//     each field. They tell serialization libraries how to map struct fields to
//     JSON keys or database columns. Similar to $casts in Laravel or field options
//     like db_column in Django.
//     See: https://pkg.go.dev/reflect#StructTag
//
//   - Pointer types (*string, *float64) represent nullable fields.
//     nil = SQL NULL. In Laravel, this is like adding ->nullable() to a migration.
//     In Django, this is null=True on a field. A non-pointer string in Go can never
//     be nil — it defaults to "" (empty string), which is different from NULL.
//
//   - Exported (capitalized) names are public; unexported (lowercase) are private.
//     In Go there are no public/private/protected keywords — capitalization IS the
//     access modifier. Think of it like: Capital = public, lowercase = private.
//
//   - "Enums" don't exist as a language feature (unlike PHP 8.1 enums or Python's
//     enum.Enum). Instead, we create a named type (type X string) and define
//     constants of that type. This gives us type safety without a dedicated keyword.
//
//   - Methods on structs are defined outside the struct body using receiver syntax.
//     For example: func (a Account) IsCreditType() bool { ... }
//     This is like defining a method in a Laravel model or a Django model, but the
//     syntax is different — the receiver (a Account) replaces PHP's $this or Python's self.
package models

import "time"

// InstitutionType is a "string enum" for categorizing financial institutions.
//
// Go enum pattern: We define a named type (InstitutionType) based on string,
// then declare constants of that type. This is the idiomatic Go replacement for:
//   - PHP 8.1:  enum InstitutionType: string { case Bank = 'bank'; ... }
//   - Django:   class InstitutionType(models.TextChoices): BANK = 'bank', ...
//   - Python:   class InstitutionType(str, Enum): BANK = 'bank'
//
// The named type provides type safety — you can't accidentally pass a plain string
// where an InstitutionType is expected (the compiler catches it).
//
// See: https://go.dev/ref/spec#Constants
type InstitutionType string

const (
	InstitutionTypeBank    InstitutionType = "bank"    // traditional banks (HSBC, CIB, NBE)
	InstitutionTypeFintech InstitutionType = "fintech" // digital-first (Telda, ValU, Fawry)
	InstitutionTypeWallet  InstitutionType = "wallet"  // virtual institution for physical cash / wallet accounts
)

// Institution represents a financial institution (e.g., HSBC, CIB, Telda).
// Accounts belong to institutions — this is the top-level grouping.
//
// Laravel analogy: This is like a BelongsTo parent model — accounts reference
// an institution_id foreign key. But note there's no hasMany() or belongsTo()
// method here; relationships are handled by SQL JOINs in the repository layer.
//
// Django analogy: Like a model referenced by Account via a ForeignKey field.
//
// Struct tags explained for this model:
//   - `json:"id"` — when this struct is marshaled to JSON (e.g., for API responses),
//     the field name becomes "id" (lowercase). Without this tag, it would be "ID".
//   - `db:"id"` — used by the sqlx/pgx database library to map database column
//     names to struct fields. Similar to how Eloquent maps snake_case columns to
//     camelCase properties, but explicit.
//   - `json:"color,omitempty"` — the "omitempty" option means: if this field is nil
//     (or zero-value), omit it entirely from the JSON output. Like Laravel's
//     $hidden but conditional on emptiness.
type Institution struct {
	ID           string          `json:"id" db:"id"`
	UserID       string          `json:"user_id" db:"user_id"`
	Name         string          `json:"name" db:"name"`
	Type         InstitutionType `json:"type" db:"type"`
	Color        *string         `json:"color,omitempty" db:"color"` // hex color for UI theming; *string means nullable — nil = no color set (SQL NULL)
	Icon         *string         `json:"icon,omitempty" db:"icon"`   // optional icon path; pointer because not every institution has one
	DisplayOrder int             `json:"display_order" db:"display_order"`
	CreatedAt    time.Time       `json:"created_at" db:"created_at"` // time.Time is Go's equivalent of Carbon (Laravel) or datetime (Django)
	UpdatedAt    time.Time       `json:"updated_at" db:"updated_at"` // See: https://pkg.go.dev/time#Time
}
