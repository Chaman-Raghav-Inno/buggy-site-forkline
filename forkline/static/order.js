(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  F.pages.order = async function () {
    const id = Number(F.params.get('id'));
    let o;

    function draw() {
      document.title = `Order #${o.id} · Forkline`;
      $('#od-title').textContent = `Order #${o.id} · ${o.restaurant_name}`;
      $('#od-status').innerHTML = F.status(o.status);
      $('#od-facts').innerHTML = F.rows([
        ['Delivery slot', `${F.day(o.slot_date)}, ${esc(o.slot_time)}`], ['Deliver to', esc(o.address_text)], ['Name', esc(o.customer)],
        ...(o.points_earned ? [['Points earned', String(o.points_earned)]] : []),
      ]);
      $('#od-cancel').hidden = !o.can_cancel;
      const events = o.events.slice().sort((a, b) => a.time.localeCompare(b.time));
      $('#od-timeline').innerHTML = events.map((e) => `<li><strong>${F.label(e.status)}</strong><br><span class="muted small">${F.day(e.at)}, ${esc(e.time)}</span></li>`).join('');
      $('#od-lines').innerHTML = o.lines.map((x) => `<tr><td class="wrap-cell">${esc(x.name)}${x.options_text ? `<br><span class="muted small">${esc(x.options_text)}</span>` : ''}</td><td class="num">${x.qty}</td><td class="num">${F.gbp(x.total)}</td></tr>`).join('');
      const total = o.food - o.points_off + o.delivery + o.service + o.small_order + o.tip;
      $('#od-totals').innerHTML = F.rows([
        ['Food', F.gbp(o.food)],
        ...(o.discount ? [[`Promo ${esc(o.promos.join(', '))}`, F.gbp(-o.discount), 'discount']] : []),
        ...(o.points_off ? [[`Points (${o.points_used})`, F.gbp(-o.points_off), 'discount']] : []),
        ['Delivery fee', F.gbp(o.delivery)], ['Service fee', F.gbp(o.service)],
        ...(o.small_order ? [['Small-order fee', F.gbp(o.small_order)]] : []),
        ...(o.tip ? [['Tip', F.gbp(o.tip)]] : []),
        ['Total paid', F.gbp(total), 'grand'],
        ['Includes VAT', F.gbp(o.vat)],
      ]);
      $('#rv-list').innerHTML = o.reviews.map((v) => `<li><div class="section-head"><strong>You rated it</strong>${F.stars(v.stars)}</div><p class="muted small">${F.date(v.date)}</p>${v.comment ? `<p>${esc(v.comment)}</p>` : ''}</li>`).join('');
      $('#mi-line').innerHTML = o.lines.map((x, i) => `<option value="${i}">${esc(x.name)} (${x.qty} ordered)</option>`).join('');
      $('#mi-list').innerHTML = o.refunds.map((x) => `<li><span>${x.qty} × ${esc(x.name)} missing · ${F.date(x.date)}</span><strong>${F.gbp(x.amount)} refunded</strong></li>`).join('');
    }

    async function act(path, payload, msgSel, done) {
      const r = await F.api(`/api/orders/${o.id}/${path}`, payload);
      if (!r.ok) return F.say($(msgSel), r.data.error || 'Something went wrong. Try again.', 'error');
      o = r.data;
      draw();
      F.say($(msgSel), done, 'success');
      return true;
    }

    $('#od-cancel').addEventListener('click', () => act('cancel', {}, '#od-msg', 'Order cancelled. You haven\'t been charged.'));
    $('#od-reorder').addEventListener('click', async () => {
      const r = await F.api(`/api/orders/${o.id}/reorder`, {});
      if (!r.ok) return F.say($('#od-msg'), r.data.error || 'Could not reorder.', 'error');
      location.href = '/cart';
    });
    $('#rv-form').addEventListener('submit', async () => {
      const stars = Number($('#rv-stars').value);
      if (!stars) return F.say($('#rv-msg'), 'Choose a rating.', 'error');
      if (await act('review', { stars, comment: $('#rv-comment').value.trim() }, '#rv-msg', 'Thanks for your review.')) $('#rv-form').reset();
    });
    $('#mi-form').addEventListener('submit', async () => {
      const qty = Number($('#mi-qty').value);
      if (!Number.isInteger(qty) || qty < 1) return F.say($('#mi-msg'), 'Enter how many were missing.', 'error');
      const r = await act('missing', { line: Number($('#mi-line').value), qty }, '#mi-msg', '');
      if (r) {
        const last = o.refunds[o.refunds.length - 1];
        F.say($('#mi-msg'), `Sorry about that. We've refunded ${F.gbp(last.amount)} to your card.`, 'success');
      }
    });

    const r = await F.api(`/api/orders/${id}`);
    o = r.data;
    draw();
    if (F.params.get('placed')) F.say($('#od-msg'), 'Order placed. We\'ll let you know when the restaurant accepts it.', 'success');
    $('#loading').hidden = true;
    $('#order').hidden = false;
  };
})();
