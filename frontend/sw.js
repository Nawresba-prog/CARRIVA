/* Service worker CARRIVA : coque de l'application disponible hors ligne.
   Règles de sécurité : seules les ressources statiques de même origine sont mises en cache ; l'API, l'authentification et tout ce qui
   n'est pas un GET ne passent JAMAIS par le cache (aucune donnée personnelle n'est stockée par ce fichier). */
const VERSION = "carriva-v2";
const SHELL = ["/", "/cv-templates.js", "/app.css", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];
const STATIC = /^\/(cv-templates\.js|manifest\.webmanifest|app\.css|i18n\.js|icons\/[\w.-]+\.png)$/;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if(req.method !== "GET" || url.origin !== self.location.origin) return;           // API en POST, tiers : réseau uniquement
  if(req.mode === "navigate" && url.pathname === "/"){                               // page : réseau d'abord, copie hors ligne en secours
    e.respondWith(fetch(req).then(r => { if(r.ok){ const c = r.clone(); caches.open(VERSION).then(x => x.put("/", c)); } return r; }).catch(() => caches.match("/")));
    return;
  }
  if(STATIC.test(url.pathname)){                                                     // statiques : cache d'abord, rafraîchi en arrière-plan
    e.respondWith(caches.match(req).then(hit => {
      const net = fetch(req).then(r => { if(r.ok){ const c = r.clone(); caches.open(VERSION).then(x => x.put(req, c)); } return r; }).catch(() => hit);
      return hit || net;
    }));
  }
  /* tout le reste (GET d'API : /jobs, /trainings, /auth, /mail…) : pas d'interception → réseau, jamais de cache */
});
