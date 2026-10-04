const CACHE_NAME = 'legacy-vault-v4';
const ASSETS = [
    '/style.css',
    '/app.js',
    '/camera.js',
    '/approval.js',
    '/manifest.json',
    '/icon.svg',
    '/static/pwa.js',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS).catch(() => undefined))
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        )).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' })
                .catch(() => caches.match('/').then((cached) => cached || Response.error()))
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cached) => cached || fetch(event.request, { cache: 'no-store' }).then((response) => {
            if (response.ok && event.request.url.startsWith(self.location.origin)) {
                const copy = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
            }
            return response;
        }).catch(() => Response.error()))
    );
});
