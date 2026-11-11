{% load static %}/* Service worker for the installed app.

   Served at /sw.js by web.views.service_worker. It is a template so the file
   paths below come from {% templatetag openblock %} static {% templatetag closeblock %} and stay right if STATIC_URL changes.

   What it does:
   - css, js, icons and product photos load from the phone at once and are
     refreshed in the background, so the app opens fast;
   - pages always come from the server, because they carry each dealer's own
     orders and prices and a fresh CSRF token. Only when there is no internet
     does it fall back: to the last copy of a public page, else the offline page.
   - POSTs, the admin, the API and login are never touched. */

const VERSION = "om-v{{ version }}";
const STATIC_CACHE = VERSION + "-static";
const IMAGE_CACHE = VERSION + "-images";
const PAGE_CACHE = VERSION + "-pages";
const MAX_IMAGES = 150;

const OFFLINE_URL = "{% url 'web:offline' %}";
const PUBLIC_PAGES = ["{% url 'web:home' %}", "{% url 'web:install' %}"];
const STATIC_PREFIX = "{% get_static_prefix %}";
const MEDIA_PREFIX = "{% get_media_prefix %}";
const SKIP = ["/admin/", "/api/", "/accounts/"];

const PRECACHE = [
  OFFLINE_URL,
  "{% static 'assets/css/style.css' %}",
  "{% static 'assets/css/web.css' %}",
  "{% static 'assets/css/pwa.css' %}",
  "{% static 'assets/js/shell.js' %}",
  "{% static 'assets/js/main.js' %}",
  "{% static 'assets/js/pwa.js' %}",
  "{% static 'assets/pwa/icon-192.png' %}",
  "{% static 'assets/pwa/favicon-32.png' %}",
  "{% static 'assets/imgs/product-placeholder.png' %}",
];

/* ---------------------------------------------------------------- install */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

/* --------------------------------------- activate: drop old versions' caches */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((name) => !name.startsWith(VERSION)).map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

/* ------------------------------------------------------------------ fetch */
self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const ownSite = url.origin === self.location.origin;
  if (ownSite && SKIP.some((prefix) => url.pathname.startsWith(prefix))) return;

  if (request.mode === "navigate") {
    event.respondWith(pageFromNetwork(request, url));
    return;
  }

  if (ownSite && url.pathname.startsWith(STATIC_PREFIX)) {
    event.respondWith(cacheThenRefresh(event, request, STATIC_CACHE));
  } else if (ownSite && url.pathname.startsWith(MEDIA_PREFIX) && request.destination === "image") {
    event.respondWith(cacheThenRefresh(event, request, IMAGE_CACHE));
  } else if (url.hostname === "unpkg.com") {
    // the icon font (ionicons) — without it every button is blank offline
    event.respondWith(cacheThenRefresh(event, request, STATIC_CACHE));
  }
});

/* Pages: network first. Keep a copy of the public pages only — never a
   signed-in page, which holds one dealer's private data. */
async function pageFromNetwork(request, url) {
  try {
    const response = await fetch(request);
    if (response.ok && PUBLIC_PAGES.includes(url.pathname)) {
      const cache = await caches.open(PAGE_CACHE);
      cache.put(url.pathname, response.clone());
    }
    return response;
  } catch (err) {
    const cache = await caches.open(PAGE_CACHE);
    return (await cache.match(url.pathname)) || (await caches.match(OFFLINE_URL));
  }
}

/* Files: answer from the cache straight away, fetch a fresh copy behind it. */
async function cacheThenRefresh(event, request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const refresh = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone()).then(() => {
          if (cacheName === IMAGE_CACHE) trim(IMAGE_CACHE, MAX_IMAGES);
        });
      }
      return response;
    })
    .catch(() => cached || Response.error());

  if (cached) {
    event.waitUntil(refresh);
    return cached;
  }
  return refresh;
}

/* Product photos add up; keep only the most recent few. */
async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - max))) {
    await cache.delete(key);
  }
}
