package models

import (
	"encoding/json"
	"testing"
)

func TestAccount_IsCreditType(t *testing.T) {
	tests := []struct {
		accountType AccountType
		want        bool
	}{
		{AccountTypeChecking, false},
		{AccountTypeSavings, false},
		{AccountTypeCurrent, false},
		{AccountTypePrepaid, false},
		{AccountTypeCreditCard, true},
		{AccountTypeCreditLimit, true},
	}
	for _, tt := range tests {
		a := Account{Type: tt.accountType}
		if got := a.IsCreditType(); got != tt.want {
			t.Errorf("IsCreditType() for %s = %v, want %v", tt.accountType, got, tt.want)
		}
	}
}

func TestAccount_AvailableCredit(t *testing.T) {
	limit := 500000.0

	// Credit card with 120K used (balance is -120000)
	a := Account{
		Type:           AccountTypeCreditCard,
		CreditLimit:    &limit,
		CurrentBalance: -120000,
	}
	if got := a.AvailableCredit(); got != 380000 {
		t.Errorf("AvailableCredit() = %v, want 380000", got)
	}

	// No credit limit
	b := Account{Type: AccountTypeChecking}
	if got := b.AvailableCredit(); got != 0 {
		t.Errorf("AvailableCredit() for non-credit = %v, want 0", got)
	}
}

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

	data, err := json.Marshal(a)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var decoded Account
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if decoded.Name != a.Name {
		t.Errorf("name = %q, want %q", decoded.Name, a.Name)
	}
	if decoded.Type != AccountTypeCreditCard {
		t.Errorf("type = %q, want %q", decoded.Type, AccountTypeCreditCard)
	}
}
