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
    if (btn.dataset.view === "foods") loadFoods();
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

// ---- foods (My Foods) ----
async function loadFoods() {
  const foods = await api("/foods/manual");
  const list = $("#foods-list");
  if (!foods.length) { list.innerHTML = '<div class="note">No custom foods yet.</div>'; return; }
  list.innerHTML = foods.map((f, i) => `
    <div class="log-row">
      <div class="log-main tappable" data-log="${i}"><div class="name">${esc(f.name)}${badge(f)}</div><div class="meta">${num(f.calories_100g)} cal/100g</div></div>
      <div class="log-right">
        <button class="food-edit" data-edit="${i}" aria-label="Edit ${esc(f.name)}">Edit</button>
        <button class="del" data-del-food="${f.id}" aria-label="Delete ${esc(f.name)}">${TRASH}</button>
      </div>
    </div>`).join("");
  list.querySelectorAll("[data-log]").forEach((el) =>
    el.addEventListener("click", () => openLogDialog(foods[el.dataset.log])));
  list.querySelectorAll("[data-del-food]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Delete this custom food? Past logged entries are kept.")) return;
      await fetch("/foods/manual/" + b.dataset.delFood, { method: "DELETE" });
      loadFoods();
    }));
  list.querySelectorAll("[data-edit]").forEach((b) =>
    b.addEventListener("click", () => openFoodForm(foods[b.dataset.edit])));  // openFoodForm defined in Task 9
}

// ---- custom food form (create/edit) ----
let editingFoodId = null;

function currentBasis() {
  const r = document.querySelector('input[name="basis"]:checked');
  return r ? r.value : "per100";
}

function applyBasisLabels() {
  const per100 = currentBasis() === "per100";
  const suffix = per100 ? "/ 100 g" : "/ serving";
  $("#lbl-cal").textContent = "Calories " + suffix;
  $("#lbl-pro").textContent = "Protein " + suffix;
  $("#lbl-carb").textContent = "Carbs " + suffix;
  $("#lbl-fat").textContent = "Fat " + suffix;
  document.querySelectorAll(".basis-serving").forEach((el) => el.classList.toggle("hidden", per100));
}

document.querySelectorAll('input[name="basis"]').forEach((r) =>
  r.addEventListener("change", applyBasisLabels));

function openFoodForm(food) {
  editingFoodId = food ? food.id : null;
  $("#food-form-title").textContent = food ? "Edit custom food" : "Add custom food";
  $("#food-name").value = food ? food.name : "";
  $("#food-brand").value = food && food.brand ? food.brand : "";
  document.querySelector('input[name="basis"][value="per100"]').checked = true; // edit prefill is per-100g
  $("#food-serving-grams").value = food && food.serving_grams ? food.serving_grams : "";
  $("#food-serving-desc").value = food && food.serving_desc ? food.serving_desc : "";
  $("#food-cal").value = food ? food.calories_100g : "";
  $("#food-pro").value = food ? food.protein_100g : "";
  $("#food-carb").value = food ? food.carbs_100g : "";
  $("#food-fat").value = food ? food.fat_100g : "";
  const hint = $("#food-form-hint"); hint.textContent = ""; hint.classList.remove("error");
  applyBasisLabels();
  $("#food-form-dialog").classList.remove("hidden");
}

function readFoodForm() {
  const hint = $("#food-form-hint");
  const name = $("#food-name").value.trim();
  if (!name) { hint.textContent = "Name is required"; hint.classList.add("error"); return null; }
  const nums = ["#food-cal", "#food-pro", "#food-carb", "#food-fat"].map((s) => parseFloat($(s).value));
  if (nums.some((n) => !Number.isFinite(n) || n < 0)) {
    hint.textContent = "Enter valid macros (0 or more)"; hint.classList.add("error"); return null;
  }
  let [cal, pro, carb, fat] = nums;
  const desc = $("#food-serving-desc").value.trim() || null;
  const grams = parseFloat($("#food-serving-grams").value);
  const hasServing = Number.isFinite(grams) && grams > 0;
  if (currentBasis() === "serving") {
    if (!hasServing) { hint.textContent = "Enter a serving size in grams"; hint.classList.add("error"); return null; }
    const k = 100 / grams; // convert per-serving -> per-100g
    cal *= k; pro *= k; carb *= k; fat *= k;
  }
  return {
    name, brand: $("#food-brand").value.trim() || null,
    calories_100g: Math.round(cal * 10) / 10, protein_100g: Math.round(pro * 10) / 10,
    carbs_100g: Math.round(carb * 10) / 10, fat_100g: Math.round(fat * 10) / 10,
    serving_desc: desc, serving_grams: hasServing ? grams : null,
  };
}

$("#food-form-cancel").addEventListener("click", () => $("#food-form-dialog").classList.add("hidden"));
$("#food-form-save").addEventListener("click", async () => {
  const payload = readFoodForm();
  if (!payload) return;
  const hint = $("#food-form-hint");
  const url = editingFoodId ? "/foods/manual/" + editingFoodId : "/foods/manual";
  const method = editingFoodId ? "PUT" : "POST";
  try {
    const resp = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!resp.ok) { hint.textContent = "Could not save. Please try again."; hint.classList.add("error"); return; }
  } catch (e) {
    hint.textContent = "Could not save. Please try again."; hint.classList.add("error"); return;
  }
  $("#food-form-dialog").classList.add("hidden");
  loadFoods();
});

$("#add-custom-food").addEventListener("click", () => openFoodForm(null));
$("#add-custom-food-search").addEventListener("click", () => openFoodForm(null));

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
