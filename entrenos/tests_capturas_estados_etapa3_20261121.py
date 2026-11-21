"""Etapa 3: los estados de las maquetas A8–A15 en la pantalla IMPLEMENTADA (Chromium, 375 px).

Cada prueba lleva la pantalla real al estado y comprueba que está; si la variable
CAPTURAS_MODO_REDUCIDO apunta a una carpeta, además guarda la captura (100 % y 130 %).
"""
import os

from django.test import TestCase

from entrenos import tests_estado_borrador_20261121 as _mod
from entrenos.tests_modo_reducido_navegador_20261121 import _Preparacion

_PLAYWRIGHT = _mod._PLAYWRIGHT


class _H:
    B = _mod.EstadoBorradorEnNavegador


class _Comun:
    _abrir = _H.B._abrir
    _ir = _H.B._ir
    _recargar = _H.B._recargar
    ev = _H.B.ev
    _guardar_serie = _H.B._guardar_serie
    _con_navegador = _H.B._con_navegador
    _sustituir = _H.B._sustituir

    def _foto(self, nombre, zoom130=True, pantalla_completa=False):
        d = os.environ.get('CAPTURAS_MODO_REDUCIDO')
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        self.page.evaluate("()=>{document.documentElement.style.zoom=''}")
        self.page.wait_for_timeout(250)
        self.page.screenshot(path=os.path.join(d, nombre + '_375.png'), full_page=pantalla_completa)
        if zoom130:
            self.page.evaluate("()=>{document.documentElement.style.zoom='1.3'}")
            self.page.wait_for_timeout(250)
            self.page.screenshot(path=os.path.join(d, nombre + '_130.png'), full_page=pantalla_completa)
            self.page.evaluate("()=>{document.documentElement.style.zoom=''}")


class EstadosDiaNormal(_Comun, TestCase):
    def setUp(self):
        _H.B.setUp(self)

    def test_a8_pospuestos_con_lista_de_pendientes(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            ids = self.ev('()=>cards.map(c=>c.dataset.formId)')
            self.ev('(f)=>dejarParaDespues(f)', ids[0])
            self.ev('(f)=>dejarParaDespues(f)', ids[1])
            self.page.wait_for_timeout(3600)  # que pase el aviso efímero
            self.assertFalse(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            solape = self.ev("""()=>{const b=document.getElementById('barra-pendientes').getBoundingClientRect();
              const a=document.querySelector('.btn-ej-next').getBoundingClientRect();
              return !(a.bottom<=b.top||a.top>=b.bottom)}""")
            self.assertFalse(solape, 'las flechas de navegación no deben tapar la barra de pendientes')
            self.page.evaluate("()=>{document.documentElement.style.zoom='1.3'}")
            self.page.wait_for_timeout(200)
            barra = self.ev("""()=>{const s=document.querySelector('.sticky').getBoundingClientRect();
              const b=document.getElementById('btn-mostrar-resumen').getBoundingClientRect();
              return {sRight:s.right,bRight:b.right,vw:innerWidth/1.3,bLeft:b.left}}""")
            self.assertLessEqual(barra['bRight'], barra['sRight'] + 1, str(barra))
            self.assertLessEqual(barra['bLeft'], barra['bRight'] - 40, str(barra))
            self.page.evaluate("()=>{document.documentElement.style.zoom=''}")
            self._foto('A8_pospuestos')

        self._con_navegador(caso)

    def test_a9_a10_ajuste_entre_series_y_propuesta_cambiada(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self._guardar_serie(0, 1, rpe=6)
            fid = self.ev('()=>cards[0].dataset.formId')
            self.ev('(f)=>saltarDescanso(f)', fid)
            self.page.wait_for_timeout(300)
            txt = self.ev('(f)=>document.getElementById("sugerencia-"+f+"-2").textContent', fid)
            self.assertIn('Siguiente serie', txt)
            self._foto('A9_A10_ajuste')
            self.ev("""(f)=>{const p=document.getElementById('peso-'+f+'-2');
              p.value=String(parseFloat(p.value)+5);p.dispatchEvent(new Event('input',{bubbles:true}));}""", fid)
            self.page.wait_for_timeout(100)
            self.assertIn('Has cambiado la propuesta',
                          self.ev('(f)=>document.getElementById("sugerencia-"+f+"-2").textContent', fid))
            self._foto('A9_A10_ajuste_cambiado')

        self._con_navegador(caso)

    def test_a14_sustituciones_local_y_confirmada_y_a12_avisos_simultaneos(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self.red['hotswap'] = (500, {'status': 'error', 'message': 'se cayo'})
            f1 = self.ev('()=>cards[1].dataset.formId')
            self._sustituir(f1, 'Press Nuevo')
            self.page.wait_for_timeout(300)
            self.assertEqual(self.ev('(f)=>ESTADO.sustituciones[f].estado', f1), 'error')
            self.ev("()=>mostrarErrorSesion('Selecciona el RPE real antes de guardar la serie.',null)")
            self._recargar()  # además aparece «Sesión recuperada»
            self.page.wait_for_timeout(300)
            self.assertFalse(self.ev('()=>document.getElementById("barra-pendientes").hidden'))
            self._foto('A12_A14_pendiente_y_recuperada')

        self._con_navegador(caso)

    def _conflicto(self, zoom):
        def caso():
            self._ir()
            self.red['otro'] = (409, {'conflicto': True, 'huella': 'abc', 'entreno_id': 1})
            self._guardar_serie(0, 1, rpe=8)
            if zoom:
                self.page.evaluate("()=>{document.documentElement.style.zoom='1.3'}")
            # Por la interfaz real: revisar, motivo del cierre parcial y confirmar.
            self.ev("()=>document.getElementById('btn-mostrar-resumen').click()")
            self.page.wait_for_timeout(600)
            self.ev("""()=>{const m=document.getElementById('motivo-cierre');
              if(m){m.selectedIndex=Math.min(1,m.options.length-1);m.dispatchEvent(new Event('change',{bubbles:true}));}
              document.getElementById('btn-confirmar-guardar').click();}""")
            self.page.wait_for_timeout(800)
            visible = self.ev("""()=>{const t=document.body.innerText;
              return t.includes('Aplicar la mía encima')&&t.includes('Ver lo guardado')}""")
            self.assertTrue(visible)
            vista = self.ev("""()=>{const z=parseFloat(document.documentElement.style.zoom)||1;
              const e=document.getElementById('save-error').getBoundingClientRect();
              const bots=[...document.querySelectorAll('#save-acciones button')].map(b=>b.getBoundingClientRect());
              const fijo=document.getElementById('btn-confirmar-guardar').getBoundingClientRect();
              return {errTop:e.top, fijoTop:fijo.top, n:bots.length,
                      botonesVisibles:bots.length===2&&bots.every(b=>b.top>=0&&b.bottom<=fijo.top+1)}}""")
            self.assertGreaterEqual(vista['errTop'], 0, vista)
            self.assertTrue(vista['botonesVisibles'], vista)
            if zoom:
                d = os.environ.get('CAPTURAS_MODO_REDUCIDO')
                if d:
                    os.makedirs(d, exist_ok=True)
                    self.page.screenshot(path=os.path.join(d, 'A15_conflicto_130real.png'))
            else:
                self._foto('A15_conflicto', zoom130=False)

        self._con_navegador(caso)

    def test_a15_conflicto_de_correcciones(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')
        self._conflicto(False)

    def test_a15_conflicto_de_correcciones_con_texto_al_130(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')
        self._conflicto(True)


class EstadosVersionReducida(_Preparacion, _Comun, TestCase):
    def setUp(self):
        _Preparacion.setUp(self)

    def test_a11_a13_reducida_con_opcional_y_avisos(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self.red['hotswap'] = (500, {'status': 'error', 'message': 'se cayo'})
            self._sustituir(self.ev('()=>cards[1].dataset.formId'), 'Press Nuevo')
            self.page.wait_for_timeout(300)
            self.ev("()=>mostrarErrorSesion('Selecciona el RPE real antes de guardar la serie.',null)")
            self._recargar()
            self.page.wait_for_timeout(300)
            self.assertTrue(self.ev('()=>!document.getElementById("hoy-card").hidden'))
            self._foto('A11_A13_reducida_avisos')

        self._con_navegador(caso)
