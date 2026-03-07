// Offline transaction queue using IndexedDB.
// When the user submits a transaction while offline, it's saved to IndexedDB.
// When connectivity is restored, queued transactions sync to the server.

const DB_NAME = 'clearmoney-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending_transactions';

// Open (or create) the IndexedDB database.
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Queue a transaction for later sync.
async function queueTransaction(formData) {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);

  const data = {};
  for (const [key, value] of formData.entries()) {
    data[key] = value;
  }
  data.queued_at = new Date().toISOString();

  store.add(data);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// Get all queued transactions.
async function getQueuedTransactions() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  const request = store.getAll();

  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Clear all queued transactions after successful sync.
async function clearQueue() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);
  store.clear();

  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// Get count of pending transactions.
async function getPendingCount() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  const request = store.count();

  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Sync all queued transactions to the server.
async function syncTransactions() {
  const transactions = await getQueuedTransactions();
  if (transactions.length === 0) return;

  try {
    const response = await fetch('/sync/transactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions: transactions }),
    });

    if (response.ok) {
      await clearQueue();
      updatePendingBadge(0);
      // Refresh the page to show updated data
      if (window.location.pathname === '/') {
        window.location.reload();
      }
    }
  } catch (err) {
    console.log('Sync failed, will retry later:', err);
  }
}

// Update the pending transactions badge in the UI.
function updatePendingBadge(count) {
  const badge = document.getElementById('pending-badge');
  if (badge) {
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }
}

// Initialize: check for pending transactions and set up online listener.
async function initOfflineQueue() {
  const count = await getPendingCount();
  updatePendingBadge(count);

  // Auto-sync when coming back online
  window.addEventListener('online', () => {
    syncTransactions();
  });

  // Try to sync on page load if online
  if (navigator.onLine && count > 0) {
    syncTransactions();
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initOfflineQueue);
} else {
  initOfflineQueue();
}
