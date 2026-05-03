// Push notification management for ClearMoney PWA.
// Handles permission requesting, subscription, and notification display.

async function initPush() {
  if (!('Notification' in window) || !('serviceWorker' in navigator)) {
    return;
  }

  // Check for pending notifications on each page load (polling approach)
  checkNotifications();

  // Re-check every 5 minutes for long-lived pages
  setInterval(checkNotifications, 5 * 60 * 1000);
}

// Request notification permission and subscribe to push.
async function requestNotificationPermission() {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return;
  }

  try {
    // Get VAPID public key from server
    const response = await fetch('/api/push/vapid-key');
    const { publicKey } = await response.json();

    if (!publicKey) {
      console.log('Push: No VAPID key configured');
      return;
    }

    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });

    // Send subscription to server
    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscription),
    });
  } catch (err) {
    console.error('Push: Subscription failed', err);
  }
}

// Check for pending notifications via polling.
// Dismiss state is stored in the DB (is_read=True) so it syncs across devices.
async function checkNotifications() {
  try {
    const response = await fetch('/api/push/check');
    if (!response.ok) return;

    const notifications = await response.json();
    const container = document.getElementById('notification-banner');
    if (!container) return;

    container.replaceChildren();

    if (!notifications || notifications.length === 0) return;

    // Show top notification (already priority-sorted by server)
    container.appendChild(buildBanner(notifications[0], container));

    // Collapse pill for additional alerts
    if (notifications.length > 1) {
      const extras = notifications.length - 1;
      const pill = document.createElement('a');
      pill.href = '/notifications';
      pill.className = 'block text-center text-xs font-medium text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/40 border border-amber-200 dark:border-amber-700 rounded-full px-3 py-1 mt-1 hover:bg-amber-200 dark:hover:bg-amber-800/60';
      pill.textContent = `${extras} more alert${extras > 1 ? 's' : ''} →`;
      container.appendChild(pill);
    }

    // Show browser notifications for unseen tags (deduped via localStorage)
    let seen = {};
    try { seen = JSON.parse(localStorage.getItem('push_seen') || '{}'); } catch (_) {}
    for (const n of notifications) {
      if (!(n.tag in seen) && Notification.permission === 'granted') {
        new Notification(n.title, { body: n.body, tag: n.tag });
      }
      seen[n.tag] = Date.now();
    }
    try { localStorage.setItem('push_seen', JSON.stringify(seen)); } catch (_) {}
  } catch (_) {
    // Silently fail — might be offline
  }
}

// Build a single notification banner element.
function buildBanner(n, container) {
  const csrf = container.dataset.csrf || '';

  const wrapper = document.createElement('div');
  wrapper.className = 'relative';

  const link = document.createElement('a');
  link.href = n.url;
  link.className = 'block bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl p-3 pr-8';

  const title = document.createElement('p');
  title.className = 'text-sm font-medium text-amber-800 dark:text-amber-300';
  title.textContent = n.title;

  const body = document.createElement('p');
  body.className = 'text-xs text-amber-600 dark:text-amber-400';
  body.textContent = n.body;

  link.appendChild(title);
  link.appendChild(body);

  const dismissBtn = document.createElement('button');
  dismissBtn.type = 'button';
  dismissBtn.className = 'absolute top-2 right-2 p-1 text-amber-400 hover:text-amber-600 dark:text-amber-500 dark:hover:text-amber-300';
  dismissBtn.setAttribute('aria-label', 'Dismiss notification');
  dismissBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
  dismissBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    wrapper.remove();
    try {
      await fetch(`/api/push/dismiss/${n.id}`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
      });
      // Re-check so collapse pill updates
      checkNotifications();
    } catch (_) {}
  });

  wrapper.appendChild(link);
  wrapper.appendChild(dismissBtn);
  return wrapper;
}

// Convert URL-safe base64 to Uint8Array (required by Push API).
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initPush);
