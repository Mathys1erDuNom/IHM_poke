const TYPE_COLORS = {
  normal: "#b7ae8c",
  feu: "#e2723c",
  eau: "#4c8fd1",
  plante: "#6fa84b",
  electrik: "#e0c23e",
  glace: "#7fd1c6",
  combat: "#b8544a",
  poison: "#9b5db0",
  sol: "#c79a4b",
  vol: "#8fa9d9",
  psy: "#d0608a",
  insecte: "#92aa3c",
  roche: "#a79567",
  spectre: "#6c5b95",
  dragon: "#5b6fd1",
  tenebres: "#5b5468",
  acier: "#9aa5b1",
  fee: "#e39fc2",
};

const STAT_LABELS = {
  hp: "PV",
  attack: "Attaque",
  defense: "Défense",
  special_attack: "Atq. spé.",
  special_defense: "Déf. spé.",
  speed: "Vitesse",
};

const STAT_ORDER = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"];
const STAT_MAX = 150; // borne d'affichage des barres, les IV/EV peuvent dépasser 100

const trainerListEl = document.getElementById("trainer-list");
const trainerIdInput = document.getElementById("trainer-id-input");
const trainerIdGoBtn = document.getElementById("trainer-id-go");
const pokemonSearchInput = document.getElementById("pokemon-search-input");
const filterInput = document.getElementById("filter-input");
const filterCountEl = document.getElementById("filter-count");
const toolbarEl = document.getElementById("toolbar");
const gridEl = document.getElementById("grid");
const emptyStateEl = document.getElementById("empty-state");
const headerEl = document.getElementById("content-header");

let currentPokemons = []; // ce qui est affiché en ce moment (collection ou résultats de recherche)
let currentMode = "empty"; // "trainer" | "search"

init();

async function init() {
  await loadTrainerList();

  trainerIdGoBtn.addEventListener("click", () => {
    const id = trainerIdInput.value.trim();
    if (id) openTrainer(id);
  });
  trainerIdInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") trainerIdGoBtn.click();
  });

  let searchTimer = null;
  pokemonSearchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = pokemonSearchInput.value.trim();
    if (!q) return;
    searchTimer = setTimeout(() => runPokemonSearch(q), 300);
  });

  filterInput.addEventListener("input", () => renderGrid());
}

async function loadTrainerList() {
  const trainers = await fetchJSON("/api/trainers");
  trainerListEl.innerHTML = "";
  trainers.forEach((t) => {
    const li = document.createElement("li");
    li.dataset.userId = t.user_id;
    li.innerHTML = `<span>Dresseur ${shortId(t.user_id)}</span><span class="count">${t.total}</span>`;
    li.addEventListener("click", () => openTrainer(t.user_id));
    trainerListEl.appendChild(li);
  });
}

async function openTrainer(userId) {
  currentMode = "trainer";
  trainerIdInput.value = userId;
  pokemonSearchInput.value = "";

  [...trainerListEl.children].forEach((li) => {
    li.classList.toggle("active", li.dataset.userId === String(userId));
  });

  const pokemons = await fetchJSON(`/api/trainers/${encodeURIComponent(userId)}/pokemons`);
  currentPokemons = pokemons;

  headerEl.innerHTML = `<h2>Dresseur ${shortId(userId)}</h2><p class="muted">${pokemons.length} Pokémon dans la collection</p>`;
  toolbarEl.hidden = false;
  filterInput.value = "";
  filterInput.placeholder = "Filtrer cette collection par nom";
  renderGrid();
}

async function runPokemonSearch(query) {
  currentMode = "search";
  [...trainerListEl.children].forEach((li) => li.classList.remove("active"));

  const results = await fetchJSON(`/api/search?q=${encodeURIComponent(query)}`);
  currentPokemons = results;

  headerEl.innerHTML = `<h2>Résultats pour « ${escapeHtml(query)} »</h2><p class="muted">${results.length} Pokémon trouvé(s), tous dresseurs confondus</p>`;
  toolbarEl.hidden = true;
  renderGrid();
}

function renderGrid() {
  const filterText = currentMode === "trainer" ? filterInput.value.trim().toLowerCase() : "";
  const visible = filterText
    ? currentPokemons.filter((p) => p.name.toLowerCase().includes(filterText))
    : currentPokemons;

  if (currentMode === "trainer") {
    filterCountEl.textContent = `${visible.length} / ${currentPokemons.length} affiché(s)`;
  }

  gridEl.innerHTML = "";
  emptyStateEl.hidden = visible.length > 0;

  visible.forEach((p) => gridEl.appendChild(buildCard(p)));
}

function buildCard(pokemon) {
  const card = document.createElement("div");
  card.className = "card";

  const primaryType = (pokemon.type && pokemon.type[0]) || "normal";
  const artColor = TYPE_COLORS[primaryType] || "#3a3d63";

  const typeChips = (pokemon.type || [])
    .map((t) => `<span class="type-chip" style="background:${TYPE_COLORS[t] || "#8b8fae"}">${t}</span>`)
    .join("");

  const statRows = STAT_ORDER.filter((key) => pokemon.stats && key in pokemon.stats)
    .map((key) => {
      const value = pokemon.stats[key];
      const pct = Math.min(100, Math.round((value / STAT_MAX) * 100));
      return `
        <div class="stat-row">
          <span>${STAT_LABELS[key]}</span>
          <span class="stat-track"><span class="stat-fill" style="width:${pct}%"></span></span>
          <span class="stat-value">${value}</span>
        </div>`;
    })
    .join("");

  const xpBlock = buildXpBlock(pokemon);
  const evoBlock = buildEvoBlock(pokemon);
  const attacksLine = (pokemon.attacks || []).length
    ? `<div class="attacks">${pokemon.attacks.join(" · ")}</div>`
    : "";
  const ownerLine = currentMode === "search"
    ? `<div class="card-owner">Dresseur ${shortId(pokemon.user_id)}</div>`
    : "";

  card.innerHTML = `
    <div class="card-art" style="background:radial-gradient(circle at 50% 35%, ${artColor}55, transparent 70%)">
      <img src="${pokemon.image}" alt="${escapeHtml(pokemon.name)}" loading="lazy" />
    </div>
    <div class="card-body">
      <h3 class="card-name">${escapeHtml(pokemon.name)}</h3>
      <div class="type-chips">${typeChips}</div>
      <div class="stats">${statRows}</div>
      ${xpBlock}
      ${attacksLine}
      ${ownerLine}
      ${evoBlock}
    </div>
  `;
  return card;
}

function buildXpBlock(pokemon) {
  if (pokemon.xp_evo === -1) {
    return `<div class="xp-block"><div class="xp-label"><span>Expérience</span><span>Bloquée</span></div></div>`;
  }
  if (!pokemon.xp_evo || pokemon.xp_evo <= 0) {
    return "";
  }
  const pct = Math.min(100, Math.round((pokemon.current_xp / pokemon.xp_evo) * 100));
  return `
    <div class="xp-block">
      <div class="xp-label"><span>Expérience</span><span>${pokemon.current_xp} / ${pokemon.xp_evo}</span></div>
      <div class="xp-track"><span class="xp-fill" style="width:${pct}%"></span></div>
    </div>`;
}

function buildEvoBlock(pokemon) {
  const evo = pokemon.evo;
  if (!evo || evo.name === "pas evo" || !evo.name) return "";
  return `<div class="evo-note">Évolue en ${escapeHtml(evo.name)}</div>`;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Requête échouée : ${url}`);
  return res.json();
}

function shortId(id) {
  const s = String(id);
  return s.length > 6 ? `#${s.slice(0, 4)}…${s.slice(-4)}` : `#${s}`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
