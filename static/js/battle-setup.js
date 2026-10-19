const setup = document.getElementById("battle-setup");
const form = document.getElementById("battle-form");

if (setup && form) {
  const maxTeamSize = Number(setup.dataset.maxTeam);
  const checks = [...form.querySelectorAll('input[name="pokemon"]')];
  const count = document.getElementById("team-count");
  const error = document.getElementById("battle-form-error");
  const enemyOptions = document.getElementById("enemy-options");
  const enemyMode = document.getElementById("enemy-mode");
  const selectionOrder = [];

  const selectedCount = () => checks.filter((input) => input.checked).length;
  const updateCount = () => { count.textContent = `${selectedCount()} / ${maxTeamSize}`; };

  checks.forEach((input) => {
    input.addEventListener("change", () => {
      if (selectedCount() > maxTeamSize) {
        input.checked = false;
        error.textContent = `Une équipe ne peut pas dépasser ${maxTeamSize} Pokémon.`;
      } else {
        error.textContent = "";
        const existingIndex = selectionOrder.indexOf(input.value);
        if (input.checked && existingIndex === -1) {
          selectionOrder.push(input.value);
        } else if (!input.checked && existingIndex !== -1) {
          selectionOrder.splice(existingIndex, 1);
        }
      }
      updateCount();
    });
  });

  form.querySelectorAll('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      enemyOptions.hidden = input.value === "waves";
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const pokemonNames = selectionOrder.filter((name) => checks.some((input) => input.checked && input.value === name));
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

  updateCount();
}