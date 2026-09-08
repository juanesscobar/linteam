const CACHE = "linteam-v1";
const APP_SHELL = ["/app/", "/app/manifest.webmanifest"];
self.addEventListener("install", (event) => { event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL))); self.skipWaiting(); });
self.addEventListener("activate", (event) => { event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))); self.clients.claim(); });
self.addEventListener("fetch", (event) => { if (event.request.method !== "GET") return; event.respondWith(fetch(event.request).catch(() => caches.match(event.request))); });
