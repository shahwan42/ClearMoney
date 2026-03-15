// Tests for the StructuredLogger middleware and device classification.
//
// Verifies that device classification (mobile/desktop/bot) works correctly
// for common User-Agent strings. The StructuredLogger middleware itself
// is tested through integration tests in the handler package.
package middleware

import "testing"

func TestClassifyDevice(t *testing.T) {
	tests := []struct {
		name string
		ua   string
		want string
	}{
		{"iPhone Safari", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1", "mobile"},
		{"Android Chrome", "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36", "mobile"},
		{"Desktop Chrome", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36", "desktop"},
		{"Desktop Firefox", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0", "desktop"},
		{"Googlebot", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "bot"},
		{"Bingbot", "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", "bot"},
		{"Spider", "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/) Spider", "bot"},
		{"Crawler", "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html) Crawler", "bot"},
		{"Empty UA", "", "desktop"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ClassifyDevice(tt.ua)
			if got != tt.want {
				t.Errorf("ClassifyDevice(%q) = %q, want %q", tt.ua, got, tt.want)
			}
		})
	}
}
