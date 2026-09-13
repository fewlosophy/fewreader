let CURRENT_FILE_PATH = "";
let SCROLL_CONTAINER = null;

// ── Mobile TOC Drawer Controls ───────────────────────────
function closeTocDrawer() {
  const drawer = document.getElementById('toc-drawer');
  const backdrop = document.getElementById('toc-backdrop');
  if (!drawer || !backdrop) return;
  drawer.style.transform = '';
  backdrop.classList.add('opacity-0', 'pointer-events-none');
  backdrop.classList.remove('opacity-100');
}

function openTocDrawer() {
  const drawer = document.getElementById('toc-drawer');
  const backdrop = document.getElementById('toc-backdrop');
  if (!drawer || !backdrop) return;
  drawer.style.transform = 'translateX(0)';
  backdrop.classList.remove('opacity-0', 'pointer-events-none');
  backdrop.classList.add('opacity-100');
}

function toggleTocDrawer() {
  const drawer = document.getElementById('toc-drawer');
  if (!drawer) return;
  const isOpen = drawer.style.transform === 'translateX(0px)' || drawer.style.transform === 'translateX(0)';
  isOpen ? closeTocDrawer() : openTocDrawer();
}

// ── Smooth In-Page Anchor Navigation ─────────────────────
// Intercepts clicks on internal hash links (TOC, footnotes, headings)
// to prevent browser native fragment jumping from pushing the top navbar out of view.
function initAnchorNavigation() {
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href === '#') return;

    const targetId = decodeURIComponent(href.slice(1));
    const targetEl = document.getElementById(targetId);
    if (!targetEl || !SCROLL_CONTAINER) return;

    // CRITICAL: Prevent browser native anchor jump which scrolls parent containers / window
    e.preventDefault();

    // Automatically dismiss the mobile TOC drawer if open
    closeTocDrawer();

    // Ensure root & wrapper have not drifted
    window.scrollTo(0, 0);
    const mw = document.getElementById('main-wrapper');
    if (mw) mw.scrollTop = 0;

    // Calculate destination inside SCROLL_CONTAINER
    const containerRect = SCROLL_CONTAINER.getBoundingClientRect();
    const targetRect = targetEl.getBoundingClientRect();
    const currentScroll = SCROLL_CONTAINER.scrollTop;
    const targetOffset = targetRect.top - containerRect.top + currentScroll;

    SCROLL_CONTAINER.scrollTo({
      top: Math.max(0, targetOffset - 16),
      behavior: 'smooth'
    });

    // Update URL hash without native browser jump
    if (history.pushState) {
      history.pushState(null, '', href);
    }
  });

  // Handle initial hash on page load without ancestor drift
  if (window.location.hash && window.location.hash.length > 1) {
    setTimeout(() => {
      const targetId = decodeURIComponent(window.location.hash.slice(1));
      const targetEl = document.getElementById(targetId);
      if (targetEl && SCROLL_CONTAINER) {
        window.scrollTo(0, 0);
        const mw = document.getElementById('main-wrapper');
        if (mw) mw.scrollTop = 0;

        const containerRect = SCROLL_CONTAINER.getBoundingClientRect();
        const targetRect = targetEl.getBoundingClientRect();
        const currentScroll = SCROLL_CONTAINER.scrollTop;
        const targetOffset = targetRect.top - containerRect.top + currentScroll;

        SCROLL_CONTAINER.scrollTop = Math.max(0, targetOffset - 16);
      }
    }, 80);
  }
}

// ── Unified Reading Progress & TOC Scrollspy ────────────
function initScrollTracking() {
  if (!SCROLL_CONTAINER) return;

  const storageKey = 'readpos_' + CURRENT_FILE_PATH;
  const badge = document.getElementById('reading-progress-badge');
  const hasHash = Boolean(window.location.hash && window.location.hash.length > 1);

  // Restore saved scroll position only if not navigating to a specific hash anchor
  if (!hasHash) {
    const savedScroll = localStorage.getItem(storageKey);
    if (savedScroll) {
      const targetTop = parseInt(savedScroll, 10);
      if (!isNaN(targetTop) && targetTop > 0) {
        requestAnimationFrame(() => {
          SCROLL_CONTAINER.scrollTop = targetTop;
        });
      }
    }
  }

  const headings = Array.from(document.querySelectorAll('.reader-content h2, .reader-content h3, .reader-content h4'));
  const tocLinks = Array.from(document.querySelectorAll('.toc a'));
  let scrollTimeout = null;
  let isTicking = false;

  function updateScrollState() {
    // 1. Reading progress
    const maxScroll = SCROLL_CONTAINER.scrollHeight - SCROLL_CONTAINER.clientHeight;
    const currentScroll = SCROLL_CONTAINER.scrollTop;
    const percent = maxScroll > 0 ? Math.min(100, Math.max(0, Math.round((currentScroll / maxScroll) * 100))) : 0;
    if (badge) {
      badge.textContent = percent + '%';
    }

    // 2. TOC Scrollspy (only if headings exist)
    if (headings.length && tocLinks.length) {
      const containerTop = SCROLL_CONTAINER.getBoundingClientRect().top;
      let currentActiveId = null;

      for (const h of headings) {
        if (h.getBoundingClientRect().top - containerTop <= 120) {
          currentActiveId = h.id;
        }
      }

      tocLinks.forEach(link => {
        const href = link.getAttribute('href') || '';
        if (currentActiveId && href === '#' + currentActiveId) {
          link.classList.add('active-heading');
        } else {
          link.classList.remove('active-heading');
        }
      });
    }

    isTicking = false;
  }

  SCROLL_CONTAINER.addEventListener('scroll', () => {
    // Throttle layout reads and DOM updates to animation frames
    if (!isTicking) {
      requestAnimationFrame(updateScrollState);
      isTicking = true;
    }

    // Debounce localStorage write
    if (!scrollTimeout) {
      scrollTimeout = setTimeout(() => {
        localStorage.setItem(storageKey, SCROLL_CONTAINER.scrollTop);
        scrollTimeout = null;
      }, 150);
    }
  }, { passive: true });

  // Initial pass
  updateScrollState();
}

// ── Keyboard Shortcuts (Next / Previous Chapter) ────────
function initKeyboardNav() {
  document.addEventListener('keydown', (e) => {
    // Don't intercept if user is typing in an input
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    if (e.key === 'ArrowLeft' || e.key === 'j') {
      const prevLink = document.getElementById('link-prev-chapter');
      if (prevLink) prevLink.click();
    } else if (e.key === 'ArrowRight' || e.key === 'k') {
      const nextLink = document.getElementById('link-next-chapter');
      if (nextLink) nextLink.click();
    }
  });
}

function initReader(filePath) {
  CURRENT_FILE_PATH = filePath;
  SCROLL_CONTAINER = document.getElementById('main-scroll-container');
  initAnchorNavigation();
  initScrollTracking();
  initKeyboardNav();
}
