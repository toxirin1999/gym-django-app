"""Etapa 3 (21-nov-2026): técnica «sin valorar».

La app ya no marca «buena» sola. «Buena» cuenta para decisiones y resúmenes solo
si la eligió el usuario (``tecnica_origen='elegida'``).
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SerieRealizada
from entrenos import tests_estado_borrador_20261121 as _mod
from rutinas.models import EjercicioBase, Rutina

_PLAYWRIGHT = _mod._PLAYWRIGHT


class _H:
    B = _mod.EstadoBorradorEnNavegador


class TecnicaOrigenServidor(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tec-etapa3', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client.force_login(self.user)
        self.rutina = Rutina.objects.create(nombre='Día técnica')
        EjercicioBase.objects.create(nombre='Sentadilla', grupo_muscular='Piernas')
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def _post(self, **extra):
        data = {
            'fecha': date.today().isoformat(), 'rutina_nombre': self.rutina.nombre,
            'ej1_nombre': 'Sentadilla', 'ej1_tipo_progresion': 'peso_reps',
        }
        for i in (1, 2, 3):
            data.update({f'ej1_peso_{i}': '60', f'ej1_reps_{i}': '5', f'ej1_rpe_{i}': '8',
                         f'ej1_completado_{i}': '1'})
        data.update(extra)
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_origen_por_serie(self):
        r = self._post(
            ej1_tecnica_1='buena', ej1_tecnica_origen_1='elegida',   # tocó «buena»
            ej1_tecnica_2='buena',                                   # página antigua: sola
            # serie 3: sin técnica
        )
        self.assertEqual(r.status_code, 200, r.content)
        s = {x.serie_numero: x for x in SerieRealizada.objects.all()}
        self.assertEqual((s[1].tecnica_calidad, s[1].tecnica_origen), ('buena', 'elegida'))
        self.assertEqual((s[2].tecnica_calidad, s[2].tecnica_origen), ('buena', 'desconocida'))
        self.assertEqual((s[3].tecnica_calidad, s[3].tecnica_origen), (None, 'sin_valorar'))

    def test_comprometida_siempre_se_conserva(self):
        self._post(ej1_tecnica_1='comprometida', ej1_tecnica_origen_1='elegida')
        self.assertEqual(SerieRealizada.objects.get(serie_numero=1).tecnica_calidad, 'comprometida')


class TecnicaConsumidores(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tec-cons', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        hoy = date.today()
        self.lunes = hoy - timedelta(days=hoy.weekday() + 7)
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='X'),
            fecha=self.lunes + timedelta(days=1), fecha_ejecucion=self.lunes + timedelta(days=1))
        self.ej = EjercicioBase.objects.create(nombre='Press banca', grupo_muscular='Pecho')

    def _serie(self, n, tecnica, origen):
        return SerieRealizada.objects.create(
            entreno=self.entreno, ejercicio=self.ej, serie_numero=n, repeticiones=5,
            peso_kg=60, completado=True, tecnica_calidad=tecnica, tecnica_origen=origen)

    def test_decisiones_no_cuentan_buena_por_defecto(self):
        from entrenos.services.decision_log_service import _tecnicas_sesion
        from entrenos.services.decision_log_service import normalizar_ejercicio
        self._serie(1, 'buena', 'desconocida')
        self._serie(2, 'buena', 'elegida')
        self._serie(3, 'aceptable', 'elegida')
        self.assertEqual(sorted(_tecnicas_sesion(self.entreno, normalizar_ejercicio('Press banca'))),
                         ['aceptable', 'buena'])

    def test_resumen_semanal_no_afirma_tecnica_limpia_sin_valoracion(self):
        from entrenos.services.resumen_semanal_service import get_resumen_semanal_gym
        self._serie(1, 'buena', 'desconocida')
        self._serie(2, None, 'sin_valorar')
        textos = [i['texto'] for i in get_resumen_semanal_gym(self.cliente, self.lunes, self.lunes + timedelta(days=6))]
        self.assertFalse(any('Técnica limpia' in t for t in textos), textos)
        self._serie(3, 'buena', 'elegida')
        textos = [i['texto'] for i in get_resumen_semanal_gym(self.cliente, self.lunes, self.lunes + timedelta(days=6))]
        self.assertTrue(any('Técnica limpia' in t for t in textos), textos)


class TecnicaEnNavegador(TestCase):
    _abrir = _H.B._abrir
    _ir = _H.B._ir
    ev = _H.B.ev
    _guardar_serie = _H.B._guardar_serie
    _con_navegador = _H.B._con_navegador

    def setUp(self):
        _H.B.setUp(self)

    def test_sin_tocar_queda_sin_valorar_y_al_tocar_envia_origen(self):
        if not _PLAYWRIGHT:
            self.skipTest('sin Playwright')

        def caso():
            self._ir()
            self._guardar_serie(0, 1)
            r = self.ev("""()=>{const f=cards[0].dataset.formId;
              const h=document.querySelector('[name="'+f+'_tecnica_1"]');
              return {tec:STATE.seriesCompletadas[f][0].tecnica||null, input:h?h.value:'',
                      origen:!!document.querySelector('[name="'+f+'_tecnica_origen_1"]'),
                      texto:document.getElementById('tecnica-impacto-'+f).textContent,
                      badge:document.getElementById('tecnica-badge-'+f+'-1').textContent}}""")
            self.assertIsNone(r['tec'])
            self.assertEqual(r['input'], '')
            self.assertFalse(r['origen'])
            self.assertIn('sin valorar', r['texto'])
            r = self.ev("""()=>{const f=cards[0].dataset.formId; selTecnica(f,'buena');
              const o=document.querySelector('[name="'+f+'_tecnica_origen_1"]');
              return {origen:o?o.value:null, s:STATE.seriesCompletadas[f][0]}}""")
            self.assertEqual(r['origen'], 'elegida')
            self.assertEqual(r['s']['tecnica'], 'buena')
            self._recargar_ok()
            self.assertEqual(self.errores_js, [])

        self._con_navegador(caso)

    def _recargar_ok(self):
        self.page.reload()
        self.page.wait_for_function('typeof STATE!=="undefined" && typeof ESTADO!=="undefined"')
        self.page.wait_for_timeout(250)
        r = self.ev("""()=>{const f=cards[0].dataset.formId;
          const o=document.querySelector('[name="'+f+'_tecnica_origen_1"]');
          return {origen:o?o.value:null, tec:STATE.seriesCompletadas[f]?.[0]?.tecnica||null}}""")
        self.assertEqual(r, {'origen': 'elegida', 'tec': 'buena'})
