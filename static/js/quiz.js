const quizApp = document.getElementById("quiz-app");
const feedback = document.getElementById("quiz-feedback");
const rewardPanel = document.getElementById("quiz-reward");
const rewardImage = document.getElementById("quiz-pokemon");
const rewardMessage = document.getElementById("quiz-reward-message");
const answerButtons = [...document.querySelectorAll(".quiz-option")];
let answerPending = false;

answerButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (answerPending) return;

    answerPending = true;
    answerButtons.forEach((option) => {
      option.disabled = true;
      option.classList.remove("is-selected", "is-wrong");
    });
    button.classList.add("is-selected");
    feedback.className = "quiz-feedback";
    feedback.textContent = "Vérification de ta réponse…";

    try {
      const response = await fetch(quizApp.dataset.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_id: quizApp.dataset.challengeId,
          answer: button.dataset.answer,
        }),
      });
      const result = await response.json();

      if (response.status === 401) {
        window.location.assign("/connexion");
        return;
      }
      if (!response.ok) throw new Error(result.message || "Le quiz a expiré.");

      if (!result.correct) {
        answerPending = false;
        button.classList.remove("is-selected");
        button.classList.add("is-wrong");
        answerButtons.forEach((option) => { option.disabled = false; });
        feedback.classList.add("is-error");
        feedback.textContent = result.message;
        return;
      }

      feedback.classList.add("is-success");
      feedback.textContent = "Bonne réponse ! Préparation de ta récompense…";
      answerButtons.forEach((option) => { option.classList.add("is-locked"); });

      window.setTimeout(() => {
        rewardImage.src = result.pokemon.image;
        rewardImage.alt = result.pokemon.name;
        rewardMessage.textContent = result.message;
        rewardPanel.hidden = false;
        rewardPanel.classList.add("is-visible");
      }, 900);
    } catch (error) {
      answerPending = false;
      answerButtons.forEach((option) => { option.disabled = false; });
      feedback.classList.add("is-error");
      feedback.textContent = error.message || "Impossible de valider ta réponse.";
    }
  });
});