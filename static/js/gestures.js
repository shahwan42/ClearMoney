/**
 * TASK-080: Pull-to-refresh gestures for mobile.
 *
 * Pull-to-refresh: drag down on the dashboard or transaction list to reload.
 *
 * This is a minimal vanilla JS touch handler — no library needed.
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
    var distanceThresholdExceeded = false; // Track if we've crossed 60px threshold

    // Track the last time the page scrolled so we can ignore touchstart events
    // that arrive while momentum is still carrying the page to the top.
    var lastScrollTime = 0;
    document.addEventListener('scroll', function() {
        lastScrollTime = Date.now();
    }, { passive: true });

    document.addEventListener('touchstart', function(e) {
        var target = e.target.closest('[data-pull-refresh]');
        if (!target) return;

        // Find the scrolling container. In our app it's usually <main>, but could be a modal/sheet.
        var scroller = target.closest('.overflow-y-auto') || target.closest('main') || window;
        var scrollTop = (scroller === window) ? window.scrollY : scroller.scrollTop;

        // Must be exactly at the top.
        if (scrollTop > 0) return;

        // Ignore if the page was scrolling within the last 400 ms (momentum arrival).
        // This prevents a fast scroll-to-top from arming pull-to-refresh.
        if (Date.now() - lastScrollTime < 400) return;
        pullStart = e.touches[0].clientY;
        pulling = true;
        pullValid = false;
        distanceThresholdExceeded = false;
    }, { passive: true });

    document.addEventListener('touchmove', function(e) {
        if (!pulling) return;

        // Cancel if the page somehow gained scroll offset during the gesture.
        var target = e.target.closest('[data-pull-refresh]');
        var scroller = target ? (target.closest('.overflow-y-auto') || target.closest('main') || window) : window;
        var scrollTop = (scroller === window) ? window.scrollY : scroller.scrollTop;

        if (scrollTop > 0) {
            pulling = false;
            if (pullIndicator) {
                pullIndicator.remove();
                pullIndicator = null;
            }
            return;
        }

        var distance = e.touches[0].clientY - pullStart;
        if (distance < 0) {
            pulling = false;
            if (pullIndicator) {
                pullIndicator.remove();
                pullIndicator = null;
            }
            return;
        }

        // Only show indicator once we cross 60px; don't update on subsequent moves
        if (distance > 60 && !distanceThresholdExceeded) {
            distanceThresholdExceeded = true;
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
})();
