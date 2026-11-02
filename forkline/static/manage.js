(function () {
  'use strict';

  const F = window.Forkline;
  const { $, $$, esc } = F;

  F.pages.manage = async function () {
    let data;
    let rid = F.params.get('restaurant') || '';

    function draw() {
      const r = data.restaurant;
      rid = String(r.id);
      document.title = `Menu and hours · ${r.name} · Forkline`;
      $('#mg-title').textContent = `Menu and hours · ${r.name}`;
      $('#mg-tabs').innerHTML = data.mine.map((x) => `<a href="/manage?restaurant=${x.id}"${x.id === r.id ? ' aria-current="page"' : ''}>${esc(x.name)}</a>`).join('');
      $('#mg-rows').innerHTML = data.menu.map((it) => `<tr data-item="${it.id}"><td class="wrap-cell"><strong>${esc(it.name)}</strong>${it.options.length ? '<br><span class="muted small">Has options</span>' : ''}</td>
          <td><label class="sr-only" for="p-${it.id}">Price of ${esc(it.name)}</label><input id="p-${it.id}" inputmode="decimal" autocomplete="off" value="${it.price.toFixed(2)}"></td>
          <td><label class="check"><input type="checkbox" id="s-${it.id}"${it.sold_out ? ' checked' : ''}> Sold out</label></td>
          <td><button type="button" class="btn btn-small" data-save="${it.id}">Save</button></td></tr>`).join('');
      $('#hr-now').textContent = `Now: ${r.hours}${r.closed_days.length ? `, closed ${r.closed_days.map((d) => F.DAYS[d]).join(', ')}` : ''}.`;
      $('#hr-open').value = r.open;
      $('#hr-close').value = r.close;
      $$('#hr-days input').forEach((i) => { i.checked = r.closed_days.includes(Number(i.value)); });
      drawReport();
    }

    function drawReport() {
      const p = data.report;
      $('#rp-date').value = p.date;
      $('#rp-facts').innerHTML = F.rows([['Orders', String(p.orders)], ['Food sales', F.gbp(p.food)]]);
      $('#rp-csv').href = `/api/manage/report.csv?${new URLSearchParams({ restaurant: rid, date: p.date }).toString()}`;
      $('#rp-csv').setAttribute('download', `sales-${p.date}.csv`);
    }

    async function load(day) {
      const q = new URLSearchParams({ restaurant: rid, date: day || '' });
      const r = await F.api('/api/manage?' + q.toString());
      if (!r.ok) {
        $('#loading').textContent = r.data.error || 'Could not load your restaurant.';
        $('#manage').hidden = true;
        $('#loading').hidden = false;
        return false;
      }
      data = r.data;
      draw();
      return true;
    }

    $('#mg-rows').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-save]');
      if (!b) return;
      const id = b.dataset.save;
      const raw = $(`#p-${id}`).value.replace(/[£,\s]/g, '');
      const price = Number(raw);
      if (!raw || Number.isNaN(price)) return F.say($('#mg-msg'), 'Enter a price, like 9.50.', 'error');
      const r = await F.api(`/api/manage/items/${id}`, { price, sold_out: $(`#s-${id}`).checked });
      if (!r.ok) return F.say($('#mg-msg'), r.data.error || 'Could not save the dish.', 'error');
      const day = $('#rp-date').value;
      data = r.data;
      draw();
      if (day !== data.report.date) await load(day);
      const it = data.menu.find((x) => String(x.id) === id);
      F.say($('#mg-msg'), `${it.name} saved: ${F.gbp(it.price)}${it.sold_out ? ', sold out' : ''}.`, 'success');
    });
    $('#hr-form').addEventListener('submit', async () => {
      const body = { restaurant: Number(rid), open: $('#hr-open').value, close: $('#hr-close').value, closed_days: $$('#hr-days input:checked').map((i) => Number(i.value)) };
      const r = await F.api('/api/manage/hours', body);
      if (!r.ok) return F.say($('#hr-msg'), r.data.error || 'Could not save the hours.', 'error');
      data = r.data;
      draw();
      F.say($('#hr-msg'), 'Opening hours saved.', 'success');
    });
    $('#rp-date').addEventListener('change', () => { if ($('#rp-date').value) load($('#rp-date').value); });

    const times = F.times().map((t) => `<option>${t}</option>`).join('');
    $('#hr-open').innerHTML = times;
    $('#hr-close').innerHTML = times;
    $('#hr-days').innerHTML = F.DAYS.map((d, i) => `<label class="check"><input type="checkbox" value="${i}"> ${d.slice(0, -1)}</label>`).join('');
    if (await load()) {
      $('#loading').hidden = true;
      $('#manage').hidden = false;
    }
  };
})();
