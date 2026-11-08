"""8-nov-2026 · Serie testigo (jalón al pecho los lunes, peso fijo, desde el 16-nov).

- Peso fijo para unas 13 reps, del mejor 1RM estimado reciente sin descargas.
- El protocolo se guarda como acuerdo (``ProtocoloTestigo``) y no existe antes del 16-nov.
- Solo los lunes y una vez al día; va aparte de las series de trabajo.
- Referencia: mediana de las 3 primeras semanas sin descarga; cuentan diferencias de 2+.
- Calibración del RPE: lo que dijo que le quedaba frente a lo que le quedaba (con 3+ estimaciones).
"""

import json
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from entrenos.models import EjercicioRealizado, EntrenoRealizado, ProtocoloTestigo, SemanaPlanGym, SerieTestigo
from entrenos.services import serie_testigo_service as st
from rutinas.models import Rutina

L16 = date(2026, 11, 16)


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('serie_testigo_20261108', password='x')
        self.cliente = self.user.cliente_perfil
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 2')

    def jalon(self, fecha, peso, reps):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Jalón al Pecho', peso_kg=peso,
                                          series=3, repeticiones=reps)
        return e


class PesoFijo(Base):
    def test_para_unas_13_reps_sin_descargas(self):
        self.jalon(date(2026, 10, 20), 60, 12)              # 1RM est. 84
        self.jalon(date(2026, 11, 3), 70, 15)               # descarga: no cuenta
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=date(2026, 11, 2), semana_plan=44,
                                     descarga=True, origen='descarga_programada')
        self.assertEqual(st.peso_fijo_desde_historial(self.cliente, L16), 57.5)  # 84 / 1,433 = 58,6 → 57,5

    def test_sin_historial(self):
        self.assertIsNone(st.peso_fijo_desde_historial(self.cliente, L16))


class Protocolo(Base):
    def test_no_existe_antes_del_16(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        self.assertIsNone(st.protocolo_vigente(self.cliente, date(2026, 11, 9)))
        self.assertFalse(ProtocoloTestigo.objects.exists())

    def test_se_crea_el_16_como_acuerdo_y_no_cambia(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        p = st.protocolo_vigente(self.cliente, L16)
        self.assertEqual((p.ejercicio, p.peso_kg, p.dia_semana, p.desde), ('Jalón al Pecho', 57.5, 0, L16))
        self.jalon(L16 + timedelta(days=1), 80, 12)          # mejora: el peso fijo no cambia
        self.assertEqual(st.protocolo_vigente(self.cliente, L16 + timedelta(days=7)).peso_kg, 57.5)

    def test_solo_los_lunes_y_una_vez(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        self.assertIsNotNone(st.toca_hoy(self.cliente, L16))
        self.assertIsNone(st.toca_hoy(self.cliente, L16 + timedelta(days=1)))
        st.registrar(self.cliente, L16, 14, 4)
        self.assertIsNone(st.toca_hoy(self.cliente, L16))


class ReferenciaYCalibracion(Base):
    def setUp(self):
        super().setUp()
        self.jalon(date(2026, 10, 20), 60, 12)

    def test_frases_de_las_primeras_semanas(self):
        s1 = st.registrar(self.cliente, L16, 14, 4)
        self.assertEqual(st.frase_serie(s1, st.resumen(self.cliente)),
                         '14 repeticiones con 57,5 kg. En la 8 dijiste que te quedaban 4; te quedaban 6. '
                         'Faltan 2 semanas para tener tu referencia.')
        self.assertIsNone(st.frase_calibracion(st.resumen(self.cliente)))

    def test_referencia_y_diferencia(self):
        st.registrar(self.cliente, L16, 14, 4)
        st.registrar(self.cliente, L16 + timedelta(weeks=1), 13, 3)
        st.registrar(self.cliente, L16 + timedelta(weeks=2), 15, 5)
        s4 = st.registrar(self.cliente, L16 + timedelta(weeks=3), 11, 2)
        res = st.resumen(self.cliente)
        self.assertEqual((res['referencia'], res['diferencia']), (14, -3))
        self.assertTrue(st.frase_serie(s4, res).endswith('3 repeticiones por debajo de tu referencia (14).'))
        self.assertEqual(st.frase_calibracion(res),
                         'Sueles quedarte corto: de media te quedaban 1,8 repeticiones más de las que dijiste '
                         '(4 series testigo). Tu RPE marcado suele estar por encima del real.')

    def test_una_rep_es_ruido(self):
        for i, reps in enumerate((14, 13, 15, 13)):
            s = st.registrar(self.cliente, L16 + timedelta(weeks=i), reps, reps - 8)
        self.assertIn('Como tu referencia (14): una repetición arriba o abajo es ruido.',
                      st.frase_serie(s, st.resumen(self.cliente)))
        self.assertIn('acierta', st.frase_calibracion(st.resumen(self.cliente)))

    def test_descarga_no_cuenta(self):
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=L16, semana_plan=49, descarga=True,
                                     origen='descarga_programada')
        s = st.registrar(self.cliente, L16, 16, 6)
        self.assertTrue(s.descarga)
        self.assertIn('Semana de descarga: no cuenta para la referencia.', st.frase_serie(s, st.resumen(self.cliente)))
        self.assertEqual(st.resumen(self.cliente)['faltan_para_referencia'], 3)

    def test_sin_llegar_a_la_8_no_hay_estimacion(self):
        s = st.registrar(self.cliente, L16, 7, 3)
        self.assertIsNone(s.quedaban_estimadas)


class Endpoint(Base):
    def test_registrar_y_otro_usuario_no(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        self.client.force_login(self.user)
        url = reverse('entrenos:registrar_serie_testigo', args=[self.cliente.id])
        r = self.client.post(url, json.dumps({'fecha': '2026-11-16', 'reps': '14', 'quedaban': '4'}),
                             content_type='application/json')
        self.assertTrue(r.json()['ok'])
        self.assertEqual(SerieTestigo.objects.get().reps, 14)
        otro = User.objects.create_user('serie_testigo_otro', password='x')
        self.client.force_login(otro)
        r = self.client.post(url, json.dumps({'fecha': '2026-11-16', 'reps': '9'}), content_type='application/json')
        self.assertEqual(r.status_code, 404)

    def test_antes_del_16_no_hay_acuerdo(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        self.client.force_login(self.user)
        r = self.client.post(reverse('entrenos:registrar_serie_testigo', args=[self.cliente.id]),
                             json.dumps({'fecha': '2026-11-09', 'reps': '14'}), content_type='application/json')
        self.assertEqual(r.status_code, 400)


class Pantallas(SimpleTestCase):
    def test_sesion_cierre_y_cuerpo(self):
        base = Path(settings.BASE_DIR)
        sesion = (base / 'entrenos/templates/entrenos/entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('{% if serie_testigo %}', sesion)
        self.assertIn("{% url \"entrenos:registrar_serie_testigo\" cliente.id %}", sesion)
        cierre = (base / 'entrenos/templates/entrenos/post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertIn('{{ serie_testigo_frase }}', cierre)
        cuerpo = (base / 'clientes/templates/clientes/cuerpo.html').read_text(encoding='utf-8')
        self.assertIn('{{ serie_testigo_calibracion }}', cuerpo)
        vistas = (base / 'entrenos/views.py').read_text(encoding='utf-8')
        self.assertIn("'serie_testigo': _serie_testigo_hoy(cliente, fecha_obj),", vistas)


class CuerpoLoEnsena(Base):
    def test_panel(self):
        self.jalon(date(2026, 10, 20), 60, 12)
        st.registrar(self.cliente, L16, 14, 4)
        from clientes.views_salud import _serie_testigo_cuerpo
        ctx = _serie_testigo_cuerpo(self.cliente, L16)
        self.assertTrue(ctx['serie_testigo_frase'].startswith('14 repeticiones con 57,5 kg.'))
        self.assertIsNone(ctx['serie_testigo_calibracion'])
