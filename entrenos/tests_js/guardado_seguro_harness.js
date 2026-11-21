// Prueba de comportamiento del guardado seguro (bloque «GUARDADO SEGURO» de
// entrenamiento_activo.html) con un DOM y un servidor simulados.
// Uso: node guardado_seguro_harness.js <ruta a la plantilla>
const fs = require('fs');
const assert = require('assert');
const plantilla = fs.readFileSync(process.argv[2], 'utf-8');
const i = plantilla.indexOf('// ── GUARDADO SEGURO');
const j = plantilla.indexOf('// ── FIN GUARDADO SEGURO');
let codigo = plantilla.slice(i, j)
  .replace(/\{\{ cliente\.id \}\}/g, '1')
  .replace(/\{\{ fecha \}\}/g, '2026-11-21')
  .replace(/\{% url [^%]*%\}/g, '/comprobar/TOKEN_PLACEHOLDER/');

function crearEntorno(opts) {
  opts = opts || {};
  const almacen = new Map();
  const log = { redirects: [], limpiado: 0, fetches: [] };
  const elementos = {};
  function el(id) {
    if (!elementos[id]) elementos[id] = {
      id, style: {}, value: '', textContent: '', innerHTML: '', disabled: false, children: [],
      setAttribute() {}, removeAttribute() {}, addEventListener() {},
      appendChild(c) { this.children.push(c); c.parentNode = this; },
      insertBefore(c) { this.children.unshift(c); c.parentNode = this; },
      get firstChild() { return this.children[0]; },
    };
    return elementos[id];
  }
  const form = el('workout-form'); form.action = '/guardar/';
  const doc = {
    body: el('body'), documentElement: el('html'),
    getElementById: (id) => (id === 'save-acciones' && !elementos[id]) ? null : (id === 'aviso-almacen' ? (elementos[id] || null) : el(id)),
    createElement: (t) => { const e = el('creado_' + Math.random()); e.tag = t; return e; },
  };
  // 'save-acciones' y 'aviso-almacen' se crean desde el codigo: se registran al insertarse.
  const insertar = doc.body.insertBefore;
  doc.body.insertBefore = function (c) { if (c.id) elementos[c.id] = c; return insertar.call(this, c); };
  const errEl = el('save-error'); errEl.parentNode = { insertBefore(c) { elementos[c.id] = c; } };
  const contexto = {
    document: doc, window: { location: { set href(v) { log.redirects.push(v); } }, crypto: null },
    localStorage: {
      getItem: (k) => almacen.has(k) ? almacen.get(k) : null,
      setItem: (k, v) => { if (opts.almacenFalla) throw new Error('cuota'); almacen.set(k, v); },
      removeItem: (k) => { almacen.delete(k); },
    },
    FormData: class { constructor() { this.e = opts.formEntries().map(x => x.slice()); }
      entries() { return this.e[Symbol.iterator](); } set(k, v) { this.e = this.e.filter(x => x[0] !== k); this.e.push([k, v]); } },
    fetch: async (url, init) => { log.fetches.push({ url, init }); return opts.fetch(url, init); },
    AbortController, TextEncoder, URL, console, setTimeout, clearTimeout, Array, Set, Math, JSON, Object, Promise,
    STATE: { seriesCompletadas: {} }, STORAGE_KEY: 'entreno_activo_1_2026-11-21', _WK_KEY: 'workout_t0_1_2026-11-21',
    sincronizarSeriesConfirmadasConFormulario() {}, duracionParaGuardar: () => 50,
    limpiarCheckpoint() { log.limpiado++; almacen.delete('entreno_activo_1_2026-11-21'); },
  };
  contexto.window.localStorage = contexto.localStorage;
  const vm = require('vm');
  vm.createContext(contexto);
  vm.runInContext('var _sessionGuardada=false; var _envioCierreEnCurso=false;\n' + codigo +
    '\nthis.__api={ejecutarEnvio,comprobarSiLlego,huellaActual,SESION_TOKEN:()=>SESION_TOKEN,leerEnvios:_leerEnvios,flags:()=>({g:_sessionGuardada,e:_envioCierreEnCurso})};', contexto);
  return { api: contexto.__api, almacen, log, elementos, contexto };
}
const json = (status, obj) => ({ status, ok: status < 400, text: async () => JSON.stringify(obj), json: async () => obj });
const esperar = (ms) => new Promise(r => setTimeout(r, ms));
const base = [['fecha', '2026-11-21'], ['rutina_nombre', 'Dia'], ['ej1_peso_1', '60'], ['ej1_reps_1', '8']];
let nPruebas = 0;
async function prueba(nombre, fn) { await fn(); nPruebas++; console.log('ok - ' + nombre); }

(async () => {
  await prueba('confirmacion que coincide con lo enviado y con el borrador limpia todo y redirige', async () => {
    let entradas = base;
    const e = crearEntorno({ formEntries: () => entradas, fetch: async (u, init) => {
      const h = e.api.leerEnvios().enviadas[0];
      return json(200, { success: true, entreno_id: 7, huella: h, revision: 1 }); } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{"seriesCompletadas":{}}');
    await e.api.ejecutarEnvio(); await esperar(300);
    assert.strictEqual(e.log.redirects.join('|'), '/entrenos/cliente/1/entreno/7/cierre/');
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), false);
    assert.strictEqual(e.almacen.has('entreno_activo_token_1_2026-11-21'), false);
    assert.strictEqual(e.almacen.has('entreno_activo_envios_1_2026-11-21'), false);
  });

  await prueba('una respuesta vieja NO borra un borrador con ediciones posteriores', async () => {
    let entradas = base;
    let h1;
    const e = crearEntorno({ formEntries: () => entradas, fetch: async () => {
      h1 = e.api.leerEnvios().enviadas[0];
      entradas = base.concat([['ej1_peso_2', '65'], ['ej1_reps_2', '9']]); // el usuario edita mientras vuela
      return json(200, { success: true, entreno_id: 7, huella: h1, revision: 1 }); } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{"seriesCompletadas":{}}');
    await e.api.ejecutarEnvio(); await esperar(300);
    assert.strictEqual(e.log.redirects.length, 0);
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true, 'el borrador debe seguir');
    assert.strictEqual(e.almacen.has('entreno_activo_token_1_2026-11-21'), true);
    assert.strictEqual(e.api.leerEnvios().confirmada, h1);
    assert.match(e.elementos['save-error'].textContent, /cambiaste cosas/);
  });

  await prueba('si el servidor acepta un contenido distinto del enviado, el borrador se conserva', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () =>
      json(200, { success: true, entreno_id: 7, huella: 'f'.repeat(64), revision: 1 }) });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.ejecutarEnvio(); await esperar(300);
    assert.strictEqual(e.log.redirects.length, 0);
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true);
  });

  await prueba('sin respuesta: estado incierto, borrador intacto, boton para comprobar', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () => { throw new TypeError('Failed to fetch'); } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.ejecutarEnvio();
    assert.match(e.elementos['save-error'].textContent, /No sé si el servidor recibió/);
    assert.ok(e.elementos['save-acciones'].children.some(b => b.textContent === 'Comprobar si llegó'));
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true);
    assert.strictEqual(e.api.flags().g, false); assert.strictEqual(e.api.flags().e, false);
    assert.strictEqual(e.api.leerEnvios().enviadas.length, 1);
  });

  await prueba('respuesta que no es JSON (502) tambien es incierta, no un rechazo', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () =>
      ({ status: 502, ok: false, text: async () => '<html>Bad gateway</html>' }) });
    await e.api.ejecutarEnvio();
    assert.match(e.elementos['save-error'].textContent, /No sé si el servidor recibió/);
  });

  await prueba('un 400 con JSON es un rechazo claro y no habla de duplicados', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () => json(400, { success: false, error: 'Falta el RPE' }) });
    await e.api.ejecutarEnvio();
    assert.strictEqual(e.elementos['save-error'].textContent, 'Falta el RPE');
    assert.doesNotMatch(e.elementos['save-error'].textContent, /ya se haya guardado/);
  });

  await prueba('409: conflicto, ofrece aplicar la mia con la huella del servidor y no borra nada', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async (u, init) => {
      if (e.log.fetches.length === 1) return json(409, { success: false, conflicto: true, huella: 'a'.repeat(64), entreno_id: 9, revision: 2 });
      return json(200, { success: true, entreno_id: 9, huella: e.api.leerEnvios().enviadas[0], revision: 3 });
    } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.ejecutarEnvio();
    assert.match(e.elementos['save-error'].textContent, /No se ha sobrescrito nada/);
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true);
    const aplicar = e.elementos['save-acciones'].children.find(b => b.textContent === 'Aplicar la mía encima');
    assert.ok(aplicar);
    aplicar.listeners = null;
  });

  await prueba('el envio lleva token, huella previa como base y excluye la duracion de la huella', async () => {
    const e = crearEntorno({ formEntries: () => base.concat([['duracion_minutos_real', '50']]), fetch: async () => { throw new TypeError('x'); } });
    await e.api.ejecutarEnvio();
    const fd = e.log.fetches[0].init.body;
    const obj = Object.fromEntries(fd.e);
    assert.strictEqual(obj.sesion_token, e.api.SESION_TOKEN());
    assert.match(obj.bases_huella, /^[0-9a-f]{64}$/);
    const h = await e.api.huellaActual();
    assert.strictEqual(obj.bases_huella, h);
  });

  await prueba('comprobar: la sesion no llego -> sigue el borrador y ofrece reintentar', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () => json(200, { success: true, existe: false }) });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.comprobarSiLlego();
    assert.match(e.elementos['save-error'].textContent, /no ha recibido/);
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true);
  });

  await prueba('comprobar: llego exactamente lo que hay en el movil -> se confirma y se limpia', async () => {
    const e0 = crearEntorno({ formEntries: () => base, fetch: async () => null });
    const h = await e0.api.huellaActual();
    const e = crearEntorno({ formEntries: () => base, fetch: async (u) => {
      assert.match(u, /\/comprobar\/[A-Za-z0-9_-]{16,64}\/$/);
      return json(200, { success: true, existe: true, huella: h, entreno_id: 5, revision: 1 }); } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.comprobarSiLlego(); await esperar(300);
    assert.strictEqual(e.log.redirects.join('|'), '/entrenos/cliente/1/entreno/5/cierre/');
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), false);
  });

  await prueba('comprobar: llego una version anterior mia -> el borrador con ediciones NO se borra', async () => {
    let entradas = base;
    const e = crearEntorno({ formEntries: () => entradas, fetch: async (u, init) => {
      if (init && init.method === 'POST') throw new TypeError('lost');
      return json(200, { success: true, existe: true, huella: e.api.leerEnvios().enviadas[0], entreno_id: 5, revision: 1 }); } });
    e.almacen.set('entreno_activo_1_2026-11-21', '{}');
    await e.api.ejecutarEnvio();                  // se envia y la respuesta se pierde
    entradas = base.concat([['ej1_peso_2', '70'], ['ej1_reps_2', '6']]); // luego edita
    await e.api.comprobarSiLlego(); await esperar(300);
    assert.strictEqual(e.log.redirects.length, 0);
    assert.strictEqual(e.almacen.has('entreno_activo_1_2026-11-21'), true);
    assert.match(e.elementos['save-error'].textContent, /versión anterior/);
  });

  await prueba('comprobar: el servidor tiene algo que este movil no conoce -> conflicto, no sobrescribe', async () => {
    const e = crearEntorno({ formEntries: () => base, fetch: async () =>
      json(200, { success: true, existe: true, huella: 'b'.repeat(64), entreno_id: 5, revision: 4 }) });
    await e.api.comprobarSiLlego();
    assert.match(e.elementos['save-error'].textContent, /no conoce/);
    assert.ok(e.elementos['save-acciones'].children.some(b => b.textContent === 'Aplicar la mía encima'));
  });

  await prueba('si el almacenamiento falla se avisa de forma permanente al cargar', async () => {
    const e = crearEntorno({ almacenFalla: true, formEntries: () => base, fetch: async () => null });
    assert.ok(e.elementos['aviso-almacen'], 'debe existir el aviso');
    assert.match(e.elementos['aviso-almacen'].textContent, /no está guardando tu borrador/);
  });

  console.log(nPruebas + ' pruebas JS ok');
})().catch(err => { console.error('FALLO', err); process.exit(1); });
