package models

import "time"

type ExchangeRateLog struct {
	ID        string    `json:"id" db:"id"`
	Date      time.Time `json:"date" db:"date"`
	Rate      float64   `json:"rate" db:"rate"`
	Source    *string   `json:"source,omitempty" db:"source"`
	Note      *string   `json:"note,omitempty" db:"note"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}
