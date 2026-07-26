const $ = (sel) => document.querySelector(sel);
const api = (path, opts) => fetch(path, opts).then((r) => (r.status === 204 ? null : r.json()));
const today = () => new Date().toISOString().slice(0, 10);

let pendingFood = null; // NormalizedFood awaiting log confirmation

// ---- view switching ----
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $("#view-" + btn.dataset.view).classList.remove("hidden");
    if (btn.dataset.view === "today") loadDay(today(), "#totals", "#day-meals");
    if (btn.dataset.view === "search") loadQuickLists();
  });
});

// ---- totals + meals rendering ----
function renderTotals(el, t) {
  $(el).innerHTML = [["cal", t.calories], ["P", t.protein_g], ["C", t.carbs_g], ["F", t.fat_g]]
    .map(([k, v]) => `<div class="cell"><b>${v}</b><span>${k}</span></div>`).join("");
}

function renderMeals(el, meals) {
  $(el).innerHTML = Object.entries(meals).map(([meal, entries]) => {
    if (!entries.length) return "";
    const rows = entries.map((e) => `
      <div class="entry">
        <div><div>${e.name}</div><small>${e.amount_g} g · ${e.calories} cal</small></div>
        <button data-del="${e.id}">✕</button>
      </div>`).join("");
    return `<div class="meal-block"><h4>${meal}</h4>${rows}</div>`;
  }).join("");
  $(el).querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      await fetch("/logs/" + b.dataset.del, { method: "DELETE" });
      loadDay(today(), "#totals", "#day-meals");
    }));
}

async function loadDay(date, totalsEl, mealsEl) {
  const day = await api("/logs/day/" + date);
  renderTotals(totalsEl, day.totals);
  renderMeals(mealsEl, day.meals);
}

// ---- search ----
let searchTimer = null;
$("#search-box").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) return loadQuickLists();
  searchTimer = setTimeout(async () => {
    const res = await api("/foods/search?q=" + encodeURIComponent(q));
    renderResults("#search-results", res.results);
    $("#quick-lists").innerHTML = res.partial ? "<small>Some sources were unavailable.</small>" : "";
  }, 300);
});

function renderResults(el, foods) {
  $(el).innerHTML = foods.map((f, i) => `
    <div class="result" data-i="${i}">
      <div><div>${f.name}</div><small>${f.brand || "generic"} · ${f.calories_100g} cal/100g</small></div>
      <button>＋</button>
    </div>`).join("");
  $(el).querySelectorAll(".result").forEach((row) =>
    row.addEventListener("click", () => openLogDialog(foods[row.dataset.i])));
}

async function loadQuickLists() {
  $("#search-results").innerHTML = "";
  const [recents, favorites] = await Promise.all([api("/recents?limit=10"), api("/favorites")]);
  const favFoods = favorites.map((f) => f.food);
  const section = (title, foods) => foods.length
    ? `<h4>${title}</h4>` + foods.map((f, i) =>
        `<div class="quick" data-list="${title}" data-i="${i}"><span>${f.name}</span><button>＋</button></div>`).join("")
    : "";
  $("#quick-lists").innerHTML = section("Recents", recents) + section("Favorites", favFoods);
  $("#quick-lists").querySelectorAll(".quick").forEach((row) => {
    const list = row.dataset.list === "Recents" ? recents : favFoods;
    row.addEventListener("click", () => openLogDialog(list[row.dataset.i]));
  });
}

// ---- log dialog ----
function openLogDialog(food) {
  pendingFood = food;
  $("#log-food-name").textContent = food.name;
  $("#log-grams").value = food.serving_grams || 100;
  $("#serving-hint").textContent = food.serving_grams
    ? `1 serving ≈ ${food.serving_grams} g${food.serving_desc ? " (" + food.serving_desc + ")" : ""}` : "";
  $("#log-dialog").classList.remove("hidden");
}
$("#log-cancel").addEventListener("click", () => $("#log-dialog").classList.add("hidden"));
$("#log-save").addEventListener("click", async () => {
  await api("/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      food: pendingFood, date: today(),
      meal_type: $("#log-meal").value, amount_g: parseFloat($("#log-grams").value),
    }),
  });
  $("#log-dialog").classList.add("hidden");
  document.querySelector('nav button[data-view="today"]').click();
});

// ---- history ----
$("#history-date").value = today();
$("#history-date").addEventListener("change", (e) =>
  loadDay(e.target.value, "#history-totals", "#history-meals"));

// ---- boot ----
loadDay(today(), "#totals", "#day-meals");
