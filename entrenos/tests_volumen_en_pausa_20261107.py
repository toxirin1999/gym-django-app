"""7-nov-2026 · Tríceps y trapecio mantienen el volumen hasta que cierre Fuerza — Hipertrofia.

Decisión de David: la pausa va ligada al cierre del bloque (semanas 45-48 de
la periodización), no a una fecha. Memoria enseña la fecha prevista (06/12).
Si el bloque se retrasa, la pausa sigue hasta su revisión. Mientras, el
entrenador no propone añadirles series, los observa y Memoria anota si caen.
Bajar volumen sí puede.
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from entrenos.models import SemanaPlanGym
from entrenos.services import propuesta_zona_service as pz

L44 = date(2026, 11, 2)  # descarga, semana 44


class Base(TestCase):
    def setUp(self):
        self.cliente = User.objects.create_user('volumen_pausa_20261107', password='x').cliente_perfil

    def semanas(self, *numeros, desde=L44):
        for i, n in enumerate(numeros):
            SemanaPlanGym.objects.create(cliente=self.cliente, lunes=desde + timedelta(weeks=i), semana_plan=n,
                                         descarga=(n in (44, 49)), origen=SemanaPlanGym.ORIGEN_AVANCE)


class LigadaAlCierre(Base):
    def test_activa_con_fin_previsto(self):
        self.semanas(44, 45)
        pausa = pz.pausa_subir_volumen(self.cliente, L44 + timedelta(days=9))
        self.assertEqual(pausa['fin_previsto'], date(2026, 12, 6))
        self.assertEqual(pausa['bloque'], 'Fuerza — Hipertrofia')
        self.assertTrue(pz.subir_en_pausa(self.cliente, 'triceps', L44 + timedelta(days=9)))
        self.assertFalse(pz.subir_en_pausa(self.cliente, 'pecho', L44 + timedelta(days=9)))

    def test_si_el_bloque_se_retrasa_la_pausa_sigue(self):
        # Una semana repetida (45 dos veces): el 07/12 aún es semana 48 y la pausa sigue.
        self.semanas(44, 45, 45, 46, 47, 48)
        hoy = date(2026, 12, 9)
        pausa = pz.pausa_subir_volumen(self.cliente, hoy)
        self.assertEqual(pausa['fin_previsto'], date(2026, 12, 13))

    def test_termina_al_salir_del_bloque_y_no_vuelve(self):
        self.semanas(44, 45, 46, 47, 48, 49)
        self.assertIsNone(pz.pausa_subir_volumen(self.cliente, date(2026, 12, 8)))
        # Aunque más adelante otra semana vuelva a caer en 44-48, la pausa no se reactiva.
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=date(2027, 11, 1), semana_plan=44,
                                     descarga=True, origen=SemanaPlanGym.ORIGEN_AVANCE)
        self.assertIsNone(pz.pausa_subir_volumen(self.cliente, date(2027, 11, 3)))

    def test_sin_periodizacion_no_hay_pausa(self):
        self.assertIsNone(pz.pausa_subir_volumen(self.cliente, L44 + timedelta(days=3)))


class Retroceso(Base):
    def _detectar(self, hoy):
        evolucion = {'estado_por_zona': {'triceps': 'retrocede'}}
        caida = {'zona': 'triceps', 'pct': -12.0, 'dudoso': False, 'ligero': False, 'ejercicio': 'Press Francés',
                 'antes': {'peso_kg': 40, 'reps': 10, 'fecha': date(2026, 8, 1)},
                 'ahora': {'peso_kg': 35, 'reps': 10, 'fecha': date(2026, 11, 1)}}
        with patch('entrenos.services.evolucion_muscular_service.calcular_evolucion_por_grupo',
                   return_value=evolucion), \
                patch('entrenos.services.evolucion_muscular_service.comparar_ejercicios', return_value=[caida]):
            return pz.detectar_zona_en_retroceso(self.cliente, hoy)

    def test_no_propone_subir_durante_el_bloque(self):
        self.semanas(44, 45)
        self.assertIsNone(self._detectar(L44 + timedelta(days=9)))

    def test_tras_el_cierre_vuelve_a_decidir(self):
        self.semanas(44, 45, 46, 47, 48, 49)
        self.assertEqual(self._detectar(date(2026, 12, 8))['zona'], 'triceps')


class MemoriaLoAnota(Base):
    def test_observado_hoy(self):
        from clientes.views import _volumen_en_pausa
        self.semanas(44)
        evolucion = {'grupos': [{'zona': 'triceps', 'nombre': 'Tríceps', 'pct': -8.0, 'estado': 'retrocede'},
                                {'zona': 'trapecios', 'nombre': 'Trapecios', 'pct': 2.0, 'estado': 'estable'}]}
        v = _volumen_en_pausa(self.cliente, date(2026, 11, 7), evolucion)
        self.assertEqual((v['bloque'], v['fin_previsto']), ('Fuerza — Hipertrofia', date(2026, 12, 6)))
        self.assertEqual(v['zonas'], [{'nombre': 'Tríceps', 'pct': -8.0, 'cae': True},
                                      {'nombre': 'Trapecios', 'pct': 2.0, 'cae': False}])

    def test_plantilla(self):
        from pathlib import Path
        from django.conf import settings
        src = (Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes' / 'memoria_entrenador.html'
               ).read_text(encoding='utf-8')
        self.assertIn('No propongo subirles series hasta que cierre {{ volumen_en_pausa.bloque }} (previsto el '
                      '{{ volumen_en_pausa.fin_previsto|date:"d/m" }}).', src)


class BajarSigueDisponible(Base):
    """La pausa solo frena subir: las vías de bajar (fatiga, por encima del máximo) no la miran."""

    def test_bajar_no_consulta_la_pausa(self):
        import inspect
        for funcion in (pz.detectar_zona_con_fatiga, pz.detectar_zona_por_encima):
            src = inspect.getsource(funcion)
            self.assertNotIn('pausa', src)
            self.assertNotIn('subir_en_pausa', src)
        self.assertIn('pausa_subir_volumen', inspect.getsource(pz.detectar_zona_en_retroceso))
        self.assertIn('subir_en_pausa', inspect.getsource(pz.detectar_zona_con_margen))
