"""Etapa 3: recorrido del modo reducido con opcionales en Chromium real.

Se omite si Playwright no esta instalado. Capturas opcionales en la carpeta que
indique la variable de entorno CAPTURAS_MODO_REDUCIDO.
"""
import os
from urllib.parse import parse_qs, urlparse

from django.test import TestCase

from entrenos import tests_estado_borrador_20261121 as _mod

_PLAYWRIGHT = _mod._PLAYWRIGHT


class _H:  # evita que el cargador de pruebas vuelva a ejecutar la clase base
    B = _mod.EstadoBorradorEnNavegador


if _PLAYWRIGHT:
    from playwright.sync_api import sync_playwright


class _Preparacion:
    PRINCIPALES = 2  # cuántos ejercicios son principales en la prueba

    _abrir = _H.B._abrir
    _ir = _H.B._ir
    ev = _H.B.ev
    _guardar_serie = _H.B._guardar_serie
    _con_navegador = _H.B._con_navegador

    def setUp(self):
        from unittest.mock import patch
        from django.urls import reverse
        from entrenos.tests_coherencia_sesion import CoherenciaEntrePantallas
        CoherenciaEntrePantallas.setUp(self)
        from entrenos.services.autoridad_diaria_gym_service import resolver_autoridad_diaria_gym
        with patch('entrenos.services.sesion_recomendada.obtener_sesion_recomendada_hoy',
                   side_effect=lambda *a, **k: CoherenciaEntrePantallas.decision_de_hoy(self)):
            autoridad = resolver_autoridad_diaria_gym(self.cliente, self.hoy)
            briefing = self.client.get(
                reverse('entrenos:briefing_entrenamiento', args=[self.cliente.id]),
                {'fecha': self.hoy.strftime('%Y-%m-%d'), 'decision_id': autoridad['decision_id'],
                 'modo_reducido': '1'})
            qs = {k: v[0] for k, v in parse_qs(urlparse(briefing.context['url_sesion']).query).items()}
            self.url_activo = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
            previa = self.client.get(self.url_activo, qs)
            nombres = [e['nombre'] for e in previa.context['ejercicios_planificados']]
            # Dos principales (multiarticulares) y el resto accesorios.
            with patch('entrenos.views._es_principal_hoy',
                       side_effect=lambda e, solo_pierna=False: e.get('nombre') in nombres[:self.PRINCIPALES]):
                resp = self.client.get(self.url_activo, qs)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(qs.get('modo_reducido'), '1')
        self.html = resp.content.decode('utf-8')
        self.doc_url = 'http://testserver' + self.url_activo + '?' + '&'.join(f'{k}={v}' for k, v in qs.items())
        self.red = {}

    def _captura(self, nombre):
        d = os.environ.get('CAPTURAS_MODO_REDUCIDO')
        if d:
            os.makedirs(d, exist_ok=True)
            self.page.screenshot(path=os.path.join(d, nombre + '.png'))



class ModoReducidoRecorrido(_Preparacion, TestCase):
    def test_recorrido_principal_y_cierre_sin_motivo_con_opcionales_sin_hacer(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            info = self.ev("""()=>cards.map((c,i)=>({i,fid:c.dataset.formId,t:parseInt(c.dataset.totalSets),
                 opc:esCardOpcional(c)}))""")
            principales = [c for c in info if not c['opc']]
            opcionales = [c for c in info if c['opc']]
            self.assertTrue(principales, info)
            self.assertTrue(opcionales, 'la rutina de prueba debe tener algun opcional en version reducida')
            self.assertTrue(all(p['i'] < o['i'] for p in principales for o in opcionales))
            self._captura('1_inicio')
            for p in principales:
                self.ev("(i)=>irEjercicio(i)", p['i'])
                for sn in range(1, p['t'] + 1):
                    r = self._guardar_serie(p['i'], sn)
                    self.assertEqual(r['error'], '')
                    # el descanso no debe frenar: lo saltamos si esta activo
                    self.ev('(f)=>saltarDescanso(f)', p['fid'])
            self.page.wait_for_timeout(300)
            self._captura('2_principal_hecho')
            botones = self.ev("""()=>[...document.querySelectorAll('[data-ej-done] button')].map(b=>b.textContent.trim())""")
            self.assertTrue(any('Terminar: bloque principal hecho' in b for b in botones), botones)
            self.assertTrue(any('(opcional)' in b for b in botones), botones)
            r = self.ev("""()=>{document.getElementById('btn-mostrar-resumen').click();
               const w=document.getElementById('motivo-cierre-wrap');
               return {motivoVisible:!!w&&w.style.display!=='none',
                       sub:document.getElementById('modal-resumen-subtitle').textContent,
                       titulo:document.getElementById('modal-resumen-title').textContent}}""")
            self.page.wait_for_function("()=>{const m=document.getElementById('modal-resumen');return m&&getComputedStyle(m).opacity==='1'}", timeout=3000) if self.ev("()=>!!document.getElementById('modal-resumen')") else None
            self.page.wait_for_timeout(1000)
            self._captura('3_resumen')
            self.assertFalse(r['motivoVisible'], r)
            self.assertEqual(r['titulo'], 'Revisar entrenamiento')
            self.assertIn('opcionales sin hacer', r['sub'])
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)

    def test_con_un_principal_pendiente_el_cierre_es_parcial_y_lista_lo_que_falta(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            r = self._guardar_serie(0, 1)
            self.assertEqual(r['error'], '')
            self.page.wait_for_timeout(200)
            r = self.ev("""()=>{const b=contarBloques();document.getElementById('btn-mostrar-resumen').click();
              return {faltan:b.faltan.length,titulo:document.getElementById('modal-resumen-title').textContent,
                      sub:document.getElementById('modal-resumen-subtitle').textContent}}""")
            self._captura('4_parcial')
            if r['faltan']:
                self.assertEqual(r['titulo'], 'Revisar sesión parcial')
                self.assertIn('Faltan del bloque principal', r['sub'])

        self._con_navegador(caso)


class ModoReducidoSinPrincipales(_Preparacion, TestCase):
    """Sin ningún principal: nada se muestra ni cuenta como opcional."""
    PRINCIPALES = 0
    _captura = ModoReducidoRecorrido._captura

    def test_etiquetas_contadores_y_cierre_comparten_la_clasificacion_efectiva(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')
        import re
        # Servidor: ningún campo oculto marca opcional.
        self.assertEqual(re.findall(r'name="ejercicio_\d+_opcional" value="(\d)"', self.html),
                         ['0'] * len(re.findall(r'name="ejercicio_\d+_opcional"', self.html)))
        self.assertNotIn('id="separador-opcional"', self.html)

        def caso():
            self._ir()
            r = self.ev("""()=>({
               etiquetas:[...document.querySelectorAll('.exname-toprow span')].filter(e=>e.textContent.trim()==='OPCIONAL').length,
               opc:cards.filter(esCardOpcional).length,
               b:contarBloques(), total:cards.reduce((n,c)=>n+parseInt(c.dataset.totalSets),0)})""")
            self.assertEqual(r['etiquetas'], 0)
            self.assertEqual(r['opc'], 0)
            self.assertEqual(r['b']['totalOpc'], 0)
            self.assertEqual(r['b']['total'], r['total'])
            self._guardar_serie(0, 1)
            r = self.ev("""()=>{document.getElementById('btn-mostrar-resumen').click();
               const w=document.getElementById('motivo-cierre-wrap');
               return {motivo:!!w&&w.style.display!=='none',
                       titulo:document.getElementById('modal-resumen-title').textContent}}""")
            self.assertTrue(r['motivo'], r)
            self.assertEqual(r['titulo'], 'Revisar sesión parcial')
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)
