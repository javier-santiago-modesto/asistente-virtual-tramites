(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const tit = s => String(s).toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase());
  const soles = n => 'S/ ' + Number(n).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const [, , slug, idAlumno] = location.pathname.split('/');
  const NATURAL = { 'certificado-estudios': 794, 'constancia-matricula': 794, 'bachiller': 1123 };

  let datos = null;

  /* ---------- utilidades de documento ---------- */
  const fecha = iso => new Date(iso + 'T00:00:00').toLocaleDateString('es-PE', { day: 'numeric', month: 'long', year: 'numeric' });
  const claseNota = n => n >= 17 ? 'n-a' : n >= 14 ? 'n-b' : n >= 11 ? 'n-c' : 'n-d';
  const nota = n => n.toFixed(1);
  const entrega = d => d.entrega_inmediata ? 'Inmediata' : d.tiempo_entrega.toLowerCase().replace('dias habiles', 'días hábiles');

  const escudo = (color = 'currentColor', size = 58) => `<svg width="${size}" height="${size}" viewBox="0 0 64 64" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M32 4 56 12v18c0 15-10 26-24 30C18 56 8 45 8 30V12z"/><path d="M32 18v22M20 24c4-2 9-2 12 1 3-3 8-3 12-1v16c-4-2-9-2-12 1-3-3-8-3-12-1z"/></svg>`;

  function barras(texto) {
    let h = '';
    for (const ch of (texto + 'SELLO').repeat(2)) {
      const c = ch.charCodeAt(0);
      h += `<i style="width:${1 + (c % 3)}px"></i><i style="width:${1 + (c % 2)}px;background:transparent"></i>`;
    }
    return `<div class="barras" aria-hidden="true">${h}</div>`;
  }
  const firmas = (a = 'Director(a) Académico(a)', b = 'Secretario(a) General', sello = true) => `
    <div class="firmas"><div class="firma"><i></i><b>${a}</b>Firma y rúbrica</div>
    ${sello ? '<div class="sello-doc">Sello<br>de<br>demo</div>' : ''}
    <div class="firma"><i></i><b>${b}</b>Firma y rúbrica</div></div>`;
  const marcaAgua = () => datos.pagado && datos.entrega_inmediata ? '' : '<div class="marca-agua" aria-hidden="true"><span>Preview</span></div>';

  /* ---------- CERTIFICADO DE ESTUDIOS ---------- */
  function certificado(d) {
    const a = d.alumno;
    const periodos = d.periodos.map(p => `
      <section class="c-periodo">
        <div class="c-pcab"><div class="c-anio">${esc(p.periodo)}</div><div class="lbl">Periodo académico</div>
          <div class="prom">Promedio <b>${p.promedio.toFixed(2)}</b></div></div>
        <table class="c-tabla"><thead><tr><th class="cod">Código</th><th>Curso</th><th class="nota">Nota</th><th class="cond">Condición</th></tr></thead>
        <tbody>${p.cursos.map(c => `<tr><td class="cod">${esc(c.id)}</td><td class="curso">${esc(c.curso)}</td>
          <td class="nota"><span class="pill ${claseNota(c.nota)}">${nota(c.nota)}</span></td>
          <td><span class="cond-t ${c.nota >= 11 ? 'cond-ok' : 'cond-no'}">${c.nota >= 11 ? 'Aprobado' : 'Desaprobado'}</span></td></tr>`).join('')}</tbody>
        <tfoot><tr><td colspan="2">Promedio del periodo ${esc(p.periodo)}</td><td class="nota">${p.promedio.toFixed(2)}</td><td></td></tr></tfoot></table>
      </section>`).join('');
    return `<article class="doc d-cert">
      <header class="c-head"><div style="color:#e8dfc9">${escudo('currentColor', 62)}</div>
        <div><p class="uni">${esc(d.universidad)} · Secretaría Académica</p><h2>Certificado de Estudios</h2></div>
        <div class="cod">N.º de documento<b>${esc(d.codigo_documento)}</b>${fecha(d.fecha_emision)}</div></header>
      <section class="c-alumno">
        <div class="nombre"><small>Apellidos y nombres</small><b>${esc(a.apellidos)}, ${esc(a.nombres)}</b></div>
        <div><small>Código de alumno</small><b>${esc(a.id)}</b></div>
        <div><small>Carrera</small><b>${esc(a.carrera)}</b></div>
      </section>
      ${periodos}
      <section class="c-resumen">
        <div><b>${d.resumen.periodos}</b><span>periodos cursados</span></div>
        <div><b>${d.resumen.cursos}</b><span>cursos registrados</span></div>
        <div><b>${d.resumen.promedio_general.toFixed(2)}</b><span>promedio general</span></div>
      </section>
      <footer class="c-pie">
        <p class="exp">Se certifica que el(la) alumno(a) arriba indicado(a) cursó los periodos académicos y obtuvo las calificaciones consignadas en este documento, en la escala vigesimal (nota aprobatoria: 11). Se expide el presente certificado a solicitud del interesado.</p>
        ${firmas()}
        <div class="verif">${barras(d.codigo_documento)}<span class="pie-demo">Documento de demostración · sin validez oficial · ${esc(d.codigo_documento)}</span></div>
      </footer>${marcaAgua()}</article>`;
  }

  /* ---------- CONSTANCIA DE MATRÍCULA ---------- */
  function constancia(d) {
    const a = d.alumno;
    return `<article class="doc d-const">
      <aside class="k-banda"><div style="color:#fff">${escudo('currentColor', 64)}</div>
        <div class="k-anio" aria-label="Año ${esc(d.periodo)}">${esc(d.periodo)}</div>
        <small>Periodo<br>académico<br>vigente</small></aside>
      <div class="k-cuerpo">
        <p class="uni">${esc(d.universidad)} · Secretaría Académica</p>
        <h2>Constancia de<br>Matrícula</h2><div class="k-barra"></div>
        <p class="k-texto">La Secretaría Académica deja constancia de que el(la) alumno(a)</p>
        <p class="k-texto" style="margin:6px 0 4px"><span class="k-nombre">${esc(tit(a.nombres))} ${esc(tit(a.apellidos))}</span></p>
        <p class="k-texto">identificado(a) con el código de alumno <b>${esc(a.id)}</b>, de la carrera de <b>${esc(tit(a.carrera))}</b>, se encuentra:</p>
        <div><span class="k-insignia"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m7.5 12.5 3 3 6-7"/></svg>${esc(d.condicion)}</span></div>
        <p class="k-texto">en el periodo académico <b>${esc(d.periodo)}</b>.</p>
        <dl class="k-ficha">
          <div><dt>Código de carrera</dt><dd>${esc(a.id_carrera)}</dd></div>
          <div><dt>Condición</dt><dd>${esc(tit(a.estado))}</dd></div>
          <div><dt>Fecha de emisión</dt><dd>${fecha(d.fecha_emision)}</dd></div>
          <div><dt>N.º de documento</dt><dd>${esc(d.codigo_documento)}</dd></div>
        </dl>
        <footer class="k-pie">${firmas('Director(a) Académico(a)', 'Registros Académicos')}
          <div class="verif">${barras(d.codigo_documento)}<span class="pie-demo">Documento de demostración · sin validez oficial</span></div></footer>
      </div>${marcaAgua()}</article>`;
  }

  /* ---------- DIPLOMA DE BACHILLER ---------- */
  const esquina = n => `<svg class="esq esq--${n}" viewBox="0 0 92 92" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
    <path d="M4 88V30C4 16 16 4 30 4h58"/><path d="M14 88V34c0-11 9-20 20-20h54" opacity=".6"/><path d="M26 30c8-10 18-8 20 0s-10 14-14 6"/><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>`;
  function diploma(d) {
    const a = d.alumno;
    return `<article class="doc d-dip">
      ${[1, 2, 3, 4].map(esquina).join('')}
      <div class="dp">
        <p class="uni">${esc(d.universidad)}</p>
        <h2 class="oro">Diploma de Bachiller</h2>
        <p class="otorga">La Universidad, por cuanto el(la) alumno(a) ha cumplido el plan de estudios, otorga a</p>
        <p class="nombre">${esc(tit(a.nombres))} ${esc(tit(a.apellidos))}</p>
        <p class="por">por haber aprobado ${d.cursos_completados} cursos y completado ${d.creditos} créditos de la carrera de ${esc(tit(a.carrera))}, el grado académico de</p>
        <p class="grado oro">${esc(d.grado)}</p>
        <p class="fecha">Expedido el ${fecha(d.fecha_emision)} · Registro ${esc(d.codigo_documento)}</p>
        <div class="dp-pie">
          <div class="firma"><i></i><b>Rector(a)</b>Firma y rúbrica</div>
          <div class="medalla"><span class="cinta cinta--1"></span><span class="cinta cinta--2"></span><div class="disco"></div>${escudo('currentColor', 60)}</div>
          <div class="firma"><i></i><b>Secretario(a) General</b>Firma y rúbrica</div>
        </div>
        <p class="pie-demo">Documento de demostración · sin validez oficial</p>
      </div>${marcaAgua()}</article>`;
  }

  const RENDER = { 'certificado-estudios': certificado, 'constancia-matricula': constancia, 'bachiller': diploma };

  /* ---------- escala del documento a la pantalla ---------- */
  function escalar() {
    const wrap = $('#docWrap'), inner = $('#docEscala'); if (wrap.hidden) return;
    const disponible = $('#escenario').clientWidth - parseFloat(getComputedStyle($('#escenario')).paddingInline) * 2;
    const ancho = NATURAL[slug], s = Math.min(1, disponible / ancho);
    inner.style.width = ancho + 'px';
    inner.style.transform = `scale(${s})`;
    wrap.style.width = ancho * s + 'px';
    wrap.style.height = inner.offsetHeight * s + 'px';
  }
  new ResizeObserver(escalar).observe($('#escenario'));

  /* ---------- panel y pasos ---------- */
  function pasos(n, hechos) {
    document.querySelectorAll('#pasos li').forEach((li, i) => {
      li.className = i < hechos ? 'hecho' : i === n ? 'activo' : '';
    });
  }
  function pintarPanel() {
    const d = datos, a = d.alumno;
    $('#pTramite').textContent = d.tramite;
    $('#pAlumno').textContent = `${tit(a.nombres)} ${tit(a.apellidos)}`;
    $('#pEntrega').textContent = entrega(d);
    $('#pCodigo').textContent = d.codigo_documento;
    $('#pPrecio').textContent = soles(d.precio);
    const acc = $('#pAccion');
    if (d.pagado) {
      pasos(3, 3);
      const extra = d.entrega_inmediata
        ? '<p class="nota">Tu documento ya está habilitado sin marca de agua.</p><button class="btn" id="btnImprimir" type="button">Descargar o imprimir PDF</button>'
        : `<p class="nota">Te avisaremos cuando tu diploma esté listo. Plazo de entrega: ${esc(entrega(d))}.</p>`;
      acc.innerHTML = `<div class="ok"><b>✓ Pago confirmado</b><span>N.º de orden ${esc(d.orden_id)}</span></div>${extra}`;
      const bi = $('#btnImprimir'); if (bi) bi.onclick = imprimir;
    } else {
      pasos(0, 0);
      acc.innerHTML = '<button class="btn" id="btnConfirmar" type="button">Confirmar trámite</button><p class="nota">Esta es una vista previa con marca de agua. Aún no se realizó ningún cobro.</p>';
      $('#btnConfirmar').onclick = confirmar;
    }
  }
  function imprimir() {
    const st = document.createElement('style');
    st.textContent = `@page{size:${slug === 'bachiller' ? 'A4 landscape' : 'A4 portrait'};margin:0}`;
    document.head.append(st); window.print(); setTimeout(() => st.remove(), 800);
  }

  /* ---------- confirmar -> ventana de pago ---------- */
  async function confirmar() {
    const btn = $('#btnConfirmar'); btn.disabled = true; btn.textContent = 'Preparando tu orden…';
    const dlg = $('#dlgPago');
    try {
      const r = await fetch('/api/pagos/ordenes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tramite: slug, id_alumno: idAlumno }) });
      const o = await r.json(); if (!r.ok) throw new Error(o.detail || 'No se pudo crear la orden de pago.');
      pasos(2, 2);
      const vence = new Date(o.vence).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' });
      $('#dlgCuerpo').innerHTML = `
        <h2 id="dlgTitulo">Confirmaste tu trámite. Falta el pago.</h2>
        <p class="dlg__sub">Revisa el resumen y paga en línea para habilitar tu documento.</p>
        <dl class="resumen">
          <div><dt>Trámite</dt><dd>${esc(datos.tramite)}</dd></div>
          <div><dt>Alumno</dt><dd>${esc(tit(datos.alumno.nombres))} ${esc(tit(datos.alumno.apellidos))}</dd></div>
          <div><dt>N.º de orden</dt><dd>${esc(o.orden_id)}</dd></div>
          <div><dt>Entrega</dt><dd>${esc(entrega(datos))}</dd></div>
          <div><dt>Orden vigente hasta</dt><dd>${esc(vence)}</dd></div>
          <div class="total"><dt>Total a pagar</dt><dd>${soles(o.monto)}</dd></div>
        </dl>
        <div class="metodo"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20M6 15h4"/></svg>
          <div><b>Pago en línea con tarjeta</b><span>Crédito o débito. Pagarás en la pasarela de pagos segura; Sello no guarda los datos de tu tarjeta.</span></div></div>
        <div class="dlg__acc"><a class="btn" href="${esc(o.checkout_url)}">Pagar ${soles(o.monto)} en línea</a>
          <button class="btn btn--2" type="button" id="btnVolverDlg">Volver a la vista previa</button></div>`;
      $('#btnVolverDlg').onclick = () => dlg.close();
      dlg.showModal();
    } catch (e) {
      $('#dlgCuerpo').innerHTML = `<h2 id="dlgTitulo">No pudimos preparar el pago</h2><p class="error">${esc(e.message)}</p><button class="btn btn--2" type="button" onclick="document.getElementById('dlgPago').close()">Cerrar</button>`;
      dlg.showModal();
    } finally { btn.disabled = false; btn.textContent = 'Confirmar trámite'; }
  }
  $('#dlgPago').addEventListener('close', () => { if (datos && !datos.pagado) pasos(0, 0); });
  $('#dlgPago').addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.close(); });

  /* ---------- carga ---------- */
  async function cargar() {
    try {
      const r = await fetch(`/api/preview/${encodeURIComponent(slug)}/${encodeURIComponent(idAlumno)}`);
      const j = await r.json();
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'No pudimos cargar la vista previa.');
      datos = j;
      document.title = `Vista previa · ${j.tramite} · Sello`;
      $('#estado').hidden = true;
      $('#docEscala').innerHTML = RENDER[slug](j);
      if (!(j.pagado && j.entrega_inmediata)) $('#docWrap').classList.add('sin-copiar');
      $('#docWrap').hidden = false; $('#panel').hidden = false;
      pintarPanel(); escalar();
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(escalar);
    } catch (e) {
      $('#estado').innerHTML = `<b>No hay vista previa disponible</b>${esc(e.message)}<br><br><a href="/">Volver al asistente</a>`;
    }
  }
  cargar();
})();
