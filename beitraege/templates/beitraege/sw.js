// Service worker of the post pages (scope /beitraege/).
// Caches nothing private: only the offline page and the icon. Photos shared
// from the gallery (Android) wait in their own cache until "Neuer Beitrag"
// takes them.
const VERSION = 'beitraege-{{ version }}';
const SHARED = 'beitraege-geteilt';
const OFFLINE = '{{ offline_url }}';
const SHARE = '{{ share_url }}';
const NEW = '{{ new_url }}';
const ICON = '{{ icon_url }}';

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll([OFFLINE, ICON])));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys
      .filter((key) => key !== VERSION && key !== SHARED)
      .map((key) => caches.delete(key))))
    .then(() => self.clients.claim()));
});

async function takeShare(request) {
  const form = await request.formData();
  const cache = await caches.open(SHARED);
  for (const key of await cache.keys()) await cache.delete(key);
  const files = form.getAll('fotos').filter((f) => f && typeof f !== 'string' && f.size);
  let count = 0;
  for (const file of files.slice(0, 10)) {
    await cache.put(`${SHARE}${count}`, new Response(file, {headers: {
      'Content-Type': file.type || 'application/octet-stream',
      'X-Name': encodeURIComponent(file.name || `foto-${count}.jpg`),
    }}));
    count += 1;
  }
  const meta = {
    title: form.get('title') || '', text: form.get('text') || '', url: form.get('url') || '',
    count, more: Math.max(files.length - 10, 0),
  };
  await cache.put(`${SHARE}meta`, new Response(JSON.stringify(meta),
    {headers: {'Content-Type': 'application/json'}}));
  return Response.redirect(`${NEW}?geteilt=1`, 303);
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.method === 'POST' && url.pathname === SHARE) {
    event.respondWith(takeShare(request));
    return;
  }
  if (request.method === 'GET' && request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
  }
});
