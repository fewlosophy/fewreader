function filterLibraryCards(query) {
  const q = query.trim().toLowerCase();
  const cards = document.querySelectorAll('#library-grid .library-card');
  let count = 0;
  cards.forEach(card => {
    const name = card.getAttribute('data-name') || '';
    if (!q || name.includes(q)) {
      card.style.display = '';
      count++;
    } else {
      card.style.display = 'none';
    }
  });
  const countEl = document.getElementById('library-count');
  if (countEl) {
    countEl.textContent = `${count} item${count !== 1 ? 's' : ''}${q ? ' found' : ''}`;
  }
}

// ── Full Text Search ────────────────────────────────────
let searchDebounceTimeout = null;

function openFullTextSearch() {
  const modal = document.getElementById('fts-modal');
  modal.classList.remove('opacity-0', 'pointer-events-none');
  const input = document.getElementById('fts-input');
  setTimeout(() => input.focus(), 100);
}

function closeFullTextSearch(e) {
  if (e && e.target !== e.currentTarget && e.currentTarget.id === 'fts-modal') return;
  const modal = document.getElementById('fts-modal');
  modal.classList.add('opacity-0', 'pointer-events-none');
}

function performSearch(query) {
  const q = query.trim();
  const resultsEl = document.getElementById('fts-results');
  const loading = document.getElementById('fts-loading');

  if (!q) {
    resultsEl.innerHTML = '<div class="p-8 text-center text-sm text-[var(--color-text-muted)]">Type to start searching your library.</div>';
    return;
  }

  loading.classList.remove('hidden');

  fetch('/api/search?q=' + encodeURIComponent(q))
    .then(res => res.json())
    .then(data => {
      const results = data.results || [];
      if (results.length === 0) {
        resultsEl.innerHTML = '<div class="p-8 text-center text-sm text-[var(--color-text-muted)]">No results found.</div>';
        return;
      }

      let html = '<div class="flex flex-col gap-1 py-1">';
      results.forEach(result => {
        html += `
          <a href="/read/${result.path}" class="flex flex-col p-3 rounded-xl hover:bg-[var(--color-surface-raised)] transition-colors">
            <span class="text-sm font-semibold text-[var(--color-text-primary)]">${result.name}</span>
            <span class="text-xs text-[var(--color-text-muted)] mt-1 truncate">${result.snippet}</span>
            <span class="text-[10px] text-[var(--color-text-muted)] mt-1 font-mono">${result.path}</span>
          </a>
        `;
      });
      html += '</div>';

      resultsEl.innerHTML = html;
    })
    .catch(err => {
      console.error("FTS fetch error:", err);
      resultsEl.innerHTML = '<div class="p-8 text-center text-sm text-red-500">Error fetching search results.</div>';
    })
    .finally(() => {
      loading.classList.add('hidden');
    });
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('fts-input');
  if (input) {
    input.addEventListener('input', (e) => {
      clearTimeout(searchDebounceTimeout);
      searchDebounceTimeout = setTimeout(() => {
        performSearch(e.target.value);
      }, 300);
    });
  }

  // Escape key to close modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeFullTextSearch();
    }

    // Command/Ctrl + K to open search
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      openFullTextSearch();
    }
  });
});
