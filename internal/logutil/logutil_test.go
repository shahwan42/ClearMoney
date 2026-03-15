// Tests for context-aware logging helpers.
//
// Verifies that SetLogger/Log correctly inject and retrieve a *slog.Logger
// from context, that Log falls back to the default logger when none is set,
// and that LogEvent formats structured events with the "entity.action" naming
// convention used throughout ClearMoney's service layer.
package logutil

import (
	"bytes"
	"context"
	"log/slog"
	"strings"
	"testing"
)

func TestLog_FallsBackToDefault(t *testing.T) {
	ctx := context.Background()
	logger := Log(ctx)
	if logger == nil {
		t.Fatal("Log() returned nil for empty context")
	}
}

func TestLog_ReturnsInjectedLogger(t *testing.T) {
	var buf bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&buf, nil))

	ctx := SetLogger(context.Background(), logger)
	got := Log(ctx)

	got.Info("test message")
	if !strings.Contains(buf.String(), "test message") {
		t.Errorf("expected injected logger to write to buffer, got: %s", buf.String())
	}
}

func TestLogEvent_WritesEventField(t *testing.T) {
	var buf bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{Level: slog.LevelInfo}))
	ctx := SetLogger(context.Background(), logger)

	LogEvent(ctx, "transaction.created", "type", "expense", "currency", "EGP")

	output := buf.String()
	if !strings.Contains(output, "event=transaction.created") {
		t.Errorf("expected event field in output, got: %s", output)
	}
	if !strings.Contains(output, "type=expense") {
		t.Errorf("expected type field in output, got: %s", output)
	}
	if !strings.Contains(output, "currency=EGP") {
		t.Errorf("expected currency field in output, got: %s", output)
	}
}

func TestLogEvent_NoExtraFields(t *testing.T) {
	var buf bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&buf, nil))
	ctx := SetLogger(context.Background(), logger)

	LogEvent(ctx, "auth.logout")

	output := buf.String()
	if !strings.Contains(output, "event=auth.logout") {
		t.Errorf("expected event field in output, got: %s", output)
	}
}
