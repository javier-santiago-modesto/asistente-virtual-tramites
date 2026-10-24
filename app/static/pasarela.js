(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const soles = n => 'S/ ' + Number(n).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const oid = location.pathname.split('/').pop();
  let orden = null;

  const exito = o => {
    $('#frm').hidden = true; $('.caja__res').hidden = false;
    const url = o.return_url + '?pago=ok';
    $('#exito').classList.add('ver'); $('#exLink').href = url;
    $('#caja').style.gridTemplateColumns = '1fr 1fr';
    setTimeout(() => { location.href = url; }, 2200);
  };

  async function cargar() {
    try {
      const r = await fetch('/api/pagos/ordenes/' + encodeURIComponent(oid)); const o = await r.json();
      if (!r.ok) throw new Error(o.detail || 'No encontramos la orden.');
      orden = o;
      $('#rTramite').textContent = o.concepto;
      $('#rMonto').textContent = soles(o.monto);
      $('#rDatos').innerHTML = `<div><dt>N.º de orden</dt><dd>${esc(o.orden_id)}</dd></div><div><dt>Alumno</dt><dd>${esc(o.id_alumno)}</dd></div>
        <div><dt>Vigente hasta</dt><dd>${esc(new Date(o.vence).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' }))}</dd></div>`;
      if (o.estado === 'pagada') return exito(o);
      if (o.estado === 'vencida') throw new Error('La orden venció. Vuelve a confirmar tu trámite para generar una nueva.');
      $('#frm').hidden = false; $('#btnPagar').textContent = 'Pagar ' + soles(o.monto);
    } catch (e) {
      $('#rTramite').textContent = 'No pudimos abrir el pago';
      $('#rDatos').innerHTML = `<p>${esc(e.message)}</p>`;
    }
  }

  $('#numero').addEventListener('input', e => { const v = e.target.value.replace(/\D/g, '').slice(0, 19); e.target.value = v.replace(/(.{4})/g, '$1 ').trim(); });
  $('#vence').addEventListener('input', e => { let v = e.target.value.replace(/\D/g, '').slice(0, 4); if (v.length > 2) v = v.slice(0, 2) + '/' + v.slice(2); e.target.value = v; });
  $('#cvv').addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4); });

  $('#frm').addEventListener('submit', async e => {
    e.preventDefault();
    const err = $('#err'); err.hidden = true;
    const btn = $('#btnPagar'); btn.disabled = true; btn.textContent = 'Procesando pago…';
    try {
      const r = await fetch(`/api/pagos/ordenes/${encodeURIComponent(oid)}/pagar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titular: $('#titular').value.trim(), numero_tarjeta: $('#numero').value, vencimiento: $('#vence').value, cvv: $('#cvv').value }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Revisa los datos de tu tarjeta.');
      exito(j);
    } catch (x) {
      err.textContent = x.message; err.hidden = false; btn.disabled = false; btn.textContent = 'Pagar ' + soles(orden.monto);
    }
  });
  cargar();
})();
