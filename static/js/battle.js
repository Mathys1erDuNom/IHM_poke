const battleApp = document.getElementById("battle-app");
const battleLog = document.getElementById("battle-log");
const movesPanel = document.getElementById("battle-moves");
const itemsPanel = document.getElementById("battle-items");
const partyPanel = document.getElementById("battle-party");
const switchPrompt = document.getElementById("battle-switch-prompt");
const nextWaveButton = document.getElementById("battle-next-wave");
const restartLink = document.getElementById("battle-restart");
const waveOverview = document.getElementById("wave-overview");
const waveProgressTrack = waveOverview.querySelector(".wave-progress-track");
let battleState = null;
let requestPending = false;
let scheduledAutoAdvanceWave = null;
let lastForcedSwitchPokemonId = null;
let lastRenderedWave = null;
const STATUS_LABELS = {
  burn: "Brûlure",
  poison: "Poison",
  paralysis: "Paralysie",
  sleep: "Sommeil",
  freeze: "Gel",
};

const byId = (id) => document.getElementById(id);

function setHp(side, pokemon) {
  const current = Math.max(0, pokemon.hp);
  const max = Math.max(1, pokemon.max_hp);
  const percentage = Math.min(100, Math.round(current / max * 100));
  byId(`${side}-hp-bar`).style.width = `${percentage}%`;
  byId(`${side}-hp-bar`).classList.toggle("is-low", percentage <= 25);
  byId(`${side}-hp-label`).textContent = `${current} / ${max} PV`;
}

function renderSide(side, pokemon) {
  byId(`${side}-name`).textContent = pokemon.name;
  byId(`${side}-status`).textContent = STATUS_LABELS[pokemon.status] || pokemon.status || "";
  byId(`${side}-status`).hidden = !pokemon.status;
  const sprite = byId(`${side}-sprite`);
  sprite.src = pokemon.gif_url || pokemon.image || "";
  sprite.alt = pokemon.name;
  sprite.hidden = false;
  sprite.onerror = () => {
    if (pokemon.image && sprite.src !== pokemon.image) sprite.src = pokemon.image;
    else sprite.hidden = true;
  };
  const types = byId(`${side}-types`);
  types.replaceChildren();
  pokemon.types.forEach((type) => {
    const chip = document.createElement("span");
    chip.className = "battle-type";
    chip.textContent = type;
    types.appendChild(chip);
  });
  setHp(side, pokemon);
}

function renderMoves() {
  movesPanel.replaceChildren();
  const pokemon = battleState.player_team[battleState.player_active];
  const canChooseMove = battleState.status === "ongoing" && pokemon.hp > 0 && !requestPending;
  pokemon.moves.forEach((move) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-move";
    button.disabled = !canChooseMove;
    const details = move.category === "statut" ? "Statut" : `Puiss. ${move.power}`;
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector("strong").textContent = move.name;
    button.querySelector("span").textContent = `${move.type} · ${details} · Préc. ${move.accuracy}%`;
    button.addEventListener("click", () => submitAction({ kind: "move", move_id: move.id }));
    movesPanel.appendChild(button);
  });
  if (!pokemon.moves.length) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-move battle-move-fallback";
    button.disabled = !canChooseMove;
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector("strong").textContent = "Lutte";
    button.querySelector("span").textContent = "normal · Puiss. 50 · Préc. 100%";
    button.addEventListener("click", () => submitAction({ kind: "move", move_id: "lutte" }));
    movesPanel.appendChild(button);
  }
}

function renderParty() {
  partyPanel.replaceChildren();
  battleState.player_team.forEach((pokemon, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-party-member";
    button.disabled = requestPending || pokemon.hp <= 0 || index === battleState.player_active || battleState.status !== "ongoing";
    button.innerHTML = `<span></span><small></small>`;
    button.querySelector("span").textContent = pokemon.name;
    button.querySelector("small").textContent = pokemon.hp > 0 ? `${pokemon.hp}/${pokemon.max_hp} PV` : "K.O.";
    button.addEventListener("click", () => submitAction({ kind: "switch", index }));
    partyPanel.appendChild(button);
  });
}

function renderItems() {
  itemsPanel.replaceChildren();
  const pokemon = battleState.player_team[battleState.player_active];
  Object.entries(battleState.player_items || {}).forEach(([itemId, uses]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-item";
    button.textContent = `${battleState.item_labels?.[itemId] || itemId} · ${uses}`;
    button.disabled = requestPending || battleState.status !== "ongoing" || pokemon.hp <= 0 || uses <= 0 || pokemon.hp >= pokemon.max_hp;
    button.addEventListener("click", () => submitAction({ kind: "item", item_id: itemId }));
    itemsPanel.appendChild(button);
  });
}

function renderLog() {
  battleLog.replaceChildren();
  battleState.log.slice(-16).forEach((entry) => {
    const item = document.createElement("li");
    item.className = `battle-log-${entry.kind || "normal"}`;
    item.textContent = entry.text;
    battleLog.appendChild(item);
  });
  battleLog.scrollTop = battleLog.scrollHeight;
}

function renderWaveOverview() {
  const isWaveMode = battleState.mode === "waves";
  waveOverview.hidden = !isWaveMode;
  if (!isWaveMode) {
    lastRenderedWave = null;
    return;
  }

  const info = battleState.wave_tier || {
    name: "Vagues",
    start: 1,
    end: Math.max(1, battleState.wave),
    capped: false,
  };
  const wave = Number(battleState.wave) || 1;
  const start = Number(info.start) || 1;
  const end = Math.max(start, Number(info.end) || start);
  const progress = info.capped
    ? 100
    : Math.round(Math.min(1, Math.max(0, (wave - start + 1) / (end - start + 1))) * 100);
  const changed = lastRenderedWave !== null && wave > lastRenderedWave;

  byId("wave-number").textContent = String(wave);
  byId("wave-tier-name").textContent = info.name;
  byId("wave-tier-range").textContent = info.capped
    ? `Tier maximal · vague ${start}+`
    : `Tier · vagues ${start}–${end}`;
  byId("wave-progress-fill").style.width = `${progress}%`;
  waveProgressTrack.setAttribute("aria-valuenow", String(progress));

  if (changed) {
    byId("wave-announcement").textContent = `Vague ${lastRenderedWave} remportée · vague ${wave} commencée !`;
    waveOverview.classList.remove("is-wave-change");
    window.requestAnimationFrame(() => waveOverview.classList.add("is-wave-change"));
  } else if (battleState.status === "wave_complete") {
    byId("wave-announcement").textContent = `Vague ${wave} remportée !`;
  } else if (!byId("wave-announcement").textContent) {
    byId("wave-announcement").textContent = "Continue jusqu’à la prochaine vague.";
  }
  lastRenderedWave = wave;
}

function renderBattle() {
  const player = battleState.player_team[battleState.player_active];
  const enemy = battleState.enemy_team[battleState.enemy_active];
  const replacementAvailable = battleState.player_team.some((pokemon, index) => index !== battleState.player_active && pokemon.hp > 0);
  const mustSwitch = battleState.status === "ongoing" && player.hp <= 0 && replacementAvailable;
  const waveComplete = battleState.status === "wave_complete";
  const modeLabel = battleState.mode === "waves"
    ? (waveComplete ? `Vague ${battleState.wave} remportée` : `Vague ${battleState.wave}`)
    : "Combat d’équipe";
  byId("battle-heading").textContent = modeLabel;
  byId("battle-turn").textContent = `Tour ${battleState.turn}`;
  renderWaveOverview();
  if (player) renderSide("player", player);
  if (enemy) renderSide("enemy", enemy);
  renderMoves();
  renderItems();
  renderParty();
  renderLog();
  switchPrompt.hidden = !mustSwitch;
  switchPrompt.textContent = mustSwitch ? "Ton Pokémon est K.O. Choisis un remplaçant pour continuer." : "";
  partyPanel.classList.toggle("needs-switch", mustSwitch);
  if (mustSwitch && lastForcedSwitchPokemonId !== player.id) {
    lastForcedSwitchPokemonId = player.id;
    window.requestAnimationFrame(() => {
      partyPanel.scrollIntoView({ behavior: "smooth", block: "center" });
      partyPanel.querySelector(".battle-party-member:not(:disabled)")?.focus({ preventScroll: true });
    });
  } else if (!mustSwitch) {
    lastForcedSwitchPokemonId = null;
  }
  nextWaveButton.hidden = !waveComplete;
  if (waveComplete && scheduledAutoAdvanceWave !== battleState.wave) {
    const completedWave = battleState.wave;
    scheduledAutoAdvanceWave = completedWave;
    window.setTimeout(() => {
      if (battleState?.status === "wave_complete" && battleState.wave === completedWave && !requestPending) {
        continueToNextWave();
      }
    }, 2500);
  }
  restartLink.hidden = !["won", "lost"].includes(battleState.status);
  if (battleState.status === "lost") {
    movesPanel.replaceChildren();
    partyPanel.replaceChildren();
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Le serveur n’a pas pu traiter l’action.");
  return result;
}

async function submitAction(action) {
  if (requestPending || battleState.status !== "ongoing") return;
  requestPending = true;
  renderMoves();
  renderItems();
  renderParty();
  try {
    battleState = await requestJson(battleApp.dataset.turnUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
  } catch (error) {
    window.alert(error.message);
  } finally {
    requestPending = false;
    renderBattle();
  }
}

async function continueToNextWave() {
  if (requestPending) return;
  requestPending = true;
  nextWaveButton.disabled = true;
  try {
    battleState = await requestJson(battleApp.dataset.waveUrl, { method: "POST" });
  } catch (error) {
    window.alert(error.message);
  } finally {
    requestPending = false;
    nextWaveButton.disabled = false;
    renderBattle();
  }
}

nextWaveButton.addEventListener("click", continueToNextWave);

requestJson(battleApp.dataset.stateUrl)
  .then((state) => { battleState = state; renderBattle(); })
  .catch((error) => { byId("battle-heading").textContent = error.message; });