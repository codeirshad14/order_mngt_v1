/* ============================================================================
   Progressive web app — loaded on every page by templates/web/_pwa_head.html.

   1. Registers the service worker (/sw.js).
   2. Runs every "Get App" button ([data-pwa-install]), right on the page:
        - Android / desktop Chrome and Edge hand us an install prompt
          (beforeinstallprompt); a click opens it straight away;
        - iPhone has no prompt (nor does a browser that has not offered one
          yet), so a click opens a small popup with the steps for that device.
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
    if (!button) return;
    e.preventDefault();

    if (!installPrompt) {
      showSteps();
      return;
    }
    installPrompt.prompt();
    installPrompt.userChoice.then(function (choice) {
      if (choice.outcome === "accepted") root.classList.add("pwa-installed");
    }).finally(function () {
      // a prompt can only be used once; the next click shows the steps
      installPrompt = null;
      root.classList.remove("pwa-can-install");
    });
  });

  /* ------------------------------------------- steps popup (no prompt) */
  var STEPS = {
    ios: {
      title: "Install on iPhone or iPad",
      steps: [
        "Open this site in <strong>Safari</strong>.",
        'Tap <strong>Share</strong> <ion-icon name="share-outline"></ion-icon> at the bottom of the screen.',
        "Scroll down, tap <strong>Add to Home Screen</strong>, then <strong>Add</strong>.",
      ],
    },
    android: {
      title: "Install on Android",
      steps: [
        "Open this site in <strong>Chrome</strong>.",
        'Tap the <strong>&#8942;</strong> menu at the top right.',
        "Tap <strong>Install app</strong> (or <strong>Add to Home screen</strong>), then <strong>Install</strong>.",
      ],
    },
    desktop: {
      title: "Install on your computer",
      steps: [
        "Open this site in <strong>Chrome</strong> or <strong>Edge</strong>.",
        'Click the install icon <ion-icon name="download-outline"></ion-icon> at the right end of the address bar, or open the browser menu and choose <strong>Install</strong>.',
        "Click <strong>Install</strong>. The app opens in its own window.",
      ],
    },
  };

  var stepsDialog = null;

  function showSteps() {
    if (!stepsDialog) {
      var help = STEPS[platform()];
      stepsDialog = document.createElement("dialog");
      stepsDialog.className = "pwa-steps";
      stepsDialog.setAttribute("aria-labelledby", "pwaStepsTitle");
      stepsDialog.innerHTML = '<div class="pwa-steps__body">' +
        '<form method="dialog" class="pwa-steps__close">' +
        '<button class="icon-btn" aria-label="Close"><ion-icon name="close-outline"></ion-icon></button></form>' +
        '<img src="' + (document.querySelector('link[rel="apple-touch-icon"]') || {}).href +
        '" alt="" width="56" height="56">' +
        '<h2 id="pwaStepsTitle">' + help.title + "</h2>" +
        "<ol>" + help.steps.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ol>" +
        '<form method="dialog"><button class="btn btn--primary">Got it</button></form></div>';
      document.body.appendChild(stepsDialog);

      // a tap on the dimmed backdrop (outside the inner box) closes it too
      stepsDialog.addEventListener("click", function (e) {
        if (e.target === stepsDialog) stepsDialog.close();
      });
    }
    stepsDialog.showModal();
  }

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
