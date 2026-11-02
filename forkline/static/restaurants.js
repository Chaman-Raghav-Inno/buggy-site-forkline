(function () {
  'use strict';

  const F = window.Forkline;
  const { $, esc } = F;

  // Whether a restaurant takes a delivery slot starting at `time` on `day`.
  function delivering(r, day, time) {
    const open = F.minutes(r.open);
    let close = F.minutes(r.close);
    let t = F.minutes(time);
    let service = day;
    if (close <= open) {
      close += 24 * 60;
      if (t < open) { t += 24 * 60; service = F.addDays(day, -1); }
    }
    if (t < open || t > close - 30) return false;
    if (r.closures.includes(service)) return false;
    const weekday = new Date(service + 'T00:00:00Z').getUTCDay();
    return !r.closed_days.includes(weekday);
  }

  F.pages.restaurants = async function () {
    let data;

    function draw() {
      const day = $('#rs-day').value;
      const time = $('#rs-time').value;
      let rows = data.restaurants.map((r) => ({ ...r, live: delivering(r, day, time) }));
      if ($('#rs-open').checked) rows = rows.filter((r) => r.live);
      const sort = $('#rs-sort').value;
      if (sort === 'fee') rows.sort((a, b) => (a.fee == null ? 99 : a.fee) - (b.fee == null ? 99 : b.fee));
      if (sort === 'rating') rows.sort((a, b) => b.rating - a.rating);
      if (sort === 'km') rows.sort((a, b) => a.km - b.km);
      $('#rs-count').textContent = `${F.plural(rows.length, 'restaurant')} · delivering ${F.day(day)} at ${time}: ${rows.filter((r) => r.live).length}`;
      $('#rs-list').innerHTML = rows.map((r) => {
        const fee = r.fee == null ? 'Too far to deliver' : `Delivery ${F.gbp(r.fee)}`;
        const closed = F.closedText(r);
        return `<a class="card rest-card${r.live ? '' : ' closed'}" href="/restaurant?id=${r.id}" data-id="${r.id}">
          <div class="section-head"><h2>${esc(r.name)}</h2>${r.live ? '<span class="pill pill-delivered">Delivering then</span>' : '<span class="pill">Not delivering then</span>'}</div>
          <p class="muted">${esc(r.cuisine)} · ${F.stars(Math.round(r.rating))} ${r.rating.toFixed(1)} (${r.ratings})</p>
          <p>${esc(r.blurb)}</p>
          <p class="rest-meta"><span>${r.km.toFixed(1)} km</span><span data-fee>${fee}</span><span>Min. order ${F.gbp(r.min_order)}</span><span>${esc(r.eta)}</span></p>
          <p class="rest-meta"><span>Open ${esc(r.hours)}</span>${closed ? `<span>${esc(closed)}</span>` : ''}</p></a>`;
      }).join('') || '<p class="muted">No restaurants match.</p>';
    }

    async function load() {
      const q = new URLSearchParams({ q: $('#rs-q').value.trim(), cuisine: $('#rs-cuisine').value });
      const r = await F.api('/api/restaurants?' + q.toString());
      if (!r.ok) return F.toast(r.data.error || 'Could not load the restaurants.', 'error');
      data = r.data;
      draw();
    }

    const first = await F.api('/api/restaurants');
    if (!first.ok) return F.toast(first.data.error || 'Could not load the restaurants.', 'error');
    data = first.data;
    $('#rs-address').innerHTML = data.addresses.map((a) => `<option value="${a.id}">${esc(a.label)}: ${esc(a.text)}</option>`).join('');
    $('#rs-address').value = String(data.address);
    $('#rs-cuisine').innerHTML += data.cuisines.map((c) => `<option>${esc(c)}</option>`).join('');
    $('#rs-day').innerHTML = [1, 2, 3, 4, 5, 6, 7].map((n) => { const d = F.addDays(data.today, n); return `<option value="${d}">${F.day(d)}</option>`; }).join('');
    $('#rs-time').innerHTML = F.times().map((t) => `<option>${t}</option>`).join('');
    $('#rs-time').value = '19:00';
    draw();

    let timer;
    $('#rs-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
    $('#rs-cuisine').addEventListener('change', load);
    ['#rs-day', '#rs-time', '#rs-sort', '#rs-open'].forEach((s) => $(s).addEventListener('change', draw));
    $('#rs-address').addEventListener('change', async () => {
      const r = await F.api('/api/address', { address: Number($('#rs-address').value) });
      if (!r.ok) return F.toast(r.data.error || 'Could not change the address.', 'error');
      await load();
    });
  };
})();
