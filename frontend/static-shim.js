/* Mode « 100 % navigateur » : CARRIVA sans serveur.
   Les appels d'API (fetch("/...")) sont interceptés et traités par les agents Python exécutés dans le navigateur (Pyodide / WebAssembly).
   Rien n'est envoyé à un serveur. Ce fichier n'est chargé que par la version statique (dist/), jamais par la version FastAPI. */
(() => {
  const BASE = window.PYODIDE_BASE || "pyodide/";
  const ASSET = /^\/(app\.css|sw\.js|cv-templates\.js|static-shim\.js|manifest\.webmanifest|icons\/|py\/|pyodide\/)/;
  const nativeFetch = window.fetch.bind(window);
  let booting = null;
  const MSG = {fr: "Chargement des agents (premier lancement, quelques secondes)…", en: "Loading the agents (first launch, a few seconds)…",
    de: "Agenten werden geladen (erster Start, einige Sekunden)…", es: "Cargando los agentes (primer inicio, unos segundos)…",
    it: "Caricamento degli agenti (primo avvio, qualche secondo)…", ar: "جارٍ تحميل الوكلاء (أول تشغيل، بضع ثوانٍ)…"};
  function banner(on){
    let b = document.getElementById("shimBanner");
    if(!on){ if(b) b.remove(); return; }
    if(b) return;
    b = document.createElement("div"); b.id = "shimBanner"; b.setAttribute("role", "status");
    b.style.cssText = "position:fixed;inset-inline:12px;bottom:12px;z-index:99999;padding:.7rem 1rem;border-radius:12px;background:#12306b;color:#fff;font:600 .9rem system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.4);text-align:center";
    const l = (document.documentElement.lang || "fr").slice(0, 2); b.textContent = MSG[document.getElementById("lang") ? document.getElementById("lang").value : l] || MSG.fr;
    document.body.appendChild(b);
  }
  function loadScript(src){ return new Promise((ok, ko) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => ko(new Error("Chargement impossible : " + src)); document.head.appendChild(s); }); }
  function boot(){
    if(booting) return booting;
    booting = (async () => {
      banner(true);
      try {
        await loadScript(BASE + "pyodide.js");
        const py = await window.loadPyodide({indexURL: new URL(BASE, document.baseURI).href});
        const files = await (await nativeFetch("py/files.json")).json();
        const dirs = new Set();
        for(const p of Object.keys(files)){ const parts = p.split("/"); for(let i = 1; i < parts.length; i++){ const d = "/home/pyodide/" + parts.slice(0, i).join("/"); if(!dirs.has(d)){ dirs.add(d); try { py.FS.mkdir(d); } catch(e){} } } }
        for(const [p, c] of Object.entries(files)) py.FS.writeFile("/home/pyodide/" + p, c);
        py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')\nfrom backend import static_api");
        const api = py.pyimport("backend.static_api");
        window.CARRIVA_STATIC = {ready: true, py};
        return api;
      } catch(e){ booting = null; throw e; } finally { banner(false); }
    })();
    return booting;
  }
  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if(typeof url === "string" && url.startsWith("/") && !url.startsWith("//") && !ASSET.test(url)){
      const u = new URL(url, location.origin);
      const method = (init.method || "GET").toUpperCase();
      const body = typeof init.body === "string" ? init.body : "";
      let out;
      try { const api = await boot(); out = JSON.parse(api.handle(method, u.pathname, u.search.slice(1), body)); }
      catch(e){ out = {status: 503, json: {detail: "Impossible de démarrer les agents dans le navigateur : " + e.message}}; }
      return new Response(JSON.stringify(out.json), {status: out.status, headers: {"content-type": "application/json"}});
    }
    return nativeFetch(input, init);
  };
  window.CARRIVA_STATIC = {ready: false, boot};
})();
