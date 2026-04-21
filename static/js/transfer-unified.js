// transfer-unified.js — Unified transfer/exchange mode detection and field calculation.
// Auto-detects transfer (same currency) vs exchange (different currencies)
// based on selected account currencies.

// Detect whether accounts have same or different currencies.
// Returns 'transfer', 'exchange', or null (incomplete selection).
function detectTransferMode() {
    var srcSel = document.getElementById('transfer-src');
    var dstSel = document.getElementById('transfer-dst');
    if (!srcSel || !dstSel) return null;
    var srcOpt = srcSel.selectedOptions[0];
    var dstOpt = dstSel.selectedOptions[0];
    var srcCur = srcOpt ? srcOpt.getAttribute('data-currency') : '';
    var dstCur = dstOpt ? dstOpt.getAttribute('data-currency') : '';
    if (!srcCur || !dstCur) return null;
    return srcCur === dstCur ? 'transfer' : 'exchange';
}

// Called on account select change — shows/hides appropriate fields and
// updates form action + button label.
function updateTransferMode() {
    var mode = detectTransferMode();
    var transferFields = document.getElementById('transfer-transfer-fields');
    var exchangeFields = document.getElementById('transfer-exchange-fields');
    var form = document.getElementById('transfer-unified-form');
    var submitLabel = document.getElementById('transfer-submit-label');
    var indicator = document.getElementById('transfer-mode-indicator');

    if (mode === 'transfer') {
        // Show transfer fields, hide exchange fields
        transferFields.classList.remove('hidden');
        transferFields.setAttribute('aria-hidden', 'false');
        exchangeFields.classList.add('hidden');
        exchangeFields.setAttribute('aria-hidden', 'true');
        // Enable transfer inputs, disable exchange inputs
        _setFieldsDisabled(transferFields, false);
        _setFieldsDisabled(exchangeFields, true);
        _clearFields(exchangeFields);
        // Update form target
        form.setAttribute('hx-post', '/transactions/transfer');
        htmx.process(form);
        submitLabel.textContent = 'Transfer';
        // Mode indicator
        indicator.textContent = 'Same currency \u2014 transfer mode';
        indicator.className = 'text-xs font-medium px-3 py-1.5 rounded-lg text-center bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300';
    } else if (mode === 'exchange') {
        // Show exchange fields, hide transfer fields
        exchangeFields.classList.remove('hidden');
        exchangeFields.setAttribute('aria-hidden', 'false');
        transferFields.classList.add('hidden');
        transferFields.setAttribute('aria-hidden', 'true');
        // Enable exchange inputs, disable transfer inputs
        _setFieldsDisabled(exchangeFields, false);
        _setFieldsDisabled(transferFields, true);
        _clearFields(transferFields);
        // Hide total display
        var totalDisplay = document.getElementById('transfer-total-display');
        if (totalDisplay) totalDisplay.classList.add('hidden');
        // Update form target
        form.setAttribute('hx-post', '/transactions/exchange-submit');
        htmx.process(form);
        submitLabel.textContent = 'Exchange';
        // Mode indicator
        indicator.textContent = 'Different currencies \u2014 exchange mode';
        indicator.className = 'text-xs font-medium px-3 py-1.5 rounded-lg text-center bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
    } else {
        // Incomplete selection — hide both
        transferFields.classList.add('hidden');
        transferFields.setAttribute('aria-hidden', 'true');
        exchangeFields.classList.add('hidden');
        exchangeFields.setAttribute('aria-hidden', 'true');
        _setFieldsDisabled(transferFields, true);
        _setFieldsDisabled(exchangeFields, true);
        submitLabel.textContent = 'Transfer';
        indicator.className = 'hidden';
        indicator.textContent = '';
    }
}

// Called on amount input — delegates to the right calc function.
function onTransferAmountInput() {
    var mode = detectTransferMode();
    if (mode === 'transfer') {
        updateTransferTotal();
    } else if (mode === 'exchange') {
        calcTransferExchange('amount');
    }
}

// Transfer mode: show total (amount + fee) when fee > 0.
function updateTransferTotal() {
    var amount = parseFloat(document.getElementById('transfer-amount').value) || 0;
    var fee = parseFloat(document.getElementById('transfer-fee').value) || 0;
    var total = amount + fee;
    var display = document.getElementById('transfer-total-display');
    var totalValue = document.getElementById('transfer-total-value');
    if (fee > 0) {
        display.classList.remove('hidden');
        totalValue.textContent = total.toFixed(2);
    } else {
        display.classList.add('hidden');
    }
}

// Exchange mode: auto-calculate the third field when two are provided.
// Rate always means "EGP per 1 USD" regardless of direction.
function calcTransferExchange(changed) {
    var amount = parseFloat(document.getElementById('transfer-amount').value) || 0;
    var rate = parseFloat(document.getElementById('transfer-rate').value) || 0;
    var counter = parseFloat(document.getElementById('transfer-counter').value) || 0;

    // Detect currency direction from account selects
    var srcSel = document.getElementById('transfer-src');
    var dstSel = document.getElementById('transfer-dst');
    var srcCur = srcSel && srcSel.selectedOptions[0] ? srcSel.selectedOptions[0].getAttribute('data-currency') : '';
    var dstCur = dstSel && dstSel.selectedOptions[0] ? dstSel.selectedOptions[0].getAttribute('data-currency') : '';
    var srcIsEGP = (srcCur === 'EGP' && dstCur === 'USD');

    if (changed === 'amount' || changed === 'rate') {
        if (amount > 0 && rate > 0) {
            if (srcIsEGP) {
                document.getElementById('transfer-counter').value = (amount / rate).toFixed(2);
            } else {
                document.getElementById('transfer-counter').value = (amount * rate).toFixed(2);
            }
        }
    } else if (changed === 'counter') {
        if (amount > 0 && counter > 0) {
            if (srcIsEGP) {
                document.getElementById('transfer-rate').value = (amount / counter).toFixed(4);
            } else {
                document.getElementById('transfer-rate').value = (counter / amount).toFixed(4);
            }
        } else if (rate > 0 && counter > 0) {
            if (srcIsEGP) {
                document.getElementById('transfer-amount').value = (counter * rate).toFixed(2);
            } else {
                document.getElementById('transfer-amount').value = (counter / rate).toFixed(2);
            }
        }
    }
}

// Helper: enable/disable all inputs within a container.
function _setFieldsDisabled(container, disabled) {
    var inputs = container.querySelectorAll('input, select');
    for (var i = 0; i < inputs.length; i++) {
        inputs[i].disabled = disabled;
    }
}

// Helper: clear all input values within a container.
function _clearFields(container) {
    var inputs = container.querySelectorAll('input');
    for (var i = 0; i < inputs.length; i++) {
        inputs[i].value = '';
    }
}
