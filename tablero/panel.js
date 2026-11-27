'use strict';
// Prototipo de extensión del tablero. Lee datos.json (que escribe metricas.py o datos_simulados.py) y NO decide nada:
// los botones solo envían una orden si se abre con ?api=URL, y el contrato de esa API es provisional.
const P = new URLSearchParams(location.search);
const FUENTE = P.get('fuente') || 'datos/datos.json';
const API = P.get('api');
const CADA = Math.max(250, Number(P.get('cada')) || 500);
const TERMINALES = ['FIN', 'FALLA'];
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt !== undefined) e.textContent = txt; return e; };
const num = (x) => typeof x === 'number' && Number.isFinite(x);
const fmt = (x, d = 1, u = '') => (num(x) ? x.toFixed(d) + u : '—');
const tiempo = (s) => (num(s) ? `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}` : '—');
const vaciar = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };

function kv(nodo, filas) {
  vaciar(nodo);
  for (const [k, v, cls] of filas) { nodo.appendChild(el('span', '', k)); nodo.appendChild(el('span', cls || '', v)); }
}

function claseEstado(e) { return e === 'FALLA' ? 'mal' : e === 'FIN' ? 'ok' : e === 'ESPERA' || e === 'SIN_DATOS' ? '' : 'activo'; }

function cabecera(d, m) {
  const f = $('fuente');
  f.textContent = d.fuente === 'simulado' ? 'DATOS SIMULADOS' : 'EN VIVO';
  f.className = 'chip ' + (d.fuente === 'simulado' ? 'aviso-c' : 'ok');
  const e = $('estado');
  e.textContent = m.estado.estado + (m.estado.motivo && m.estado.estado === 'FALLA' ? ` · ${m.estado.motivo}` : '');
  e.className = 'chip grande ' + claseEstado(m.estado.estado);
  const edad = Date.now() / 1000 - d.generado;
  const viejo = num(edad) && edad > 3 && !TERMINALES.includes(m.estado.estado);
  $('edad').textContent = num(edad) ? `actualizado hace ${edad.toFixed(0)} s` : '';
  const a = $('aviso');
  a.hidden = !viejo;
  a.textContent = viejo ? `DATOS DESACTUALIZADOS (${edad.toFixed(0)} s): el estado mostrado puede no ser el real` : '';
}

function colorSector(vueltas, n, i) {
  const v = vueltas[n].sectores[i];
  if (!num(v)) return '';
  const todos = vueltas.map((x) => x.sectores[i]).filter(num);
  if (vueltas.length > 1 && v <= Math.min(...todos)) return 'morado';
  if (n === 0) return '';
  const prev = vueltas[n - 1].sectores[i];
  return num(prev) && v <= prev ? 'verde' : 'amarillo';
}

function cronometraje(m) {
  const c = m.cronometraje;
  kv($('crono-resumen'), [['Vuelta', `${Math.min(m.estado.vuelta || 0, m.mision.vueltas_total)}/${m.mision.vueltas_total}`], ['Última', tiempo(c.ultima)],
    ['Mejor', tiempo(c.mejor)], ['Delta', num(c.delta) ? (c.delta >= 0 ? '+' : '−') + Math.abs(c.delta).toFixed(1) + ' s' : '—']]);
  const t = $('vueltas');
  vaciar(t);
  const cab = el('tr');
  for (const h of ['Vuelta', 'Tiempo', 'S1', 'S2', 'S3', 'S4']) cab.appendChild(el('th', '', h));
  t.appendChild(cab);
  c.vueltas.forEach((v, n) => {
    const fila = el('tr');
    fila.appendChild(el('td', '', `${v.numero}${v.valida ? '' : ' ✗'}`));
    fila.appendChild(el('td', '', tiempo(v.duracion)));
    v.sectores.forEach((s, i) => fila.appendChild(el('td', colorSector(c.vueltas, n, i), tiempo(s))));
    t.appendChild(fila);
  });
}

function estaciones(d, m) {
  const g = $('est-grid');
  vaciar(g);
  const por = Object.fromEntries(m.estaciones.map((s) => [s.estacion, s]));
  for (let n = 1; n <= 4; n++) {
    const s = por[n] || {};
    const caja = el('div', 'est' + (m.estado.estacion === n && !TERMINALES.includes(m.estado.estado) ? ' actual' : '') + (s.valido === false ? ' fallo' : ''));
    caja.appendChild(el('b', '', `E${n} · ${(d.banderas.estaciones || {})[n] || '—'}`));
    caja.appendChild(el('span', num(s.t_pit_s) && s.t_pit_s > m.pits.limite_s ? 'lento' : '', `pit ${fmt(s.t_pit_s, 1, ' s')}`));
    caja.appendChild(el('span', '', `error ${fmt(s.err_pos_pre_cm, 1)} → ${fmt(s.err_pos_post_cm, 1, ' cm')}`));
    caja.appendChild(el('span', '', s.valido === undefined ? 'sin pit' : s.valido ? 'válido' : 'NO válido'));
    g.appendChild(caja);
  }
}

function carrito(d, m) {
  const t = d.telemetria || {};
  kv($('carrito-kv'), [['Pieza', m.estado.pieza || 'vacío'], ['cd', fmt(m.estado.cd, 3)], ['ca', fmt(m.estado.ca, 3)], ['v', fmt(t.v, 2, ' m/s')],
    ['ω', fmt(t.w, 2, ' rad/s')], ['Batería', fmt(t.bateria, 2, ' V')], ['Latencia', fmt(t.latencia_ms, 0, ' ms')], ['Video', t.video || 'lo da el tablero base']]);
}

function banderas(d) {
  const b = d.banderas || {}, i = d.intervenciones || { contador: 0, bitacora: [] };
  kv($('banderas-kv'), [['Bandera', b.bandera || '—', b.bandera === 'roja' ? 'mal' : ''], ['Turno', b.turno === true ? 'autorizado' : b.turno === false ? 'NO autorizado' : '—'],
    ['Enlace', b.enlace === true ? 'vivo' : b.enlace === false ? 'PERDIDO' : '—', b.enlace === false ? 'mal' : ''], ['Intervenciones', String(i.contador)]]);
  const ul = $('bitacora');
  vaciar(ul);
  for (const x of i.bitacora) ul.appendChild(el('li', '', `${x.tipo || ''} ${x.descripcion || ''}`));
  if (!i.bitacora.length) ul.appendChild(el('li', 'tenue', 'sin intervenciones registradas'));
}

function pits(m) {
  const p = m.pits, r = p.reduccion, e = m.escalas, ru = m.rubrica_estimada;
  kv($('pits-kv'), [['Pits', `${m.mision.pits_validos}/${m.mision.pits} válidos (de ${m.mision.pits_esperados})`], ['Tiempo medio / máx.', `${fmt(p.t_medio_s)} / ${fmt(p.t_max_s)} s`],
    [`Más de ${p.limite_s} s`, String(p.lentos), p.lentos ? 'aviso-c' : ''], ['Con corrección', String(p.con_correccion)], ['Reintentos', String(p.reintentos)],
    ['Error antes (media / p95)', `${fmt(p.err_pos_pre_cm.media)} / ${fmt(p.err_pos_pre_cm.p95)} cm`], ['Error después', `${fmt(p.err_pos_post_cm.media)} / ${fmt(p.err_pos_post_cm.p95)} cm`],
    ['Error menor tras el pit', r ? `${r.mejoran}/${r.n} (${(r.fraccion * 100).toFixed(0)} %)` : '—', r ? (r.cumple ? 'ok' : 'mal') : ''],
    ['Escalas convergen', e.convergio ? 'sí' : 'no', e.convergio ? 'ok' : ''], ['Vueltas válidas', `${m.mision.vueltas_validas}/${m.mision.vueltas_total}`],
    ['Puntos (estimación)', `tanda ${ru.tanda_pts}/4 · pieza ${ru.pieza_pts}/3`]]);
}

function evidencia(d) {
  const ev = d.evidencia, ul = $('evidencia-lista');
  vaciar(ul);
  if (!ev) {
    kv($('evidencia-kv'), [['Estado', 'sin verificar']]);
    ul.appendChild(el('li', 'tenue', 'python3 evidencia/verificar_evidencias.py CARPETA --json informe.json'));
    return;
  }
  kv($('evidencia-kv'), [['Estado', ev.ok ? 'COMPLETA' : 'INCOMPLETA', ev.ok ? 'ok' : 'mal'], ['Fallas / avisos', `${ev.fallas} / ${ev.avisos}`]]);
  for (const h of ev.hallazgos.filter((x) => x.nivel !== 'OK').slice(0, 14)) ul.appendChild(el('li', h.nivel, `${h.nivel} ${h.item}: ${h.detalle}`));
}

function eventos(m) {
  const ul = $('eventos-lista');
  vaciar(ul);
  for (const e of m.eventos_recientes.slice().reverse().slice(0, 18)) {
    const hora = new Date(e.ts * 1000).toISOString().slice(11, 19);
    const dato = e.motivo || (e.datos && (e.datos.texto || e.datos.campo || e.datos.de)) || '';
    ul.appendChild(el('li', e.tipo === 'falla' ? 'FALLA' : '', `${hora}  ${e.tipo}  ${e.estado || ''} ${e.estacion ? 'E' + e.estacion : ''}  ${dato}`));
  }
}

function pintar(d) {
  const m = d.metricas;
  cabecera(d, m); cronometraje(m); estaciones(d, m); carrito(d, m); banderas(d); pits(m); evidencia(d); eventos(m);
}

async function cargar() {
  if (location.protocol === 'file:' && window.DATOS) return window.DATOS;      // doble clic: no hay fetch posible, se usa datos.js
  try {
    const r = await fetch(FUENTE + (FUENTE.includes('?') ? '&' : '?') + 't=' + Date.now(), { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) {
    if (window.DATOS) return window.DATOS;      // abierto con doble clic (file://): usa datos.js
    throw e;
  }
}

async function orden(nombre) {
  const a = $('aviso');
  if (!API) { a.hidden = false; a.textContent = 'Sin API: este panel es de solo lectura. Ábrelo con ?api=URL del tablero para enviar órdenes.'; return; }
  try {
    const r = await fetch(API.replace(/\/$/, '') + '/orden', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ orden: nombre }) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    a.hidden = true;
  } catch (e) { a.hidden = false; a.textContent = `La orden "${nombre}" NO se envió: ${e.message}`; }
}

document.querySelectorAll('[data-orden]').forEach((b) => b.addEventListener('click', () => orden(b.dataset.orden)));
$('estop').addEventListener('click', () => orden('estop'));
$('api').textContent = API ? `API: ${API}` : 'Sin ?api=: botones de solo demostración';

async function ciclo() {
  try { pintar(await cargar()); }
  catch (e) { const a = $('aviso'); a.hidden = false; a.textContent = `Sin datos de ${FUENTE}: ${e.message}`; }
  setTimeout(ciclo, CADA);
}
ciclo();
