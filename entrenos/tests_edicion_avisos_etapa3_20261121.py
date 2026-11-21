"""Etapa 3: edición coherente (EA-8), error superior (EA-2), propuesta que cambia (EA-7),
tarjeta «Hoy» (EA-11) y texto de progresión (EA-10)."""
import os
import re

from django.test import TestCase

from entrenos import tests_estado_borrador_20261121 as _mod
from entrenos.tests_modo_reducido_navegador_20261121 import _Preparacion

_PLAYWRIGHT = _mod._PLAYWRIGHT


class _H:
    B = _mod.EstadoBorradorEnNavegador


class _Base:
    _abrir = _H.B._abrir
    _ir = _H.B._ir
    ev = _H.B.ev
    _guardar_serie = _H.B._guardar_serie
    _con_navegador = _H.B._con_navegador

    def _captura(self, nombre):
        d = os.environ.get('CAPTURAS_MODO_REDUCIDO')
        if d:
            os.makedirs(d, exist_ok=True)
            self.page.screenshot(path=os.path.join(d, nombre + '.png'))


class EdicionYAvisosEnDiaNormal(_Base, TestCase):
    def setUp(self):
        _H.B.setUp(self)

    def test_texto_de_progresion_sale_del_rpe_objetivo(self):
        textos = re.findall(r'Para al llegar a \d+ reps o a RPE ([\d,]+), lo que llegue antes\. '
                            r'Luego apunta el RPE real\. Si llegas al tope con RPE ([\d,]+) o menos', self.html)
        self.assertTrue(textos, 'no se encontró el texto de parada en la página')
        for obj, sube in textos:
            self.assertEqual(float(sube.replace(',', '.')), float(obj.replace(',', '.')) - 1, (obj, sube))

    def test_error_superior_se_limpia_al_guardar_y_al_cambiar_de_ejercicio(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            r = self.ev("""()=>{const f=cards[0].dataset.formId;
              guardarSeriePanel(f,1,parseInt(cards[0].dataset.totalSets));   // sin RPE
              const fb=document.getElementById('session-feedback');
              return {visible:!fb.hidden&&fb.textContent.length>0}}""")
            self.assertTrue(r['visible'])
            r = self.ev("""()=>{const f=cards[0].dataset.formId;
              document.getElementById('rpe-hid-'+f+'-1').value=8;
              guardarSeriePanel(f,1,parseInt(cards[0].dataset.totalSets));
              return {oculto:document.getElementById('session-feedback').hidden}}""")
            self.assertTrue(r['oculto'])
            self.ev("()=>{mostrarErrorSesion('x',null);irEjercicio(1)}")
            self.assertTrue(self.ev("()=>document.getElementById('session-feedback').hidden"))
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)

    def test_propuesta_cambiada_deja_de_afirmar_lo_propuesto_y_vuelve_si_se_restaura(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self._guardar_serie(0, 1, rpe=6)
            r = self.ev("""()=>{const f=cards[0].dataset.formId;
              const b=document.getElementById('sugerencia-'+f+'-2');
              const p=document.getElementById('peso-'+f+'-2');
              const orig=b.textContent; const pesoOrig=p.value;
              p.value=String(parseFloat(p.value)+5); p.dispatchEvent(new Event('input',{bubbles:true}));
              return {orig, pesoOrig}}""")
            self.page.wait_for_timeout(100)
            r2 = self.ev("""()=>{const f=cards[0].dataset.formId;
              const b=document.getElementById('sugerencia-'+f+'-2'); return b.textContent}""")
            self.assertIn('Has cambiado la propuesta', r2)
            r3 = self.ev("""(po)=>{const f=cards[0].dataset.formId;
              const p=document.getElementById('peso-'+f+'-2'); p.value=po;
              p.dispatchEvent(new Event('input',{bubbles:true}));
              return new Promise(res=>setTimeout(()=>res(document.getElementById('sugerencia-'+f+'-2').textContent),50))}""",
                         r['pesoOrig'])
            self.assertEqual(r3, r['orig'])

        self._con_navegador(caso)

    def test_corregir_una_serie_regenera_el_bloque_de_ejercicio_terminado(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            info = self.ev("()=>({fid:cards[0].dataset.formId,t:parseInt(cards[0].dataset.totalSets)})")
            for sn in range(1, info['t'] + 1):
                self._guardar_serie(0, sn, rpe=8)
                self.ev('(f)=>saltarDescanso(f)', info['fid'])
            antes = self.ev("""(f)=>{const d=document.querySelectorAll('#card-'+f+' [data-ej-done]');
                                    return {n:d.length, txt:d[0]?.textContent||''}}""", info['fid'])
            self.assertEqual(antes['n'], 1)
            # Corrige la serie 1 con otro peso.
            self.ev("""(f)=>{editarSeriePanel(f,1,parseInt(cards[0].dataset.totalSets));
              const p=document.getElementById('peso-'+f+'-1'); p.value='200';
              document.getElementById('rpe-hid-'+f+'-1').value=8;
              guardarSeriePanel(f,1,parseInt(cards[0].dataset.totalSets));}""", info['fid'])
            durante = self.ev("(f)=>document.querySelectorAll('#card-'+f+' [data-ej-done]').length", info['fid'])
            self.assertEqual(durante, 0, 'el bloque viejo no debe seguir enseñando datos anteriores')
            self.ev('(f)=>saltarDescanso(f)', info['fid'])
            despues = self.ev("""(f)=>{const d=document.querySelectorAll('#card-'+f+' [data-ej-done]');
                                      return {n:d.length, txt:d[0]?.textContent||''}}""", info['fid'])
            self.assertEqual(despues['n'], 1)
            self.assertNotEqual(despues['txt'], antes['txt'])
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)

    def test_sin_avisos_de_contexto_no_hay_tarjeta_hoy(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self.assertEqual(self.ev("()=>document.getElementById('hoy-card')?'si':'no'"), 'no')

        self._con_navegador(caso)


class HoyEnVersionReducida(_Preparacion, _Base, TestCase):
    def setUp(self):
        _Preparacion.setUp(self)

    def test_los_avisos_se_agrupan_y_peso_reps_rpe_guardar_quedan_en_la_primera_pantalla(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            r = self.ev("""()=>{const c=document.getElementById('hoy-card');
              const f=cards[0].dataset.formId;
              const g=document.getElementById('btn-guardar-'+f+'-1')||document.querySelector('#reg-'+f+'-1 .btn-guardar-serie, #reg-'+f+'-1 button[onclick*="guardarSeriePanel"]');
              const rect=el=>{const b=el.getBoundingClientRect();return {top:b.top,bottom:b.bottom}};
              return {hay:!!c, visible:c&&!c.hidden, resumen:document.getElementById('hoy-res').textContent,
                      abierto:c.open, peso:rect(document.getElementById('peso-'+f+'-1')),
                      guardar:g?rect(g):null, alto:innerHeight}}""")
            self._captura('5_hoy_reducida_inicio')
            self.assertTrue(r['hay'] and r['visible'])
            self.assertIn('Versión reducida', r['resumen'])
            self.assertLessEqual(r['peso']['bottom'], r['alto'] * 1.6)  # alcanzable con un gesto de scroll
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)
