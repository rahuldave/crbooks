const search = document.querySelector("#search");
const buttons = [...document.querySelectorAll("[data-filter]")];
const cards = [...document.querySelectorAll(".book-card")];
const resultCount = document.querySelector("#result-count");
const emptyState = document.querySelector("#empty-state");
let activeCategory = "all";

function applyFilters() {
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  for (const card of cards) {
    const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
    const matchesQuery = !query || card.dataset.search.includes(query);
    const show = matchesCategory && matchesQuery;
    card.hidden = !show;
    if (show) visible += 1;
  }
  resultCount.textContent = visible === cards.length
    ? `Showing all ${visible} books`
    : `Showing ${visible} of ${cards.length} books`;
  emptyState.hidden = visible !== 0;
}

for (const button of buttons) {
  button.addEventListener("click", () => {
    activeCategory = button.dataset.filter;
    for (const item of buttons) item.classList.toggle("active", item === button);
    applyFilters();
  });
}

search.addEventListener("input", applyFilters);

