const CACHE_NAME = 'readlite-pwa-v1';

// Essential App Shell assets to pre-cache on install
const PRECACHE_ASSETS = [
  '/',
  '/static/custom.css',
  '/static/manifest.webmanifest',
  '/static/icons/icon.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png'
];

// Install: pre-cache app shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean up outdated cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network-first with offline fallback for pages and reading content
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only handle GET requests
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // Static assets: Cache-first with background network update
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // Fetch update in background
          fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
            }
          }).catch(() => {});
          return cachedResponse;
        }
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const copy = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // Navigation and Book Reading routes (/, /library/..., /read/...):
  // Network-first: always fetch fresh content when online, fallback to cache when offline
  event.respondWith(
    fetch(request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return networkResponse;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) {
          return cached;
        }
        // If navigating to an uncached page while offline, fallback to library root
        if (request.mode === 'navigate') {
          const rootCached = await caches.match('/');
          if (rootCached) {
            return rootCached;
          }
        }
        return new Response(
          '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Offline — ReadLite</title></head><body style="font-family:sans-serif;text-align:center;padding:50px;background:#111;color:#eee;"><h2>Offline</h2><p>This book or page has not been cached yet. Please open it once while online.</p><a href="/" style="color:#94a3b8;">Go to Library</a></body></html>',
          { headers: { 'Content-Type': 'text/html' } }
        );
      })
  );
});
