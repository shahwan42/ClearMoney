// Tests for shared validation helpers (requireTrimmedName, requireNotEmpty,
// requirePositive, requirePositiveInt, defaultDate). Verifies trimming,
// empty-string rejection, positive-number enforcement, and date defaults.
package service

import (
	"testing"
	"time"
)

func TestRequireTrimmedName(t *testing.T) {
	tests := []struct {
		name      string
		value     string
		fieldName string
		want      string
		wantErr   string
	}{
		{
			name:      "valid name",
			value:     "Savings",
			fieldName: "account name",
			want:      "Savings",
		},
		{
			name:      "trims whitespace",
			value:     "  Savings  ",
			fieldName: "account name",
			want:      "Savings",
		},
		{
			name:      "empty string",
			value:     "",
			fieldName: "account name",
			wantErr:   "account name is required",
		},
		{
			name:      "whitespace only",
			value:     "   ",
			fieldName: "institution name",
			wantErr:   "institution name is required",
		},
		{
			name:      "category field name",
			value:     "",
			fieldName: "category name",
			wantErr:   "category name is required",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := requireTrimmedName(tt.value, tt.fieldName)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error %q, got nil", tt.wantErr)
				}
				if err.Error() != tt.wantErr {
					t.Errorf("error = %q, want %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.want {
				t.Errorf("got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestRequireNotEmpty(t *testing.T) {
	tests := []struct {
		name      string
		value     string
		fieldName string
		wantErr   string
	}{
		{
			name:      "non-empty value",
			value:     "abc-123",
			fieldName: "account_id",
		},
		{
			name:      "empty string",
			value:     "",
			fieldName: "account_id",
			wantErr:   "account_id is required",
		},
		{
			name:      "different field name",
			value:     "",
			fieldName: "fund_name",
			wantErr:   "fund_name is required",
		},
		{
			name:      "transaction type field",
			value:     "",
			fieldName: "transaction type",
			wantErr:   "transaction type is required",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := requireNotEmpty(tt.value, tt.fieldName)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error %q, got nil", tt.wantErr)
				}
				if err.Error() != tt.wantErr {
					t.Errorf("error = %q, want %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestRequirePositive(t *testing.T) {
	tests := []struct {
		name      string
		value     float64
		fieldName string
		wantErr   string
	}{
		{
			name:      "positive value",
			value:     100.50,
			fieldName: "amount",
		},
		{
			name:      "zero",
			value:     0,
			fieldName: "amount",
			wantErr:   "amount must be positive",
		},
		{
			name:      "negative",
			value:     -5.0,
			fieldName: "amount",
			wantErr:   "amount must be positive",
		},
		{
			name:      "different field name",
			value:     0,
			fieldName: "monthly limit",
			wantErr:   "monthly limit must be positive",
		},
		{
			name:      "unit_price field",
			value:     -1.0,
			fieldName: "unit_price",
			wantErr:   "unit_price must be positive",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := requirePositive(tt.value, tt.fieldName)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error %q, got nil", tt.wantErr)
				}
				if err.Error() != tt.wantErr {
					t.Errorf("error = %q, want %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestRequirePositiveInt(t *testing.T) {
	tests := []struct {
		name      string
		value     int
		fieldName string
		wantErr   string
	}{
		{
			name:      "positive value",
			value:     12,
			fieldName: "num_installments",
		},
		{
			name:      "zero",
			value:     0,
			fieldName: "num_installments",
			wantErr:   "num_installments must be positive",
		},
		{
			name:      "negative",
			value:     -1,
			fieldName: "num_installments",
			wantErr:   "num_installments must be positive",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := requirePositiveInt(tt.value, tt.fieldName)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error %q, got nil", tt.wantErr)
				}
				if err.Error() != tt.wantErr {
					t.Errorf("error = %q, want %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestDefaultDate(t *testing.T) {
	t.Run("zero time returns now", func(t *testing.T) {
		before := time.Now()
		got := defaultDate(time.Time{})
		after := time.Now()

		if got.Before(before) || got.After(after) {
			t.Errorf("expected time between %v and %v, got %v", before, after, got)
		}
	})

	t.Run("non-zero time returns same", func(t *testing.T) {
		specific := time.Date(2025, 6, 15, 10, 30, 0, 0, time.UTC)
		got := defaultDate(specific)
		if !got.Equal(specific) {
			t.Errorf("got %v, want %v", got, specific)
		}
	})
}
