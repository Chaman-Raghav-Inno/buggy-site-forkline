(function () {
  'use strict';

  const F = window.Forkline;
  const { $, $$, esc } = F;

  F.pages.checkout = async function () {
    let q;

    function tip() {
      const v = ($$('input[name="tip"]').find((i) => i.checked) || {}).value;
      if (v === 'custom') return { amount: Number($('#co-custom').value.replace(/[£,\s]/g, '') || 0) };
      return Number(v) ? { percent: Number(v) } : null;
    }

    function body() {
      return { address: Number($('#co-address').value), tip: tip(), use_points: $('#co-points').checked };
    }

    function draw() {
      const r = q.restaurant;
      $('#co-from').textContent = `Your order from ${r.name}`;
      const closed = F.closedText(r);
      $('#co-hours').textContent = `${r.name} delivers ${r.hours}${closed ? ` · ${closed}` : ''}. Slots from tomorrow up to 7 days ahead.`;
      $('#co-lines').innerHTML = q.lines.map((x) => `<li class="line"><div>${x.qty} × ${esc(x.name)}${x.options_text ? `<p class="muted small">${esc(x.options_text)}</p>` : ''}</div><strong>${F.gbp(x.total)}</strong></li>`).join('');
      const blocks = Math.floor(q.points_balance / 100);
      $('#co-points-label').textContent = blocks ? `Use my points: ${q.points_balance} points, up to ${F.gbp(blocks)} off` : `You have ${q.points_balance} points (100 points take £1 off)`;
      $('#co-points').disabled = !blocks;
      $('#co-totals').innerHTML = F.rows([
        ['Food', F.gbp(q.food)],
        ...q.discounts.map((d) => [`Promo ${esc(d.code)}`, F.gbp(-d.amount), 'discount']),
        ...(q.points_off ? [[`Points (${q.points_used})`, F.gbp(-q.points_off), 'discount']] : []),
        ['Delivery fee', r.fee == null ? 'Too far' : F.gbp(q.delivery)],
        ['Service fee', F.gbp(q.service)],
        ...(q.small_order ? [['Small-order fee', F.gbp(q.small_order)]] : []),
        ...(q.tip ? [['Tip', F.gbp(q.tip)]] : []),
        ['Total', F.gbp(q.total), 'grand'],
      ]);
    }

    async function requote() {
      const r = await F.api('/api/quote', body());
      if (!r.ok) return F.say($('#co-msg'), r.data.error || 'Could not work out your total.', 'error');
      F.say($('#co-msg'), '');
      q = r.data;
      draw();
    }

    $('#co-form').addEventListener('change', (e) => {
      if (e.target.name === 'tip') $('#co-custom-field').hidden = e.target.value !== 'custom';
      if (e.target.matches('#co-date, #co-time')) return;
      requote();
    });
    $('#co-form').addEventListener('submit', async () => {
      const msg = $('#co-msg');
      const date = $('#co-date').value;
      const time = $('#co-time').value;
      if (!date) return F.say(msg, 'Choose a delivery day.', 'error');
      if (!time) return F.say(msg, 'Choose a delivery slot.', 'error');
      if (date < $('#co-date').min) return F.say(msg, 'Choose a day from tomorrow onwards.', 'error');
      $('#co-place').disabled = true;
      const r = await F.api('/api/orders', { ...body(), date, time });
      $('#co-place').disabled = false;
      if (!r.ok) return F.say(msg, r.data.error || 'Could not place your order.', 'error');
      location.href = `/order?id=${r.data.id}&placed=1`;
    });

    const r = await F.api('/api/quote', {});
    if (!r.ok) return F.toast(r.data.error || 'Could not load your order.', 'error');
    q = r.data;
    $('#loading').hidden = true;
    if (!q.lines.length) {
      $('#co-empty').hidden = false;
      return;
    }
    $('#co-address').innerHTML = q.addresses.map((a) => `<option value="${a.id}">${esc(a.label)}: ${esc(a.text)}</option>`).join('');
    $('#co-address').value = String(q.address);
    $('#co-date').min = F.addDays(q.today, 1);
    $('#co-date').value = F.addDays(q.today, 1);
    $('#co-time').innerHTML = '<option value="">Choose a slot</option>' + F.times().map((t) => `<option>${t}</option>`).join('');
    draw();
    $('#co-form').hidden = false;
  };
})();
