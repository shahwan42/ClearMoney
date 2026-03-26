// Push notification management for ClearMoney PWA.
// Handles permission requesting, subscription, and notification display.

async function initPush() {
  if (!('Notification' in window) || !('serviceWorker' in navigator)) {
    return;
  }

  // Check for pending notifications on each page load (polling approach)
  checkNotifications();
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
    if (!notifications || notifications.length === 0) return;

    // Load seen notification tags from localStorage
    let seenTags = JSON.parse(localStorage.getItem('push_seen') || '{}');

    // Auto-reset: remove tags that are no longer returned by server
    const currentTags = new Set(notifications.map(n => n.tag));
    for (const tag in seenTags) {
      if (!currentTags.has(tag)) {
        delete seenTags[tag];
      }
    }

    // Filter to only unseen notifications
    const unseenNotifications = notifications.filter(n => !(n.tag in seenTags));
    if (unseenNotifications.length === 0) {
      // All notifications have been seen; clear the banner
      const container = document.getElementById('notification-banner');
      if (container) {
        container.replaceChildren();
      }
      return;
    }

    // Show the first unseen notification
    const n = unseenNotifications[0];

    // Show in-app notification banner
    const container = document.getElementById('notification-banner');
    if (container) {
      const link = document.createElement('a');
      link.href = n.url;
      link.className = 'block bg-amber-50 border border-amber-200 rounded-xl p-3 mb-3';

      const title = document.createElement('p');
      title.className = 'text-sm font-medium text-amber-800';
      title.textContent = n.title;

      const body = document.createElement('p');
      body.className = 'text-xs text-amber-600';
      body.textContent = n.body;

      link.appendChild(title);
      link.appendChild(body);
      container.replaceChildren(link);
    }

    // Also show browser notification if permission granted
    if (Notification.permission === 'granted') {
      new Notification(n.title, { body: n.body, tag: n.tag });
    }

    // Mark this notification as seen
    seenTags[n.tag] = Date.now();
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
