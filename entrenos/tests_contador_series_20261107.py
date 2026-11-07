"""7-nov-2026 · El contador de series dice qué cuenta.

- Plan y lo hecho se cuentan igual: directas enteras, indirectas a la mitad.
- El Farmer Walk: antebrazo y medio trapecio, en el plan y en lo hecho.
- Plan: la semana en curso, con directas e indirectas y el periodo.
- Memoria: media de semanas completas sin descarga, y lo dice.
"""

from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse

from entrenos.models import SemanaPlanGym, SerieRealizada
from entrenos.services.marcador_semanal_service import (
    grupos_de_serie, marcador_semanal, media_semanal_series, series_hechas_detalle,
)
from entrenos.tests_cola_semanal import LUNES, ColaSemanalBase
from rutinas.models import EjercicioBase


class _Base(ColaSemanalBase):
    def series(self, entreno, nombre, grupo, n):
        base, _ = EjercicioBase.objects.get_or_create(
            nombre=nombre, defaults={'grupo_muscular': grupo, 'tipo_progresion': 'peso_reps'},
        )
        for i in range(1, n + 1):
            SerieRealizada.objects.create(entreno=entreno, ejercicio=base, serie_numero=i,
                                          repeticiones=12, peso_kg=50, rpe_real=8, completado=True)


class Reglas(_Base):
    def test_directas_indirectas_y_farmer(self):
        self.assertEqual(grupos_de_serie('Press Francés con Barra Z', 'Tríceps'), [('tríceps', 1.0)])
        self.assertEqual(grupos_de_serie('Convergent Machine Press', 'Pecho'), [('pecho', 1.0), ('tríceps', 0.5)])
        self.assertEqual(grupos_de_serie('Farmer Walk (Paseo del Granjero)', 'trapecios'),
                         [('antebrazos', 1.0), ('trapecio', 0.5)])
        self.assertEqual(grupos_de_serie('Farmer Walk (Paseo del Granjero)', 'antebrazos'),
                         [('antebrazos', 1.0), ('trapecio', 0.5)])

    def test_hechas_con_detalle(self):
        e = self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        self.series(e, 'Convergent Machine Press', 'Pecho', 4)
        self.series(e, 'Press Francés con Barra Z', 'Tríceps', 3)
        total, directas, indirectas = series_hechas_detalle(self.cliente, LUNES, LUNES)
        self.assertEqual((total['tríceps'], directas['tríceps'], indirectas['tríceps']), (5, 3, 2))

    def test_filas_con_directas_e_indirectas_y_periodo(self):
        e = self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        self.series(e, 'Convergent Machine Press', 'Pecho', 4)
        m = marcador_semanal(self.cliente, LUNES)
        filas = {f['clave']: f for f in m['filas']}
        self.assertEqual((filas['pecho']['directas'], filas['pecho']['indirectas']), (4, 0))
        self.assertTrue(m['periodo'].startswith('Últimos 7 días · '))

    def test_plan_cuenta_indirectas_como_lo_hecho(self):
        from collections import Counter
        from entrenos.services import marcador_semanal_service as m
        ent = {'rutina_nombre': 'Dia 1', 'ejercicios': [
            {'nombre': 'Convergent Machine Press', 'grupo_muscular': 'pecho', 'series': 4},
            {'nombre': 'Press Francés con Barra Z', 'grupo_muscular': 'triceps', 'series': 3},
            {'nombre': 'Farmer Walk (Paseo del Granjero)', 'grupo_muscular': 'trapecios', 'series': 3},
        ]}

        class P:
            def generar_entrenamiento_para_fecha(self, fecha):
                return ent if fecha == LUNES else None
        with patch('entrenos.services.sesion_recomendada._build_planificador', return_value=P()):
            plan, _ = m.series_plan_semana(self.cliente, LUNES)
        self.assertEqual(plan, Counter({'pecho': 4, 'tríceps': 5, 'antebrazos': 3, 'trapecio': 1.5}))


class Memoria(_Base):
    def test_media_de_semanas_completas_sin_descarga(self):
        hoy = LUNES + timedelta(days=30)
        lunes_hoy = hoy - timedelta(days=hoy.weekday())
        semana_descarga = lunes_hoy - timedelta(days=7)
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=semana_descarga, semana_plan=44,
                                     descarga=True, origen='descarga_programada')
        e = self.entrenar(semana_descarga, 'Dia 1 - Descarga')
        self.series(e, 'Press Francés con Barra Z', 'Tríceps', 2)  # no cuenta: descarga
        e = self.entrenar(lunes_hoy - timedelta(days=14), 'Dia 1 - Hipertrofia')
        self.series(e, 'Press Francés con Barra Z', 'Tríceps', 8)
        self.series(e, 'Convergent Machine Press', 'Pecho', 4)
        e = self.entrenar(hoy, 'Dia 1 - Hipertrofia')
        self.series(e, 'Press Francés con Barra Z', 'Tríceps', 9)  # semana en curso: no cuenta
        media = media_semanal_series(self.cliente, hoy)
        self.assertEqual(media['semanas'], 4)
        self.assertEqual(media['hasta'], lunes_hoy - timedelta(days=8))
        self.assertEqual(media['grupos']['tríceps'], {'total': 2.5, 'directas': 2.0, 'indirectas': 0.5})

    def test_memoria_lo_explica(self):
        src = open('clientes/templates/clientes/partials/_mapa_evolucion_muscular.html', encoding='utf-8').read()
        self.assertIn('Media semanal', src)
        self.assertIn('sin descarga', src)
        self.assertIn('Plan enseña la semana en curso', src)
        self.assertNotIn('Volumen actual', src)

    def test_plan_lo_explica(self):
        self.client.force_login(self.cliente.user)
        datos = {'filas': [{'grupo': 'Tríceps', 'clave': 'tríceps', 'hechas': 17, 'directas': 9, 'indirectas': 8,
                            'minimo': 10, 'maximo': 19, 'plan': 15.5, 'estado': 'ok', 'cubren': [],
                            'pct': 89, 'pct_min': 52}],
                 'frase': None, 'periodo': 'Últimos 7 días · 01/11–07/11'}
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value=datos):
            r = self.client.get(reverse('clientes:trayectoria_plan'))
        self.assertContains(r, '9 directas + 8 de indirectas')
        self.assertContains(r, 'Cuenta las series de trabajo de este periodo (últimos 7 días · 01/11–07/11), no una media.')
