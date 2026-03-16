// Package service — ExportService generates CSV exports of transactions.
//
// Generates downloadable CSV files with transaction history for a date range.
// The CSV format is universal — importable into Excel, Google Sheets, or other tools.
//
// Laravel analogy: Like using Laravel Excel (maatwebsite/excel) to export a collection
// to CSV, or a custom response with StreamedResponse and fputcsv(). In ClearMoney,
// Go's encoding/csv package handles the writing.
//
// Django analogy: Like a view that returns HttpResponse(content_type='text/csv') and
// uses csv.writer to write rows. Or Django REST Framework's CSVRenderer.
//
// Go pattern: The function accepts io.Writer (an interface), not a specific type.
// This means it can write to an HTTP response, a file, a buffer, or any other writer.
// This is Go's interface-based polymorphism — the caller decides WHERE to write.
// In PHP: you'd pass a resource or stream. In Python: a file-like object.
// See: https://pkg.go.dev/io#Writer
// See: https://pkg.go.dev/encoding/csv for Go's CSV writing package
package service

import (
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"time"

	"github.com/shahwan42/clearmoney/internal/logutil"
	"github.com/shahwan42/clearmoney/internal/repository"
)

// ExportService wraps the transaction repo for data export operations.
type ExportService struct {
	txRepo *repository.TransactionRepo
}

// NewExportService creates the export service with a transaction repository.
func NewExportService(txRepo *repository.TransactionRepo) *ExportService {
	return &ExportService{txRepo: txRepo}
}

// ExportTransactionsCSV writes transactions in the given date range as CSV.
//
// io.Writer is Go's key abstraction: it's an interface with a single Write method.
// Any type that has Write([]byte) (int, error) satisfies it — HTTP responses, files,
// buffers, etc. The handler passes http.ResponseWriter; tests could pass bytes.Buffer.
// This is Go's version of PHP's streams or Python's file-like objects.
//
// csv.NewWriter wraps the io.Writer and handles escaping, quoting, and newlines.
// `defer writer.Flush()` ensures all buffered data is written when the function returns.
func (s *ExportService) ExportTransactionsCSV(ctx context.Context, userID string, w io.Writer, from, to time.Time) error {
	txs, err := s.txRepo.GetByDateRange(ctx, userID, from, to)
	if err != nil {
		return fmt.Errorf("querying transactions: %w", err)
	}

	writer := csv.NewWriter(w)
	defer writer.Flush()

	// Header row
	if err := writer.Write([]string{
		"Date", "Type", "Amount", "Currency", "Account ID", "Category ID",
		"Note", "Created At",
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
			tx.CreatedAt.Format(time.RFC3339),
		}
		if err := writer.Write(record); err != nil {
			return err
		}
	}

	logutil.LogEvent(ctx, "export.csv_downloaded", "row_count", len(txs))
	return nil
}
