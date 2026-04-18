// quick-entry.js — Tab switching for the quick-entry bottom sheet.
// Open/close/swipe-to-dismiss is handled by the shared BottomSheet module.

// setQuickEntryTab toggles the active/inactive styles on the tab bar buttons.
function setQuickEntryTab(mode) {
    var tabTx = document.getElementById('tab-transaction');
    var tabMove = document.getElementById('tab-move');
    var base = 'flex-1 py-3 text-sm font-medium text-center rounded-lg border';
    var active = base + ' bg-teal-50 text-teal-700 border-teal-200';
    var inactive = base + ' bg-gray-50 text-gray-500 border-gray-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-600';

    if (tabTx) tabTx.className = (mode === 'transaction') ? active : inactive;
    if (tabMove) tabMove.className = (mode === 'move') ? active : inactive;
}

function openQuickEntry() {
    setQuickEntryTab('transaction');
    BottomSheet.open('quick-entry');
}

function closeQuickEntry() {
    var form = document.getElementById('quick-entry-form');
    if (form) form.reset();
    var result = document.getElementById('quick-entry-result');
    if (result) result.innerHTML = '';
    BottomSheet.close('quick-entry');
}
