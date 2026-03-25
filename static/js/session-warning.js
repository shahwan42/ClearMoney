// session-warning.js — Warn users before session expires.
// Checks /api/session-status every 5 minutes and shows a warning banner
// when the session will expire within 24 hours.

(function() {
  var WARNING_THRESHOLD = 24 * 60 * 60; // 24 hours in seconds
  var CHECK_INTERVAL = 5 * 60 * 1000; // 5 minutes in ms
  var warningShown = false;

  function checkSession() {
    fetch('/api/session-status', { credentials: 'same-origin' })
      .then(function(r) {
        if (r.status === 401) {
          showExpiredBanner();
          return null;
        }
        return r.json();
      })
      .then(function(data) {
        if (!data) return;
        if (data.expires_in_seconds < WARNING_THRESHOLD && !warningShown) {
          showWarningBanner(data.expires_in_seconds);
          warningShown = true;
        }
      })
      .catch(function() { /* network error — skip silently */ });
  }

  function showWarningBanner(secondsLeft) {
    var hours = Math.floor(secondsLeft / 3600);
    var msg = hours > 0
      ? 'Your session expires in ' + hours + ' hour' + (hours !== 1 ? 's' : '') + '. '
      : 'Your session expires soon. ';

    var banner = document.createElement('div');
    banner.id = 'session-warning';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'polite');
    banner.className = 'fixed top-14 left-0 right-0 z-50 bg-amber-50 dark:bg-amber-900/30 border-b border-amber-200 dark:border-amber-700 px-4 py-2 text-sm text-amber-800 dark:text-amber-200 text-center';
    banner.innerHTML = msg
      + '<a href="/login" class="underline font-medium">Sign in again</a> to continue.'
      + '<button onclick="this.parentElement.remove()" class="ml-2 text-amber-500 hover:text-amber-700" aria-label="Dismiss">&times;</button>';
    document.body.appendChild(banner);
  }

  function showExpiredBanner() {
    if (document.getElementById('session-warning')) return;
    var banner = document.createElement('div');
    banner.id = 'session-warning';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'assertive');
    banner.className = 'fixed top-14 left-0 right-0 z-50 bg-red-50 dark:bg-red-900/30 border-b border-red-200 dark:border-red-700 px-4 py-2 text-sm text-red-700 dark:text-red-300 text-center';
    banner.innerHTML = 'Your session has expired. <a href="/login" class="underline font-medium">Sign in again</a>.';
    document.body.appendChild(banner);
  }

  // Start checking after page loads
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(checkSession, 10000); // First check after 10 seconds
      setInterval(checkSession, CHECK_INTERVAL);
    });
  } else {
    setTimeout(checkSession, 10000);
    setInterval(checkSession, CHECK_INTERVAL);
  }
})();
