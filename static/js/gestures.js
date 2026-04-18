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
        // Must be exactly at the top — scrollY > 0 means content is still scrolling.
        if (window.scrollY > 0) return;
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
        if (window.scrollY > 0) {
            pulling = false;
            return;
        }

        var distance = e.touches[0].clientY - pullStart;
        if (distance < 0) { pulling = false; return; }

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

    // --- Swipe-to-Delete ---
    // Works on any element with [data-swipe-delete] attribute.
    // Swipe left reveals a delete button; user must tap the button to delete.
    // Swipe right or tap elsewhere dismisses the revealed button.
    // Only one row can be revealed at a time.

    var swipeStart = 0;
    var swipeEl = null;
    var revealedEl = null; // Track which row currently has delete button revealed

    function resetSwipeRow(el) {
        if (!el) return;
        el.style.transition = 'transform 0.2s ease';
        el.style.transform = 'translateX(0)';
        var bg = el.querySelector('.swipe-delete-bg');
        if (bg) bg.remove();
    }

    function revealDeleteButton(el) {
        if (!el) return;
        var bg = document.createElement('div');
        bg.className = 'swipe-delete-bg absolute right-0 top-0 bottom-0 w-24 bg-red-500 flex items-center justify-center rounded-r-lg';
        bg.innerHTML = '<button type="button" class="swipe-delete-btn w-full h-full flex flex-col items-center justify-center text-white" aria-label="Delete transaction"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg><span class="text-xs font-medium">Delete</span></button>';
        el.style.position = 'relative';
        el.style.overflow = 'visible';
        el.appendChild(bg);

        bg.querySelector('.swipe-delete-btn').addEventListener('click', function(e) {
            e.stopPropagation();
            var url = el.getAttribute('data-swipe-delete');
            if (url) {
                var note = el.querySelector('[data-transaction-note]');
                var date = el.querySelector('[data-transaction-date]');
                var amount = el.querySelector('[data-transaction-amount]');
                var summary = '';
                if (amount) summary = amount.textContent.trim() + (note ? ' — ' + note.textContent.trim() : '') + (date ? ' (' + date.textContent.trim() + ')' : '');

                ConfirmDialog.show({
                    title: 'Delete transaction',
                    message: summary || 'Are you sure you want to delete this transaction?',
                    confirmText: 'Delete',
                    confirmClass: 'bg-red-500 hover:bg-red-600 text-white',
                    cancelText: 'Cancel'
                }).then(function(confirmed) {
                    if (confirmed) {
                        fetch(url, { method: 'DELETE', headers: { 'HX-Request': 'true' } })
                            .then(function(resp) {
                                el.style.transition = 'all 0.3s ease';
                                el.style.transform = 'translateX(-100%)';
                                el.style.opacity = '0';
                                setTimeout(function() { el.remove(); }, 300);
                                revealedEl = null;
                                var related = resp.headers.get('X-Related-Deleted');
                                if (related) {
                                    related.split(',').forEach(function(rid) {
                                        var relEl = document.getElementById('tx-' + rid);
                                        if (relEl) {
                                            relEl.style.transition = 'all 0.3s ease';
                                            relEl.style.opacity = '0';
                                            relEl.style.maxHeight = '0';
                                            setTimeout(function() { relEl.remove(); }, 300);
                                        }
                                    });
                                }
                            });
                    } else {
                        resetSwipeRow(el);
                        revealedEl = null;
                    }
                });
            } else {
                resetSwipeRow(el);
                revealedEl = null;
            }
        });
    }

    document.addEventListener('touchstart', function(e) {
        var target = e.target.closest('[data-swipe-delete]');
        if (target) {
            if (revealedEl && revealedEl !== target) {
                resetSwipeRow(revealedEl);
                revealedEl = null;
            }
            swipeStart = e.touches[0].clientX;
            swipeEl = target;
        } else if (revealedEl) {
            resetSwipeRow(revealedEl);
            revealedEl = null;
        }
    }, { passive: true });

    document.addEventListener('click', function(e) {
        if (revealedEl && !revealedEl.contains(e.target)) {
            resetSwipeRow(revealedEl);
            revealedEl = null;
        }
    });

    document.addEventListener('touchmove', function(e) {
        if (!swipeEl) return;
        var dx = e.touches[0].clientX - swipeStart;
        if (dx > 0) { dx = 0; }
        if (dx < -80) { dx = -80; }
        swipeEl.style.transform = 'translateX(' + dx + 'px)';
        swipeEl.style.transition = 'none';
    }, { passive: true });

    document.addEventListener('touchend', function() {
        if (!swipeEl) return;
        var dx = parseInt(swipeEl.style.transform.replace(/[^-\d]/g, '') || '0');
        if (dx <= -60) {
            if (revealedEl && revealedEl !== swipeEl) {
                resetSwipeRow(revealedEl);
            }
            revealDeleteButton(swipeEl);
            revealedEl = swipeEl;
        } else {
            resetSwipeRow(swipeEl);
            if (revealedEl === swipeEl) {
                revealedEl = null;
            }
        }
        swipeEl = null;
    });
})();
