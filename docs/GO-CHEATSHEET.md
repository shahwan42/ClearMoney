# Go Cheat Sheet for Laravel/Django Developers

> Quick reference for Go syntax and patterns used in this codebase.

---

## 1. Variables & Types

```go
// Go                              // PHP / Python equivalent
var name string = "Ahmed"          // $name = "Ahmed";  /  name = "Ahmed"
name := "Ahmed"                    // Same (short declaration — most common)
count := 42                        // Type inferred as int
balance := 50000.00                // Type inferred as float64

// Constants
const MaxRetries = 3               // define('MAX_RETRIES', 3)  /  MAX_RETRIES = 3

// Pointers (nullable values)
var note *string                   // $note = null;  /  note = None
s := "hello"
note = &s                          // note now points to the string "hello"
fmt.Println(*note)                 // Dereference: prints "hello"
```

## 2. Structs (Classes)

```go
// Defining a struct (like a class without methods)
type User struct {
    Name  string   // Public (uppercase = exported)
    email string   // Private (lowercase = unexported)
    Age   *int     // Nullable int (pointer)
}

// Creating instances
u := User{Name: "Ahmed", Age: nil}       // Like new User(['name' => 'Ahmed'])
u2 := User{}                              // Zero-value: Name="", email="", Age=nil

// Methods (like class methods)
func (u User) DisplayName() string {     // Receiver = the "self" or "$this"
    return u.Name
}
u.DisplayName()                           // Call the method
```

## 3. Interfaces

```go
// Go interfaces are implicit — no "implements" keyword needed.
// If a type has the methods, it satisfies the interface.

type Reader interface {
    Read(p []byte) (n int, err error)
}

// Any struct with a Read method automatically implements Reader.
// This is like Python's duck typing but with compile-time checks.
```

## 4. Error Handling

```go
// Go has NO try/catch. Functions return errors explicitly.

// Function that can fail:
func GetUser(id string) (User, error) {
    if id == "" {
        return User{}, fmt.Errorf("id cannot be empty")
    }
    // ...
    return user, nil  // nil error = success
}

// Calling it:
user, err := GetUser("123")
if err != nil {
    // Handle error (like catch block)
    log.Printf("failed: %v", err)
    return
}
// Use user safely here

// Wrapping errors (adding context):
if err != nil {
    return fmt.Errorf("getting user %s: %w", id, err)
    //                 ^-- adds context    ^-- wraps original error
}
```

## 5. Slices & Maps (Arrays & Dictionaries)

```go
// Slices (like PHP arrays / Python lists)
numbers := []int{1, 2, 3}
numbers = append(numbers, 4)            // numbers is now [1, 2, 3, 4]
first := numbers[0]                      // 1

// Maps (like PHP associative arrays / Python dicts)
ages := map[string]int{
    "Ahmed": 30,
    "Sara":  25,
}
ages["Ali"] = 28                         // Add entry
age, ok := ages["Ahmed"]                 // ok=true if key exists
```

## 6. Control Flow

```go
// If/else (no parentheses needed!)
if balance > 0 {
    fmt.Println("positive")
} else if balance == 0 {
    fmt.Println("zero")
} else {
    fmt.Println("negative")
}

// For loops (Go only has "for", no while/foreach)
for i := 0; i < 10; i++ { }             // Classic for loop
for _, item := range items { }           // foreach ($items as $item)
for key, value := range myMap { }        // foreach ($map as $key => $value)
for condition { }                        // while (condition) { }

// Switch
switch accountType {
case "checking", "savings":              // Multiple values in one case
    fmt.Println("debit account")
case "credit_card":
    fmt.Println("credit account")
default:
    fmt.Println("unknown")
}
```

## 7. Functions

```go
// Basic function
func add(a, b int) int {
    return a + b
}

// Multiple return values (VERY common in Go)
func divide(a, b float64) (float64, error) {
    if b == 0 {
        return 0, fmt.Errorf("division by zero")
    }
    return a / b, nil
}
result, err := divide(10, 3)

// Anonymous functions (closures)
handler := func(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("hello"))
}

// Variadic functions (like PHP's ...$args)
func sum(nums ...int) int { }
```

## 8. Goroutines & Concurrency

```go
// Goroutines are lightweight threads (like Python async tasks)
go doSomething()    // Runs doSomething() concurrently (non-blocking)

// This codebase uses goroutines sparingly:
// - The HTTP server handles each request in its own goroutine (automatic)
// - refresh_views.go refreshes materialized views concurrently
```

## 9. Packages & Imports

```go
package handler                   // This file belongs to the "handler" package

import (
    "fmt"                         // Standard library
    "net/http"                    // Standard library (nested package)

    "github.com/go-chi/chi/v5"   // Third-party package

    "github.com/ahmedelsamadisi/clearmoney/internal/models"  // Our code
)

// Using imported packages:
models.Account{}                  // Access exported names from other packages
chi.NewRouter()                   // Using third-party package
```

## 10. Common Patterns in This Codebase

### Constructor Pattern
```go
// Go has no constructors. We use "New" functions instead.
// Like: $repo = new InstitutionRepo($db);

func NewInstitutionRepo(db *sql.DB) *InstitutionRepo {
    return &InstitutionRepo{db: db}
}
```

### Method Receiver Pattern
```go
// Methods are defined on structs using a "receiver" parameter.
// The receiver is like $this in PHP or self in Python.

func (r *InstitutionRepo) GetAll(ctx context.Context) ([]models.Institution, error) {
    // r is like $this — access r.db, etc.
}

// * (pointer receiver) = method can modify the struct (most common)
// No * (value receiver) = method gets a copy (for read-only methods)
```

### The Blank Identifier _
```go
// _ discards a value you don't need (like $_ in PHP)
for _, item := range items { }   // Don't need the index
result, _ := someFunc()          // Intentionally ignoring the error
```

### Defer (like try/finally)
```go
func readFile() {
    f, _ := os.Open("file.txt")
    defer f.Close()              // Will run when function returns (like finally)
    // ... use f ...
}                                // f.Close() runs here automatically
```

### Type Assertions
```go
// Converting interface{} (any) to a specific type
value, ok := someInterface.(string)  // ok is true if it's actually a string
```

---

## 11. SQL in Go

```go
// Single row query (like $user = User::find($id))
row := db.QueryRowContext(ctx,
    `SELECT id, name FROM users WHERE id = $1`, id)
//                                          ^-- PostgreSQL placeholder ($1, $2, ...)
//                                              (MySQL uses ? instead)

var user User
err := row.Scan(&user.ID, &user.Name)
//              ^-- & = "scan into this variable" (pointer/reference)

// Multiple rows (like User::all())
rows, err := db.QueryContext(ctx, `SELECT id, name FROM users`)
defer rows.Close()  // Always close rows when done
for rows.Next() {
    var u User
    rows.Scan(&u.ID, &u.Name)
    users = append(users, u)
}

// Insert with RETURNING (PostgreSQL feature)
err := db.QueryRowContext(ctx,
    `INSERT INTO users (name) VALUES ($1) RETURNING id, created_at`,
    user.Name,
).Scan(&user.ID, &user.CreatedAt)

// Database transactions (atomic operations)
tx, err := db.BeginTx(ctx, nil)      // Start transaction
defer tx.Rollback()                   // Rollback if we don't commit
// ... do multiple queries using tx instead of db ...
tx.Commit()                           // Commit all changes atomically
```

---

## 12. HTTP in Go

```go
// Handler function signature (every HTTP handler looks like this)
func MyHandler(w http.ResponseWriter, r *http.Request) {
    // w = response writer (like Laravel's Response or Django's HttpResponse)
    // r = request (like Laravel's Request or Django's HttpRequest)

    // Read query params
    name := r.URL.Query().Get("name")          // $_GET['name'] / request.GET['name']

    // Read form data
    r.ParseForm()
    email := r.FormValue("email")              // $_POST['email'] / request.POST['email']

    // Read JSON body
    var data MyStruct
    json.NewDecoder(r.Body).Decode(&data)      // json_decode(file_get_contents('php://input'))

    // Read URL params (chi router)
    id := chi.URLParam(r, "id")                // Route::get('/users/{id}', ...)

    // Write response
    w.WriteHeader(http.StatusOK)               // http_response_code(200)
    w.Write([]byte("hello"))                   // echo "hello"

    // Write JSON
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(data)            // return response()->json($data)

    // Redirect
    http.Redirect(w, r, "/login", http.StatusSeeOther)  // return redirect('/login')
}
```

---

## 13. Testing in Go

```go
// Test file must end with _test.go
// Test function must start with Test
// Test function receives *testing.T

func TestAdd(t *testing.T) {
    result := add(2, 3)
    if result != 5 {
        t.Errorf("expected 5, got %d", result)
    }
}

// Table-driven tests (very common in Go)
func TestDivide(t *testing.T) {
    tests := []struct {
        name    string
        a, b    float64
        want    float64
        wantErr bool
    }{
        {"normal", 10, 2, 5, false},
        {"zero", 10, 0, 0, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := divide(tt.a, tt.b)
            if (err != nil) != tt.wantErr {
                t.Errorf("error = %v, wantErr %v", err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("got %v, want %v", got, tt.want)
            }
        })
    }
}

// Run tests
// go test ./...              # All tests
// go test ./internal/service  # Just one package
// go test -run TestAdd        # Just one test
// go test -v                  # Verbose output
```
