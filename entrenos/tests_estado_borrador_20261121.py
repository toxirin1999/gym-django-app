"""Estado del borrador del entrenamiento activo (21-nov-2026).

El borrador conserva, ademas de las series: ejercicios pospuestos (en orden),
sustituciones con su objetivo, molestias, fallo, tope, el descanso por su hora
de fin y la propuesta de la serie siguiente. Molestias y sustituciones distinguen
entre estado local y confirmado por el servidor; un reintento no duplica.

Parte servidor: pruebas Django normales.
Parte navegador: Chromium real (Playwright); se omite si no esta instalado.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from entrenos.tests_coherencia_sesion import CoherenciaEntrePantallas

try:  # pragma: no cover - depende del entorno
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT = True
except Exception:  # pragma: no cover
    _PLAYWRIGHT = False

BASE = Path(__file__).resolve().parent
JS_ACTIVO = BASE / 'static' / 'entrenos' / 'js' / 'entrenamiento_activo.js'
TEMPLATE = BASE / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


class ServidorEventosIdempotentes(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='evt', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'E'})
        self.client.force_login(self.user)
        self.url_molestia = reverse('entrenos:api_reportar_molestia', args=[self.cliente.id])
        self.url_swap = reverse('entrenos:api_save_hot_swap', args=[self.cliente.id])

    def molestia(self, **extra):
        cuerpo = {'ejercicio_nombre': 'Sentadilla', 'zona': 'rodilla', 'severidad': 2, 'descripcion': 'pincha'}
        cuerpo.update(extra)
        return self.client.post(self.url_molestia, json.dumps(cuerpo), content_type='application/json')

    def lesiones(self):
        from hyrox.models import UserInjury
        return UserInjury.objects.filter(cliente=self.cliente)

    def test_reintento_con_el_mismo_evento_no_duplica_lesion(self):
        evento = 'abcdef0123456789abcdef'
        r1 = self.molestia(evento=evento)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(self.lesiones().count(), 1)
        self.assertFalse(r1.json()['repetido'])
        r2 = self.molestia(evento=evento)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self.lesiones().count(), 1)
        self.assertTrue(r2.json()['repetido'])
        self.assertTrue(r2.json()['lesion_creada'])

    def test_reintento_tras_escalar_no_vuelve_a_escribir(self):
        from hyrox.models import UserInjury
        self.molestia(evento='aaaaaaaa11111111', severidad=2)
        lesion = self.lesiones().get()
        antes = lesion.notas_medicas
        self.molestia(evento='bbbbbbbb22222222', severidad=3)  # escala
        lesion.refresh_from_db()
        escalada = lesion.notas_medicas
        self.assertNotEqual(antes, escalada)
        self.assertIn('[evento:bbbbbbbb22222222]', escalada)
        self.molestia(evento='bbbbbbbb22222222', severidad=3)  # reintento
        lesion.refresh_from_db()
        self.assertEqual(lesion.notas_medicas, escalada)
        self.assertEqual(UserInjury.objects.filter(cliente=self.cliente).count(), 1)

    def test_eventos_distintos_misma_zona_siguen_sin_duplicar_lesion(self):
        self.molestia(evento='cccccccc33333333')
        self.molestia(evento='dddddddd44444444')
        self.assertEqual(self.lesiones().count(), 1)

    def test_evento_invalido_se_rechaza(self):
        r = self.molestia(evento='x y;')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.lesiones().count(), 0)

    def test_sin_evento_mantiene_el_comportamiento_anterior(self):
        r = self.molestia()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.lesiones().count(), 1)
        self.assertFalse(r.json()['repetido'])

    def test_severidad_leve_no_crea_lesion_ni_con_reintento(self):
        self.molestia(evento='eeeeeeee55555555', severidad=1)
        self.molestia(evento='eeeeeeee55555555', severidad=1)
        self.assertEqual(self.lesiones().count(), 0)

    def hot_swap(self, original='Sentadilla', sustituto='Prensa', fecha='2026-11-21'):
        return self.client.post(
            self.url_swap,
            json.dumps({'original_name': original, 'substitute_name': sustituto, 'fecha': fecha}),
            content_type='application/json')

    def test_hot_swap_sin_plan_en_sesion_se_distingue_de_un_error(self):
        r = self.hot_swap()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['codigo'], 'sin_plan')

    def _plan_en_sesion(self):
        sesion = self.client.session
        sesion[f'plan_anual_{self.cliente.id}'] = json.dumps({
            'entrenos_por_fecha': {'2026-11-21': {'ejercicios': [{'nombre': 'Sentadilla'}]}}})
        sesion.save()

    def test_hot_swap_es_idempotente_ante_un_reintento(self):
        self._plan_en_sesion()
        r1 = self.hot_swap()
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()['status'], 'success')
        r2 = self.hot_swap()  # antes: 404 porque el original ya no estaba
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['repetido'])

    def test_hot_swap_con_otro_sustituto_sigue_sin_encontrar_el_original(self):
        self._plan_en_sesion()
        self.hot_swap()
        r = self.hot_swap(sustituto='Otro')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['codigo'], 'sin_original')


class PlantillaEstadoBorrador(TestCase):
    """Contrato de la plantilla: lo que no puede perderse sin que alguien lo note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = TEMPLATE.read_text(encoding='utf-8')

    def test_cerrar_el_banner_no_borra_el_borrador(self):
        m = re.search(r"aviso-recuperada.*?innerHTML=(.*?)\n", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertNotIn('removeItem(STORAGE_KEY)', m.group(1))
        self.assertIn('descartarBorrador', self.src)  # la accion explicita sigue existiendo

    def test_checkpoint_incluye_el_estado_extra(self):
        cp = self.src.split('function guardarCheckpoint()', 1)[1].split('function limpiarCheckpoint', 1)[0]
        self.assertIn('recopilarEstadoExtra()', cp)

    def test_molestia_y_sustitucion_llevan_evento(self):
        self.assertIn('evento:rec.evento', self.src.replace(' ', ''))
        self.assertIn('rec.evento=_nuevoToken()', self.src.replace(' ', ''))


class SustitucionPorLesionServidor(TestCase):
    """Las alternativas por lesion y por molestia traen lo mismo que la de maquina ocupada."""
    DESTINO = 'Low-to-High Cable Fly'
    original = 'Sentadilla Hack'

    def setUp(self):
        CoherenciaEntrePantallas.setUp(self)
        from rutinas.models import EjercicioBase
        EjercicioBase.objects.filter(nombre='Prensa de Piernas').update(
            grupo_muscular='otros', risk_tags=['flexion_rodilla_profunda'])

    def _post_real(self, nombre_url, cuerpo):
        r = self.client.post(reverse(nombre_url, args=[self.cliente.id]), json.dumps(cuerpo),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_servidor_alternativas_de_lesion_traen_datos_de_sustitucion_y_respetan_restricciones(self):
        datos = self._post_real('entrenos:api_alternativas_lesion', {
            'ejercicio_nombre': self.original, 'grupo_muscular': 'otros',
            'tags_restringidos': ['flexion_rodilla_profunda'], 'fase_lesion': 'lesion_activa',
            'rango': '12-15', 'rpe_objetivo': 8})
        nombres = [a['nombre'] for a in datos['alternativas']]
        self.assertNotIn('Prensa de Piernas', nombres)      # tiene la etiqueta restringida
        self.assertNotIn(self.original, nombres)
        alt = datos['alternativas'][nombres.index(self.DESTINO)]
        for clave in ('ultima', 'tipo_progresion', 'usa_peso', 'pr_peso', 'peso_hueco_kg', 'peso_historico_kg'):
            self.assertIn(clave, alt)
        self.assertTrue(alt['usa_peso'])
        self.assertGreater(alt['peso_hueco_kg'], 0)
        self.assertIn('peso_hueco_motivo', alt)

    def test_servidor_alternativas_de_molestia_traen_los_mismos_datos(self):
        with patch('analytics.planificador_helms.utils.helpers.obtener_sustituto_en_caliente',
                   return_value={'nombre': self.DESTINO, 'patron': 'x'}):
            datos = self._post_real('entrenos:api_reportar_molestia', {
                'ejercicio_nombre': self.original, 'zona': 'rodilla', 'severidad': 2,
                'solo_alternativas': True, 'rango': '12-15', 'rpe_objetivo': 8})
        from hyrox.models import UserInjury
        self.assertEqual(UserInjury.objects.filter(cliente=self.cliente).count(), 0)
        alt = datos['alternativas'][0]
        self.assertEqual(alt['nombre'], self.DESTINO)
        self.assertTrue(alt['usa_peso'])
        self.assertGreater(alt['peso_hueco_kg'], 0)
        self.assertIn('peso_anterior', alt)


# ───────────────────────── Navegador real ─────────────────────────

@__import__('unittest').skipUnless(_PLAYWRIGHT, 'Playwright no esta instalado')
class EstadoBorradorEnNavegador(TestCase):
    def setUp(self):
        CoherenciaEntrePantallas.setUp(self)
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym
        with patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
                   side_effect=lambda *a, **k: CoherenciaEntrePantallas.decision_de_hoy(self)):
            autoridad = resolver_autoridad_diaria_gym(self.cliente, self.hoy)
            fecha = self.hoy.strftime('%Y-%m-%d')
            briefing = self.client.get(
                reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id]),
                {'fecha': fecha, 'decision_id': autoridad['decision_id']})
            qs = {k: v[0] for k, v in parse_qs(urlparse(briefing.context['url_sesion']).query).items()}
            self.url_activo = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
            resp = self.client.get(self.url_activo, qs)
        self.assertEqual(resp.status_code, 200)
        self.html = resp.content.decode('utf-8')
        self.doc_url = 'http://testserver' + self.url_activo + '?' + '&'.join(f'{k}={v[0]}' for k, v in
                                                                             parse_qs(urlparse(briefing.context['url_sesion']).query).items())
        self.red = {}

    # -- utilidades --------------------------------------------------------
    def _abrir(self, pw):
        self.browser = pw.chromium.launch()
        ctx = self.browser.new_context(viewport={'width': 375, 'height': 800})
        self.llamadas = []
        self.page = ctx.new_page()
        self.errores_js = []
        self.page.on('pageerror', lambda e: self.errores_js.append(str(e)))
        self.consola = []
        self.page.on('console', lambda m: self.consola.append(m.text) if m.type in ('warning', 'error') else None)
        self.page.on('dialog', lambda d: d.accept())

        def manejar(route):
            req = route.request
            url = req.url
            if url.startswith(self.doc_url.split('?')[0]) and req.method == 'GET':
                return route.fulfill(status=200, content_type='text/html; charset=utf-8', body=self.html)
            if url.endswith('/static/entrenos/js/entrenamiento_activo.js'):
                return route.fulfill(status=200, content_type='application/javascript',
                                     body=JS_ACTIVO.read_text(encoding='utf-8'))
            if req.method == 'POST':
                cuerpo = req.post_data or ''
                try:
                    cuerpo = json.loads(cuerpo)
                except Exception:
                    pass
                clave = ('molestia' if 'reportar-molestia' in url else 'hotswap' if 'save-hot-swap' in url
                         else 'alt_lesion' if 'alternativas-lesion' in url else 'otro')
                self.llamadas.append((clave, cuerpo))
                respuesta = self.red.get(clave, (200, {'status': 'ok', 'mensaje': 'ok', 'alternativas': []}))
                estado, datos = respuesta(cuerpo) if callable(respuesta) else respuesta
                if estado == 'caida':
                    return route.abort()
                return route.fulfill(status=estado, content_type='application/json', body=json.dumps(datos))
            return route.fulfill(status=200, content_type='text/plain', body='')

        ctx.route('**/*', manejar)
        return ctx

    def _ir(self):
        self.page.goto(self.doc_url)
        self.page.wait_for_function('typeof STATE!=="undefined" && typeof ESTADO!=="undefined"')
        self.page.wait_for_timeout(150)

    def _recargar(self):
        self.page.reload()
        self.page.wait_for_function('typeof STATE!=="undefined" && typeof ESTADO!=="undefined"')
        self.page.wait_for_timeout(250)

    def ev(self, js, arg=None):
        return self.page.evaluate(js, arg) if arg is not None else self.page.evaluate(js)

    def _guardar_serie(self, idx, sn=1, rpe=8):
        return self.ev("""([idx,sn,rpe])=>{
          const fid=cards[idx].dataset.formId, total=parseInt(cards[idx].dataset.totalSets);
          document.getElementById('rpe-hid-'+fid+'-'+sn).value=rpe;
          guardarSeriePanel(fid,sn,total);
          return {fid,total,hechas:STATE.seriesCompletadas[fid].length,
                  error:document.getElementById('session-feedback')?.textContent||''};
        }""", [idx, sn, rpe])

    def _con_navegador(self, fn):
        with sync_playwright() as pw:
            self._abrir(pw)
            try:
                fn()
            finally:
                self.browser.close()

    # -- pruebas -----------------------------------------------------------
    def test_descanso_vuelve_con_su_hora_de_fin_sin_reiniciarse(self):
        def caso():
            self._ir()
            r = self._guardar_serie(0)
            self.assertEqual(r['hechas'], 1, r['error'])
            fid = r['fid']
            fin = self.ev('(fid)=>STATE.timers[fid].endTs', fid)
            self.page.wait_for_timeout(2200)
            self._recargar()
            self.assertEqual(self.ev('(fid)=>STATE.timers[fid].endTs', fid), fin)  # misma hora de fin
            self.assertNotEqual(self.ev('(fid)=>getComputedStyle(document.getElementById("desc-"+fid)).display', fid), 'none')
            self.assertEqual(self.ev('(fid)=>getComputedStyle(document.getElementById("registro-"+fid)).display', fid), 'none')
            restante = self.ev('(fid)=>STATE.timers[fid].seg', fid)
            esperado = round((fin - self.ev('Date.now()')) / 1000)
            self.assertLessEqual(abs(restante - esperado), 2)
            self.assertNotIn('TERMINÓ', self.ev('(fid)=>document.getElementById("pd-de-"+fid).textContent', fid))
            self.assertEqual(self.errores_js, [])
        self._con_navegador(caso)

    def test_descanso_terminado_mientras_estabas_fuera_lo_indica_y_no_salta_solo(self):
        def caso():
            self._ir()
            r = self._guardar_serie(0)
            fid = r['fid']
            self.ev("""(fid)=>{const k=STORAGE_KEY,d=JSON.parse(localStorage.getItem(k));
              d.descansos[fid].endTs=Date.now()-120000;localStorage.setItem(k,JSON.stringify(d));}""", fid)
            self.ev('()=>{window.__sinGuardar=true}')
            self.page.evaluate("()=>{window.addEventListener('beforeunload',()=>{},{once:true})}")
            self._recargar()
            self.assertEqual(self.ev('(fid)=>document.getElementById("pd-de-"+fid).textContent', fid), 'TERMINÓ')
            self.assertIn('SEGUIR', self.ev('(fid)=>document.getElementById("btn-saltar-"+fid).textContent', fid))
            self.page.wait_for_timeout(1500)  # no avanza solo a la serie siguiente
            self.assertNotEqual(self.ev('(fid)=>getComputedStyle(document.getElementById("desc-"+fid)).display', fid), 'none')
            self.assertEqual(self.ev('(fid)=>STATE.timers[fid].interval', fid), None)
            # El usuario continua: ahora si aparece la serie siguiente.
            self.ev('(fid)=>saltarDescanso(fid)', fid)
            self.assertNotEqual(self.ev('(fid)=>getComputedStyle(document.getElementById("reg-"+fid+"-2")).display', fid), 'none')
        self._con_navegador(caso)

    def test_pospuestos_ordenados_sobreviven_y_se_recuperan_en_ese_orden(self):
        def caso():
            self._ir()
            ids = self.ev('()=>cards.map(c=>c.dataset.formId)')
            self.ev('(f)=>dejarParaDespues(f)', ids[0])        # ejercicio 0 -> va al 1
            self.ev('(f)=>dejarParaDespues(f)', ids[1])        # ejercicio 1 -> va al 2
            self.assertEqual(self.ev('()=>ESTADO.pospuestos.slice()'), [ids[0], ids[1]])
            self._recargar()
            self.assertEqual(self.ev('()=>ESTADO.pospuestos.slice()'), [ids[0], ids[1]])
            self.assertFalse(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            chips = self.ev('()=>[...document.querySelectorAll("#barra-pendientes .bp-chip")].map(b=>b.textContent)')
            self.assertEqual(len(chips), 2)
            self.assertTrue(chips[0].startswith('1 · ') and chips[1].startswith('2 · '))
            # Con todo lo demas hecho, el siguiente pendiente es el primer pospuesto.
            self.ev("""(ids)=>{ids.slice(2).forEach((f,i)=>{const c=document.getElementById('card-'+f);
              STATE.seriesCompletadas[f]=Array.from({length:parseInt(c.dataset.totalSets)},()=>({peso:10,reps:10,rpe:8}));});
              STATE.ejActual=2;}""", ids)
            self.assertEqual(self.ev('()=>siguientePendiente()'), 0)
            # Un ejercicio terminado deja la lista.
            self.ev("""(f)=>{const c=document.getElementById('card-'+f);
              STATE.seriesCompletadas[f]=Array.from({length:parseInt(c.dataset.totalSets)},()=>({peso:10,reps:10,rpe:8}));
              guardarCheckpoint();}""", ids[0])
            self.assertEqual(self.ev('()=>ESTADO.pospuestos.slice()'), [ids[1]])
        self._con_navegador(caso)

    def _sustituir(self, fid, nombre='Press Nuevo'):
        return self.ev("""([fid,nombre])=>{
          const original=document.querySelector('#card-'+fid+' .cyber-ejercicio-nombre').textContent.trim();
          _swapFormId=fid;_swapNombreOriginal=original;
          confirmarSwap(nombre,40,'40 kg × 10',10,{usa_peso:true,tipo_progresion:'peso_reps',pr_peso:50});
          return original;}""", [fid, nombre])

    def test_sustitucion_con_objetivo_sobrevive_y_distingue_local_de_confirmada(self):
        def caso():
            self.red['hotswap'] = (404, {'status': 'error', 'codigo': 'sin_plan', 'message': 'x'})
            self._ir()
            fid = self.ev('()=>cards[1].dataset.formId')
            original = self._sustituir(fid)
            self.page.wait_for_timeout(200)
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', fid), 'local')  # sin plan en sesion: viaja con el guardado
            self.assertTrue(self.ev('()=>document.getElementById("barra-pendientes").hidden'))  # nada que reintentar
            self._recargar()
            self.assertEqual(self.ev('(f)=>document.querySelector("#card-"+f+" .cyber-ejercicio-nombre").textContent.trim()', fid), 'Press Nuevo')
            self.assertEqual(self.ev('(f)=>document.querySelector("input[name=\\""+f+"_nombre\\"]").value', fid), 'Press Nuevo')
            self.assertEqual(self.ev('(f)=>document.querySelector("input[name=\\""+f+"_sustituye_a\\"]").value', fid), original)
            objetivo = self.ev('(f)=>document.querySelector("input[name=\\""+f+"_objetivo_sustituto\\"]").value', fid)
            self.assertIn('hereda_de', objetivo)
            self.assertEqual(self.ev('(f)=>document.getElementById("peso-"+f+"-1").value', fid), '40')
            self.assertEqual(self.errores_js, [])
        self._con_navegador(caso)

    def test_sustitucion_con_error_queda_visible_y_el_reintento_la_confirma(self):
        def caso():
            self.red['hotswap'] = (500, {'status': 'error', 'message': 'se cayo'})
            self._ir()
            fid = self.ev('()=>cards[1].dataset.formId')
            self._sustituir(fid)
            self.page.wait_for_timeout(250)
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', fid), 'error')
            self.assertFalse(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            self._recargar()  # el error sigue ahi tras recuperar la sesion
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', fid), 'error')
            self.assertIn('no se pudo confirmar', self.ev('()=>document.getElementById("barra-pendientes").textContent'))
            self.red['hotswap'] = (200, {'status': 'success'})
            self.page.click('#barra-pendientes .bp-accion .bp-chip')
            self.page.wait_for_timeout(300)
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', fid), 'confirmado')
            self.assertTrue(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            eventos = {c[1]['evento'] for c in self.llamadas if c[0] == 'hotswap'}
            self.assertEqual(len(eventos), 1)  # el reintento reutiliza el mismo evento
        self._con_navegador(caso)

    def _molestia(self, fid, zona='rodilla', sev=2):
        self.ev("""([fid,zona,sev])=>{
          MOL={fid:fid,ejNombre:'X',ejOriginal:'X',zona:zona,severidad:sev};
          document.getElementById('mol-desc-input').value='pincha';
          confirmarMolestia();}""", [fid, zona, sev])

    def test_molestia_fallida_se_ve_se_conserva_y_el_reintento_no_cambia_el_evento(self):
        def caso():
            self.red['molestia'] = ('caida', None)
            self._ir()
            fid = self.ev('()=>cards[0].dataset.formId')
            self._molestia(fid)
            self.page.wait_for_timeout(300)
            self.assertEqual(self.ev('()=>ESTADO.molestias[0].estado'), 'error')
            self.assertIn('sin confirmar', self.ev('(f)=>document.getElementById("mol-btn-"+f).textContent', fid))
            self.assertFalse(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            evento = self.ev('()=>ESTADO.molestias[0].evento')
            self._recargar()
            self.assertEqual(self.ev('()=>ESTADO.molestias.length'), 1)
            self.assertEqual(self.ev('()=>ESTADO.molestias[0].estado'), 'error')
            self.assertEqual(self.ev('(f)=>document.getElementById("mol-zona-"+f).value', fid), 'rodilla')
            self.assertEqual(self.ev('(f)=>document.getElementById("mol-rep-"+f).value', fid), 'true')
            self.red['molestia'] = (200, {'status': 'ok', 'mensaje': 'ok', 'alternativas': []})
            self.page.click('#barra-pendientes .bp-accion .bp-chip')
            self.page.wait_for_timeout(300)
            self.assertEqual(self.ev('()=>ESTADO.molestias[0].estado'), 'confirmado')
            self.assertNotIn('sin confirmar', self.ev('(f)=>document.getElementById("mol-btn-"+f).textContent', fid))
            self.assertTrue(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            enviados = [c[1]['evento'] for c in self.llamadas if c[0] == 'molestia']
            # El primer envio cayo en la red y el reintento reutiliza el mismo evento:
            # asi el servidor no puede crear dos lesiones.
            self.assertEqual(enviados, [evento, evento])
        self._con_navegador(caso)

    # -- Sustitucion por lesion y por molestia: recorrido completo -----------
    # Las respuestas del servidor son las de las vistas reales de Django (calculadas
    # antes de abrir el navegador, con el historial del cliente); el navegador las usa
    # como si llegaran por red. Lo que se comprueba aqui es lo que hace el movil con ellas.
    DESTINO = 'Low-to-High Cable Fly'

    def _post_real(self, nombre_url, cuerpo):
        r = self.client.post(reverse(nombre_url, args=[self.cliente.id]), json.dumps(cuerpo),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _preparar_lesion(self):
        from rutinas.models import EjercicioBase
        EjercicioBase.objects.filter(nombre='Prensa de Piernas').update(
            grupo_muscular='otros', risk_tags=['flexion_rodilla_profunda'])
        # Primera tarjeta del plan (la prueba lo comprueba en el navegador).
        self.original = 'Sentadilla Hack'

    def _comprobar_sustitucion_aplicada(self, fid, original, alt, via):
        nombre_tarjeta = self.ev('(f)=>document.querySelector("#card-"+f+" .cyber-ejercicio-nombre").textContent.trim()', fid)
        self.assertEqual(nombre_tarjeta, alt['nombre'])
        self.assertEqual(self.ev('(f)=>document.querySelector("input[name=\\""+f+"_nombre\\"]").value', fid), alt['nombre'])
        self.assertEqual(self.ev('(f)=>document.querySelector("input[name=\\""+f+"_sustituye_a\\"]").value', fid), original)
        objetivo = json.loads(self.ev('(f)=>document.querySelector("input[name=\\""+f+"_objetivo_sustituto\\"]").value', fid))
        self.assertEqual(objetivo.get('hereda_de'), original)
        self.assertIn('Objetivo del hueco de ' + original,
                      self.ev('(f)=>document.querySelector("#card-"+f+" .sa-obj-heredado").textContent', fid))
        peso = alt.get('peso_hueco_kg') or alt.get('peso_historico_kg') or 0
        self.assertGreater(peso, 0)
        self.assertEqual(float(self.ev('(f)=>document.getElementById("peso-"+f+"-1").value', fid)), float(peso))
        rec = self.ev('(f)=>ESTADO.sustituciones[f]', fid)
        self.assertEqual(rec['via'], via)
        self.assertEqual(rec['sustituyeA'], original)

    def _tarjeta_original(self):
        fid = self.ev('()=>cards[0].dataset.formId')
        original = self.ev('(f)=>document.querySelector("#card-"+f+" .cyber-ejercicio-nombre").textContent.trim()', fid)
        self.assertEqual(original, self.original)
        return fid, original

    def test_alerta_de_lesion_aplica_la_sustitucion_completa_y_sobrevive(self):
        self._preparar_lesion()
        respuesta = self._post_real('entrenos:api_alternativas_lesion', {
            'ejercicio_nombre': self.original, 'grupo_muscular': 'otros',
            'tags_restringidos': ['flexion_rodilla_profunda'], 'fase_lesion': 'lesion_activa'})
        self.red['alt_lesion'] = (200, respuesta)
        self.red['hotswap'] = (200, {'status': 'success'})

        def caso():
            self._ir()
            fid, original = self._tarjeta_original()
            self.ev('([f,n])=>abrirAlternativasLesion(n,"otros","flexion_rodilla_profunda","lesion_activa",f)', [fid, original])
            self.page.wait_for_selector('#alt-lesion-lista button[data-alt-lesion]')
            lista = self.ev('()=>_altLesionLista')
            nombres = [a['nombre'] for a in lista]
            idx = nombres.index(self.DESTINO)
            alt = lista[idx]
            self.page.click(f'#alt-lesion-lista button[data-alt-lesion="{idx}"]')
            self.page.wait_for_timeout(250)
            self.assertEqual(self.ev('()=>document.getElementById("modal-alt-lesion-overlay").style.display'), 'none')
            self._comprobar_sustitucion_aplicada(fid, original, alt, 'lesion')
            envio = [c[1] for c in self.llamadas if c[0] == 'hotswap']
            self.assertEqual((envio[0]['original_name'], envio[0]['substitute_name']), (original, self.DESTINO))
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', fid), 'confirmado')
            self._recargar()
            self._comprobar_sustitucion_aplicada(fid, original, alt, 'lesion')
            self.assertEqual(self.errores_js, [])
        self._con_navegador(caso)

    def test_alerta_de_lesion_sin_respuesta_muestra_error_y_permite_reintentar(self):
        self._preparar_lesion()
        buena = self._post_real('entrenos:api_alternativas_lesion', {
            'ejercicio_nombre': self.original, 'grupo_muscular': 'otros',
            'tags_restringidos': ['flexion_rodilla_profunda'], 'fase_lesion': 'lesion_activa'})
        self.red['alt_lesion'] = (500, {'status': 'error'})

        def caso():
            self._ir()
            fid, original = self._tarjeta_original()
            self.ev('([f,n])=>abrirAlternativasLesion(n,"otros","flexion_rodilla_profunda","lesion_activa",f)', [fid, original])
            self.page.wait_for_selector('#alt-lesion-lista [role=alert]')
            self.red['alt_lesion'] = (200, buena)
            self.page.click('#alt-lesion-lista [role=alert] button')
            self.page.wait_for_selector('#alt-lesion-lista button[data-alt-lesion]')
            self.assertGreater(len(self.ev('()=>_altLesionLista')), 0)
        self._con_navegador(caso)

    def test_alternativa_de_molestia_conserva_sustituye_a_objetivo_y_un_solo_evento(self):
        self._preparar_lesion()
        with patch('analytics.planificador_helms.utils.helpers.obtener_sustituto_en_caliente',
                   return_value={'nombre': self.DESTINO, 'patron': 'x'}):
            buscar = self._post_real('entrenos:api_reportar_molestia', {
                'ejercicio_nombre': self.original, 'zona': 'rodilla', 'severidad': 2, 'solo_alternativas': True})
        self.red['molestia'] = lambda cuerpo: (200, buscar if cuerpo.get('solo_alternativas')
                                                else {'status': 'ok', 'lesion_creada': True, 'alternativas': []})

        def caso():
            self._ir()
            fid, original = self._tarjeta_original()
            self.ev('([f,n])=>{abrirModalMolestia(f,n);MOL.zona="rodilla";MOL.severidad=2;buscarAlternativas();}', [fid, original])
            self.page.wait_for_selector('#mol-alt-lista .mol-alt-item')
            alt = self.ev('()=>MOL.alternativas[0]')
            self.assertEqual(alt['nombre'], self.DESTINO)
            self.assertEqual([c for c in self.llamadas if c[0] == 'molestia' and not c[1].get('solo_alternativas')], [])
            self.page.wait_for_timeout(600)
            self.assertTrue(self.ev('()=>{const c=document.querySelector(".mol-zona-chip");const r=c.getBoundingClientRect();return c.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'),
                            'el modal de molestia debe recibir toques')
            self.page.click('#mol-alt-lista .mol-alt-item')
            self.page.wait_for_timeout(400)
            self._comprobar_sustitucion_aplicada(fid, original, alt, 'molestia')
            creaciones = [c[1] for c in self.llamadas if c[0] == 'molestia' and not c[1].get('solo_alternativas')]
            self.assertEqual(len(creaciones), 1)
            self.assertEqual(creaciones[0]['ejercicio_nombre'], original)   # bajo el ejercicio que molesto
            self.assertTrue(creaciones[0]['evento'])
            self.assertEqual(self.ev('()=>ESTADO.molestias[0].estado'), 'confirmado')
            self._recargar()
            self._comprobar_sustitucion_aplicada(fid, original, alt, 'molestia')
            self.assertEqual(self.errores_js, [])
        self._con_navegador(caso)

    def test_fallo_y_tope_se_conservan(self):
        def caso():
            self._ir()
            fid = self.ev('()=>cards[0].dataset.formId')
            self.ev("(f)=>{falloFormId=f;seleccionarFallo('no_previsto');}", fid)
            antes = self.ev('(f)=>document.getElementById("tope-"+f).value', fid)
            if self.ev('(f)=>!!document.getElementById("tope-btn-"+f)', fid):
                self.ev('(f)=>toggleTopeMaquina(f)', fid)
            esperado_tope = self.ev('(f)=>document.getElementById("tope-"+f).value', fid)
            self._recargar()
            self.assertEqual(self.ev('(f)=>document.getElementById("fallo-"+f).value', fid), 'no_previsto')
            self.assertIn('no previsto', self.ev('(f)=>document.getElementById("fallo-btn-"+f).textContent', fid))
            self.assertEqual(self.ev('(f)=>document.getElementById("tope-"+f).value', fid), esperado_tope)
            self.assertEqual(self.errores_js, [])
        self._con_navegador(caso)

    def test_cerrar_el_banner_oculta_el_aviso_y_conserva_el_borrador(self):
        def caso():
            self._ir()
            r = self._guardar_serie(0)
            self.assertEqual(r['hechas'], 1, r['error'])
            self._recargar()
            self.assertTrue(self.ev('()=>!!document.getElementById("aviso-recuperada")'), self.consola)
            self.page.click('#aviso-recuperada button')
            self.assertFalse(self.ev('()=>!!document.getElementById("aviso-recuperada")'))
            self.assertIsNotNone(self.ev('()=>localStorage.getItem(STORAGE_KEY)'))
            self._recargar()  # sigue recuperandose la misma sesion
            self.assertEqual(self.ev('(f)=>STATE.seriesCompletadas[f].length', r['fid']), 1)
        self._con_navegador(caso)

    def test_propuesta_de_la_serie_siguiente_vuelve_igual(self):
        def caso():
            self._ir()
            r = self._guardar_serie(0, rpe=6)  # margen: propone subir
            self.assertEqual(r['hechas'], 1, r['error'])
            fid = r['fid']
            leer = """(fid)=>({peso:document.getElementById('peso-'+fid+'-2').value,
                reps:document.getElementById('reps-hid-'+fid+'-2').value,
                plan:document.getElementById('peso-'+fid+'-2').dataset.planWeight,
                banner:document.getElementById('sugerencia-'+fid+'-2')?.innerHTML||'',
                bannerDisplay:document.getElementById('sugerencia-'+fid+'-2')?.style.display||'',
                guardar:document.querySelector('.btn-guardar[data-fid="'+fid+'"][data-sn="2"] .btn-guardar-txt')?.textContent||''})"""
            self.page.wait_for_timeout(150)  # el texto de Guardar se refresca en el siguiente frame
            antes = self.ev(leer, fid)
            # El usuario ya pulso «Saltar» o termino el descanso: la propuesta sigue en el borrador.
            self._recargar()
            self.page.wait_for_timeout(150)
            despues = self.ev(leer, fid)
            self.assertEqual(despues['peso'], antes['peso'])
            self.assertEqual(despues['reps'], antes['reps'])
            self.assertEqual(despues['plan'], antes['plan'])
            self.assertEqual(despues['banner'], antes['banner'])
            self.assertEqual(despues['bannerDisplay'], antes['bannerDisplay'])
            self.assertEqual(despues['guardar'], antes['guardar'])
        self._con_navegador(caso)

    def test_ejercicio_completo_recupera_su_bloque_de_cierre(self):
        def caso():
            self._ir()
            fid = self.ev('()=>cards[0].dataset.formId')
            total = self.ev('(f)=>parseInt(document.getElementById("card-"+f).dataset.totalSets)', fid)
            for sn in range(1, total + 1):
                r = self._guardar_serie(0, sn=sn)
                self.assertEqual(r['hechas'], sn, r['error'])
                if sn < total:
                    self.ev('(f)=>saltarDescanso(f)', fid)
            self.ev('(f)=>saltarDescanso(f)', fid)  # «terminar ejercicio»
            self.assertTrue(self.ev('(f)=>!!document.querySelector("#card-"+f+" [data-ej-done]")', fid), self.consola)
            self._recargar()
            self.assertTrue(self.ev('(f)=>!!document.querySelector("#card-"+f+" [data-ej-done]")', fid))
            self.assertEqual(self.ev('(f)=>document.querySelectorAll("#card-"+f+" [data-ej-done]").length', fid), 1)
        self._con_navegador(caso)
