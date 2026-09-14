// Theme
(function () {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved === 'dark' || (!saved && prefersDark)) {
    document.documentElement.classList.add('dark');
  }
})();

// Reader font family
(function () {
  if (localStorage.getItem('readingFont') === 'serif') {
    document.documentElement.classList.add('font-serif-mode');
  }
})();

// Reader font size
(function () {
  const sizes = ['1rem', '1.0625rem', '1.125rem', '1.3125rem', '1.5625rem'];
  const idx = Math.min(sizes.length - 1, Math.max(0, parseInt(localStorage.getItem('fontSizeIdx') || '2', 10)));
  document.documentElement.style.setProperty('--reader-font-size', sizes[idx]);
})();

// ── Theme ─────────────────────────────────────────────
function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// ── Font family mode (Sans vs Serif) ───────────────────
function toggleSerifFont() {
  const isSerif = document.documentElement.classList.toggle('font-serif-mode');
  localStorage.setItem('readingFont', isSerif ? 'serif' : 'sans');
  const btn = document.getElementById('btn-font-family');
  if (btn) btn.textContent = isSerif ? 'Serif' : 'Sans';
}

// ── Sidebar / drawer ──────────────────────────────────
function openSidebar() {
  document.getElementById('sidebar').style.transform = 'translateX(0)';
  const bd = document.getElementById('drawer-backdrop');
  bd.classList.remove('opacity-0', 'pointer-events-none');
  bd.classList.add('opacity-100');
}

function closeSidebar() {
  document.getElementById('sidebar').style.transform = '';
  const bd = document.getElementById('drawer-backdrop');
  bd.classList.add('opacity-0', 'pointer-events-none');
  bd.classList.remove('opacity-100');
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const isOpen = sidebar.style.transform === 'translateX(0px)' || sidebar.style.transform === 'translateX(0)';
  isOpen ? closeSidebar() : openSidebar();
}

// ── Font size ─────────────────────────────────────────
const FONT_SIZES = ['1rem', '1.0625rem', '1.125rem', '1.3125rem', '1.5625rem'];

function adjustFontSize(delta) {
  let idx = parseInt(localStorage.getItem('fontSizeIdx') || '2', 10);
  idx = Math.max(0, Math.min(FONT_SIZES.length - 1, idx + delta));
  document.documentElement.style.setProperty('--reader-font-size', FONT_SIZES[idx]);
  localStorage.setItem('fontSizeIdx', idx);
  updateFontSizeButtons();
}

function updateFontSizeButtons() {
  const idx = parseInt(localStorage.getItem('fontSizeIdx') || '2', 10);
  const dec = document.getElementById('btn-font-decrease');
  const inc = document.getElementById('btn-font-increase');
  if (dec) dec.disabled = idx === 0;
  if (inc) inc.disabled = idx === FONT_SIZES.length - 1;
}

// ── Real-time Sidebar Filter ──────────────────────────
function filterSidebar(query) {
  const q = query.trim().toLowerCase();
  const items = document.querySelectorAll('#sidebar-tree .sidebar-item');
  items.forEach(item => {
    const name = item.getAttribute('data-name') || '';
    if (!q || name.includes(q)) {
      item.style.display = '';
      // Auto-expand parent details
      let parentDetails = item.closest('details');
      while (parentDetails) {
        parentDetails.open = true;
        parentDetails = parentDetails.parentElement.closest('details');
      }
    } else {
      // If it's a category and has visible children matching query, show it
      const hasMatchingChild = item.querySelector(`.sidebar-item[data-name*="${q}"]`);
      if (q && hasMatchingChild) {
        item.style.display = '';
        const details = item.querySelector('details');
        if (details) details.open = true;
      } else {
        item.style.display = 'none';
      }
    }
  });
}

// ── Prevent Viewport / Wrapper Scroll Drift ────────────
function preventViewportScroll() {
  if (window.scrollY !== 0 || window.scrollX !== 0) {
    window.scrollTo(0, 0);
  }
  if (document.documentElement.scrollTop !== 0) {
    document.documentElement.scrollTop = 0;
  }
  if (document.body.scrollTop !== 0) {
    document.body.scrollTop = 0;
  }
  const mw = document.getElementById('main-wrapper');
  if (mw && mw.scrollTop !== 0) {
    mw.scrollTop = 0;
  }
}
window.addEventListener('scroll', preventViewportScroll, { passive: true });

document.addEventListener('DOMContentLoaded', () => {
  updateFontSizeButtons();
  const isSerif = document.documentElement.classList.contains('font-serif-mode');
  const btn = document.getElementById('btn-font-family');
  if (btn) btn.textContent = isSerif ? 'Serif' : 'Sans';
  const mw = document.getElementById('main-wrapper');
  if (mw) mw.addEventListener('scroll', preventViewportScroll, { passive: true });
});