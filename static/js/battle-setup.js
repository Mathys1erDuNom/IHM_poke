const setup = document.getElementById("battle-setup");
const form = document.getElementById("battle-form");

if (setup && form) {
  const maxTeamSize = Number(setup.dataset.maxTeam);
  const allPokemon = JSON.parse(document.getElementById("battle-pokemon-data").textContent);
  const pokemonPicker = document.getElementById("battle-pokemon-picker");
  const searchInput = document.getElementById("battle-search");
  const typeFilter = document.getElementById("battle-type-filter");
  const sortSelect = document.getElementById("battle-sort");
  const filterCount = document.getElementById("battle-filter-count");
  const pagination = document.getElementById("battle-selection-pagination");
  const previousPageButton = document.getElementById("battle-prev-page");
  const nextPageButton = document.getElementById("battle-next-page");
  const pageIndicator = document.getElementById("battle-page-indicator");
  const count = document.getElementById("team-count");
  const error = document.getElementById("battle-form-error");
  const enemyOptions = document.getElementById("enemy-options");
  const enemyMode = document.getElementById("enemy-mode");
  const selectionOrder = [];
  const pageSize = 25;
  let currentPage = 1;

  const normalize = (value) => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("fr");
  const updateCount = () => { count.textContent = `${selectionOrder.length} / ${maxTeamSize}`; };

  [...new Set(allPokemon.flatMap((pokemon) => pokemon.types || []))]
    .sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }))
    .forEach((type) => {
      const option = document.createElement("option");
      option.value = type;
      option.textContent = type;
      typeFilter.appendChild(option);
    });

  function filteredPokemon() {
    const query = normalize(searchInput.value.trim());
    const selectedType = typeFilter.value;
    const results = allPokemon
      .map((pokemon, index) => ({ pokemon, index }))
      .filter(({ pokemon }) => {
        const matchesName = !query || normalize(pokemon.name).includes(query);
        const matchesType = !selectedType || (pokemon.types || []).includes(selectedType);
        return matchesName && matchesType;
      });

    if (sortSelect.value === "alpha" || sortSelect.value === "reverse-alpha") {
      const direction = sortSelect.value === "alpha" ? 1 : -1;
      results.sort((a, b) => direction * a.pokemon.name.localeCompare(b.pokemon.name, "fr", { sensitivity: "base" }));
    } else {
      results.sort((a, b) => {
        const dateA = Date.parse(a.pokemon.captured_at || "");
        const dateB = Date.parse(b.pokemon.captured_at || "");
        if (Number.isFinite(dateA) && Number.isFinite(dateB) && dateA !== dateB) return dateB - dateA;
        if (Number.isFinite(dateA) !== Number.isFinite(dateB)) return Number.isFinite(dateB) ? 1 : -1;
        return a.index - b.index;
      });
    }
    return results.map(({ pokemon }) => pokemon);
  }

  function renderPokemonPage() {
    const results = filteredPokemon();
    const pageCount = Math.max(1, Math.ceil(results.length / pageSize));
    currentPage = Math.min(currentPage, pageCount);
    const start = (currentPage - 1) * pageSize;
    const pagePokemon = results.slice(start, start + pageSize);
    pokemonPicker.replaceChildren();

    if (!pagePokemon.length) {
      const empty = document.createElement("p");
      empty.className = "battle-empty-results";
      empty.textContent = "Aucun Pokémon ne correspond à ta recherche.";
      pokemonPicker.appendChild(empty);
    }

    pagePokemon.forEach((pokemon) => {
      const label = document.createElement("label");
      label.className = "battle-pokemon-choice";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.name = "pokemon";
      checkbox.value = pokemon.name;
      checkbox.checked = selectionOrder.includes(pokemon.name);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          if (selectionOrder.length >= maxTeamSize) {
            checkbox.checked = false;
            error.textContent = `Une équipe ne peut pas dépasser ${maxTeamSize} Pokémon.`;
            return;
          }
          selectionOrder.push(pokemon.name);
        } else {
          const selectedIndex = selectionOrder.indexOf(pokemon.name);
          if (selectedIndex !== -1) selectionOrder.splice(selectedIndex, 1);
        }
        error.textContent = "";
        updateCount();
      });
      label.appendChild(checkbox);

      if (pokemon.gif_url) {
        const image = document.createElement("img");
        image.src = pokemon.gif_url;
        image.alt = "";
        image.loading = "lazy";
        label.appendChild(image);
      }

      const info = document.createElement("span");
      info.className = "battle-pokemon-info";
      const name = document.createElement("strong");
      name.textContent = pokemon.name;
      const types = document.createElement("span");
      types.textContent = (pokemon.types || []).join(" / ");
      const stats = document.createElement("span");
      stats.className = "battle-stat-list";
      [
        ["PV", "hp"], ["Atq", "attack"], ["Déf", "defense"],
        ["Atq Spé", "special_attack"], ["Déf Spé", "special_defense"], ["Vit", "speed"],
      ].forEach(([labelText, stat]) => {
        const value = document.createElement("span");
        value.textContent = `${labelText} ${pokemon.stats[stat]}`;
        stats.appendChild(value);
      });
      info.append(name, types, stats);
      label.appendChild(info);
      pokemonPicker.appendChild(label);
    });

    filterCount.textContent = `${results.length} Pokémon · ${selectionOrder.length} sélectionné(s)`;
    pagination.hidden = results.length <= pageSize;
    previousPageButton.disabled = currentPage <= 1;
    nextPageButton.disabled = currentPage >= pageCount;
    pageIndicator.textContent = `Page ${currentPage} / ${pageCount}`;
    updateCount();
  }

  function resetPageAndRender() {
    currentPage = 1;
    renderPokemonPage();
  }

  searchInput.addEventListener("input", resetPageAndRender);
  typeFilter.addEventListener("change", resetPageAndRender);
  sortSelect.addEventListener("change", resetPageAndRender);
  previousPageButton.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderPokemonPage();
    }
  });
  nextPageButton.addEventListener("click", () => {
    const pageCount = Math.max(1, Math.ceil(filteredPokemon().length / pageSize));
    if (currentPage < pageCount) {
      currentPage += 1;
      renderPokemonPage();
    }
  });

  form.querySelectorAll('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      enemyOptions.hidden = input.value === "waves";
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const pokemonNames = [...selectionOrder];
    if (!pokemonNames.length) {
      error.textContent = "Sélectionne au moins un Pokémon.";
      return;
    }

    const mode = form.querySelector('input[name="mode"]:checked').value;
    const selectedEnemy = enemyMode.selectedOptions[0];
    const payload = {
      mode,
      pokemon_names: pokemonNames,
      enemy_mode: enemyMode.value,
      team_id: selectedEnemy.dataset.teamId || "",
    };
    const submitButton = document.getElementById("battle-start");
    submitButton.disabled = true;
    error.textContent = "Préparation du combat…";
    try {
      const response = await fetch(setup.dataset.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Le combat n’a pas pu démarrer.");
      window.location.assign(result.redirect);
    } catch (requestError) {
      error.textContent = requestError.message;
      submitButton.disabled = false;
    }
  });

  renderPokemonPage();
}