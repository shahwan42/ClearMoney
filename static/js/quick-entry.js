// quick-entry.js — Controls the quick-entry bottom sheet.
// The sheet slides up from the bottom when the FAB is tapped,
// similar to a native mobile bottom sheet with swipe-to-dismiss.

var overlay = document.getElementById('quick-entry-overlay');
var sheet = document.getElementById('quick-entry-sheet');

// setQuickEntryTab toggles the active/inactive styles on the tab bar buttons.
function setQuickEntryTab(mode) {
    var tabTx = document.getElementById('tab-transaction');
    var tabEx = document.getElementById('tab-exchange');
    var base = 'flex-1 py-2 text-sm font-medium text-center rounded-lg border';
    var active = base + ' bg-teal-50 text-teal-700 border-teal-200';
    var inactive = base + ' bg-gray-50 text-gray-500 border-gray-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-600';

    if (tabTx && tabEx) {
        tabTx.className = (mode === 'transaction') ? active : inactive;
        tabEx.className = (mode === 'exchange') ? active : inactive;
    }
}

function openQuickEntry() {
    // Show overlay and slide sheet up
    overlay.classList.remove('hidden');
    // Force reflow so transition fires
    sheet.offsetHeight;
    sheet.classList.remove('translate-y-full');
    sheet.classList.add('translate-y-0');

    // Reset to Transaction tab on every open
    setQuickEntryTab('transaction');

    // Trigger HTMX to load the form content
    htmx.trigger(sheet, 'open-quick-entry');

    // Prevent body scroll while sheet is open
    document.body.style.overflow = 'hidden';
}

function closeQuickEntry() {
    sheet.classList.remove('translate-y-0');
    sheet.classList.add('translate-y-full');
    overlay.classList.add('hidden');
    document.body.style.overflow = '';

    // Clear form content after animation so it reloads fresh next time
    setTimeout(function() {
        document.getElementById('quick-entry-content').innerHTML = '';
    }, 300);
}

// Swipe-to-dismiss: track touch on the sheet handle area
(function() {
    var handle = document.getElementById('quick-entry-handle');
    var startY = 0;
    var currentY = 0;
    var isDragging = false;

    handle.addEventListener('touchstart', function(e) {
        startY = e.touches[0].clientY;
        isDragging = true;
        sheet.style.transition = 'none';
    });

    handle.addEventListener('touchmove', function(e) {
        if (!isDragging) return;
        currentY = e.touches[0].clientY;
        var diff = currentY - startY;
        // Only allow dragging downward
        if (diff > 0) {
            sheet.style.transform = 'translateY(' + diff + 'px)';
        }
    });

    handle.addEventListener('touchend', function() {
        if (!isDragging) return;
        isDragging = false;
        sheet.style.transition = '';
        sheet.style.transform = '';

        var diff = currentY - startY;
        // If dragged more than 100px down, close the sheet
        if (diff > 100) {
            closeQuickEntry();
        } else {
            // Snap back
            sheet.classList.add('translate-y-0');
        }
        startY = 0;
        currentY = 0;
    });
})();
