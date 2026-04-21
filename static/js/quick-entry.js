// quick-entry.js — UI logic for the quick-entry bottom sheet.
// Open/close/swipe-to-dismiss is handled by the shared BottomSheet module.

function openQuickEntry() {
    BottomSheet.open('quick-entry', {url: '/transactions/quick-form'});
}

function closeQuickEntry() {
    var form = document.getElementById('quick-entry-form');
    if (form) form.reset();
    var result = document.getElementById('quick-entry-result');
    if (result) result.innerHTML = '';
    BottomSheet.close('quick-entry');
}
