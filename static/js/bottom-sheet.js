// bottom-sheet.js — Reusable bottom sheet manager.
// Provides open/close/swipe-to-dismiss for any element with data-bottom-sheet="name".
// Similar to a Laravel/Livewire modal component but using vanilla JS + HTMX.
//
// Usage:
//   BottomSheet.open('sheet-name')                         — open with no content load
//   BottomSheet.open('sheet-name', {url: '/form'})         — open and load content via HTMX
//   BottomSheet.open('sheet-name', {trigger: 'my-event'})  — open and fire HTMX trigger
//   BottomSheet.close('sheet-name')                        — close and clear content

var BottomSheet = (function() {
    var sheets = {};

    // register (or re-register) a sheet by looking up its DOM elements.
    // Always refreshes references to handle hx-boost body swaps that replace DOM nodes.
    function register(name) {
        var overlay = document.getElementById(name + '-overlay');
        var sheet = document.getElementById(name + '-sheet');
        var handle = document.getElementById(name + '-handle');
        var content = document.getElementById(name + '-content');

        if (!overlay || !sheet) return null;

        var existing = sheets[name];

        // If already registered with the same DOM nodes, skip re-registration
        if (existing && existing.overlay === overlay && existing.sheet === sheet) {
            return existing;
        }

        var entry = { overlay: overlay, sheet: sheet, handle: handle, content: content };
        sheets[name] = entry;

        // Close on overlay click
        overlay.addEventListener('click', function() { close(name); });

        // Swipe-to-dismiss on drag handle
        if (handle) {
            setupSwipe(name, handle, sheet);
        }

        return entry;
    }

    function setupSwipe(name, handle, sheet) {
        var startY = 0, currentY = 0, isDragging = false;

        handle.addEventListener('touchstart', function(e) {
            startY = e.touches[0].clientY;
            isDragging = true;
            sheet.style.transition = 'none';
        });

        handle.addEventListener('touchmove', function(e) {
            if (!isDragging) return;
            currentY = e.touches[0].clientY;
            var diff = currentY - startY;
            if (diff > 0) {
                sheet.style.transform = 'translateY(' + diff + 'px)';
            }
        });

        handle.addEventListener('touchend', function() {
            if (!isDragging) return;
            isDragging = false;
            sheet.style.transition = '';
            sheet.style.transform = '';
            if (currentY - startY > 100) {
                close(name);
            } else {
                sheet.classList.add('translate-y-0');
            }
            startY = 0;
            currentY = 0;
        });
    }

    // Focus the first visible input/textarea/select inside a container
    function focusFirstInput(container) {
        var el = container.querySelector('input:not([type="hidden"]), textarea, select');
        if (el) el.focus();
    }

    function open(name, opts) {
        // Always re-register to get fresh DOM references (hx-boost swaps the body)
        var s = register(name);
        if (!s) return;

        s.overlay.classList.remove('hidden');
        s.sheet.offsetHeight; // Force reflow so transition fires
        s.sheet.classList.remove('translate-y-full');
        s.sheet.classList.add('translate-y-0');
        document.body.style.overflow = 'hidden';

        // Load content via HTMX if URL provided
        if (opts && opts.url) {
            htmx.ajax('GET', opts.url, {
                target: '#' + name + '-content',
                swap: 'innerHTML'
            });
            // Focus first input after HTMX content settles
            s.content.addEventListener('htmx:afterSettle', function handler() {
                s.content.removeEventListener('htmx:afterSettle', handler);
                focusFirstInput(s.content);
            });
        } else if (s.content) {
            // For static/pre-loaded content, focus after slide-up animation (300ms)
            setTimeout(function() { focusFirstInput(s.content); }, 300);
        }

        // Fire a custom HTMX trigger event on the sheet element
        if (opts && opts.trigger) {
            htmx.trigger(s.sheet, opts.trigger);
        }

        // Optional callback after open
        if (opts && opts.onOpen) {
            opts.onOpen(s);
        }
    }

    function close(name) {
        var s = sheets[name];
        if (!s) return;

        s.sheet.classList.remove('translate-y-0');
        s.sheet.classList.add('translate-y-full');
        s.overlay.classList.add('hidden');
        document.body.style.overflow = '';

        // Clear content after animation unless marked as persistent
        if (s.content && !s.sheet.hasAttribute('data-bottom-sheet-persist')) {
            setTimeout(function() {
                s.content.innerHTML = '';
            }, 300);
        }
    }

    function init() {
        document.querySelectorAll('[data-bottom-sheet]').forEach(function(el) {
            var name = el.getAttribute('data-bottom-sheet');
            register(name);
        });
    }

    // Close topmost open sheet on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Find any open sheet (overlay not hidden) and close it
            for (var name in sheets) {
                var s = sheets[name];
                if (s && s.overlay && !s.overlay.classList.contains('hidden')) {
                    close(name);
                    break;
                }
            }
        }
    });

    // Auto-initialize on page load and after HTMX content swaps
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    document.addEventListener('htmx:afterSettle', init);

    return { open: open, close: close, init: init };
})();
