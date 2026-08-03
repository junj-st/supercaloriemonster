const $ = (sel) => document.querySelector(sel);
const api = (path, opts) => fetch(path, opts).then((r) => (r.status === 204 ? null : r.json()));
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (n) => { const x = +n; return Number.isFinite(x) ? String(x) : "0"; };
const badge = (f) => (f.source === "manual" ? '<span class="badge-custom">Custom</span>' : "");
const skeleton = (n) => Array.from({ length: n }, () => '<div class="skeleton-row"></div>').join("");
const TRASH = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>';

let pendingFood = null; // NormalizedFood awaiting log confirmation

// ---- view switching ----
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $("#view-" + btn.dataset.view).classList.remove("hidden");
    if (btn.dataset.view === "today") loadDay(today(), "#totals", "#day-meals", true);
    if (btn.dataset.view === "search") loadQuickLists();
    if (btn.dataset.view === "history") loadDay($("#history-date").value || today(), "#history-totals", "#history-meals", false);
  });
});

// ---- totals + meals rendering ----
function renderTotals(el, t) {
  const pill = (cls, label, v) =>
    `<div class="macro-pill macro-pill--${cls}"><span class="macro-label">${label}</span><span class="macro-value">${num(v)}g</span></div>`;
  $(el).innerHTML = `
    <div class="total-card">
      <div class="kcal-line"><span class="kcal-total">${(+t.calories).toLocaleString()}</span><span class="kcal-unit">kcal</span></div>
      <div class="macro-row">
        ${pill("protein", "protein", t.protein_g)}
        ${pill("carbs", "carbs", t.carbs_g)}
        ${pill("fat", "fat", t.fat_g)}
      </div>
    </div>`;
}

function renderMeals(el, meals, allowAdd, reload) {
  const blocks = Object.entries(meals).map(([meal, entries]) => {
    if (!entries.length) return "";
    const rows = entries.map((e) => `
      <div class="log-row">
        <div class="log-main"><div class="name">${esc(e.name)}</div><div class="meta">${num(e.amount_g)} g</div></div>
        <div class="log-right">
          <span class="kcal">${num(e.calories)} cal</span>
          <button class="del" data-del="${e.id}" aria-label="Delete ${esc(e.name)}">${TRASH}</button>
        </div>
      </div>`).join("");
    return `<div class="meal-block"><div class="meal-label">${meal}</div>${rows}</div>`;
  }).join("");

  if (!blocks) {
    $(el).innerHTML = `
      <div class="empty">
        <p class="empty-text">Nothing logged yet</p>
        ${allowAdd ? '<button class="btn-primary" id="empty-add">Add food</button>' : ""}
      </div>`;
    const add = $("#empty-add");
    if (add) add.addEventListener("click", () => document.querySelector('nav button[data-view="search"]').click());
    return;
  }

  $(el).innerHTML = blocks;
  $(el).querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      await fetch("/logs/" + b.dataset.del, { method: "DELETE" });
      reload();
    }));
}

async function loadDay(date, totalsEl, mealsEl, allowAdd) {
  const day = await api("/logs/day/" + date);
  renderTotals(totalsEl, day.totals);
  renderMeals(mealsEl, day.meals, allowAdd, () => loadDay(date, totalsEl, mealsEl, allowAdd));
}

// ---- search ----
let searchTimer = null;
let searchSeq = 0;
$("#search-box").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) return loadQuickLists();
  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq;
    $("#search-results").innerHTML = skeleton(4);
    $("#quick-lists").innerHTML = "";
    const res = await api("/foods/search?q=" + encodeURIComponent(q));
    if (seq !== searchSeq) return; // a newer search has since started; discard stale results
    renderResults("#search-results", res.results);
    $("#quick-lists").innerHTML = res.partial ? '<div class="note">Some sources were unavailable.</div>' : "";
  }, 300);
});

function renderResults(el, foods) {
  if (!foods.length) { $(el).innerHTML = '<div class="note">No matches found.</div>'; return; }
  $(el).innerHTML = foods.map((f, i) => `
    <div class="log-row tappable" data-i="${i}">
      <div class="log-main"><div class="name">${esc(f.name)}${badge(f)}</div><div class="meta">${esc(f.brand || "generic")} · ${num(f.calories_100g)} cal/100g</div></div>
      <span class="add-mark">+</span>
    </div>`).join("");
  $(el).querySelectorAll(".log-row").forEach((row) =>
    row.addEventListener("click", () => openLogDialog(foods[row.dataset.i])));
}

async function loadQuickLists() {
  $("#search-results").innerHTML = "";
  const [recents, favorites] = await Promise.all([api("/recents?limit=10"), api("/favorites")]);
  const favFoods = favorites.map((f) => f.food);
  const section = (title, foods) => foods.length
    ? `<div class="section-label">${title}</div>` + foods.map((f, i) =>
        `<div class="log-row tappable" data-list="${title}" data-i="${i}"><div class="log-main"><div class="name">${esc(f.name)}${badge(f)}</div></div><span class="add-mark">+</span></div>`).join("")
    : "";
  $("#quick-lists").innerHTML = section("Recents", recents) + section("Favorites", favFoods);
  $("#quick-lists").querySelectorAll(".log-row").forEach((row) => {
    const list = row.dataset.list === "Recents" ? recents : favFoods;
    row.addEventListener("click", () => openLogDialog(list[row.dataset.i]));
  });
}

// ---- log dialog ----
let syncingAmount = false; // guards against servings<->grams feedback loops

function openLogDialog(food) {
  pendingFood = food;
  $("#log-food-name").textContent = food.name;
  const hint = $("#serving-hint");
  hint.textContent = "";
  hint.classList.remove("error");
  const servingsInput = $("#log-servings");
  const gramsInput = $("#log-grams");
  if (food.serving_grams) {
    servingsInput.disabled = false;
    servingsInput.value = 1;
    gramsInput.value = food.serving_grams;
    hint.textContent =
      `1 serving ≈ ${food.serving_grams} g${food.serving_desc ? " (" + food.serving_desc + ")" : ""}`;
  } else {
    servingsInput.disabled = true;
    servingsInput.value = "";
    gramsInput.value = 100;
  }
  $("#log-dialog").classList.remove("hidden");
}

// two-way sync: editing servings updates grams, editing grams updates servings.
// Programmatic .value assignment does not fire "input" events, and the
// syncingAmount flag is an extra guard against any accidental re-entrancy.
$("#log-servings").addEventListener("input", () => {
  if (syncingAmount || !pendingFood || !pendingFood.serving_grams) return;
  const servings = parseFloat($("#log-servings").value);
  if (!Number.isFinite(servings)) return;
  syncingAmount = true;
  $("#log-grams").value = Math.round(servings * pendingFood.serving_grams);
  syncingAmount = false;
});
$("#log-grams").addEventListener("input", () => {
  if (syncingAmount || !pendingFood || !pendingFood.serving_grams) return;
  const grams = parseFloat($("#log-grams").value);
  if (!Number.isFinite(grams)) return;
  syncingAmount = true;
  $("#log-servings").value = Math.round((grams / pendingFood.serving_grams) * 100) / 100;
  syncingAmount = false;
});

$("#log-cancel").addEventListener("click", () => $("#log-dialog").classList.add("hidden"));
$("#log-save").addEventListener("click", async () => {
  const hint = $("#serving-hint");
  const grams = parseFloat($("#log-grams").value);
  if (!Number.isFinite(grams) || grams <= 0) {
    hint.textContent = "Enter a valid amount in grams";
    hint.classList.add("error");
    return;
  }
  try {
    const resp = await fetch("/logs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        food: pendingFood, date: today(),
        meal_type: $("#log-meal").value, amount_g: grams,
      }),
    });
    if (!resp.ok) {
      hint.textContent = "Could not save entry. Please try again.";
      hint.classList.add("error");
      return;
    }
  } catch (e) {
    hint.textContent = "Could not save entry. Please try again.";
    hint.classList.add("error");
    return;
  }
  $("#log-dialog").classList.add("hidden");
  document.querySelector('nav button[data-view="today"]').click();
});

// ---- history ----
$("#history-date").value = today();
$("#history-date").addEventListener("change", (e) =>
  loadDay(e.target.value, "#history-totals", "#history-meals", false));

// ---- boot ----
loadDay(today(), "#totals", "#day-meals", true);

// ---- PWA registration ----
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js"));
}
