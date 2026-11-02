(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  F.pages.account = async function () {
    function draw(a) {
      $('#ac-hello').textContent = `Hello, ${a.name.split(' ')[0]}`;
      $('#ac-points').textContent = `${a.points} points`;
      $('#ac-history').innerHTML = a.history.map((h) => `<li><span>${esc(h.what)}<br><span class="muted small">${F.date(h.date)}</span></span><strong>${h.points > 0 ? '+' : ''}${h.points}</strong></li>`).join('')
        || '<li class="muted">No points yet.</li>';
      $('#ac-addresses').innerHTML = a.addresses.map((x) => `<li><span><strong>${esc(x.label)}</strong><br><span class="muted small">${esc(x.text)}</span></span></li>`).join('');
    }

    $('#ad-form').addEventListener('submit', async () => {
      const msg = $('#ad-msg');
      const street = $('#ad-street').value.trim();
      const postcode = $('#ad-postcode').value.trim().toUpperCase();
      if (!street) return F.say(msg, 'Enter the street address.', 'error');
      if (!/^FL[1-9] ?\d[A-Z]{2}$/.test(postcode)) return F.say(msg, 'Enter a Forkline postcode, like FL2 4QT.', 'error');
      const r = await F.api('/api/account/addresses', { label: $('#ad-label').value.trim(), street, postcode });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not save the address.', 'error');
      draw(r.data);
      $('#ad-form').reset();
      F.say(msg, 'Address saved. You can choose it at checkout.', 'success');
    });

    const r = await F.api('/api/account');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your account.', 'error');
    draw(r.data);
  };
})();
