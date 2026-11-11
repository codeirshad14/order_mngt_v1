/* ============================================================================
   Page widgets — small, self-registering behaviours. Each one no-ops on pages
   that don't contain its markup, so every page can load this single file.
   ========================================================================== */

/* ------------------------------------------------------------------ tabs */
/* <div class="tabs"><button data-tab="profile" class="is-active">…</button></div>
   <section class="tab-panel" data-panel="profile">…</section>            */
function initTabs() {
  document.querySelectorAll(".tabs").forEach((tabs) => {
    const scope = tabs.closest("[data-tabs-scope]") || document;

    tabs.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tab]");
      if (!btn) return;

      tabs.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("is-active", b === btn);
        b.setAttribute("aria-selected", String(b === btn));
      });
      scope.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.hidden = panel.dataset.panel !== btn.dataset.tab;
      });
    });
  });
}

/* -------------------------------------------------- segmented row filter */
/* Filters the rows of the table named by data-filter-target, matching each
   row's data-status against the clicked button's data-filter.            */
function initSegments() {
  document.querySelectorAll(".segment[data-filter-target]").forEach((seg) => {
    const table = document.querySelector(seg.dataset.filterTarget);
    if (!table) return;

    seg.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-filter]");
      if (!btn) return;

      seg.querySelectorAll("button").forEach((b) =>
        b.classList.toggle("is-active", b === btn)
      );

      const want = btn.dataset.filter;
      table.querySelectorAll("tbody tr").forEach((row) => {
        row.hidden = want !== "all" && row.dataset.status !== want;
      });
      updateEmptyState(table);
    });
  });
}

/* ----------------------------------------------------------- text search */
/* <input data-search-target="#ordersTable"> filters rows by text content.
   The target can be a table (its tbody rows are filtered) or any container
   such as the shop's card grid (its direct children are). */
function searchItems(target) {
  return target.tBodies?.length
    ? [...target.querySelectorAll("tbody tr")]
    : [...target.children];
}

function initTableSearch() {
  document.querySelectorAll("[data-search-target]").forEach((input) => {
    const table = document.querySelector(input.dataset.searchTarget);
    if (!table) return;

    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      searchItems(table).forEach((row) => {
        row.hidden = q !== "" && !row.textContent.toLowerCase().includes(q);
      });
      updateEmptyState(table);
    });
  });
}

/* Re-adds the totals row from the rows still on screen.

   A table whose totals come from the server is right until the search box
   hides some rows in the browser — then the figures underneath describe
   orders that are no longer visible. Each body cell that counts carries
   data-sum="name", and the totals cell that holds it data-sum-total="name",
   so nothing here depends on column positions or colspans.

   Money is added as paise and divided back at the end: adding 0.1 + 0.2 as
   floats gives 0.30000000000000004, and a totals row must not show that. */
function retotal(table) {
  const foot = table.tFoot;
  if (!foot) return;

  const rows = [...table.querySelectorAll("tbody tr")].filter((tr) => !tr.hidden);

  foot.querySelectorAll("[data-sum-total]").forEach((cell) => {
    const name = cell.dataset.sumTotal;
    let paise = 0;
    let decimals = 0;

    rows.forEach((row) => {
      const source = row.querySelector(`[data-sum="${name}"]`);
      if (!source) return;
      const text = source.textContent.replace(/[^0-9.-]/g, "");
      const value = parseFloat(text);
      if (Number.isNaN(value)) return;
      // how many decimals the column is printed to — a quantity has none
      decimals = Math.max(decimals, (text.split(".")[1] || "").length);
      paise += Math.round(value * 100);
    });

    const total = paise / 100;
    const target = cell.querySelector("strong") || cell;
    target.textContent = decimals ? total.toFixed(2) : String(total);
  });
}

/* Shows the sibling [data-empty] block when a filter hides every row, keeps
   the "N products" count in the toolbar honest, and re-adds the totals. */
function updateEmptyState(table) {
  const panel = table.closest(".panel");
  if (!panel) return;

  const visible = searchItems(table).filter((el) => !el.hidden).length;

  const count = panel.querySelector("[data-visible-count]");
  if (count) count.textContent = visible;

  if (table.tagName === "TABLE") retotal(table);

  const empty = panel.querySelector("[data-empty]");
  if (!empty) return;
  empty.hidden = visible > 0;
  table.hidden = visible === 0;
}

/* ----------------------------------------------------------------- inbox */
function initInbox() {
  const list = document.querySelector(".inbox__list");
  if (!list) return;

  list.addEventListener("click", (e) => {
    const thread = e.target.closest(".thread");
    if (!thread) return;

    list.querySelectorAll(".thread").forEach((t) =>
      t.classList.toggle("is-active", t === thread)
    );
    thread.classList.remove("is-unread");

    // swap the conversation header to the selected thread
    const view = document.querySelector(".inbox__view");
    if (!view) return;
    const name = thread.querySelector(".thread__name")?.textContent.trim();
    const avatar = thread.querySelector(".avatar")?.innerHTML;
    const head = view.querySelector(".inbox__head");
    if (name && head) {
      head.querySelector("strong").textContent = name;
      const headAvatar = head.querySelector(".avatar");
      if (headAvatar && avatar) headAvatar.innerHTML = avatar;
    }
  });
}

/* Keeps the composer from submitting and appends the typed line locally, so
   the static page still feels alive. */
function initComposer() {
  const form = document.querySelector(".inbox__composer");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = form.querySelector("input");
    const text = input.value.trim();
    if (!text) return;

    const stream = document.querySelector(".inbox__messages");
    const bubble = document.createElement("div");
    bubble.className = "bubble bubble--out";
    bubble.textContent = text;

    const time = document.createElement("time");
    time.textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    bubble.appendChild(time);

    stream.appendChild(bubble);
    stream.scrollTop = stream.scrollHeight;
    input.value = "";
  });
}

/* ------------------------------------------------------------ pagination */
function initPagination() {
  document.querySelectorAll(".pagination__pages").forEach((pages) => {
    pages.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn || btn.disabled) return;
      pages.querySelectorAll("button").forEach((b) =>
        b.classList.toggle("is-active", b === btn)
      );
    });
  });
}

/* ------------------------------------------------ animate bars into view */
/* Progress fills start at 0 and grow to their inline width once in view. */
function initReveal() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const targets = document.querySelectorAll(".progress span[style*='width']");
  if (!targets.length) return;

  targets.forEach((el) => {
    el.dataset.finalWidth = el.style.width;
    el.style.width = "0%";
  });

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        if (el.dataset.finalWidth) el.style.width = el.dataset.finalWidth;
        io.unobserve(el);
      });
    },
    { threshold: 0.25 }
  );
  targets.forEach((el) => io.observe(el));
}

/* -------------------------------------------------- topbar profile menu */
/* Lives here rather than in shell.js, which is hand-maintained. */
function initUserMenu() {
  const btn = document.getElementById("userMenuBtn");
  const panel = document.getElementById("userMenu");
  if (!btn || !panel) return;

  const items = () => [...panel.querySelectorAll(".menu__item")];

  function open() {
    panel.hidden = false;
    btn.setAttribute("aria-expanded", "true");
  }
  function close({ refocus = false } = {}) {
    panel.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (refocus) btn.focus();
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    panel.hidden ? open() : close();
  });

  // clicking anywhere outside dismisses it
  document.addEventListener("click", (e) => {
    if (!panel.hidden && !panel.contains(e.target) && e.target !== btn) close();
  });

  document.addEventListener("keydown", (e) => {
    if (panel.hidden) return;
    if (e.key === "Escape") close({ refocus: true });
  });

  // arrow keys walk the menu once it's open
  panel.addEventListener("keydown", (e) => {
    if (!/^Arrow(Down|Up)$/.test(e.key)) return;
    e.preventDefault();
    const list = items();
    const i = list.indexOf(document.activeElement);
    const next = e.key === "ArrowDown" ? i + 1 : i - 1;
    list[(next + list.length) % list.length].focus();
  });

  btn.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      open();
      items()[0]?.focus();
    }
  });
}

/* ----------------------------------------------------- collapsed nav tips */
/* Shows the menu name beside the icon when the sidebar is a rail. The tooltip
   is a single fixed element on <body> because the sidebar clips its own
   children — see the .nav-tip note in style.css. */
function initNavTips() {
  const app = document.getElementById("app");
  const nav = document.getElementById("sidebarNav");
  if (!app || !nav) return;

  const tip = document.createElement("div");
  tip.className = "nav-tip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);

  // only in rail mode — the drawer and the full sidebar already show labels
  const isRail = () =>
    app.classList.contains("is-collapsed") && window.innerWidth > 900;

  function show(link) {
    if (!isRail()) return;
    const label =
      link.dataset.tip || link.querySelector(".nav__label")?.textContent.trim();
    if (!label) return;

    tip.textContent = label;
    tip.classList.add("is-visible");

    const r = link.getBoundingClientRect();
    const h = tip.offsetHeight;
    tip.style.left = `${r.right + 12}px`;
    // keep it on screen for links near the top or bottom edge
    const top = r.top + r.height / 2 - h / 2;
    tip.style.top = `${Math.max(8, Math.min(top, window.innerHeight - h - 8))}px`;
  }

  const hide = () => tip.classList.remove("is-visible");

  nav.addEventListener("mouseover", (e) => {
    const link = e.target.closest(".nav__link");
    if (link) show(link);
  });
  nav.addEventListener("mouseleave", hide);
  nav.addEventListener("focusin", (e) => {
    const link = e.target.closest(".nav__link");
    if (link) show(link);
  });
  nav.addEventListener("focusout", hide);

  // any movement invalidates the anchor point
  nav.addEventListener("scroll", hide);
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
  document.getElementById("navToggle")?.addEventListener("click", hide);
}

/* ------------------------------------------------ mobile bottom bar + sheet */
/* Four thumb targets on phones: Home, Catalog, Order, More. "More" opens a
   sheet whose rows are cloned from the rendered sidebar, so the full menu
   still comes from NAV_ITEMS in shell.js and is never duplicated here. */
/* `match` is the sidebar link's data-tip, spelled exactly as the template
   writes it — "Catelogs" is this project's spelling and the match is literal.
   It used to read "Catalogs", which matched nothing, so the Catalog tab fell
   through to a fallback path left over from the static mockup and every tap
   landed on a 404.

   There are no fallbacks any more. A sidebar link is the only source of a
   real URL here; if one is missing — a role that cannot see that menu — the
   tab is left out rather than pointed at a file that does not exist. */
const BOTTOM_TABS = [
  { label: "Home", icon: "home-outline", match: "Dashboard" },
  { label: "Catalog", icon: "journal-outline", match: "Catelogs" },
  { label: "Order", icon: "receipt-outline", match: "Orders" },
];

function initBottomBar() {
  const app = document.getElementById("app");
  const nav = document.getElementById("sidebarNav");
  if (!app || !nav) return;

  /* Reuse the link the sidebar actually rendered, so the bottom bar can only
     ever point where the sidebar points. */
  const linkFor = (tab) =>
    [...nav.querySelectorAll(".nav__link")].find((a) => a.dataset.tip === tab.match);

  const bar = document.createElement("nav");
  bar.className = "bottombar";
  bar.setAttribute("aria-label", "Primary");
  bar.innerHTML =
    BOTTOM_TABS.map((t) => {
      const link = linkFor(t);
      if (!link) return "";          // that menu is not open to this login
      const href = link.getAttribute("href");
      const badge = link.querySelector(".nav__count")?.outerHTML || "";
      /* Which tab is current is already worked out on the server and marked on
         the sidebar link. Reading it back from there beats body[data-page],
         which is a fixed string in the template and so never matched. */
      const here = link.classList.contains("is-active");
      return `
      <a href="${href}" class="bottombar__item${here ? " is-active" : ""}"
         ${here ? 'aria-current="page"' : ""}>
        <ion-icon name="${t.icon}"></ion-icon>
        <span>${t.label}</span>
        ${badge}
      </a>`;
    }).join("") +
    `
      <button type="button" class="bottombar__item" id="moreBtn"
              aria-haspopup="dialog" aria-expanded="false" aria-controls="moreSheet">
        <ion-icon name="ellipsis-horizontal-outline"></ion-icon>
        <span>More</span>
      </button>`;
  document.body.appendChild(bar);

  const sheet = document.createElement("div");
  sheet.className = "sheet";
  sheet.id = "moreSheet";
  sheet.innerHTML = `
    <div class="sheet__backdrop" data-close></div>
    <div class="sheet__panel" role="dialog" aria-modal="true" aria-label="All menus">
      <div class="sheet__grip"></div>
      <div class="sheet__head">
        <h2>All Menus</h2>
        <button class="icon-btn" type="button" data-close aria-label="Close menu">
          <ion-icon name="close-outline"></ion-icon>
        </button>
      </div>
      <div class="sheet__list"></div>
    </div>`;
  document.body.appendChild(sheet);

  const moreBtn = document.getElementById("moreBtn");
  const list = sheet.querySelector(".sheet__list");

  /* Cloned on open rather than at boot, so it reflects the sidebar even if
     something re-renders the nav later. */
  function fill() {
    list.innerHTML = "";
    nav.querySelectorAll(".nav__link").forEach((link) => {
      const row = link.cloneNode(true);
      row.className =
        "sheet__item" + (link.classList.contains("is-active") ? " is-active" : "");
      row.removeAttribute("data-tip");
      list.appendChild(row);
    });
  }

  function open() {
    fill();
    sheet.classList.add("is-open");
    moreBtn.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }
  function close() {
    sheet.classList.remove("is-open");
    moreBtn.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
  }

  moreBtn.addEventListener("click", open);
  sheet.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]") || e.target.closest(".sheet__item")) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && sheet.classList.contains("is-open")) {
      close();
      moreBtn.focus();
    }
  });
  // growing past the breakpoint hides the bar; don't strand the sheet open
  window.addEventListener("resize", () => {
    if (window.innerWidth > 900 && sheet.classList.contains("is-open")) close();
  });
}

/* ------------------------------------------------------------------ boot */
/* ------------------------------------------------------------------ modal */
/* <button data-modal-open="addProduct"> opens #addProduct; anything with
   data-modal-close inside it closes. A modal rendered with .is-open (the
   server does that when the form came back with errors) stays open on load. */
function initModals() {
  const modals = document.querySelectorAll(".modal");
  if (!modals.length) return;

  let lastFocused = null;

  function open(modal) {
    lastFocused = document.activeElement;
    modal.hidden = false;
    // let the browser paint the hidden state first so the transition runs
    requestAnimationFrame(() => modal.classList.add("is-open"));
    document.body.style.overflow = "hidden";
    modal.querySelector("input, select, textarea, button")?.focus();
  }

  function close(modal) {
    modal.classList.remove("is-open");
    document.body.style.overflow = "";
    lastFocused?.focus();
    // wait for the transition before hiding, but never hang if it doesn't fire
    const done = () => (modal.hidden = true);
    modal.addEventListener("transitionend", done, { once: true });
    setTimeout(done, 300);
  }

  document.querySelectorAll("[data-modal-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modal = document.getElementById(btn.dataset.modalOpen);
      if (modal) open(modal);
    });
  });

  modals.forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target.closest("[data-modal-close]")) close(modal);
    });
    // server said "reopen me" — it is already .is-open, just unhide it
    if (modal.classList.contains("is-open")) {
      modal.hidden = false;
      document.body.style.overflow = "hidden";
      modal.querySelector(".field-error")?.closest(".field")
        ?.scrollIntoView({ block: "center" });
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const openModal = document.querySelector(".modal.is-open");
    if (openModal) close(openModal);
  });
}

/* -------------------------------------------------------------- shop cart */
/* Each card's form posts through fetch instead of navigating, so adding to
   the cart never reloads the page. Without JS the forms still post normally.

   Bound once on the document rather than on each form: the search swaps the
   cards for new ones, and those have no listener of their own. */
function initShopCart() {
  const flash = document.querySelector(".content");
  if (!flash) return;

  function note(text, ok) {
    const el = document.createElement("div");
    el.className = "form-alert" + (ok ? " form-alert--ok" : "");
    el.textContent = text;
    flash.prepend(el);
    setTimeout(() => el.remove(), 2500);
  }

  /* Briefly turn the clicked button into a tick, so the confirmation lands
     where the finger was and not only in the toast at the top. */
  function confirmOn(btn) {
    const icon = btn?.querySelector("ion-icon");
    if (!icon) return;
    const was = icon.getAttribute("name");
    icon.setAttribute("name", "checkmark-outline");
    btn.classList.add("is-added");
    setTimeout(() => {
      icon.setAttribute("name", was);
      btn.classList.remove("is-added");
    }, 1400);
  }

  function redraw(cart) {
    // the shop has a live cart table; the products list just wants the toast
    const panel = document.getElementById("cartPanel");
    if (!panel) return;
    panel.hidden = false;
    panel.querySelector("[data-cart-no]").textContent = cart.order_no;
    panel.querySelector("[data-cart-link]").href = cart.url;
    panel.querySelector("[data-cart-qty]").textContent = cart.qty;
    panel.querySelector("[data-cart-total]").textContent = cart.total;

    panel.querySelector("[data-cart-rows]").replaceChildren(
      ...cart.items.map((item) => {
        const tr = document.createElement("tr");
        // textContent, never innerHTML — product names are user data
        for (const [value, cls] of [[item.name, ""], [item.qty, "num"], [item.total, "num"]]) {
          const td = document.createElement("td");
          td.textContent = value;
          if (cls) td.className = cls;
          tr.append(td);
        }
        return tr;
      })
    );
  }

  document.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-add-form]");
    if (!form) return;

    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;

    try {
      const res = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await res.json();
      if (data.ok) {
        redraw(data.cart);
        note(data.message, true);
        confirmOn(btn);
      } else {
        note(data.error, false);
      }
    } catch {
      form.submit(); // network or parsing trouble — fall back to a normal post
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

/* --------------------------------------------------- product detail images */
/* Click a thumbnail and it trades places with the large image, so Front is
   what you see by default and any side can take its place. */
function initDetailGallery() {
  const media = document.querySelector(".detail__media");
  if (!media) return;

  const mainFig = media.querySelector(".is-main");
  if (!mainFig) return;

  media.addEventListener("click", (e) => {
    const fig = e.target.closest("figure");
    if (!fig || fig === mainFig) return;

    const a = mainFig.querySelector("img");
    const b = fig.querySelector("img");
    const capA = mainFig.querySelector("figcaption");
    const capB = fig.querySelector("figcaption");

    [a.src, b.src] = [b.src, a.src];
    [a.alt, b.alt] = [b.alt, a.alt];
    [capA.textContent, capB.textContent] = [capB.textContent, capA.textContent];
  });
}

/* ------------------------------------------ type-to-pick product select */
/* Turns #id_product into a text box with a native dropdown: type any part of
   the name, part no or brand and pick from the suggestions. The original
   <select> is kept (hidden) and still carries the value that gets posted, so
   the form works unchanged — and without JS the plain select is still there. */
function initProductPicker() {
  const select = document.getElementById("id_product");
  if (!select || select.dataset.picker === "on") return;

  const options = [...select.options].filter((o) => o.value);
  if (!options.length) return;

  const list = document.createElement("datalist");
  list.id = "productPickerList";
  options.forEach((o) => list.append(new Option(o.textContent, o.textContent)));

  const box = document.createElement("input");
  box.type = "text";
  box.className = "input";
  box.id = "productPicker";
  box.setAttribute("list", list.id);
  box.placeholder = "Type a name, part no or brand…";
  box.autocomplete = "off";

  const hint = select.closest(".field")?.querySelector("[data-picker-hint]");
  const byLabel = new Map(options.map((o) => [o.textContent, o.value]));

  function sync() {
    const id = byLabel.get(box.value);
    select.value = id || "";
    if (hint) {
      hint.textContent = id
        ? "Selected"
        : box.value
          ? "Keep typing, then pick from the list"
          : `${options.length} products available`;
    }
  }

  box.addEventListener("input", sync);
  box.addEventListener("change", sync);

  select.hidden = true;
  select.dataset.picker = "on";
  select.after(box, list);
  sync();
}

/* ------------------------------------------------- filter a <select> box */
/* <input data-filter-select="#id_product"> narrows that select as you type,
   without touching the server. Options are rebuilt rather than hidden —
   display:none on an <option> is ignored by some browsers. */
function initSelectFilter() {
  document.querySelectorAll("[data-filter-select]").forEach((input) => {
    const select = document.querySelector(input.dataset.filterSelect);
    if (!select) return;

    const all = [...select.options].map((o) => ({
      value: o.value,
      label: o.textContent,
      hay: o.textContent.toLowerCase(),
    }));
    const counter = input.closest(".field")?.querySelector("[data-filter-count]");

    function render() {
      const q = input.value.trim().toLowerCase();
      const keep = q ? all.filter((o) => o.value === "" || o.hay.includes(q)) : all;
      const chosen = select.value;

      select.replaceChildren(
        ...keep.map((o) => new Option(o.label, o.value, false, o.value === chosen))
      );

      // with exactly one real match, pick it so the user can just hit Add
      const real = keep.filter((o) => o.value !== "");
      if (q && real.length === 1) select.value = real[0].value;

      if (counter) {
        counter.textContent = q
          ? `${real.length} of ${all.length - 1} products`
          : `${all.length - 1} products`;
      }
    }

    input.addEventListener("input", render);
    render();
  });
}

/* ------------------------------------------------------- live filter swap */
/* A [data-live] panel keeps its search box and its filter links working
   without ever reloading the page: they fetch the same view, which answers
   with only its [data-live-region] blocks, and those are swapped in.

   The filtering itself still runs in the database, so a search covers every
   record — not just the rows already on screen, which is all a client-side
   filter could ever see once the list is paginated. */

const LIVE_WAIT = 250;          // ms of quiet typing before asking the server

function initLiveFilter() {
  document.querySelectorAll("[data-live]").forEach((panel) => {
    const url = panel.dataset.liveUrl || location.pathname;
    const form = panel.querySelector("form.search");
    const box = form?.querySelector('input[type="search"]');
    // the search box names its own parameter: "q" on most pages, but the
    // payment page has two panels searching side by side, as oq and pq
    const key = box?.name || "q";

    let timer = null;
    let inFlight = null;

    /* The filter as it stands right now, read from the address bar rather
       than kept in a variable.

       That matters on a page with more than one live panel. Each panel used
       to cache the query at start-up, so once one panel filtered and rewrote
       the URL, the other was still holding the query from page load — and
       its next request would quietly drop the first panel's filter. load()
       keeps the address bar current, so reading it back is always right. */
    function current() {
      return new URLSearchParams(location.search);
    }

    function swap(html) {
      const fresh = new DOMParser().parseFromString(html, "text/html");
      fresh.querySelectorAll("[data-live-region]").forEach((region) => {
        const here = panel.querySelector(`#${CSS.escape(region.id)}`);
        if (here) here.innerHTML = region.innerHTML;
      });
    }

    async function load(params, { push = false } = {}) {
      const query = params.toString();
      inFlight?.abort();                 // an older answer must not land later
      const mine = new AbortController();
      inFlight = mine;
      panel.classList.add("is-loading");

      try {
        const res = await fetch(query ? `${url}?${query}` : url, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          signal: mine.signal,
        });
        if (!res.ok) throw new Error(res.status);
        swap(await res.text());

        // keep the address bar honest, so the filtered view can be shared,
        // bookmarked and reloaded
        const here = query ? `${url}?${query}` : url;
        history[push ? "pushState" : "replaceState"]({ live: true }, "", here);
      } catch (err) {
        if (err.name === "AbortError") return;   // a newer keystroke won
        location.assign(query ? `${url}?${query}` : url);  // fall back to a full load
      } finally {
        if (inFlight === mine) {
          inFlight = null;
          panel.classList.remove("is-loading");
        }
      }
    }

    function withTerm() {
      const params = current();
      const term = box ? box.value.trim() : "";
      if (term) params.set(key, term);
      else params.delete(key);
      params.delete("page");           // a new search starts at page one
      return params;
    }

    box?.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => load(withTerm()), LIVE_WAIT);
    });

    /* Fold a form's own fields into the filter. A field the form carries
       replaces its current value, or clears it when left blank; anything the
       form does not carry is untouched, so the search box and the date form
       never wipe each other out. */
    function mergeForm(target) {
      const params = current();
      const data = new FormData(target);
      for (const name of new Set(data.keys())) {
        const value = data.getAll(name).find((v) => String(v).trim());
        if (value) params.set(name, value);
        else params.delete(name);
      }
      params.delete("page");           // a changed filter starts at page one
      return params;
    }

    /* Every form that filters — the search box, and a period or date form
       where the page has one.

       Opted in by attribute rather than by tag, because a [data-live] panel
       can also hold POST forms — the shop's Add button sits inside one — and
       those must submit normally.

       Delegated to the panel rather than bound to each form, because a form
       can itself live inside a swapped region: the reports' date form does,
       and a listener bound to it would be thrown away by the first swap. */
    function fromForm(e) {
      const target = e.target.closest("form[data-live-form]");
      if (!target) return null;
      e.preventDefault();
      clearTimeout(timer);
      return mergeForm(target);
    }

    panel.addEventListener("submit", (e) => {
      const params = fromForm(e);
      if (params) load(params, { push: true });
    });

    // a select or a date box applies as soon as it is changed; a text box
    // waits for the debounce above, or for Enter
    panel.addEventListener("change", (e) => {
      if (e.target.matches('input[type="search"], input[type="text"]')) return;
      const params = fromForm(e);
      if (params) load(params, { push: true });
    });

    /* The stock segment, Clear, the page size switch and the pager — each is
       a plain ?query link, and each one already spells out what the filter
       becomes, so its href replaces the query outright.

       data-live-skip opts a link out. Not every ?query link is a filter: the
       payment page's Receive button is ?pay=<order>, which has to be a real
       navigation because it opens a modal that lives outside the swapped
       region. Swallowing that click would leave the button doing nothing. */
    panel.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;   // let it open a tab
      const link = e.target.closest('a[href^="?"]');
      if (!link || link.hasAttribute("data-live-skip")) return;

      e.preventDefault();
      clearTimeout(timer);
      const params = new URLSearchParams(link.getAttribute("href").slice(1));
      if (box) box.value = params.get(key) || "";
      load(params, { push: true });
    });

    // back and forward through the filters that were clicked
    window.addEventListener("popstate", () => {
      const params = current();
      if (box) box.value = params.get(key) || "";
      load(params);
    });
  });
}

/* ------------------------------------------------------ marking a visit */
/* Two small jobs on the attendance form:

   1. ask the browser where the phone is, and put that in the hidden fields;
   2. show the photo back before it is sent, so a thumb over the lens is
      caught at the door rather than in the report a week later.

   The location is a courtesy, not a gate. Permission can be refused, a phone
   can be indoors with no fix, and the visit still happened — so a failure
   says so plainly and leaves the form perfectly usable. */
function initVisitCapture() {
  const form = document.querySelector("[data-visit-form]");
  if (!form) return;

  const state = form.querySelector("[data-visit-state]");
  const retry = form.querySelector("[data-visit-retry]");
  const lat = form.querySelector('input[name="latitude"]');
  const lng = form.querySelector('input[name="longitude"]');
  const acc = form.querySelector('input[name="accuracy_m"]');
  const place = form.querySelector('input[name="place"]');

  /* Turn the coordinates into something a person can read — "MI Road, Jaipur"
     rather than two numbers.

     Looked up here, once, and stored with the visit. Doing it when a report
     is read would mean one call per row every time somebody opened the page.

     OpenStreetMap's Nominatim needs no key. It is a courtesy service with a
     rate limit, so a failure is silent: the visit keeps its coordinates and
     the report falls back to showing those. */
  async function nameThePlace(latitude, longitude) {
    if (!place) return;
    try {
      const res = await fetch(
        "https://nominatim.openstreetmap.org/reverse?format=jsonv2"
        + `&lat=${latitude}&lon=${longitude}&zoom=16&addressdetails=1`,
        { headers: { Accept: "application/json" } },
      );
      if (!res.ok) return;
      const data = await res.json();
      const a = data.address || {};

      // build a short line from the useful parts, skipping whatever this
      // particular spot does not have
      const near = a.neighbourhood || a.suburb || a.village || a.hamlet || a.road;
      const town = a.city || a.town || a.county || a.state_district;
      const short = [near, town, a.state].filter(Boolean).slice(0, 3).join(", ");

      place.value = (short || data.display_name || "").slice(0, 200);
      if (place.value) {
        say(`${place.value} — ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`,
            "checkmark-circle-outline", "ok");
      }
    } catch {
      /* offline, blocked or rate-limited — the coordinates are enough */
    }
  }

  function say(text, icon, tone) {
    if (!state) return;
    state.innerHTML = "";
    const glyph = document.createElement("ion-icon");
    glyph.setAttribute("name", icon);
    // textContent, never innerHTML — this carries browser error messages
    state.append(glyph, document.createTextNode(" " + text));
    state.className = "visit-where__state" + (tone ? ` is-${tone}` : "");
  }

  function locate() {
    if (!navigator.geolocation) {
      say("This browser cannot report a location. The visit will save without one.",
          "alert-circle-outline", "warn");
      return;
    }

    say("Looking for your location…", "location-outline");
    if (retry) retry.hidden = true;

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        // six decimals is about a tenth of a metre — far past what a phone
        // knows, and it matches the column on the model
        if (lat) lat.value = coords.latitude.toFixed(6);
        if (lng) lng.value = coords.longitude.toFixed(6);
        if (acc) acc.value = Math.round(coords.accuracy);

        say(`${coords.latitude.toFixed(6)}, ${coords.longitude.toFixed(6)} `
            + `(±${Math.round(coords.accuracy)} m)`,
            "checkmark-circle-outline", "ok");

        // and put a name to it, which replaces the line above if it works
        nameThePlace(coords.latitude, coords.longitude);
      },
      (err) => {
        const why = err.code === err.PERMISSION_DENIED
          ? "Location permission was refused."
          : err.code === err.TIMEOUT
            ? "Finding the location took too long."
            : "The location could not be read.";
        say(`${why} The visit will save without it.`, "alert-circle-outline", "warn");
        if (retry) retry.hidden = false;
      },
      // a real fix, not the coarse one from the network, and no stale answer
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  retry?.addEventListener("click", locate);
  locate();

  /* show the photo back */
  const file = form.querySelector('input[type="file"]');
  const preview = form.querySelector("[data-visit-preview]");
  const shot = preview?.querySelector("img");

  file?.addEventListener("change", () => {
    const picked = file.files && file.files[0];
    if (!picked || !shot) {
      if (preview) preview.hidden = true;
      return;
    }
    // release the previous one, or every retake leaks a blob
    if (shot.dataset.url) URL.revokeObjectURL(shot.dataset.url);
    const url = URL.createObjectURL(picked);
    shot.dataset.url = url;
    shot.src = url;
    preview.hidden = false;
  });
}

/* ------------------------------------------------------- date pickers */
/* The calendar drawn to the left of a date range is decoration — clicking it
   did nothing, which is the one thing everybody tries. This opens the picker
   for the first date field beside it.

   Delegated on the document, so it covers the reports' date, month and year
   controls and the order list's, including the ones swapped in by a live
   filter. showPicker() needs a user gesture, which a click is, and throws if
   the browser will not open it — hence the fallback to simply focusing. */
function initDatePickers() {
  document.addEventListener("click", (e) => {
    const icon = e.target.closest(".range-filter__dates ion-icon");
    if (!icon) return;

    const field = icon
      .closest(".range-filter__dates")
      ?.querySelector('input[type="date"], input[type="month"], input[type="week"]');
    if (!field) return;          // a year box is a plain number, nothing to open

    try {
      if (typeof field.showPicker === "function") field.showPicker();
      else field.focus();
    } catch {
      field.focus();
    }
  });
}

/* ------------------------------------------------ topbar product search */
/* The box in the header searches every product as you type and lists the
   matches underneath. Picking one opens that product; nothing reloads until
   something is chosen. */

const SUGGEST_WAIT = 200;
const SUGGEST_MIN = 2;          // one letter matches nearly everything

function initSuggest() {
  const wrap = document.querySelector("[data-suggest]");
  if (!wrap) return;

  const input = wrap.querySelector("input");
  const panel = wrap.querySelector("[data-suggest-panel]");
  const url = wrap.dataset.suggestUrl;
  const listUrl = wrap.dataset.suggestList;   // where Enter goes
  let timer = null;
  let inFlight = null;
  let hits = [];                // the rows, in the order they are shown
  let at = -1;                  // which one the arrow keys are on

  function close() {
    panel.hidden = true;
    input.setAttribute("aria-expanded", "false");
    at = -1;
  }

  function highlight(next) {
    if (!hits.length) return;
    at = (next + hits.length) % hits.length;
    hits.forEach((row, i) => {
      row.classList.toggle("is-active", i === at);
      if (i === at) row.scrollIntoView({ block: "nearest" });
    });
  }

  function row(product) {
    const link = document.createElement("a");
    link.className = "search__hit";
    link.href = product.url;
    link.setAttribute("role", "option");

    const img = document.createElement("img");
    img.src = product.image;
    img.alt = "";
    img.loading = "lazy";

    const main = document.createElement("div");
    const name = document.createElement("strong");
    // textContent, never innerHTML — product names are user data
    name.textContent = product.name;
    const meta = document.createElement("small");
    meta.className = "muted";
    meta.textContent = `${product.brand} · ${product.partno}`;
    main.append(name, meta);

    const side = document.createElement("div");
    side.className = "search__hit-side";
    const price = document.createElement("span");
    price.textContent = product.price;
    const badge = document.createElement("span");
    badge.className = `badge badge--${product.badge}`;
    badge.textContent = product.label;
    side.append(price, badge);

    link.append(img, main, side);
    return link;
  }

  function render(data, term) {
    hits = [];
    at = -1;
    panel.replaceChildren();

    if (!data.results.length) {
      const none = document.createElement("p");
      none.className = "search__none";
      none.textContent = `Nothing matches “${term}”.`;
      panel.append(none);
    } else {
      data.results.forEach((product) => {
        const link = row(product);
        panel.append(link);
        hits.push(link);
      });

      if (data.total > data.results.length) {
        const more = document.createElement("a");
        more.className = "search__more";
        more.href = data.url;
        more.textContent = `See all ${data.total} matches`;
        panel.append(more);
        hits.push(more);
      }
    }

    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  async function look() {
    const term = input.value.trim();
    if (term.length < SUGGEST_MIN) {
      close();
      return;
    }

    inFlight?.abort();
    const mine = new AbortController();
    inFlight = mine;

    try {
      const res = await fetch(`${url}?q=${encodeURIComponent(term)}`, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: mine.signal,
      });
      if (!res.ok) throw new Error(res.status);
      render(await res.json(), term);
    } catch (err) {
      if (err.name !== "AbortError") close();   // stay quiet, don't nag
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(look, SUGGEST_WAIT);
  });

  // coming back to a box that still holds its term shows the matches again
  input.addEventListener("focus", () => {
    if (hits.length && panel.hidden && input.value.trim().length >= SUGGEST_MIN) {
      panel.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      close();
      return;
    }
    if (e.key === "Enter") {
      // whatever is highlighted, or else the full list for what was typed —
      // built from the box, so a half-typed word never opens a stale search
      const term = input.value.trim();
      const target =
        at >= 0 ? hits[at].href : term ? `${listUrl}?q=${encodeURIComponent(term)}` : "";
      if (target) {
        e.preventDefault();
        location.assign(target);
      }
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (panel.hidden) {
      clearTimeout(timer);
      look();
      return;
    }
    e.preventDefault();
    highlight(e.key === "ArrowDown" ? at + 1 : at - 1);
  });

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) close();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initBottomBar();
  initNavTips();
  initUserMenu();
  initTabs();
  initSegments();
  initTableSearch();
  initInbox();
  initComposer();
  initPagination();
  initReveal();
  initModals();
  initShopCart();
  initLiveFilter();
  initDatePickers();
  initVisitCapture();
  initSuggest();
  initDetailGallery();
  initSelectFilter();
  initProductPicker();
});
