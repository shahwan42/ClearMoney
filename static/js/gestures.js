/**
 * TASK-080: Pull-to-refresh and swipe gestures for mobile.
 *
 * Pull-to-refresh: drag down on the dashboard or transaction list to reload.
 * Swipe-to-delete: swipe left on a transaction row to reveal delete action.
 *
 * These are minimal vanilla JS touch handlers — no library needed.
 */

(function() {
    'use strict';

    // --- Pull-to-Refresh ---
    // Works on any element with [data-pull-refresh] attribute.
    // The attribute value is the URL to refresh (via HTMX).
    // Guard: re-check scrollY during touchmove to avoid triggering during momentum bounces.

    var pullStart = 0;
    var pulling = false;
    var pullIndicator = null;
    var pullValid = false; // Only true when indicator shown after valid sustained pull

    document.addEventListener('touchstart', function(e) {
        var target = e.target.closest('[data-pull-refresh]');
        if (!target) return;
        if (window.scrollY > 0) return; // Strict: only pull when truly at top (scrollY = 0)
        pullStart = e.touches[0].clientY;
        pulling = true;
        pullValid = false;
    }, { passive: true });

    document.addEventListener('touchmove', function(e) {
        if (!pulling) return;
        if (window.scrollY > 0) { pulling = false; return; } // Cancel if page scrolled at all
        var distance = e.touches[0].clientY - pullStart;
        if (distance < 0) { pulling = false; return; }
        if (distance > 60 && !pullIndicator) {
            pullValid = true;
            pullIndicator = document.createElement('div');
            pullIndicator.className = 'fixed top-0 left-0 right-0 flex justify-center py-2 z-50 animate-fade-in';
            pullIndicator.innerHTML = '<div class="bg-teal-500 text-white text-xs px-3 py-1 rounded-full shadow">Release to refresh</div>';
            document.body.appendChild(pullIndicator);
        }
    }, { passive: true });

    document.addEventListener('touchend', function() {
        pulling = false;
        if (pullIndicator) {
            pullIndicator.remove();
            pullIndicator = null;
            if (pullValid) {
                pullValid = false;
                // Reload the page (simple approach — works with HTMX boosted pages)
                window.location.reload();
            }
        }
        pullValid = false;
    });

    // --- Swipe-to-Delete ---
    // Works on any element with [data-swipe-delete] attribute.
    // The attribute value is the URL to DELETE (via fetch).

    var swipeStart = 0;
    var swipeEl = null;

    document.addEventListener('touchstart', function(e) {
        var target = e.target.closest('[data-swipe-delete]');
        if (!target) return;
        swipeStart = e.touches[0].clientX;
        swipeEl = target;
    }, { passive: true });

    document.addEventListener('touchmove', function(e) {
        if (!swipeEl) return;
        var dx = e.touches[0].clientX - swipeStart;
        if (dx > 0) { dx = 0; } // Only swipe left
        if (dx < -80) { dx = -80; }
        swipeEl.style.transform = 'translateX(' + dx + 'px)';
        swipeEl.style.transition = 'none';

        // Show delete indicator
        if (dx < -50 && !swipeEl.querySelector('.swipe-delete-bg')) {
            var bg = document.createElement('div');
            bg.className = 'swipe-delete-bg absolute right-0 top-0 bottom-0 w-16 bg-red-500 flex items-center justify-center rounded-r-lg';
            bg.innerHTML = '<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>';
            swipeEl.style.position = 'relative';
            swipeEl.style.overflow = 'visible';
            swipeEl.appendChild(bg);
        }
    }, { passive: true });

    document.addEventListener('touchend', function() {
        if (!swipeEl) return;
        var dx = parseInt(swipeEl.style.transform.replace(/[^-\d]/g, '') || '0');
        if (dx <= -60) {
            // Trigger delete
            var url = swipeEl.getAttribute('data-swipe-delete');
            if (url && confirm('Delete this transaction?')) {
                fetch(url, { method: 'DELETE', headers: { 'HX-Request': 'true' } })
                    .then(function() {
                        swipeEl.style.transition = 'all 0.3s ease';
                        swipeEl.style.transform = 'translateX(-100%)';
                        swipeEl.style.opacity = '0';
                        setTimeout(function() { swipeEl.remove(); }, 300);
                    });
            } else {
                swipeEl.style.transition = 'transform 0.2s ease';
                swipeEl.style.transform = 'translateX(0)';
                var bg = swipeEl.querySelector('.swipe-delete-bg');
                if (bg) bg.remove();
            }
        } else {
            swipeEl.style.transition = 'transform 0.2s ease';
            swipeEl.style.transform = 'translateX(0)';
            var bg = swipeEl.querySelector('.swipe-delete-bg');
            if (bg) bg.remove();
        }
        swipeEl = null;
    });
})();
