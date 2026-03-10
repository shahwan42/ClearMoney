// Package models — account_test.go contains unit tests for Account methods.
//
// Go testing patterns for someone coming from PHP/Python:
//
// 1. FILE NAMING: Test files MUST end with _test.go. The Go toolchain automatically
//    discovers and runs them. This is like PHPUnit looking for *Test.php files or
//    pytest discovering test_*.py files.
//
// 2. PACKAGE: Test files use the same package as the code they test (package models).
//    This gives them access to all exported AND unexported symbols — like testing
//    a Laravel model from within the same namespace.
//
// 3. FUNCTION NAMING: Test functions must start with "Test" and take *testing.T.
//    Convention: TestTypeName_MethodName (e.g., TestAccount_IsCreditType).
//    Similar to PHPUnit's testMethodName() or pytest's test_method_name().
//
// 4. TABLE-DRIVEN TESTS: The Go community's standard pattern for testing multiple
//    inputs/outputs. You define a slice of test cases (like a data provider in
//    PHPUnit's @dataProvider or pytest's @pytest.mark.parametrize), then loop
//    through them. See TestAccount_IsCreditType below.
//
// 5. NO ASSERTIONS LIBRARY: Unlike PHPUnit's $this->assertEquals() or pytest's
//    assert, Go's testing package only provides t.Error/t.Fatal/t.Errorf. You
//    write plain if-statements for assertions. Some teams use testify for
//    assert/require, but the stdlib approach is idiomatic.
//
// 6. t.Errorf vs t.Fatalf:
//    - t.Errorf: logs failure but CONTINUES the test (like a soft assertion)
//    - t.Fatalf: logs failure and STOPS the test immediately (like a hard assertion)
//    Use t.Fatalf when subsequent code depends on this check passing.
//
// Run these tests with: go test ./internal/models/ -v
//
// See: https://pkg.go.dev/testing for the full testing package documentation
package models

import (
	"encoding/json"
	"testing"
)

// TestAccount_IsCreditType uses the TABLE-DRIVEN TEST pattern.
//
// This is the idiomatic Go way to test a function with multiple inputs.
// It's equivalent to:
//   - PHPUnit: @dataProvider with an array of [input, expected] pairs
//   - pytest:  @pytest.mark.parametrize("account_type,expected", [...])
//
// The pattern:
//   1. Define a slice of anonymous structs (each struct is one test case)
//   2. Loop through them with range
//   3. Assert the expected output for each case
//
// Anonymous structs (struct { ... } without a type name) are a Go convenience
// for one-off data structures. In PHP/Python you'd use an associative array/dict.
func TestAccount_IsCreditType(t *testing.T) {
	tests := []struct {
		accountType AccountType
		want        bool
	}{
		{AccountTypeSavings, false},
		{AccountTypeCurrent, false},
		{AccountTypePrepaid, false},
		{AccountTypeCreditCard, true},
		{AccountTypeCreditLimit, true},
	}
	for _, tt := range tests {
		// Create an Account with only the Type field set.
		// Go structs zero-initialize all unset fields (empty string, 0, false, nil).
		// This is unlike PHP where unset properties might cause errors.
		a := Account{Type: tt.accountType}
		if got := a.IsCreditType(); got != tt.want {
			// t.Errorf formats a message and marks the test as failed but continues.
			// The %s verb prints strings, %v prints any value in its default format.
			t.Errorf("IsCreditType() for %s = %v, want %v", tt.accountType, got, tt.want)
		}
	}
}

// TestAccount_AvailableCredit tests the credit calculation method.
//
// Notice the &limit syntax: since CreditLimit is *float64 (a pointer), you can't
// pass a literal value directly. You first assign to a variable (limit := 500000.0),
// then take its address with & (address-of operator). This creates a pointer to
// the variable.
//
// PHP equivalent: There's no direct equivalent — PHP doesn't have pointers.
// Python equivalent: Everything in Python is a reference, so this concept doesn't
// directly map. The closest analogy is Optional[float] in type hints.
func TestAccount_AvailableCredit(t *testing.T) {
	limit := 500000.0

	// Credit card with 120K used (balance is -120000)
	a := Account{
		Type:           AccountTypeCreditCard,
		CreditLimit:    &limit, // & takes the address of limit, creating a *float64 pointer
		CurrentBalance: -120000,
	}
	if got := a.AvailableCredit(); got != 380000 {
		t.Errorf("AvailableCredit() = %v, want 380000", got)
	}

	// No credit limit — CreditLimit is nil (its zero value as a pointer).
	// This tests the nil-guard in AvailableCredit().
	b := Account{Type: AccountTypeCurrent}
	if got := b.AvailableCredit(); got != 0 {
		t.Errorf("AvailableCredit() for non-credit = %v, want 0", got)
	}
}

// TestAccount_JSONSerialization tests round-trip JSON marshaling/unmarshaling.
//
// This verifies that struct tags (json:"...") work correctly — a struct can be
// serialized to JSON and deserialized back without data loss.
//
// json.Marshal = PHP's json_encode() or Python's json.dumps()
// json.Unmarshal = PHP's json_decode() or Python's json.loads()
//
// See: https://pkg.go.dev/encoding/json for Go's JSON package
func TestAccount_JSONSerialization(t *testing.T) {
	limit := 500000.0
	a := Account{
		ID:             "test-id",
		Name:           "HSBC Credit Card",
		Type:           AccountTypeCreditCard,
		Currency:       CurrencyEGP,
		CurrentBalance: -120000,
		CreditLimit:    &limit,
	}

	// Marshal: struct -> JSON bytes (like json_encode in PHP)
	data, err := json.Marshal(a)
	if err != nil {
		// t.Fatalf stops the test immediately — no point continuing if marshal failed.
		t.Fatalf("marshal: %v", err)
	}

	// Unmarshal: JSON bytes -> struct (like json_decode in PHP)
	// Note the &decoded — Unmarshal needs a pointer to write into.
	var decoded Account
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if decoded.Name != a.Name {
		// %q prints a string with quotes — useful for debugging whitespace issues
		t.Errorf("name = %q, want %q", decoded.Name, a.Name)
	}
	if decoded.Type != AccountTypeCreditCard {
		t.Errorf("type = %q, want %q", decoded.Type, AccountTypeCreditCard)
	}
}
