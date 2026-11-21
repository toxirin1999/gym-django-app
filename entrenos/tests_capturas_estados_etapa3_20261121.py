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
    _esperar_resumen_quieto = _Preparacion._esperar_resumen_quieto
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

    def _comprobar_conflicto_resoluble(self):
        """Con un conflicto pendiente: solo acciones que lo resuelven y todo el contenido accesible."""
        v = self.ev("""()=>{const ov=document.getElementById('modal-resumen-overlay');
          const cont=document.querySelector('.modal-resumen-full');
          const guardar=document.getElementById('btn-confirmar-guardar');
          const acciones=[...document.querySelectorAll('#save-acciones button')].map(b=>b.textContent.trim());
          const visibles=[...ov.querySelectorAll('button')].filter(b=>{const s=getComputedStyle(b),r=b.getBoundingClientRect();
              return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0}).map(b=>b.textContent.trim());
          const pos=getComputedStyle(document.querySelector('.mr-actions')).position;
          return {guardarOculto:getComputedStyle(guardar).display==='none',acciones,visibles,pos,
                  enConflicto:cont.classList.contains('en-conflicto')}}""")
        self.assertTrue(v['enConflicto'], v)
        self.assertTrue(v['guardarOculto'], v)
        self.assertEqual(v['acciones'], ['Aplicar la mía encima', 'Ver lo guardado'], v)
        self.assertNotIn('Reintentar guardado', v['visibles'], v)
        self.assertNotIn('Guardar entrenamiento', v['visibles'], v)
        self.assertEqual(v['pos'], 'static', 'el pie no debe ser fijo ni tapar contenido')
        # Cada pieza del contenido se puede llevar a la vista y nada la cubre.
        for sel in ['#save-error', '#save-acciones button:first-child', '#save-acciones button:last-child',
                    '#modal-resumen-title', '#modal-resumen-subtitle', '#modal-series',
                    '#modal-ejercicios-lista', '#btn-volver-editar']:
            r = self.ev("""(s)=>{const e=document.querySelector(s);if(!e)return {falta:true};
              e.scrollIntoView({block:'center'});
              const q=e.getBoundingClientRect();
              const top=document.elementFromPoint(q.left+q.width/2,Math.min(Math.max(q.top+Math.min(q.height,8),1),innerHeight-1));
              return {ok:!!top&&(e===top||e.contains(top)||top.contains(e)),top:top&&(top.id||top.className||top.tagName)}}""", sel)
            self.assertFalse(r.get('falta'), sel)
            self.assertTrue(r['ok'], (sel, r))

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
            self._comprobar_conflicto_resoluble()
            self.ev("()=>{document.querySelector('.modal-resumen-full').scrollTop=0}")
            self.page.wait_for_timeout(200)
            if zoom:
                d = os.environ.get('CAPTURAS_MODO_REDUCIDO')
                if d:
                    os.makedirs(d, exist_ok=True)
                    self.page.screenshot(path=os.path.join(d, 'A15_conflicto_130real.png'))
            else:
                self._foto('A15_conflicto', zoom130=False)

        self._con_navegador(caso)

    def _enviar_cierre(self):
        self.ev("()=>document.getElementById('btn-mostrar-resumen').click()")
        self.page.wait_for_timeout(500)
        self.ev("""()=>{const m=document.getElementById('motivo-cierre');
          if(m){m.selectedIndex=Math.min(1,m.options.length-1);m.dispatchEvent(new Event('change',{bubbles:true}));}
          document.getElementById('btn-confirmar-guardar').click();}""")
        self.page.wait_for_timeout(600)

    def _pulsar(self, texto):
        self.ev("""(t)=>[...document.querySelectorAll('#save-acciones button')].find(b=>b.textContent.trim()===t).click()""", texto)
        self.page.wait_for_timeout(600)

    def test_aplicar_la_mia_usa_la_revision_actual_y_detecta_otro_cambio_concurrente(self):
        """El conflicto lleva la huella que el servidor tiene AHORA; si cambia otra vez antes de
        aplicar, el servidor vuelve a avisar y «Aplicar la mía» pasa a usar la nueva."""
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            def servidor(cuerpo):
                s = str(cuerpo)
                if 'name="resolver_conflicto"\r\n\r\nh2' in s:
                    return 200, {'success': True, 'huella': 'x', 'entreno_id': 7}
                if 'name="resolver_conflicto"\r\n\r\nh1' in s:   # otro móvil ya cambió a h2
                    return 409, {'conflicto': True, 'huella': 'h2', 'entreno_id': 7, 'revision': 3}
                return 409, {'conflicto': True, 'huella': 'h1', 'entreno_id': 7, 'revision': 2}
            self.red['otro'] = servidor
            self._guardar_serie(0, 1, rpe=8)
            self._enviar_cierre()
            self._pulsar('Aplicar la mía encima')       # intenta con h1; otro móvil ya cambió a h2
            self.assertEqual(self.ev('()=>document.getElementById("save-error").textContent.includes("otro contenido")'), True)
            self._pulsar('Aplicar la mía encima')       # ahora con h2
            envios = [c for k, c in self.llamadas if k == 'otro' and 'resolver_conflicto' in str(c)]
            self.assertEqual(len(envios), 2, self.llamadas)
            self.assertIn('h1', str(envios[0]))
            self.assertNotIn('h2', str(envios[0]))
            self.assertIn('h2', str(envios[1]))
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)

    def test_el_conflicto_pendiente_sobrevive_a_volver_a_editar(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self.red['otro'] = (409, {'conflicto': True, 'huella': 'abc', 'entreno_id': 1})
            self._guardar_serie(0, 1, rpe=8)
            self._enviar_cierre()
            self.ev("()=>document.getElementById('btn-volver-editar').click()")
            self.page.wait_for_timeout(500)
            self.ev("()=>document.getElementById('btn-mostrar-resumen').click()")
            self._esperar_resumen_quieto()
            self._comprobar_conflicto_resoluble()
            self.assertEqual(self.errores_js, [])

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
