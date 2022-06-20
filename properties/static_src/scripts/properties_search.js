document.addEventListener("DOMContentLoaded", function () {
  const searchEl = document.getElementById("id_search");

  if (!searchEl) {
    return;
  }

  const properties = document.getElementById("properties");

  // properties is a bunch of card divs, if they contain the search term, show them
  const search = function () {
    const searchTerm = searchEl.value.toLowerCase();
    const cards = properties.querySelectorAll(".card");

    for (let i = 0; i < cards.length; i++) {
      const card = cards[i];
      const cardText = card.innerText.toLowerCase();

      if (cardText.includes(searchTerm)) {
        card.style.display = "block";
      } else {
        card.style.display = "none";
      }
    }
  };

  searchEl.addEventListener("keyup", search);
});
