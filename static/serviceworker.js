// serviceworker.js

const CACHE_NAME = 'gymproject-cache-v1';
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

// Evento 'install': Se dispara cuando el Service Worker se instala.
// Aquí es donde guardamos los archivos principales en la caché.
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME )
      .then(cache => {
        console.log('Cache abierta');
        // Ojo: Las URLs de Django {% static %} no funcionarán aquí directamente.
        // Las registraremos en el HTML. Este es un placeholder conceptual.
        // Por ahora, nos enfocaremos en registrar el SW y la estrategia de fetch.
        return cache.addAll([]); // Empezamos con una caché vacía que llenaremos dinámicamente.
      })
  );
});

// Evento 'fetch': Se dispara cada vez que la app pide un recurso (un archivo, una imagen, etc.).
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Si el recurso está en la caché, lo devolvemos desde ahí (¡súper rápido!).
        if (response) {
          return response;
        }

        // Si no está en la caché, vamos a la red a buscarlo.
        return fetch(event.request).then(
          response => {
            // Si la respuesta no es válida, no la cacheamos.
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clonamos la respuesta porque solo se puede consumir una vez.
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        );
      })
  );
});

// Evento 'activate': Se dispara para limpiar cachés antiguas.
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
