// Auto-calculate the third exchange field when two are provided.
// Rate always means "EGP per 1 USD" regardless of direction.
// USD→EGP: counter = amount * rate   |  EGP→USD: counter = amount / rate
function calcExchange(changed) {
  var amount = parseFloat(document.getElementById('exchange-amount').value) || 0;
  var rate = parseFloat(document.getElementById('exchange-rate').value) || 0;
  var counter = parseFloat(document.getElementById('exchange-counter').value) || 0;

  // Detect currency direction from account selects
  var srcSel = document.getElementById('exchange-src');
  var dstSel = document.getElementById('exchange-dst');
  var srcCur = srcSel && srcSel.selectedOptions[0] ? srcSel.selectedOptions[0].getAttribute('data-currency') : '';
  var dstCur = dstSel && dstSel.selectedOptions[0] ? dstSel.selectedOptions[0].getAttribute('data-currency') : '';
  var srcIsEGP = (srcCur === 'EGP' && dstCur === 'USD');

  if (changed === 'amount' || changed === 'rate') {
    if (amount > 0 && rate > 0) {
      if (srcIsEGP) {
        document.getElementById('exchange-counter').value = (amount / rate).toFixed(2);
      } else {
        document.getElementById('exchange-counter').value = (amount * rate).toFixed(2);
      }
    }
  } else if (changed === 'counter') {
    if (amount > 0 && counter > 0) {
      if (srcIsEGP) {
        document.getElementById('exchange-rate').value = (amount / counter).toFixed(4);
      } else {
        document.getElementById('exchange-rate').value = (counter / amount).toFixed(4);
      }
    } else if (rate > 0 && counter > 0) {
      if (srcIsEGP) {
        document.getElementById('exchange-amount').value = (counter * rate).toFixed(2);
      } else {
        document.getElementById('exchange-amount').value = (counter / rate).toFixed(2);
      }
    }
  }
}
