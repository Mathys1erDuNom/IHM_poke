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

const STAT_TIERS = [
  { max: 50,  color: "#e04b4b" }, // rouge
  { max: 100, color: "#f0913a" }, // orange
  { max: 150, color: "#5eb85e" }, // vert
  { max: Infinity, color: "#4c8fd1" }, // bleu
];

function statColor(value) {
  return STAT_TIERS.find((t) => value < t.max).color;
}

const STAT_ORDER = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"];
const STAT_MAX = 200; // borne d'affichage des barres, les IV/EV peuvent dépasser 100
const PAGE_SIZE = 25;

const trainerButtonsEl = document.getElementById("trainer-buttons");
const filterInput = document.getElementById("filter-input");
const screenTitleEl = document.getElementById("screen-title");
const placeholderEl = document.getElementById("placeholder");
const loadingStateEl = document.getElementById("loading-state");
const emptyStateEl = document.getElementById("empty-state");
const gridEl = document.getElementById("grid");
const prevPageBtn = document.getElementById("prev-page");
const nextPageBtn = document.getElementById("next-page");
const pageIndicatorEl = document.getElementById("page-indicator");
const paginationEl = document.getElementById("pagination");

let allCollections = []; // [{ user_id, pokemons: [...] }, ...]
let currentTrainer = null; // user_id actuellement affiché
let currentPage = 1;

const sortButtonsEl = document.getElementById("sort-buttons");
let currentSort = "recent"; // "recent" ou "alpha"

init();

async function init() {
  loadingStateEl.hidden = false;
  placeholderEl.hidden = true;

  try {
    allCollections = await fetchJSON("/api/collections");
  } catch (err) {
    loadingStateEl.textContent = "Impossible de charger les dresseurs. Vérifie la connexion à la base.";
    return;
  }

  loadingStateEl.hidden = true;

  if (allCollections.length === 0) {
    placeholderEl.hidden = false;
    placeholderEl.querySelector("p").textContent =
      "Aucun dresseur pour l'instant. Une collection apparaîtra ici dès qu'un Pokémon aura été capturé.";
    return;
  }

  placeholderEl.hidden = false;
  renderTrainerButtons();
  filterInput.addEventListener("input", () => {
    currentPage = 1;
    renderGrid();
  });

  prevPageBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderGrid();
    }
  });

  nextPageBtn.addEventListener("click", () => {
    const trainer = allCollections.find((t) => String(t.user_id) === String(currentTrainer));
    const total = trainer ? trainer.pokemons.length : 0;
    const maxPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (currentPage < maxPage) {
      currentPage += 1;
      renderGrid();
    }
  });

  sortButtonsEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".sort-btn");
    if (!btn) return;

    currentSort = btn.dataset.sort;
    [...sortButtonsEl.children].forEach((b) => b.classList.toggle("active", b === btn));
    currentPage = 1;

    renderGrid();
  });
}

function renderTrainerButtons() {
  trainerButtonsEl.innerHTML = "";
  allCollections.forEach((trainer) => {
    const btn = document.createElement("button");
    btn.className = "trainer-btn";
    btn.dataset.userId = trainer.user_id;
    btn.innerHTML = `
      <span class="dot"></span>
      <span>Dresseur ${shortId(trainer.user_id)}</span>
      <span class="count">${trainer.pokemons.length}</span>
    `;
    btn.addEventListener("click", () => selectTrainer(trainer.user_id));
    trainerButtonsEl.appendChild(btn);
  });
}

function selectTrainer(userId) {
  currentTrainer = userId;
  currentPage = 1;

  [...trainerButtonsEl.children].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.userId === String(userId));
  });

  const trainer = allCollections.find((t) => String(t.user_id) === String(userId));
  screenTitleEl.textContent = `Dresseur ${shortId(userId)} · ${trainer.pokemons.length} Pokémon`;

  placeholderEl.hidden = true;
  filterInput.hidden = false;
  filterInput.value = "";
  sortButtonsEl.hidden = false; 

  renderGrid();
}
function getTimestamp(pokemon) {
  // On essaie plusieurs noms de champs possibles pour la date de capture.
  const candidats = [pokemon.caught_at, pokemon.created_at, pokemon.captured_at, pokemon.date, pokemon.timestamp];
  for (const c of candidats) {
    if (c) {
      const t = new Date(c).getTime();
      if (!isNaN(t)) return t;
    }
  }
  return null;
}

function sortPokemons(list, mode) {
  const arr = [...list];

  if (mode === "alpha") {
    arr.sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));
    return arr;
  }

  // mode "recent" : le plus récent en premier
  const toutesLesDates = arr.every((p) => getTimestamp(p) !== null);
  if (toutesLesDates) {
    arr.sort((a, b) => getTimestamp(b) - getTimestamp(a));
  } else {
    // Pas de champ date dans les données : on suppose que le tableau
    // arrive déjà dans l'ordre de capture (ancien -> récent), donc on inverse.
    arr.reverse();
  }
  return arr;
}

function renderGrid() {
  if (!currentTrainer) return;

  const trainer = allCollections.find((t) => String(t.user_id) === String(currentTrainer));
  const filterText = filterInput.value.trim().toLowerCase();
  const hasFilter = filterText.length > 0;

  let visible = trainer.pokemons.filter((p) => {
    if (!p || !p.name) return false;
    return !hasFilter || p.name.toLowerCase().includes(filterText);
  });

  visible = sortPokemons(visible, currentSort);

  if (!hasFilter) {
    const maxPage = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
    currentPage = Math.min(currentPage, maxPage);
    const start = (currentPage - 1) * PAGE_SIZE;
    const paged = visible.slice(start, start + PAGE_SIZE);

    paginationEl.hidden = visible.length <= PAGE_SIZE;
    prevPageBtn.disabled = currentPage <= 1;
    nextPageBtn.disabled = currentPage >= maxPage;
    pageIndicatorEl.textContent = `Page ${currentPage}/${maxPage}`;

    gridEl.innerHTML = "";
    emptyStateEl.hidden = paged.length > 0;
    paged.forEach((p) => gridEl.appendChild(buildCard(p)));
    return;
  }

  paginationEl.hidden = true;
  prevPageBtn.disabled = true;
  nextPageBtn.disabled = true;
  pageIndicatorEl.textContent = "Page 1";

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

  // =========================
  // STATS
  // =========================
  const statRows = STAT_ORDER.filter((key) => pokemon.stats && key in pokemon.stats)
    .map((key) => {
      const value = pokemon.stats[key];
      const pct = Math.min(100, Math.round((value / STAT_MAX) * 100));
      const color = statColor(value);

      return `
        <div class="stat-row">
          <span>${STAT_LABELS[key]}</span>
          <span class="stat-track">
            <span class="stat-fill" style="width:${pct}%; background:${color}"></span>
          </span>
          <span class="stat-value">${value}</span>
        </div>`;
    })
    .join("");

  // =========================
  // IV
  // =========================
  const ivRows = buildIvRows(pokemon);

  const xpBlock = buildXpBlock(pokemon);
  const evoBlock = buildEvoBlock(pokemon);

  const attacksLine = (pokemon.attacks || []).length
    ? `<div class="attacks">${pokemon.attacks.join(" · ")}</div>`
    : "";

  const isShiny = /_shiny$/i.test(pokemon.name);
  const baseName = isShiny ? pokemon.name.replace(/_shiny$/i, "") : pokemon.name;
  const gifFolder = isShiny ? "shiny" : "normal";
  const gifSrc = `/images/gif/${gifFolder}/${slugifyName(baseName)}.gif`;
  const fallbackSrc = escapeHtml(pokemon.image || "");

  card.innerHTML = `
    <div class="card-art" style="background:radial-gradient(circle at 50% 35%, ${artColor}55, transparent 70%)">
      <img src="${gifSrc}" alt="${escapeHtml(pokemon.name)}" loading="lazy"
           onerror="this.onerror=null; this.src='${fallbackSrc}';" />
    </div>

    <div class="card-body">
      <h3 class="card-name">${escapeHtml(pokemon.name)}</h3>

      <div class="type-chips">${typeChips}</div>

      <!-- STATS -->
      <div class="iv-section">
        <div class="iv-title">Statistiques</div>
        <div class="stats">
          ${statRows}
        </div>
      </div>

      <!-- IV -->
      ${ivRows}

      <!-- XP -->
      ${xpBlock}

      <!-- ATTAQUES -->
      ${attacksLine}

      <!-- ÉVOLUTION -->
      ${evoBlock}
    </div>
  `;

  return card;
}


function buildIvRows(pokemon) {
  if (!pokemon.ivs || typeof pokemon.ivs !== "object") {
    return "";
  }

  const ivRows = STAT_ORDER
    .filter((key) => key in pokemon.ivs)
    .map((key) => {
      const value = Number(pokemon.ivs[key]);

      // IV maximum = 31
      const pct = Math.min(100, Math.round((value / 31) * 100));

      // Couleur selon la valeur de l'IV
      let color;

      if (value <= 7) {
        color = "#e04b4b";       // rouge
      } else if (value <= 15) {
        color = "#f0913a";       // orange
      } else if (value <= 23) {
        color = "#e0c23e";       // jaune
      } else {
        color = "#5eb85e";       // vert
      }

      return `
        <div class="stat-row iv-row">
          <span>${STAT_LABELS[key]}</span>

          <span class="stat-track">
            <span
              class="stat-fill"
              style="width:${pct}%; background:${color}">
            </span>
          </span>

          <span class="stat-value">${value}/31</span>
        </div>
      `;
    })
    .join("");

  if (!ivRows) {
    return "";
  }

  return `
    <div class="iv-section">
      <div class="iv-title">IVs</div>
      <div class="ivs">
        ${ivRows}
      </div>
    </div>
  `;
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

function slugifyName(name) {
  return String(name)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // enlève les accents (é, â, ...)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ""); // enlève espaces, apostrophes, points, tirets
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}