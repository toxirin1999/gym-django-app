// serviceworker.js

const CACHE_NAME = 'gymproject-cache-v3';
// Lista de archivos estáticos principales de tu app para cachear.
// ¡IMPORTANTE! Debes ajustar esta lista a tus archivos reales.
const URLS_TO_CACHE = [
  '/', // La página de inicio
  '{% static "css/dashboard_bladestyle.css" %}',
  '{% static "css/blade-runner-atmosphere.css" %}',
  '{% static "js/cronometros.js" %}', // Ejemplo, añade tus JS importantes
  'https://cdn.tailwindcss.com', // Cachear Tailwind
  'https://cdn.jsdelivr.net/npm/chart.js' // Cachear Chart.js
];

self.addEventListener('install', event => {
  self.skipWaiting(); // Activate immediately, don't wait for old SW to be released
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll([])));
});

// Solo cachear archivos estáticos — nunca páginas HTML dinámicas de Django.
const STATIC_EXTENSIONS = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ico'];

function isStaticAsset(url) {
  const path = new URL(url).pathname;
  return STATIC_EXTENSIONS.some(ext => path.endsWith(ext)) || path.startsWith('/static/');
}

self.addEventListener('fetch', event => {
  // Solo interceptar GET; dejar pasar POST/PUT/etc. sin tocar
  if (event.request.method !== 'GET') return;

  // Páginas HTML de Django: siempre red primero, nunca cachear
  if (!isStaticAsset(event.request.url)) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Archivos estáticos: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (!response || response.status !== 200 || response.type !== 'basic') return response;
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    Promise.all([
      // Take control of all open pages immediately
      clients.claim(),
      // Delete all old caches
      caches.keys().then(names =>
        Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
      )
    ])
  );
});
