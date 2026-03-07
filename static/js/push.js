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

    // Show in-app notification banner
    const container = document.getElementById('notification-banner');
    if (container && notifications.length > 0) {
      const n = notifications[0]; // show the most important one
      container.innerHTML = `
        <a href="${n.url}" class="block bg-amber-50 border border-amber-200 rounded-xl p-3 mb-3">
          <p class="text-sm font-medium text-amber-800">${n.title}</p>
          <p class="text-xs text-amber-600">${n.body}</p>
        </a>
      `;
    }

    // Also show browser notification if permission granted
    if (Notification.permission === 'granted' && notifications.length > 0) {
      const n = notifications[0];
      new Notification(n.title, { body: n.body, tag: n.tag });
    }
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
