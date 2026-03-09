// health.go — Health check endpoint for uptime monitoring and container orchestration.
//
// Every web application needs a health check endpoint that load balancers, Kubernetes,
// and monitoring tools can ping to verify the service is alive.
//
// Similar to:
//   - Laravel: Route::get('/healthz', fn() => response('ok', 200));
//   - Django: path('healthz/', lambda req: HttpResponse('ok'))
//
// This endpoint is registered outside the auth middleware group (see router.go),
// so it's publicly accessible without authentication.
package handler

import "net/http"

// Healthz is a minimal health check handler.
// Returns 200 OK with body "ok" if the server is running.
//
// This is a plain function with the http.HandlerFunc signature:
//   func(http.ResponseWriter, *http.Request)
//
// In Go, any function matching this signature can be used as an HTTP handler.
// This is different from Laravel/Django where you need a controller class —
// in Go, a single function is sufficient.
//
// The function name is exported (starts with uppercase H) so it can be
// referenced from other packages (like router.go and tests).
//
// See: https://pkg.go.dev/net/http#HandlerFunc
func Healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok"))
}
