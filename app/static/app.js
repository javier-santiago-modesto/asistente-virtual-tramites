(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const el = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
  const esc = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const titulo = s => s.toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase());

  const estado = { id: null, ocupado: false };

  /* ---------- API ---------- */
  async function api(url, opciones) {
    const r = await fetch(url, opciones);
    let j = null; try { j = await r.json(); } catch (_) {}
    if (!r.ok) {
      const d = j && j.detail;
      throw new Error(typeof d === 'string' ? d : (Array.isArray(d) && d[0] && d[0].msg) || 'No pudimos completar la solicitud.');
    }
    return j;
  }
  const post = (u, b) => api(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) });

  /* ---------- Markdown mínimo y seguro (se escapa todo antes) ---------- */
  function inline(t) {
    return esc(t)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, '$1<em>$2</em>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }
  function markdown(src) {
    const out = []; let lista = null;
    const cerrar = () => { if (lista) { out.push(`</${lista}>`); lista = null; } };
    for (const raw of src.split('\n')) {
      const l = raw.trimEnd();
      let m;
      if (!l.trim()) { cerrar(); continue; }
      if ((m = l.match(/^\s*(#{1,4})\s+(.*)/))) { cerrar(); out.push(`<h4>${inline(m[2])}</h4>`); continue; }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) { cerrar(); out.push('<hr>'); continue; }
      if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (lista !== 'ul') { cerrar(); out.push('<ul>'); lista = 'ul'; } out.push(`<li>${inline(m[1])}</li>`); continue; }
      if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (lista !== 'ol') { cerrar(); out.push('<ol>'); lista = 'ol'; } out.push(`<li>${inline(m[1])}</li>`); continue; }
      if (lista && /^\s{2,}\S/.test(l)) { out.push(`<li style="list-style:none;margin-left:-.2rem">${inline(l.trim())}</li>`); continue; }
      cerrar(); out.push(`<p>${inline(l)}</p>`);
    }
    cerrar(); return out.join('');
  }

  /* ---------- Mensajes ---------- */
  const cont = () => $('#mensajes');
  const bajar = () => { const c = cont(); c.scrollTop = c.scrollHeight; };

  function agregarUsuario(texto) {
    const f = el('div', 'fila fila--yo'); const b = el('div', 'burbuja'); b.textContent = texto;
    f.append(b); cont().append(f); bajar();
  }
  const NOMBRE_PREVIEW = { 'certificado-estudios': 'Certificado de Estudios', 'constancia-matricula': 'Constancia de Matrícula', 'bachiller': 'Diploma de Bachiller' };
  function tarjetaPreview(url) {
    const slug = url.split('/')[2];
    const c = el('div', 'previa');
    c.innerHTML = `<div class="previa__mini" aria-hidden="true"><i></i><i></i><i></i><i class="c"></i><span>Preview</span></div>
      <div class="previa__txt"><b>Tu ${esc(NOMBRE_PREVIEW[slug] || 'documento')} está listo para previsualizar</b>
      <span>Se abre en una página aparte. Ahí confirmas el trámite y pagas en línea.</span></div>`;
    const a = el('a', 'previa__btn', 'Abrir vista previa'); a.href = url; a.target = '_blank'; a.rel = 'noopener';
    c.append(a); return c;
  }
  /* Los títulos de trámites de una lista numerada se vuelven botones: un clic inicia la validación */
  function hacerClicables(burbuja) {
    burbuja.querySelectorAll('ol > li').forEach(li => {
      const nombre = li.textContent.trim().replace('Matrícula', 'Matricula');
      const pregunta = PREGUNTA[nombre];
      if (!pregunta) return;
      li.classList.add('opcion'); li.tabIndex = 0; li.setAttribute('role', 'button');
      li.title = 'Clic para validar si puedes tramitarlo';
      const ir = () => enviar(pregunta);
      li.onclick = ir;
      li.onkeydown = ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ir(); } };
    });
  }
  function agregarAsistente(texto, { error = false, previewUrl = null } = {}) {
    const f = el('div', 'fila'); f.append(el('div', 'fila__ico'));
    const b = el('div', 'burbuja' + (error ? ' burbuja--error' : ''));
    if (error) b.textContent = texto; else { b.innerHTML = markdown(texto); hacerClicables(b); }
    if (previewUrl) b.append(tarjetaPreview(previewUrl));
    // Botones de respuesta rápida cuando el asistente pide confirmar
    if (!error && /(desea|deseas|quieres|quiere)[^?¿\n]{0,40}continuar|¿continuar|confirm(a|as|ar) (que|si)/i.test(texto) && /\?\s*$/.test(texto.trim())) {
      const r = el('div', 'respuestas');
      [['Sí, continuar', 'Sí, deseo continuar con el trámite.', 'resp resp--si'], ['Por ahora no', 'No, por ahora no deseo continuar.', 'resp']].forEach(([t, msg, c]) => {
        const bt = el('button', c, t); bt.type = 'button'; bt.onclick = () => { r.remove(); enviar(msg); }; r.append(bt);
      });
      b.append(r);
    }
    f.append(b); cont().append(f);
    bajar();
  }

  const FRASES = ['Revisando tus datos…', 'Consultando tu historial…', 'Verificando requisitos…', 'Preparando tu respuesta…'];
  let timerFrase;
  function mostrarEscribiendo() {
    const f = el('div', 'fila'); f.id = 'escribiendo'; f.append(el('div', 'fila__ico'));
    const b = el('div', 'burbuja', '<div class="escribiendo"><i></i><i></i><i></i><span></span></div>');
    f.append(b); cont().append(f); bajar();
    const s = b.querySelector('span'); let i = 0; s.textContent = FRASES[0];
    timerFrase = setInterval(() => { i = (i + 1) % FRASES.length; s.textContent = FRASES[i]; }, 2200);
  }
  function ocultarEscribiendo() { clearInterval(timerFrase); const f = $('#escribiendo'); if (f) f.remove(); }

  function fijarOcupado(v) {
    estado.ocupado = v;
    $('#btnEnviar').disabled = v;
    document.querySelectorAll('.tramite,.chip,.resp').forEach(b => b.disabled = v);
    document.body.classList.toggle('ocupado', v);
  }

  async function enviar(texto, { silencioso = false } = {}) {
    texto = texto.trim(); if ((!texto && !silencioso) || estado.ocupado) return;
    if (!silencioso) agregarUsuario(texto);
    fijarOcupado(true); mostrarEscribiendo();
    try {
      const r = await post(silencioso ? '/sesion/iniciar' : '/chat', silencioso ? { id_alumno: estado.id } : { id_alumno: estado.id, mensaje: texto });
      ocultarEscribiendo(); agregarAsistente(r.respuesta, { previewUrl: r.preview_url });
    } catch (e) {
      ocultarEscribiendo(); agregarAsistente(e.message + ' Intenta de nuevo en unos segundos.', { error: true });
    } finally { fijarOcupado(false); $('#texto').focus({ preventScroll: true }); }
  }

  /* ---------- Panel lateral ---------- */
  const PREGUNTA = {
    'Certificado de Estudios': 'Quiero tramitar mi Certificado de Estudios',
    'Constancia de Matricula': 'Quiero tramitar mi Constancia de Matrícula',
    'Bachiller': 'Quiero tramitar mi Bachiller',
  };
  function pintarTramites(lista) {
    const c = $('#tramites'); c.innerHTML = '';
    lista.forEach(t => {
      const b = el('button', 'tramite'); b.type = 'button';
      b.innerHTML = `<span class="tramite__nombre">${esc(t.NOMBRETRAMITE.replace('Matricula', 'Matrícula'))}</span>
        <span class="tramite__desc">${esc(t.DESCRIPCIONTRAMITE)}</span>
        <span class="tramite__pie"><span class="etq">S/ ${esc(Number(t.PRECIOTRAMITE).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))}</span><span class="etq etq--t">${esc(t.TIEMPOENTREGA.toLowerCase())}</span></span>`;
      b.onclick = () => enviar(PREGUNTA[t.NOMBRETRAMITE] || `Quiero tramitar ${t.NOMBRETRAMITE}`);
      c.append(b);
    });
  }
  const SUGERENCIAS = ['¿Qué requisitos piden para el Bachiller?', '¿Qué es una constancia de matrícula?', '¿Para qué sirve el certificado de estudios?', '¿Cuánto demora cada trámite?'];
  function pintarSugerencias() {
    const c = $('#sugerencias'); c.innerHTML = '';
    SUGERENCIAS.forEach(s => { const b = el('button', 'chip', esc(s)); b.type = 'button'; b.onclick = () => enviar(s); c.append(b); });
  }

  /* ---------- Ingreso ---------- */
  async function ingresar(e) {
    e.preventDefault();
    const id = $('#idalumo').value.trim().toUpperCase();
    const err = $('#ingresoError'); err.hidden = true;
    if (!/^N\d{1,6}$/.test(id)) { err.textContent = 'Tu código empieza con N y sigue con hasta 6 números. Ejemplo: N000456.'; err.hidden = false; $('#idalumo').focus(); return; }
    const btn = $('#btnIngreso'); btn.disabled = true; btn.textContent = 'Buscando…';
    try {
      const [a, t] = await Promise.all([api(`/alumno/${id}`), api('/tramites')]);
      estado.id = id; try { sessionStorage.setItem('idalumo', id); } catch (_) {}
      const nombre = titulo(a.nombres.split(' ')[0]);
      $('#avatar').textContent = nombre[0];
      $('#perfilNombre').textContent = `${nombre} ${titulo(a.apellidos.split(' ')[0])}`;
      $('#perfilMeta').textContent = `${titulo(a.carrera)} · ${titulo(a.estado)}`;
      pintarTramites(t); pintarSugerencias();
      $('#entrada').hidden = true; $('#app').hidden = false; cont().innerHTML = '';
      enviar('', { silencioso: true });
    } catch (x) {
      err.textContent = x.message; err.hidden = false; $('#idalumo').focus();
    } finally { btn.disabled = false; btn.textContent = 'Empezar'; }
  }

  function salir() {
    estado.id = null; try { sessionStorage.removeItem('idalumo'); } catch (_) {}
    $('#app').hidden = true; $('#entrada').hidden = false; $('#idalumo').value = ''; $('#idalumo').focus();
  }

  /* ---------- Compositor ---------- */
  function autoaltura() { const t = $('#texto'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 144) + 'px'; }
  $('#texto').addEventListener('input', autoaltura);
  $('#texto').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#formChat').requestSubmit(); } });
  $('#formChat').addEventListener('submit', e => { e.preventDefault(); const t = $('#texto'); const v = t.value; t.value = ''; autoaltura(); enviar(v); });
  $('#formIngreso').addEventListener('submit', ingresar);
  $('#btnSalir').addEventListener('click', salir);
  $('#idalumo').focus();
})();
