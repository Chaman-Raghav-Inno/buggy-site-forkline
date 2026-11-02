(function () {
  'use strict';

  const F = window.Forkline;
  const { $, $$, esc } = F;

  F.pages.restaurant = async function () {
    const id = Number(F.params.get('id'));
    let r;
    let item = null;
    let pending = null;

    function drawCart(c) {
      $('#rt-cart').innerHTML = c.count
        ? `<strong>Your cart</strong><span class="muted small">${F.plural(c.count, 'item')} from ${esc(c.restaurant_name)}</span><span class="btn btn-small">Go to cart</span>`
        : '<strong>Your cart</strong><span class="muted small">Nothing in it yet</span>';
      F.setCount(c.count);
    }

    function optionsHtml(it) {
      return it.options.map((g) => {
        const many = g.type === 'many';
        const title = `${esc(g.name)}${g.required ? ' (required)' : ''}${many ? ` (up to ${g.max})` : ''}`;
        const choices = g.choices.map((c) => `<label><input type="${many ? 'checkbox' : 'radio'}" name="opt-${g.id}" value="${c.id}" data-price="${c.price}"${!many && g.default === c.id ? ' checked' : ''}> ${esc(c.name)}<span class="opt-price">${c.price ? '+' + F.gbp(c.price) : ''}</span></label>`).join('');
        return `<fieldset class="opt-group"><legend>${title}</legend>${choices}</fieldset>`;
      }).join('');
    }

    function chosen() {
      const out = {};
      item.options.forEach((g) => {
        const picked = $$(`#it-options input[name="opt-${g.id}"]:checked`).map((i) => i.value);
        if (g.type === 'many') out[g.id] = picked;
        else if (picked.length) out[g.id] = picked[0];
      });
      return out;
    }

    function price() {
      const extras = $$('#it-options input:checked').reduce((s, i) => s + Number(i.dataset.price), 0);
      const qty = Math.max(1, Number($('#it-qty').value) || 1);
      $('#it-add').textContent = `Add ${qty} to cart · ${F.gbp((item.price + extras) * qty)}`;
    }

    function open(it) {
      item = it;
      $('#it-name').textContent = it.name;
      $('#it-desc').textContent = it.description + (it.offer ? ` Offer: ${it.offer}, every second portion is free.` : '');
      $('#it-options').innerHTML = optionsHtml(it);
      $('#it-qty').value = 1;
      F.say($('#it-msg'), '');
      price();
      $('#it-dialog').showModal();
    }

    async function add(body) {
      const res = await F.api('/api/cart/lines', body);
      if (res.status === 409) {
        pending = body;
        $('#nc-text').textContent = res.data.error;
        $('#nc-dialog').returnValue = '';
        $('#nc-dialog').showModal();
        return;
      }
      if (!res.ok) return F.say($('#it-msg'), res.data.error || 'Could not add that dish.', 'error');
      $('#it-dialog').close();
      drawCart({ count: res.data.count, restaurant_name: res.data.restaurant ? res.data.restaurant.name : r.name });
      F.toast(`Added ${body.qty} × ${item.name}.`);
    }

    $('#it-options').addEventListener('change', price);
    $('#it-qty').addEventListener('input', price);
    $('#it-cancel').addEventListener('click', () => $('#it-dialog').close());
    $('#it-form').addEventListener('submit', () => {
      const qty = Number($('#it-qty').value);
      if (!Number.isInteger(qty) || qty < 1 || qty > 20) return F.say($('#it-msg'), 'Choose 1 to 20.', 'error');
      add({ item: item.id, qty, options: chosen() });
    });
    $$('#nc-dialog button').forEach((b) => b.addEventListener('click', () => $('#nc-dialog').close(b.dataset.value)));
    $('#nc-dialog').addEventListener('close', () => {
      if ($('#nc-dialog').returnValue === 'new' && pending) add({ ...pending, replace: true });
      pending = null;
    });
    $('#rt-menu').addEventListener('click', (e) => {
      const b = e.target.closest('[data-item]');
      if (b) open(r.menu.find((it) => String(it.id) === b.dataset.item));
    });

    const res = await F.api(`/api/restaurants/${id}`);
    if (!res.ok) {
      $('#loading').textContent = res.data.error || 'We couldn\'t find that restaurant.';
      return;
    }
    r = res.data;
    document.title = `${r.name} · Forkline`;
    $('#rt-name').textContent = r.name;
    $('#rt-meta').innerHTML = `${esc(r.cuisine)} · ${F.stars(Math.round(r.rating))} ${r.rating.toFixed(1)} (${r.ratings} ratings) · ${esc(r.eta)}`;
    $('#rt-blurb').textContent = r.blurb;
    const closed = F.closedText(r);
    $('#rt-facts').innerHTML = F.rows([
      ['Delivering to', esc(r.address)], ['Distance', `${r.km.toFixed(1)} km`],
      ['Delivery fee', r.fee == null ? 'Too far to deliver' : F.gbp(r.fee)], ['Minimum order', F.gbp(r.min_order)],
      ['Opening hours', esc(r.hours)], ['Closed', closed ? esc(closed.replace(/Closed /g, '')) : 'Open every day'],
    ]);
    $('#rt-menu').innerHTML = r.menu.map((it) => `<li class="menu-item"><div><strong>${esc(it.name)}</strong>
        ${it.veg ? ' <span class="pill pill-veg">Veggie</span>' : ''}${it.offer ? ` <span class="pill pill-offer">${esc(it.offer)}</span>` : ''}${it.sold_out ? ' <span class="pill pill-soldout">Sold out</span>' : ''}
        <p class="muted small">${esc(it.description)}</p><p class="price">${F.gbp(it.price)}${it.options.length ? ' <span class="muted small">+ options</span>' : ''}</p></div>
        <button type="button" class="btn btn-small" data-item="${it.id}">Add</button></li>`).join('');
    $('#rt-reviews').innerHTML = r.reviews.map((v) => `<li><div class="section-head"><strong>${esc(v.name)}</strong>${F.stars(v.stars)}</div>
        <p class="muted small">${F.date(v.date)}</p>${v.comment ? `<p>${esc(v.comment)}</p>` : ''}</li>`).join('') || '<li class="muted">No reviews yet.</li>';
    drawCart(r.cart);
    $('#loading').hidden = true;
    $('#restaurant').hidden = false;
  };
})();
