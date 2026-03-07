// Package service — ExportService generates CSV exports of transactions.
// Like Laravel's Excel export or Django CSV response.
package service

import (
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"time"

	"github.com/ahmedelsamadisi/clearmoney/internal/repository"
)

type ExportService struct {
	txRepo *repository.TransactionRepo
}

func NewExportService(txRepo *repository.TransactionRepo) *ExportService {
	return &ExportService{txRepo: txRepo}
}

// ExportTransactionsCSV writes transactions in the given date range as CSV.
func (s *ExportService) ExportTransactionsCSV(ctx context.Context, w io.Writer, from, to time.Time) error {
	txs, err := s.txRepo.GetByDateRange(ctx, from, to)
	if err != nil {
		return fmt.Errorf("querying transactions: %w", err)
	}

	writer := csv.NewWriter(w)
	defer writer.Flush()

	// Header row
	if err := writer.Write([]string{
		"Date", "Type", "Amount", "Currency", "Account ID", "Category ID",
		"Note", "Is Building Fund", "Created At",
	}); err != nil {
		return err
	}

	for _, tx := range txs {
		note := ""
		if tx.Note != nil {
			note = *tx.Note
		}
		catID := ""
		if tx.CategoryID != nil {
			catID = *tx.CategoryID
		}

		record := []string{
			tx.Date.Format("2006-01-02"),
			string(tx.Type),
			fmt.Sprintf("%.2f", tx.Amount),
			string(tx.Currency),
			tx.AccountID,
			catID,
			note,
			fmt.Sprintf("%v", tx.IsBuildingFund),
			tx.CreatedAt.Format(time.RFC3339),
		}
		if err := writer.Write(record); err != nil {
			return err
		}
	}

	return nil
}
