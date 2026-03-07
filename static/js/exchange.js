// Auto-calculate the third exchange field when two are provided.
// amount * rate = counter_amount
function calcExchange(changed) {
  var amount = parseFloat(document.getElementById('exchange-amount').value) || 0;
  var rate = parseFloat(document.getElementById('exchange-rate').value) || 0;
  var counter = parseFloat(document.getElementById('exchange-counter').value) || 0;

  if (changed === 'amount' || changed === 'rate') {
    if (amount > 0 && rate > 0) {
      document.getElementById('exchange-counter').value = (amount * rate).toFixed(2);
    }
  } else if (changed === 'counter') {
    if (amount > 0 && counter > 0) {
      document.getElementById('exchange-rate').value = (counter / amount).toFixed(4);
    } else if (rate > 0 && counter > 0) {
      document.getElementById('exchange-amount').value = (counter / rate).toFixed(2);
    }
  }
}
