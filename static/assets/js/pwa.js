/* ============================================================================
   Progressive web app — loaded on every page by templates/web/_pwa_head.html.

   1. Registers the service worker (/sw.js).
   2. Runs every "Get App" button ([data-pwa-install]). Each one is a plain
      link to the install page, so it always does something:
        - Android / desktop Chrome and Edge hand us an install prompt
          (beforeinstallprompt); a click then opens it straight away;
        - iPhone has no prompt, so the link opens the page that shows the
          Share -> Add to Home Screen steps.
      Inside the installed app the buttons hide themselves.
   3. Shows a small "You are offline" bar when the connection drops.
   4. Keeps the phone's status-bar colour in step with the dark-mode switch.
   ========================================================================== */
(function () {
  "use strict";

  var swUrl = document.currentScript && document.currentScript.dataset.sw;
  var root = document.documentElement;
  var installPrompt = null;

  /* ------------------------------------------------------------- helpers */
  function isInstalled() {
    return window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
  }

  // "ios", "android" or "desktop" — the install page shows that one's steps first
  function platform() {
    var ua = navigator.userAgent;
    var iPadOS = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
    if (/iPhone|iPad|iPod/.test(ua) || iPadOS) return "ios";
    if (/Android/.test(ua)) return "android";
    return "desktop";
  }

  function installButtons() {
    return document.querySelectorAll("[data-pwa-install]");
  }

  /* ----------------------------------------------------- service worker */
  if (swUrl && "serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(swUrl, { scope: "/" }).catch(function () {
        /* not fatal: the site works the same, it just is not installable */
      });
    });
  }

  /* ----------------------------------------------------- install prompt */
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();            // hold it for our own button
    installPrompt = e;
    root.classList.add("pwa-can-install");
  });

  window.addEventListener("appinstalled", function () {
    installPrompt = null;
    root.classList.remove("pwa-can-install");
    root.classList.add("pwa-installed");
  });

  document.addEventListener("click", function (e) {
    var button = e.target.closest("[data-pwa-install]");
    if (!button || !installPrompt) return;   // no prompt: let the link open the install page

    e.preventDefault();
    installPrompt.prompt();
    installPrompt.userChoice.then(function (choice) {
      if (choice.outcome === "accepted") root.classList.add("pwa-installed");
    }).finally(function () {
      // a prompt can only be used once; the next click follows the link
      installPrompt = null;
      root.classList.remove("pwa-can-install");
    });
  });

  /* ------------------------------------------------------- offline bar */
  function initOfflineBar() {
    var bar = document.createElement("div");
    bar.className = "pwa-offline";
    bar.setAttribute("role", "status");
    bar.innerHTML = '<ion-icon name="cloud-offline-outline"></ion-icon>' +
      "<span>You are offline. Changes will not save until you reconnect.</span>";
    document.body.appendChild(bar);

    function update() {
      bar.classList.toggle("is-on", !navigator.onLine);
    }
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
  }

  /* ------------------------------------------------- status-bar colour */
  var BAR_COLOURS = { light: "#ffffff", dark: "#181a2c" };

  function paintStatusBar() {
    var theme = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (meta) {
      meta.setAttribute("content", BAR_COLOURS[theme]);
    });
  }

  /* ---------------------------------------------------------------- boot */
  document.addEventListener("DOMContentLoaded", function () {
    root.setAttribute("data-platform", platform());

    if (isInstalled()) {
      root.classList.add("pwa-standalone");
      installButtons().forEach(function (b) { b.hidden = true; });
    }

    initOfflineBar();

    paintStatusBar();
    new MutationObserver(paintStatusBar).observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  });
})();
