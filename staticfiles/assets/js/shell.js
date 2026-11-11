/* ============================================================================
   App shell — the chrome every page shares (drawer, collapse, theme,
   command-search shortcut).

   The sidebar links themselves live in templates/mybase.html and are rendered
   by Django with {% url %}, so adding a page means editing that nav block.
   ========================================================================== */

const THEME_KEY = "om-theme";
const COLLAPSE_KEY = "om-nav-collapsed";
const MOBILE = 900;

/* ---------------------------------------------------------------- storage */
/* Private windows and blocked site-data both throw here, so every read and
   write is guarded and the UI falls back to its default. */
function readStore(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeStore(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* not fatal — the preference just won't survive a reload */
  }
}

/* ------------------------------------------------------------------ theme */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.querySelector("#themeToggle ion-icon");
  if (icon) icon.setAttribute("name", theme === "dark" ? "sunny-outline" : "moon-outline");
}

function initTheme() {
  const saved = readStore(THEME_KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"));

  const toggle = document.getElementById("themeToggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    writeStore(THEME_KEY, next);
  });
}

/* ----------------------------------------------------- drawer & collapse */
function initSidebar() {
  const app = document.getElementById("app");
  const toggle = document.getElementById("navToggle");
  const backdrop = document.getElementById("backdrop");
  if (!app || !toggle) return;

  const isMobile = () => window.innerWidth <= MOBILE;

  // desktop preference is remembered; the drawer always starts closed
  if (readStore(COLLAPSE_KEY) === "1") app.classList.add("is-collapsed");

  function closeDrawer() {
    app.classList.remove("is-drawer-open");
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", () => {
    if (isMobile()) {
      const open = app.classList.toggle("is-drawer-open");
      toggle.setAttribute("aria-expanded", String(open));
    } else {
      const collapsed = app.classList.toggle("is-collapsed");
      writeStore(COLLAPSE_KEY, collapsed ? "1" : "0");
    }
  });

  backdrop?.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && app.classList.contains("is-drawer-open")) {
      closeDrawer();
      toggle.focus();
    }
  });

  // picking a page closes the drawer behind you
  document.getElementById("sidebarNav")?.addEventListener("click", (e) => {
    if (e.target.closest(".nav__link") && isMobile()) closeDrawer();
  });

  // never leave the drawer stranded open when crossing the breakpoint
  let wasMobile = isMobile();
  window.addEventListener("resize", () => {
    if (isMobile() !== wasMobile) {
      closeDrawer();
      wasMobile = isMobile();
    }
  });
}

/* ------------------------------------------------------- search shortcut */
function initSearchShortcut() {
  const input = document.querySelector(".topbar .search input");
  if (!input) return;
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== input && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) {
      e.preventDefault();
      input.focus();
    }
  });
}

/* ------------------------------------------------------------------ boot */
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initSidebar();
  initSearchShortcut();
});
