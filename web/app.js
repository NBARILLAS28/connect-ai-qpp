'use strict';
/* Mando PC — cliente (PWA). Sin dependencias. */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const LS = {
  get(k, d) { try { const v = localStorage.getItem('mpc_' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('mpc_' + k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem('mpc_' + k); } catch {} },
};

/* ───────────── estado ───────────── */
const PRESETS = {
  ahorro: { w: 640, q: 45, fps: 10 },
  normal: { w: 960, q: 58, fps: 12 },
  nitido: { w: 1400, q: 75, fps: 10 },
};
const S = {
  ws: null, ok: false, info: null, tab: 'pantalla', cerrando: false,
  modo: LS.get('modo', 'pad'), sens: LS.get('sens', 1.2), cal: LS.get('cal', 'normal'),
  mods: { ctrl: false, alt: false, shift: false, cmd: false },
  arrLock: false, ocultos: false, dir: null,
};
let token = null;

function leerToken() {
  const m = location.hash.match(/[#&]t=([^&]+)/);
  if (m) { const t = decodeURIComponent(m[1]); LS.set('token', t); return t; }
  return LS.get('token', null);
}
function nombreDispositivo() {
  const u = navigator.userAgent;
  if (/iPhone/i.test(u)) return 'iPhone';
  if (/iPad/i.test(u)) return 'iPad';
  if (/Android/i.test(u)) return 'Android';
  if (/Windows/i.test(u)) return 'PC Windows';
  if (/Mac/i.test(u)) return 'Mac';
  return 'Celular';
}
const instalada = () => !!(navigator.standalone || (window.matchMedia && matchMedia('(display-mode: standalone)').matches));
function fijarManifest() {
  // el manifest lleva el token: así la app de la pantalla de inicio nace ya vinculada
  if (token) $('#lnkManifest').href = '/manifest.webmanifest?t=' + encodeURIComponent(token);
}
/* cambia un código de un solo uso (QR) por la llave propia de este celular */
async function vincular(codigo) {
  try {
    const r = await fetch('/vincular', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo, nombre: nombreDispositivo() }) });
    if (!r.ok) return false;
    const d = await r.json();
    token = d.token; LS.set('token', d.token); LS.set('nombreDisp', d.nombre);
    history.replaceState(null, '', location.pathname);
    fijarManifest();
    return true;
  } catch { return false; }
}
function pintarVinculo() {
  const nom = (S.info && S.info.dispositivo) || LS.get('nombreDisp', 'Este celular');
  $('#nomDisp').textContent = '📱 ' + nom;
  $('#vinc').textContent = token ? '· vinculado ✓' : ''; $('#vinc').className = 'muted' + (token ? ' ok' : '');
  $('#estInst').textContent = instalada()
    ? 'Instalada como app ✓ Entra siempre que quieras, sin volver a escanear.'
    : '⚠ Falta agregarla a la pantalla de inicio. Sin eso el navegador puede borrar la vinculación (Safari lo hace tras unos 7 días sin uso).';
}
function recordatorio() {
  if (!token || instalada() || S.avisoOculto) return;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  $('#avisoTxt').innerHTML = ios
    ? '✅ Celular vinculado. Para que no se pierda: toca <b>Compartir</b> (□↑) y luego <b>Agregar a pantalla de inicio</b>.'
    : '✅ Celular vinculado. Para que no se pierda: menú <b>⋮</b> → <b>Agregar a pantalla de inicio</b> (o Instalar app).';
  $('#aviso').hidden = false;
}

/* ───────────── utilidades UI ───────────── */
let toastT;
function toast(msg, ms = 2200) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), ms);
}
function vibrar(n = 10) { try { navigator.vibrate && navigator.vibrate(n); } catch {} }

function modal(titulo, texto, botones) {
  return new Promise(res => {
    $('#mTitulo').textContent = titulo; $('#mTexto').textContent = texto || '';
    const cont = $('#mBotones'); cont.innerHTML = '';
    for (const b of botones) {
      const el = document.createElement('button');
      el.className = 'b grande' + (b.clase ? ' ' + b.clase : ''); el.textContent = b.t;
      el.onclick = () => { $('#modal').hidden = true; res(b.v); };
      cont.appendChild(el);
    }
    $('#modal').hidden = false;
  });
}
const confirmar = (t, x, ok = 'Confirmar', clase = 'peligro') =>
  modal(t, x, [{ t: ok, v: true, clase }, { t: 'Cancelar', v: false }]);

/* ───────────── conexión ───────────── */
let reintento = 500, pingT = 0;

function setEstado(tipo) {
  $('#dot').className = 'dot ' + (tipo === 'ok' ? '' : tipo === 'mid' ? 'mid' : 'off');
  if (tipo !== 'ok') $('#ms').textContent = '';
}
function msg(txt) {
  const m = $('#msg'); if (txt) { m.textContent = txt; m.classList.remove('oculto'); } else m.classList.add('oculto');
}
function send(o) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(o)); }

function conectar() {
  if (!token) return mostrarLogin();
  setEstado('mid'); msg('Conectando…');
  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.binaryType = 'arraybuffer';
  S.ws = ws;
  ws.onopen = () => ws.send(JSON.stringify({ op: 'auth', token }));
  ws.onmessage = ev => {
    if (typeof ev.data !== 'string') return dibujar(ev.data);
    const m = JSON.parse(ev.data);
    if (m.t === 'hello') alConectar(m);
    else if (m.t === 'denegado') { S.cerrando = true; LS.del('token'); token = null; mostrarLogin('Esta vinculación ya no es válida (se quitó desde la laptop o es un código vencido). Vincula el celular de nuevo.'); }
    else if (m.t === 'pong') { const ms = Math.round(performance.now() - m.ts); $('#ms').textContent = ms + ' ms'; setEstado(ms > 400 ? 'mid' : 'ok'); }
    else if (m.t === 'estado') pintarEstado(m);
    else if (m.t === 'clip') { $('#txtClip').value = m.s || '(vacío)'; }
    else if (m.t === 'monitor') { S.info.pantalla = m.pantalla; S.info.monitor = m.i; $('#bMon').textContent = '🖥 ' + m.i; actualizarStream(); }
    else if (m.t === 'err') toast(m.m, 3500);
  };
  ws.onclose = () => {
    S.ok = false; clearInterval(pingT);
    if (S.cerrando) return;
    setEstado('off'); msg('Sin conexión con la laptop. Reintentando…');
    setTimeout(conectar, reintento); reintento = Math.min(reintento * 1.6, 5000);
  };
}

function alConectar(m) {
  S.ok = true; S.info = m; reintento = 500; $('#login').hidden = true;
  setEstado('ok'); $('#host').textContent = m.host || 'Mando PC';
  pintarEstado(m);
  $('#bMon').hidden = m.monitores < 2; $('#bMon').textContent = '🖥 ' + m.monitor;
  $('#infoSis').textContent = `Mando PC ${m.version} · ${({ win: 'Windows', mac: 'macOS', linux: 'Linux' })[m.os]}`;
  armarAtajos(); armarTeclado(); pintarVinculo(); recordatorio();
  if (m.avisos && m.avisos.length) toast(m.avisos[0], 9000);
  clearInterval(pingT);
  pingT = setInterval(() => send({ op: 'ping', ts: performance.now() }), 4000);
  send({ op: 'ping', ts: performance.now() });
  msg('Esperando imagen…');
  actualizarStream();
  if (S.tab === 'archivos' && !S.dir) cargarDir();
}

function pintarEstado(m) {
  if (m.host) $('#host').textContent = m.host;
  $('#lock').hidden = !m.bloqueada;
  $('#bat').textContent = m.bateria != null ? `${m.cargando ? '⚡' : '🔋'} ${m.bateria}%` : '';
}

function mostrarLogin(err) {
  $('#login').hidden = false; $('#loginErr').textContent = err || '';
  $('#inToken').value = '';
}
$('#bConectar').onclick = async () => {
  const txt = $('#inToken').value.trim();
  if (txt.length < 8) return ($('#loginErr').textContent = 'Pega el enlace completo del QR.');
  $('#loginErr').textContent = 'Vinculando…';
  const mt = txt.match(/[#?&]t=([^&\s]+)/), mc = txt.match(/[#?&]c=([^&\s]+)/);
  let ok = false;
  if (mt) { token = decodeURIComponent(mt[1]); LS.set('token', token); ok = true; }
  else ok = await vincular(mc ? decodeURIComponent(mc[1]) : txt);
  if (!ok) return ($('#loginErr').textContent = 'Ese código no sirve o ya venció. En la laptop recarga la página de vincular y vuelve a intentar.');
  fijarManifest(); S.cerrando = false; $('#login').hidden = true; conectar();
};

/* ───────────── pantalla ───────────── */
const stage = $('#stage'), cv = $('#cv'), ctx = cv.getContext('2d', { alpha: false });
const vista = { z: 1, tx: 0, ty: 0, fw: 0, fh: 0 };

async function dibujar(buf) {
  try {
    const blob = new Blob([new Uint8Array(buf, 1)], { type: 'image/jpeg' });
    const bmp = await createImageBitmap(blob);
    if (cv.width !== bmp.width || cv.height !== bmp.height) { cv.width = bmp.width; cv.height = bmp.height; ajustarVista(true); }
    ctx.drawImage(bmp, 0, 0); bmp.close && bmp.close();
    msg('');
  } catch {}
  send({ op: 'ack' });
}

function ajustarVista(reset) {
  if (!cv.width) return;
  const r = stage.getBoundingClientRect();
  const esc = Math.min(r.width / cv.width, r.height / cv.height);
  vista.fw = cv.width * esc; vista.fh = cv.height * esc;
  cv.style.width = vista.fw + 'px'; cv.style.height = vista.fh + 'px';
  if (reset) { vista.z = 1; vista.tx = (r.width - vista.fw) / 2; vista.ty = (r.height - vista.fh) / 2; }
  aplicarVista();
}
function aplicarVista() {
  const r = stage.getBoundingClientRect();
  const w = vista.fw * vista.z, h = vista.fh * vista.z;
  vista.tx = w <= r.width ? (r.width - w) / 2 : Math.min(0, Math.max(r.width - w, vista.tx));
  vista.ty = h <= r.height ? (r.height - h) / 2 : Math.min(0, Math.max(r.height - h, vista.ty));
  cv.style.transform = `translate(${vista.tx}px,${vista.ty}px) scale(${vista.z})`;
}
new ResizeObserver(() => ajustarVista(vista.z === 1)).observe(stage);

function actualizarStream() {
  if (!S.ok) return;
  const p = PRESETS[S.cal] || PRESETS.normal;
  const on = S.tab === 'pantalla' && !document.hidden;
  send({ op: 'screen', on, w: p.w, q: p.q, fps: p.fps });
}
document.addEventListener('visibilitychange', actualizarStream);

/* normaliza un punto del dedo a 0..1 sobre la pantalla remota */
function norm(e) {
  const r = cv.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
}

/* ---- gestos ---- */
const ptrs = new Map();
const T = { ini: 0, movido: false, dos: false, dosIni: 0, dosMovido: 0, arr: false, tapFin: 0, larga: null, hecho: false, pinch: null, pdx: 0, pdy: 0, sdx: 0, sdy: 0, raf: 0, abs: null, ultTapVista: 0 };

function planificar() { if (!T.raf) T.raf = requestAnimationFrame(vaciar); }
function vaciar() {
  T.raf = 0;
  const ix = Math.round(T.pdx), iy = Math.round(T.pdy);
  if (ix || iy) { T.pdx -= ix; T.pdy -= iy; send({ op: 'mv', dx: ix, dy: iy }); }
  if (T.sdx || T.sdy) { send({ op: 'scr', dx: T.sdx, dy: T.sdy }); T.sdx = T.sdy = 0; }
  if (T.abs) { send({ op: 'abs', x: T.abs.x, y: T.abs.y }); T.abs = null; }
}
function mover(dx, dy, dt) {
  if (!S.info) return;
  const v = Math.hypot(dx, dy) / Math.max(dt, 1);
  const gan = S.sens * (1 + Math.min(v, 3) * 0.25);
  const k = S.info.pantalla.w / (vista.fw * vista.z) * gan;
  T.pdx += dx * k; T.pdy += dy * k; planificar();
}

stage.addEventListener('pointerdown', e => {
  stage.setPointerCapture(e.pointerId);
  const now = performance.now();
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: now });
  const n = ptrs.size;
  if (n === 1) {
    T.ini = now; T.movido = false; T.dos = false; T.arr = false; T.hecho = false;
    if (S.modo === 'pad' && now - T.tapFin < 300) { T.arr = true; send({ op: 'dn', b: 'l' }); }
    if (S.modo === 'touch') {
      const p = norm(e); send({ op: 'abs', x: p.x, y: p.y });
      T.larga = setTimeout(() => {
        if (!T.movido && ptrs.size === 1) { send({ op: 'clk', b: 'r', n: 1 }); T.hecho = true; vibrar(20); }
      }, 550);
    }
  } else if (n === 2) {
    clearTimeout(T.larga);
    if (T.arr) { send({ op: 'up', b: 'l' }); T.arr = false; }
    if (S.modo === 'touch' && T.movido) { send({ op: 'up', b: 'l' }); }
    T.dos = true; T.dosIni = now; T.dosMovido = 0;
    if (S.modo === 'view') {
      const [a, b] = [...ptrs.values()];
      T.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), z: vista.z };
    }
  }
});

stage.addEventListener('pointermove', e => {
  const p = ptrs.get(e.pointerId); if (!p) return;
  const dx = e.clientX - p.x, dy = e.clientY - p.y, dt = e.timeStamp - (p.last || p.t); p.last = e.timeStamp;
  p.x = e.clientX; p.y = e.clientY;
  if (ptrs.size === 1 && !T.dos) {
    if (!T.movido && Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > 8) {
      T.movido = true; clearTimeout(T.larga);
      if (S.modo === 'touch') send({ op: 'dn', b: 'l' });
    }
    if (S.modo === 'pad') mover(dx, dy, dt);
    else if (S.modo === 'touch' && T.movido) { T.abs = norm(e); planificar(); }
    else if (S.modo === 'view') { vista.tx += dx; vista.ty += dy; aplicarVista(); }
  } else if (ptrs.size === 2) {
    T.dosMovido += Math.hypot(dx, dy);
    if (S.modo === 'view' && T.pinch) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y), cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const r = stage.getBoundingClientRect();
      const z2 = Math.min(6, Math.max(1, T.pinch.z * d / Math.max(T.pinch.d, 1)));
      const f = z2 / vista.z, px = cx - r.left, py = cy - r.top;
      vista.tx = px - (px - vista.tx) * f + dx / 2; vista.ty = py - (py - vista.ty) * f + dy / 2; vista.z = z2;
      aplicarVista();
    } else if (S.modo !== 'view') {
      T.sdx += dx / 2; T.sdy += dy / 2; planificar();
    }
  }
});

function terminar(e) {
  if (!ptrs.has(e.pointerId)) return;
  const now = performance.now();
  ptrs.delete(e.pointerId);
  if (T.dos) {
    if (ptrs.size === 0) {
      if (S.modo !== 'view' && T.dosMovido < 12 && now - T.dosIni < 350) { send({ op: 'clk', b: 'r', n: 1 }); vibrar(); }
      T.dos = false; T.pinch = null; T.tapFin = 0;
    }
    return;
  }
  clearTimeout(T.larga);
  if (e.type === 'pointercancel') { if (T.arr) send({ op: 'up', b: 'l' }); T.arr = false; return; }
  if (S.modo === 'pad') {
    if (T.arr) { send({ op: 'up', b: 'l' }); T.arr = false; T.tapFin = 0; }
    else if (!T.movido && now - T.ini < 300) { send({ op: 'clk', b: 'l', n: 1 }); T.tapFin = now; }
    else T.tapFin = 0;
  } else if (S.modo === 'touch') {
    if (T.movido) { if (T.abs) { send({ op: 'abs', x: T.abs.x, y: T.abs.y }); T.abs = null; } send({ op: 'up', b: 'l' }); }
    else if (!T.hecho) send({ op: 'clk', b: 'l', n: 1 });
    T.hecho = false;
  } else if (S.modo === 'view') {
    if (!T.movido && now - T.ini < 250) {
      if (now - T.ultTapVista < 320) { ajustarVista(true); T.ultTapVista = 0; } else T.ultTapVista = now;
    }
  }
}
stage.addEventListener('pointerup', terminar);
stage.addEventListener('pointercancel', terminar);
stage.addEventListener('contextmenu', e => e.preventDefault());

/* barra inferior de la pantalla */
function pintarModo() { $$('#modos button').forEach(b => b.classList.toggle('on', b.dataset.modo === S.modo)); }
$$('#modos button').forEach(b => (b.onclick = () => { S.modo = b.dataset.modo; LS.set('modo', S.modo); pintarModo(); if (S.modo !== 'view') ajustarVista(true); }));
$('#bClicL').onclick = () => { send({ op: 'clk', b: 'l', n: 1 }); vibrar(); };
$('#bClicR').onclick = () => { send({ op: 'clk', b: 'r', n: 1 }); vibrar(); };
$('#bArr').onclick = e => {
  S.arrLock = !S.arrLock; e.currentTarget.classList.toggle('on', S.arrLock);
  send({ op: S.arrLock ? 'dn' : 'up', b: 'l' });
  toast(S.arrLock ? 'Arrastre activo: mueve el dedo para seleccionar' : 'Arrastre terminado');
};
$('#bMon').onclick = () => {
  if (!S.info) return;
  const sig = S.info.monitor % S.info.monitores + 1;
  send({ op: 'monitor', i: sig });
};

/* ───────────── teclado ───────────── */
const esMac = () => S.info && S.info.os === 'mac';
function modsActivos() { return Object.keys(S.mods).filter(k => S.mods[k]); }
function limpiarMods() { for (const k in S.mods) S.mods[k] = false; $$('.mod').forEach(b => b.classList.remove('on')); }

function tecla(nombre) {
  send({ op: 'key', k: nombre, m: modsActivos() }); limpiarMods(); vibrar(6);
}
function texto(s) {
  const m = modsActivos();
  if (m.length && s.length === 1) { send({ op: 'key', k: s.toLowerCase(), m }); limpiarMods(); }
  else send({ op: 'txt', s });
}
function combo(teclas) { send({ op: 'combo', keys: teclas }); vibrar(6); }

function boton(txt, fn, clase = 'b', accesorio = false) {
  const b = document.createElement('button'); b.className = clase; b.textContent = txt;
  if (accesorio) { // no robar el foco del teclado en vivo
    b.addEventListener('pointerdown', e => { e.preventDefault(); fn(b); });
  } else b.onclick = () => fn(b);
  return b;
}
function botonMod(nombre, etiqueta, accesorio) {
  const b = boton(etiqueta, el => { S.mods[nombre] = !S.mods[nombre]; $$('.mod[data-m="' + nombre + '"]').forEach(x => x.classList.toggle('on', S.mods[nombre])); }, 'b mod', accesorio);
  b.dataset.m = nombre; return b;
}

let tecladoArmado = false;
function armarTeclado() {
  if (tecladoArmado) return; tecladoArmado = true;
  const mods = $('#mods');
  [['ctrl', 'Ctrl'], ['alt', 'Alt'], ['shift', '⇧ Shift'], ['cmd', esMac() ? '⌘ Cmd' : '⊞ Win']].forEach(([n, l]) => mods.appendChild(botonMod(n, l)));
  const fijas = $('#teclasFijas');
  [['Esc', 'esc'], ['Tab', 'tab'], ['Supr', 'delete'], ['⌫', 'backspace'], ['Enter', 'enter'],
   ['Inicio', 'home'], ['Fin', 'end'], ['RePág', 'page_up'], ['AvPág', 'page_down'], ['Espacio', 'space']]
    .forEach(([l, k]) => fijas.appendChild(boton(l, () => tecla(k))));
  const fl = $('#flechas');
  ['', ['▲', 'up'], '', ['◀', 'left'], ['▼', 'down'], ['▶', 'right']].forEach(x => {
    if (!x) fl.appendChild(document.createElement('span')); else fl.appendChild(boton(x[0], () => tecla(x[1])));
  });
  const f = $('#teclasF');
  for (let i = 1; i <= 12; i++) f.appendChild(boton('F' + i, () => tecla('f' + i)));
  const C = esMac() ? 'cmd' : 'ctrl';
  const at = $('#atajosKb');
  [['Copiar', [C, 'c']], ['Pegar', [C, 'v']], ['Cortar', [C, 'x']], ['Deshacer', [C, 'z']],
   ['Rehacer', [C, esMac() ? 'shift' : 'y', ...(esMac() ? ['z'] : [])]], ['Todo', [C, 'a']],
   ['Guardar', [C, 's']], ['Buscar', [C, 'f']], ['Nueva pestaña', [C, 't']],
   ['Cerrar pestaña', [C, 'w']], ['Actualizar', [C, 'r']], [esMac() ? 'Cambiar app' : 'Alt+Tab', [esMac() ? 'cmd' : 'alt', 'tab']]]
    .forEach(([l, k]) => at.appendChild(boton(l, () => combo(k))));
  // barra accesoria sobre el teclado en vivo
  const acc = $('#acc');
  [['ctrl', 'Ctrl'], ['alt', 'Alt'], ['shift', '⇧'], ['cmd', esMac() ? '⌘' : '⊞']].forEach(([n, l]) => acc.appendChild(botonMod(n, l, true)));
  [['Esc', 'esc'], ['Tab', 'tab'], ['◀', 'left'], ['▲', 'up'], ['▼', 'down'], ['▶', 'right'], ['Supr', 'delete'], ['Inicio', 'home'], ['Fin', 'end']]
    .forEach(([l, k]) => acc.appendChild(boton(l, () => tecla(k), 'b', true)));
  acc.appendChild(boton('Cerrar ⌄', () => $('#live').blur(), 'b', true));
}

/* entrada en vivo */
const live = $('#live'), SENT = '​';
function resetLive() { live.value = SENT; try { live.setSelectionRange(1, 1); } catch {} }
function abrirVivo() { resetLive(); live.focus(); }
live.addEventListener('focus', () => { resetLive(); $('#acc').hidden = false; posAcc(); });
live.addEventListener('blur', () => { $('#acc').hidden = true; });
live.addEventListener('input', e => {
  if (e.isComposing) return;
  const t = e.inputType || '';
  if (t.startsWith('delete')) tecla('backspace');
  else if (t === 'insertLineBreak' || t === 'insertParagraph') tecla('enter');
  else { const d = e.data != null ? e.data : live.value.replace(SENT, ''); if (d) texto(d); }
  resetLive();
});
live.addEventListener('compositionend', e => { if (e.data) texto(e.data); resetLive(); });
live.addEventListener('keydown', e => { // teclados físicos / teclas especiales
  const mapa = { Enter: 'enter', Backspace: 'backspace', Tab: 'tab', Escape: 'esc', ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Delete: 'delete' };
  if (mapa[e.key] && e.key !== 'Backspace' && e.key !== 'Enter') { e.preventDefault(); tecla(mapa[e.key]); }
});
$('#bKb').onclick = abrirVivo;
$('#bKbVivo').onclick = abrirVivo;

$('#bEscribir').onclick = () => {
  const v = $('#txtLargo').value; if (!v) return;
  send({ op: 'txt', s: v + ($('#chkEnter').checked ? '\n' : '') }); toast('Enviado');
};
$('#bPegar').onclick = () => {
  const v = $('#txtLargo').value; if (!v) return;
  send({ op: 'paste', s: v }); if ($('#chkEnter').checked) setTimeout(() => send({ op: 'key', k: 'enter', m: [] }), 250); toast('Pegado en la laptop');
};
$('#bTraerClip').onclick = () => send({ op: 'getclip' });
$('#bCopiarClip').onclick = () => {
  const ta = $('#txtClip'); ta.removeAttribute('readonly'); ta.select(); ta.setSelectionRange(0, 999999);
  let ok = false; try { ok = document.execCommand('copy'); } catch {}
  ta.setAttribute('readonly', ''); ta.blur(); toast(ok ? 'Copiado' : 'Mantén presionado el texto para copiar');
};

/* la barra accesoria sigue al teclado (visualViewport) */
function posAcc() {
  const vv = window.visualViewport; const acc = $('#acc'); if (!vv) return;
  document.documentElement.style.setProperty('--vh', vv.height + 'px');
  if (!acc.hidden) acc.style.top = (vv.offsetTop + vv.height - acc.offsetHeight) + 'px';
  window.scrollTo(0, 0);
}
if (window.visualViewport) { visualViewport.addEventListener('resize', posAcc); visualViewport.addEventListener('scroll', posAcc); }

/* ───────────── control ───────────── */
$$('[data-act]').forEach(b => (b.onclick = async () => {
  const c = b.dataset.conf;
  if (c && c !== 'no') {
    if (!(await confirmar(b.textContent.trim(), c, 'Sí, continuar'))) return;
  }
  send({ op: 'act', n: b.dataset.act }); vibrar(8);
  if (!c) { /* multimedia: sin aviso */ } else toast('Hecho');
}));
function armarAtajos() {
  const g = $('#misAtajos'); g.innerHTML = '';
  (S.info.atajos || []).forEach((a, i) => g.appendChild(boton(`${a.i} ${a.n}`, () => { send({ op: 'sc', i }); vibrar(8); })));
  if (!g.children.length) g.innerHTML = '<p class="muted peq">Sin atajos. Edítalos en ~/.mando-pc/config.json</p>';
}
$('#bUrl').onclick = () => { const u = $('#inUrl').value.trim(); if (u) { send({ op: 'url', u }); toast('Abriendo en la laptop'); } };
$('#inUrl').addEventListener('keydown', e => { if (e.key === 'Enter') $('#bUrl').click(); });

const rSens = $('#rSens');
rSens.value = S.sens; $('#vSens').textContent = '×' + S.sens;
rSens.oninput = () => { S.sens = parseFloat(rSens.value); $('#vSens').textContent = '×' + S.sens; LS.set('sens', S.sens); };
function pintarCal() { $$('#calidad button').forEach(b => b.classList.toggle('on', b.dataset.cal === S.cal)); }
$$('#calidad button').forEach(b => (b.onclick = () => { S.cal = b.dataset.cal; LS.set('cal', S.cal); pintarCal(); actualizarStream(); }));
$('#bSalir').onclick = async () => {
  if (!(await confirmar('Olvidar esta laptop', 'Este celular dejará de tener acceso hasta que lo vincules otra vez.', 'Olvidar'))) return;
  S.cerrando = true; LS.del('token'); token = null; history.replaceState(null, '', location.pathname);
  try { S.ws.close(); } catch {} mostrarLogin();
};

/* ───────────── archivos ───────────── */
async function api(ruta, opts = {}) {
  const r = await fetch(ruta, { ...opts, headers: { ...(opts.headers || {}), Authorization: 'Bearer ' + token } });
  if (r.status === 401) { S.cerrando = true; mostrarLogin('Sesión no válida.'); throw new Error('401'); }
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r;
}
const fmtTam = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : n < 1073741824 ? (n / 1048576).toFixed(1) + ' MB' : (n / 1073741824).toFixed(2) + ' GB';
const icono = n => { const e = (n.split('.').pop() || '').toLowerCase();
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'svg'].includes(e)) return '🖼️';
  if (['mp4', 'mov', 'mkv', 'avi', 'webm'].includes(e)) return '🎞️';
  if (['mp3', 'wav', 'm4a', 'flac', 'ogg'].includes(e)) return '🎵';
  if (['pdf'].includes(e)) return '📕'; if (['doc', 'docx', 'txt', 'md', 'rtf'].includes(e)) return '📄';
  if (['xls', 'xlsx', 'csv'].includes(e)) return '📊'; if (['ppt', 'pptx'].includes(e)) return '📽️';
  if (['zip', 'rar', '7z', 'gz'].includes(e)) return '🗜️'; return '📎'; };

async function cargarDir(path) {
  try {
    const r = await api('/api/ls?' + new URLSearchParams({ path: path || S.dir || '', ocultos: S.ocultos ? '1' : '0' }));
    const d = await r.json(); S.dir = d.path;
    $('#ruta').textContent = d.path;
    const rap = $('#rapidos'); rap.innerHTML = '';
    d.rapidos.forEach(q => rap.appendChild(boton(q.n, () => cargarDir(q.p))));
    const l = $('#lista'); l.innerHTML = '';
    const fila = (ic, nm, sz, fn) => {
      const el = document.createElement('div'); el.className = 'it';
      el.innerHTML = '<span class="ic"></span><span class="nm"></span><span class="sz"></span>';
      el.children[0].textContent = ic; el.children[1].textContent = nm; el.children[2].textContent = sz; el.onclick = fn; l.appendChild(el);
    };
    if (d.parent) fila('⬆️', '..', '', () => cargarDir(d.parent));
    const sep = d.path.includes('\\') ? '\\' : '/';
    d.items.forEach(it => {
      const full = d.path.replace(/[\\/]$/, '') + sep + it.n;
      if (it.d) fila('📁', it.n, '', () => cargarDir(full));
      else fila(icono(it.n), it.n, fmtTam(it.s), () => accionArchivo(full, it));
    });
    if (!d.items.length) l.innerHTML = '<div class="it muted">Carpeta vacía</div>';
  } catch (e) { if (String(e.message) !== '401') toast('No pude abrir la carpeta: ' + e.message, 3500); }
}

async function accionArchivo(full, it) {
  const q = await modal(it.n, fmtTam(it.s), [
    { t: '⬇︎ Descargar al celular', v: 'bajar', clase: 'acento' },
    { t: '🖥 Abrir en la laptop', v: 'abrir' },
    { t: 'Cancelar', v: null }]);
  if (q === 'bajar') {
    try {
      const r = await api('/api/ticket', { method: 'POST', body: JSON.stringify({ path: full }) });
      const { url } = await r.json();
      const a = document.createElement('a'); a.href = url; a.download = it.n; document.body.appendChild(a); a.click(); a.remove();
      toast('Descargando…');
    } catch (e) { toast('Error: ' + e.message, 3500); }
  } else if (q === 'abrir') {
    try { await api('/api/abrir', { method: 'POST', body: JSON.stringify({ path: full }) }); toast('Abierto en la laptop'); } catch (e) { toast('Error: ' + e.message, 3500); }
  }
}

$('#bSubir').onclick = () => $('#fileIn').click();
$('#fileIn').onchange = e => {
  const fs = [...e.target.files]; if (!fs.length) return;
  const fd = new FormData(); fs.forEach(f => fd.append('file', f, f.name));
  const x = new XMLHttpRequest();
  x.open('POST', '/api/subir?' + new URLSearchParams({ dir: S.dir || '' }));
  x.setRequestHeader('Authorization', 'Bearer ' + token);
  x.upload.onprogress = ev => { if (ev.lengthComputable) toast(`Subiendo… ${Math.round(ev.loaded / ev.total * 100)}%`, 8000); };
  x.onload = () => { if (x.status === 200) { toast('✓ ' + fs.length + ' archivo(s) subido(s)'); cargarDir(); } else toast('Error al subir (' + x.status + ')', 3500); };
  x.onerror = () => toast('Error de red al subir', 3500);
  x.send(fd); e.target.value = '';
};
$('#bOcultos').onclick = e => { S.ocultos = !S.ocultos; e.currentTarget.classList.toggle('on', S.ocultos); cargarDir(); };
$('#bRefrescar').onclick = () => cargarDir();

/* ───────────── pestañas ───────────── */
$$('#tabs button').forEach(b => (b.onclick = () => {
  S.tab = b.dataset.tab;
  $$('#tabs button').forEach(x => x.classList.toggle('on', x === b));
  $$('.tab').forEach(t => t.classList.toggle('on', t.id === 'tab-' + S.tab));
  if (S.tab === 'pantalla') requestAnimationFrame(() => ajustarVista(vista.z === 1));
  if (S.tab === 'archivos' && S.ok && !S.dir) cargarDir();
  actualizarStream();
}));

/* ───────────── arranque ───────────── */
async function iniciar() {
  token = leerToken();
  const mc = location.hash.match(/[#&]c=([^&]+)/);
  if (mc) await vincular(decodeURIComponent(mc[1])); // llegó por el QR
  pintarModo(); pintarCal(); fijarManifest();
  try { navigator.storage && navigator.storage.persist && navigator.storage.persist(); } catch {}
  $('#bAviso').onclick = () => { $('#aviso').hidden = true; S.avisoOculto = true; };
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  conectar();
}
iniciar();
