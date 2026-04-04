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

    console.log('Push: Subscribed successfully');
  } catch (err) {
    console.error('Push: Subscription failed', err);
  }
}

// Check for pending notifications via polling (works without VAPID).
async function checkNotifications() {
  try {
    const response = await fetch('/api/push/check');
    if (!response.ok) return;

    const notifications = await response.json();
    if (!notifications || notifications.length === 0) {
      // No active notifications — clear banner and reset dismissed tags
      const container = document.getElementById('notification-banner');
      if (container) container.replaceChildren();
      localStorage.removeItem('push_dismissed');
      return;
    }

    // Load dismissed tags from localStorage
    let dismissedTags = JSON.parse(localStorage.getItem('push_dismissed') || '{}');

    // Auto-reset: remove dismissed tags that are no longer returned by server
    // (condition resolved — allow re-firing if it recurs)
    const currentTags = new Set(notifications.map(n => n.tag));
    for (const tag in dismissedTags) {
      if (!currentTags.has(tag)) {
        delete dismissedTags[tag];
      }
    }
    localStorage.setItem('push_dismissed', JSON.stringify(dismissedTags));

    // Filter out dismissed notifications
    const visibleNotifications = notifications.filter(n => !(n.tag in dismissedTags));

    const container = document.getElementById('notification-banner');
    if (!container) return;

    if (visibleNotifications.length === 0) {
      container.replaceChildren();
      return;
    }

    // Load seen tags for browser notification dedup
    let seenTags = JSON.parse(localStorage.getItem('push_seen') || '{}');

    // Auto-reset seen tags for resolved conditions
    for (const tag in seenTags) {
      if (!currentTags.has(tag)) {
        delete seenTags[tag];
      }
    }

    // Render all visible notifications in the banner
    container.replaceChildren();
    for (const n of visibleNotifications) {
      const wrapper = document.createElement('div');
      wrapper.className = 'relative';

      const link = document.createElement('a');
      link.href = n.url;
      link.className = 'block bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl p-3 pr-8 mb-2';

      const title = document.createElement('p');
      title.className = 'text-sm font-medium text-amber-800 dark:text-amber-300';
      title.textContent = n.title;

      const body = document.createElement('p');
      body.className = 'text-xs text-amber-600 dark:text-amber-400';
      body.textContent = n.body;

      link.appendChild(title);
      link.appendChild(body);

      // Dismiss button
      const dismissBtn = document.createElement('button');
      dismissBtn.type = 'button';
      dismissBtn.className = 'absolute top-2 right-2 p-1 text-amber-400 hover:text-amber-600 dark:text-amber-500 dark:hover:text-amber-300';
      dismissBtn.setAttribute('aria-label', 'Dismiss notification');
      dismissBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
      dismissBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        wrapper.remove();
        const dismissed = JSON.parse(localStorage.getItem('push_dismissed') || '{}');
        dismissed[n.tag] = Date.now();
        localStorage.setItem('push_dismissed', JSON.stringify(dismissed));
      });

      wrapper.appendChild(link);
      wrapper.appendChild(dismissBtn);
      container.appendChild(wrapper);

      // Show browser notification for unseen items
      if (!(n.tag in seenTags) && Notification.permission === 'granted') {
        new Notification(n.title, { body: n.body, tag: n.tag });
      }
      seenTags[n.tag] = Date.now();
    }

    localStorage.setItem('push_seen', JSON.stringify(seenTags));
  } catch (err) {
    // Silently fail — might be offline
  }
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
