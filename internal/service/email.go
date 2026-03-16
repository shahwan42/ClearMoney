// email.go — Email service wrapping the Resend API for sending magic links.
//
// Isolated behind an interface-like struct so it can be swapped for testing
// or replaced with another provider later. In development mode, emails are
// logged to stdout instead of being sent.
//
// Laravel analogy: Like Mail::to($user)->send(new MagicLinkMail($token)) with
// a configurable driver (smtp, ses, log).
// Django analogy: Like send_mail() with EMAIL_BACKEND — can swap to console
// backend for development.
package service

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/resend/resend-go/v2"
)

// EmailService sends transactional emails via the Resend API.
type EmailService struct {
	client *resend.Client
	from   string  // verified sender address (e.g., "noreply@clearmoney.app")
	appURL string  // base URL for magic links (e.g., "https://clearmoney.app")
	devMode bool   // when true, log emails instead of sending
}

// NewEmailService creates a new email service.
// If apiKey is empty, dev mode is enabled (emails logged, not sent).
func NewEmailService(apiKey, from, appURL string) *EmailService {
	svc := &EmailService{
		from:   from,
		appURL: appURL,
	}
	if apiKey == "" {
		svc.devMode = true
		slog.Warn("email service running in dev mode (no RESEND_API_KEY) — emails will be logged, not sent")
	} else {
		svc.client = resend.NewClient(apiKey)
	}
	return svc
}

// IsDevMode returns true when the email service is in dev mode (no API key).
func (s *EmailService) IsDevMode() bool { return s.devMode }

// LinkURL returns the full magic link URL for a given token.
func (s *EmailService) LinkURL(token string) string {
	return fmt.Sprintf("%s/auth/verify?token=%s", s.appURL, token)
}

// SendMagicLink sends a magic link email to the given address.
// The link format is: {appURL}/auth/verify?token={token}
func (s *EmailService) SendMagicLink(ctx context.Context, to, token string) error {
	link := fmt.Sprintf("%s/auth/verify?token=%s", s.appURL, token)

	subject := "Sign in to ClearMoney"
	html := fmt.Sprintf(`
		<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
			<h2 style="color: #0d9488; margin-bottom: 24px;">ClearMoney</h2>
			<p style="color: #334155; font-size: 16px; line-height: 1.5;">Click the button below to sign in to your account. This link expires in 15 minutes.</p>
			<div style="margin: 32px 0;">
				<a href="%s" style="background-color: #0d9488; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600; display: inline-block;">Sign in to ClearMoney</a>
			</div>
			<p style="color: #94a3b8; font-size: 14px; line-height: 1.5;">If you didn't request this link, you can safely ignore this email.</p>
			<p style="color: #cbd5e1; font-size: 12px; margin-top: 32px;">If the button doesn't work, copy and paste this URL into your browser:<br>%s</p>
		</div>
	`, link, link)

	if s.devMode {
		slog.Info("magic link email (dev mode — not sent)",
			"to", to,
			"link", link,
		)
		return nil
	}

	params := &resend.SendEmailRequest{
		From:    s.from,
		To:      []string{to},
		Subject: subject,
		Html:    html,
	}

	_, err := s.client.Emails.Send(params)
	if err != nil {
		return fmt.Errorf("sending magic link email via Resend: %w", err)
	}

	slog.Info("magic link email sent", "to", to)
	return nil
}
