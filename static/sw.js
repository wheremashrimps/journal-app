// Folio's service worker. It's what lets Folio install as an app. It passes every request
// straight to the network: journal data is private and always fresh, so nothing is cached here.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
