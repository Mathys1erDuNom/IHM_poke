const battleApp = document.getElementById("battle-app");
const battleLog = document.getElementById("battle-log");
const movesPanel = document.getElementById("battle-moves");
const itemsPanel = document.getElementById("battle-items");
const partyPanel = document.getElementById("battle-party");
const nextWaveButton = document.getElementById("battle-next-wave");
const restartLink = document.getElementById("battle-restart");
let battleState = null;
let requestPending = false;
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
  byId(`${side}-level`).textContent = `Niv. ${pokemon.level}`;
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
    button.disabled = !canChooseMove || move.pp <= 0;
    const details = move.category === "statut" ? "Statut" : `Puiss. ${move.power}`;
    button.innerHTML = `<strong></strong><span></span><small></small>`;
    button.querySelector("strong").textContent = move.name;
    button.querySelector("span").textContent = `${move.type} · ${details} · Préc. ${move.accuracy}%`;
    button.querySelector("small").textContent = `PP ${move.pp} / ${move.max_pp}`;
    button.addEventListener("click", () => submitAction({ kind: "move", move_id: move.id }));
    movesPanel.appendChild(button);
  });
  if (pokemon.moves.length && pokemon.moves.every((move) => move.pp <= 0)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "battle-move battle-move-fallback";
    button.disabled = !canChooseMove;
    button.innerHTML = `<strong></strong><span></span><small></small>`;
    button.querySelector("strong").textContent = "Lutte";
    button.querySelector("span").textContent = "normal · Puiss. 50 · Préc. 100%";
    button.querySelector("small").textContent = "PP illimités · 25% de recul";
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

function renderBattle() {
  const player = battleState.player_team[battleState.player_active];
  const enemy = battleState.enemy_team[battleState.enemy_active];
  const modeLabel = battleState.mode === "waves" ? `Vague ${battleState.wave}` : "Combat d’équipe";
  byId("battle-heading").textContent = modeLabel;
  byId("battle-turn").textContent = `Tour ${battleState.turn}`;
  if (player) renderSide("player", player);
  if (enemy) renderSide("enemy", enemy);
  renderMoves();
  renderItems();
  renderParty();
  renderLog();
  nextWaveButton.hidden = battleState.status !== "wave_complete";
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

nextWaveButton.addEventListener("click", async () => {
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
});

requestJson(battleApp.dataset.stateUrl)
  .then((state) => { battleState = state; renderBattle(); })
  .catch((error) => { byId("battle-heading").textContent = error.message; });