(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  F.pages.help = async function () {
    const r = await F.api('/api/promos');
    if (!r.ok) {
      $('#offers').innerHTML = '<li class="muted">Could not load the current codes.</li>';
      return;
    }
    $('#offers').innerHTML = r.data.promos.map((p) => `<li><code>${esc(p.code)}</code>: ${esc(p.text)}${p.first_only ? ' (first order only)' : ''}. Last day ${F.date(p.until)}.</li>`).join('');
  };
})();
