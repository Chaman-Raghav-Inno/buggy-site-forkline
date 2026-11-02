(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  F.pages.orders = async function () {
    $('#or-rows').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-reorder]');
      if (!b) return;
      const r = await F.api(`/api/orders/${b.dataset.reorder}/reorder`, {});
      if (!r.ok) return F.say($('#or-msg'), r.data.error || 'Could not reorder.', 'error');
      location.href = '/cart';
    });

    const r = await F.api('/api/orders');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your orders.', 'error');
    $('#or-rows').innerHTML = r.data.orders.map((o) => `<tr><td><a href="/order?id=${o.id}">#${o.id}</a></td><td>${esc(o.restaurant_name)}</td>
        <td>${F.day(o.slot_date)}, ${esc(o.slot_time)}</td><td>${o.items}</td><td class="num">${F.gbp(o.total)}</td><td>${F.status(o.status)}</td>
        <td><div class="actions"><a class="btn btn-small btn-ghost" href="/order?id=${o.id}">View</a><button type="button" class="btn btn-small" data-reorder="${o.id}">Reorder</button></div></td></tr>`).join('')
      || '<tr><td colspan="7" class="muted">No orders yet.</td></tr>';
  };
})();
