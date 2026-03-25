/**
 * Page progress bar — thin animated bar at top during HTMX requests.
 *
 * Like YouTube/GitHub loading indicator. Hooks into HTMX lifecycle:
 * - htmx:beforeRequest → start after 100ms delay
 * - htmx:afterSettle → complete to 100% then fade
 * - htmx:responseError → turn red briefly
 */
(function() {
    var bar = document.getElementById('page-progress');
    if (!bar) return;

    var timer = null;

    document.addEventListener('htmx:beforeRequest', function() {
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
        bar.style.width = '100%';
        setTimeout(function() {
            bar.style.opacity = '0';
            bar.setAttribute('aria-hidden', 'true');
            setTimeout(function() { bar.style.width = '0'; }, 300);
        }, 150);
    }

    document.addEventListener('htmx:afterSettle', complete);

    document.addEventListener('htmx:responseError', function() {
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
