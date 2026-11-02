(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  F.pages.cart = async function () {
    let c;

    function draw() {
      F.setCount(c.count);
      const empty = !c.lines.length;
      $('#ct-empty').hidden = !empty;
      $('#cart').hidden = empty;
      if (empty) return;
      const r = c.restaurant;
      $('#ct-from').textContent = `From ${r.name}`;
      $('#ct-where').textContent = `${r.km.toFixed(1)} km away · minimum order ${F.gbp(r.min_order)}`;
      $('#ct-lines').innerHTML = c.lines.map((x) => `<li class="line" data-line="${x.id}"><div><strong>${esc(x.name)}</strong>${x.offer ? ` <span class="pill pill-offer">${esc(x.offer)}</span>` : ''}
          ${x.options_text ? `<p class="muted small">${esc(x.options_text)}</p>` : ''}<p class="muted small">${F.gbp(x.unit)} each</p></div>
          <div class="line-ctrl"><label class="sr-only" for="q-${x.id}">Quantity of ${esc(x.name)}</label><input id="q-${x.id}" type="number" min="1" max="20" value="${x.qty}" inputmode="numeric">
          <strong class="line-total">${F.gbp(x.total)}</strong><button type="button" class="link" data-remove="${x.id}">Remove</button></div></li>`).join('');
      $('#pr-list').innerHTML = c.promos.map((p) => `<li><span><code>${esc(p)}</code></span><button type="button" class="link" data-code="${esc(p)}">Remove</button></li>`).join('');
      const total = c.food - c.discount + c.delivery + c.small_order;
      $('#ct-totals').innerHTML = F.rows([
        ['Food', F.gbp(c.food)],
        ...c.discounts.map((d) => [`Promo ${esc(d.code)}`, F.gbp(-d.amount), 'discount']),
        ['Delivery fee', c.restaurant.fee == null ? 'Too far' : F.gbp(c.delivery)],
        ...(c.small_order ? [['Small-order fee', F.gbp(c.small_order)]] : []),
        ['Total', F.gbp(total), 'grand'],
      ]);
      const notes = [...c.notes];
      if (c.food < r.min_order) notes.push(`${r.name} has a minimum order of ${F.gbp(r.min_order)}.`);
      $('#ct-note').textContent = notes.join(' ') || 'Tips and points are added at checkout.';
    }

    async function setQty(id, qty) {
      const r = await F.api(`/api/cart/lines/${id}`, { qty });
      if (!r.ok) {
        F.toast(r.data.error || 'Could not update your cart.', 'error');
      } else {
        c = r.data;
      }
      draw();
    }

    $('#ct-lines').addEventListener('change', (e) => {
      const input = e.target.closest('input');
      if (!input) return;
      const qty = parseInt(input.value, 10);
      if (Number.isNaN(qty)) return draw();
      setQty(Number(input.closest('[data-line]').dataset.line), qty);
    });
    $('#ct-lines').addEventListener('click', (e) => {
      const b = e.target.closest('[data-remove]');
      if (b) setQty(Number(b.dataset.remove), 0);
    });
    $('#pr-form').addEventListener('submit', async () => {
      const msg = $('#pr-msg');
      const code = $('#pr-code').value.trim();
      if (!code) return F.say(msg, 'Enter a promo code.', 'error');
      const r = await F.api('/api/cart/promo', { code });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not use that code.', 'error');
      c = r.data;
      draw();
      $('#pr-code').value = '';
      F.say(msg, `${code.toUpperCase()} applied.`, 'success');
    });
    $('#pr-list').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-code]');
      if (!b) return;
      const r = await F.api('/api/cart/promo/remove', { code: b.dataset.code });
      if (!r.ok) return F.toast(r.data.error || 'Could not remove the code.', 'error');
      c = r.data;
      draw();
      F.say($('#pr-msg'), '');
    });

    const r = await F.api('/api/cart');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your cart.', 'error');
    c = r.data;
    $('#loading').hidden = true;
    draw();
  };
})();
