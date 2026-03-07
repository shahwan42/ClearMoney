// Service Worker for ClearMoney PWA.
// Caches the app shell (layout, CSS, icons) for fast subsequent loads.
// This is like Laravel's asset caching but at the browser level.

const CACHE_NAME = 'clearmoney-v1';

// App shell resources to pre-cache on install.
const APP_SHELL = [
  '/',
  '/static/css/app.css',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  '/static/manifest.json',
];

// Install: pre-cache app shell resources.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  // Activate immediately without waiting for existing clients to close.
  self.skipWaiting();
});

// Activate: clean up old caches when a new version deploys.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  // Take control of all open tabs immediately.
  self.clients.claim();
});

// Fetch: network-first for HTML (pages), cache-first for static assets.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only handle same-origin requests.
  if (url.origin !== location.origin) return;

  // Static assets: cache-first (serve from cache, fall back to network).
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        });
      })
    );
    return;
  }

  // HTML pages: network-first (try network, fall back to cache).
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
});
