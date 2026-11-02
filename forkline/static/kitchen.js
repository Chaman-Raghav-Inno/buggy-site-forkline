(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;
  const NEXT = { accepted: 'Start preparing', preparing: 'Out for delivery', out: 'Mark delivered' };

  F.pages.kitchen = async function () {
    let data;

    function draw() {
      const r = data.restaurant;
      document.title = `Kitchen · ${r.name} · Forkline`;
      $('#kt-title').textContent = `Kitchen · ${r.name}`;
      $('#kt-tabs').innerHTML = data.mine.map((x) => `<a href="/kitchen?restaurant=${x.id}"${x.id === r.id ? ' aria-current="page"' : ''}>${esc(x.name)}</a>`).join('');
      $('#kt-rows').innerHTML = data.orders.map((o) => {
        let actions = '';
        if (o.status === 'placed') actions = `<button type="button" class="btn btn-small" data-id="${o.id}" data-action="accept">Accept</button><button type="button" class="btn btn-small btn-ghost" data-id="${o.id}" data-action="reject">Reject</button>`;
        else if (NEXT[o.status]) actions = `<button type="button" class="btn btn-small" data-id="${o.id}" data-action="next">${NEXT[o.status]}</button>`;
        return `<tr><td>#${o.id}</td><td>${F.day(o.slot_date)}, ${esc(o.slot_time)}</td><td class="wrap-cell">${esc(o.customer)}<br><span class="muted small">${esc(o.address_text)}</span></td>
          <td class="wrap-cell">${o.lines.map((x) => `${x.qty} × ${esc(x.name)}${x.options_text ? ` <span class="muted small">(${esc(x.options_text)})</span>` : ''}`).join('<br>')}</td>
          <td class="num">${F.gbp(o.food)}</td><td>${F.status(o.status)}</td><td><div class="actions">${actions}</div></td></tr>`;
      }).join('') || '<tr><td colspan="7" class="muted">No orders yet.</td></tr>';
    }

    $('#kt-rows').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-action]');
      if (!b) return;
      b.disabled = true;
      const r = await F.api(`/api/kitchen/orders/${b.dataset.id}`, { action: b.dataset.action });
      if (!r.ok) {
        b.disabled = false;
        return F.say($('#kt-msg'), r.data.error || 'Could not update the order.', 'error');
      }
      data = r.data;
      draw();
      const o = data.orders.find((x) => String(x.id) === b.dataset.id);
      F.say($('#kt-msg'), `Order #${b.dataset.id} is now ${F.label(o.status).toLowerCase()}.`, 'success');
    });

    const rid = F.params.get('restaurant');
    const r = await F.api('/api/kitchen' + (rid ? `?restaurant=${encodeURIComponent(rid)}` : ''));
    if (!r.ok) {
      $('#kt-rows').innerHTML = `<tr><td colspan="7" class="muted">${esc(r.data.error || 'Could not load your orders.')}</td></tr>`;
      return;
    }
    data = r.data;
    draw();
  };
})();
