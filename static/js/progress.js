/**
 * Page progress bar — thin animated bar at top during HTMX requests.
 *
 * Like YouTube/GitHub loading indicator. Hooks into HTMX lifecycle:
 * - htmx:beforeRequest → start after 100ms delay
 * - htmx:afterSettle → complete to 100% then fade
 * - htmx:responseError → turn red briefly
 *
 * Re-queries #page-progress on each event because hx-boost replaces <body>,
 * creating a new #page-progress element. A cached reference would become stale.
 */
(function() {
    var timer = null;

    function getBar() {
        return document.getElementById('page-progress');
    }

    document.addEventListener('htmx:beforeRequest', function() {
        var bar = getBar();
        if (!bar) return;

        timer = setTimeout(function() {
            bar.style.opacity = '1';
            bar.setAttribute('aria-hidden', 'false');
            bar.style.width = '30%';
            setTimeout(function() { bar.style.width = '70%'; }, 200);
            setTimeout(function() { bar.style.width = '90%'; }, 500);
        }, 100);
    });

    function complete() {
        clearTimeout(timer);
        var bar = getBar();
        if (!bar) return;

        bar.style.width = '100%';
        setTimeout(function() {
            bar.style.opacity = '0';
            bar.setAttribute('aria-hidden', 'true');
            setTimeout(function() { bar.style.width = '0'; }, 300);
        }, 150);
    }

    document.addEventListener('htmx:afterSettle', complete);

    document.addEventListener('htmx:responseError', function() {
        var bar = getBar();
        if (!bar) return;

        clearTimeout(timer);
        bar.style.width = '100%';
        bar.className = bar.className.replace('bg-teal-500', 'bg-red-500');
        setTimeout(function() {
            bar.style.opacity = '0';
            bar.setAttribute('aria-hidden', 'true');
            setTimeout(function() {
                bar.style.width = '0';
                bar.className = bar.className.replace('bg-red-500', 'bg-teal-500');
            }, 300);
        }, 1000);
    });
})();
