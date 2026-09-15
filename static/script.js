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

const filterInput = document.getElementById("filter-input");
const loadingStateEl = document.getElementById("loading-state");
const emptyStateEl = document.getElementById("empty-state");
const collectionsEl = document.getElementById("collections");

let allCollections = []; // [{ user_id, pokemons: [...] }, ...] chargé une seule fois

init();

async function init() {
  try {
    allCollections = await fetchJSON("/api/collections");
  } catch (err) {
    loadingStateEl.textContent = "Impossible de charger les collections. Vérifie la connexion à la base.";
    return;
  }

  loadingStateEl.hidden = true;

  if (allCollections.length === 0) {
    emptyStateEl.textContent = "Aucune collection pour l'instant. Elle apparaîtra ici dès qu'un Pokémon aura été capturé.";
    emptyStateEl.hidden = false;
    return;
  }

  renderAll();
  filterInput.addEventListener("input", () => renderAll());
}

function renderAll() {
  const filterText = filterInput.value.trim().toLowerCase();
  collectionsEl.innerHTML = "";
  let visibleSections = 0;

  allCollections.forEach((trainer) => {
    const pokemons = filterText
      ? trainer.pokemons.filter((p) => p.name.toLowerCase().includes(filterText))
      : trainer.pokemons;

    if (pokemons.length === 0) return;
    visibleSections += 1;
    collectionsEl.appendChild(buildTrainerSection(trainer.user_id, pokemons));
  });

  emptyStateEl.hidden = visibleSections > 0;
}

function buildTrainerSection(userId, pokemons) {
  const section = document.createElement("section");
  section.className = "trainer-section";

  const header = document.createElement("div");
  header.className = "trainer-section-header";
  header.innerHTML = `<h2>Dresseur ${shortId(userId)}</h2><span class="muted">${pokemons.length} Pokémon</span>`;

  const grid = document.createElement("div");
  grid.className = "grid";
  pokemons.forEach((p) => grid.appendChild(buildCard(p)));

  section.appendChild(header);
  section.appendChild(grid);
  return section;
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