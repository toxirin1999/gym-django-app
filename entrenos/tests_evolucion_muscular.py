"""Contrato del cálculo de evolución por grupo muscular (mapa corporal de Memoria)."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from entrenos.services.evolucion_muscular_service import (
    ZONAS,
    calcular_evolucion_por_grupo,
    comparar_ejercicios,
    normalizar_zona,
)
from entrenos.services.modelo_usuario_service import _get_grupos_musculares
from rutinas.models import Rutina


class NormalizarZonaTests(SimpleTestCase):
    def test_variantes_con_y_sin_tilde_y_mayusculas_son_la_misma_zona(self):
        for grupo in ('Cuádriceps', 'Cuadriceps', 'cuadriceps', ' CUÁDRICEPS '):
            self.assertEqual(normalizar_zona(grupo, 'Lo que sea'), 'cuadriceps')
        for grupo in ('Glúteos', 'Gluteos', 'gluteo'):
            self.assertEqual(normalizar_zona(grupo, ''), 'gluteos')
        for grupo in ('Bíceps', 'Biceps', 'bíceps'):
            self.assertEqual(normalizar_zona(grupo, ''), 'biceps')
        for grupo in ('Tríceps', 'Triceps'):
            self.assertEqual(normalizar_zona(grupo, ''), 'triceps')

    def test_alias_del_catalogo_se_mapean_a_su_zona(self):
        self.assertEqual(normalizar_zona('chest', ''), 'pecho')
        self.assertEqual(normalizar_zona('Hombro', ''), 'hombros')
        self.assertEqual(normalizar_zona('Rowing', ''), 'espalda')
        self.assertEqual(normalizar_zona('Dominadas', ''), 'espalda')
        self.assertEqual(normalizar_zona('Isquiotibiales', ''), 'isquios')
        self.assertEqual(normalizar_zona('Abdominales', ''), 'core')

    def test_grupo_especifico_manda_sobre_el_nombre(self):
        # El grupo asignado es la fuente de verdad aunque el nombre sugiera otra cosa.
        self.assertEqual(normalizar_zona('Tríceps', 'Fondos en paralelas'), 'triceps')

    def test_grupo_generico_o_vacio_se_infiere_por_nombre(self):
        casos = {
            ('Piernas', 'Prensa de piernas'): 'cuadriceps',
            ('Pierna', 'Hip thrust con barra'): 'gluteos',
            ('Otros', 'Curl femoral tumbado'): 'isquios',
            ('', 'Elevación de gemelos en prensa'): 'gemelos',
            (None, 'Elevaciones laterales con mancuernas'): 'hombros',
            ('Full body', 'Encogimientos con barra'): 'trapecios',
            ('-', 'Curl con barra Z'): 'biceps',
            ('Otros', 'Extensión de tríceps en polea'): 'triceps',
            ('Otros', 'Crunch en polea (Cable Crunch)'): 'core',
            ('Otros', 'Press banca con mancuernas'): 'pecho',
            ('Otros', 'Jalón al pecho'): 'espalda',
            ('Otros', 'Extensiones de cuádriceps en máquina'): 'cuadriceps',
        }
        for (grupo, nombre), esperado in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(normalizar_zona(grupo, nombre), esperado)

    def test_sin_pistas_devuelve_none(self):
        self.assertIsNone(normalizar_zona('Otros', 'Movimiento misterioso'))
        self.assertIsNone(normalizar_zona(None, ''))

    def test_zonas_canonicas(self):
        self.assertEqual(
            set(ZONAS),
            {'pecho', 'espalda', 'hombros', 'biceps', 'triceps', 'antebrazos',
             'core', 'trapecios', 'gluteos', 'cuadriceps', 'isquios', 'gemelos'},
        )


class _DatosEntrenoMixin:
    HOY = date(2026, 10, 10)

    def setUp(self):
        user = get_user_model().objects.create_user(username='evo', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.rutina = Rutina.objects.create(nombre='Rutina evo')
        self._entrenos = {}

    def _ej(self, dias_atras, nombre, peso, reps, grupo=None, **extra):
        fecha = self.HOY - timedelta(days=dias_atras)
        entreno = self._entrenos.get(fecha)
        if entreno is None:
            entreno = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            )
            self._entrenos[fecha] = entreno
        EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
            entreno=entreno, nombre_ejercicio=nombre, grupo_muscular=grupo,
            peso_kg=peso, repeticiones=reps, series=3, **extra,
        )])

    def _grupo(self, resultado, zona):
        return next(g for g in resultado['grupos'] if g['zona'] == zona)


class EvolucionPorGrupoTests(_DatosEntrenoMixin, TestCase):

    def test_devuelve_todas_las_zonas_aunque_no_haya_datos(self):
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        self.assertEqual({g['zona'] for g in r['grupos']}, set(ZONAS))
        self.assertTrue(all(g['estado'] == 'sin_datos' for g in r['grupos']))
        self.assertIsNone(r['media_pct'])
        self.assertEqual(r['n_con_datos'], 0)

    def test_usa_e1rm_no_peso_bruto(self):
        # Mismo peso, más repeticiones: el peso bruto no cambia, el e1RM sí.
        self._ej(120, 'Press banca con barra', 80, 5, 'Pecho')
        self._ej(10, 'Press banca con barra', 80, 10, 'Pecho')
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        # Epley: 80*(1+5/30)=93.33 → 80*(1+10/30)=106.67  → +14.3 %
        self.assertAlmostEqual(pecho['pct'], 14.3, places=1)
        self.assertEqual(pecho['estado'], 'progresa')

    def test_considera_todos_los_ejercicios_no_solo_veinte(self):
        for i in range(30):
            self._ej(120, f'Ejercicio pecho {i:02d}', 50, 8, 'Pecho')
            self._ej(10, f'Ejercicio pecho {i:02d}', 60, 8, 'Pecho')
        self._ej(120, 'Prensa de piernas', 150, 10, 'Piernas')
        self._ej(10, 'Prensa de piernas', 200, 10, 'Piernas')
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        self.assertEqual(self._grupo(r, 'pecho')['n_ejercicios'], 30)
        cuads = self._grupo(r, 'cuadriceps')
        self.assertAlmostEqual(cuads['pct'], 33.3, places=1)
        self.assertEqual(cuads['estado'], 'progresa_mucho')

    def test_unifica_grupos_con_y_sin_tilde(self):
        self._ej(120, 'Sentadilla', 100, 5, 'Cuadriceps')
        self._ej(10, 'Sentadilla', 110, 5, 'Cuádriceps')
        self._ej(120, 'Extensiones de cuádriceps', 50, 10, 'Cuádriceps')
        self._ej(10, 'Extensiones de cuádriceps', 55, 10, 'Cuadriceps')
        cuads = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'cuadriceps')
        self.assertEqual(cuads['n_ejercicios'], 2)
        self.assertAlmostEqual(cuads['pct'], 10.0, places=1)

    def test_variantes_de_nombre_del_mismo_ejercicio_se_comparan(self):
        self._ej(120, 'Press Banca Con Barra', 80, 5, 'Pecho')
        self._ej(10, 'press banca con barra ', 88, 5, 'Pecho')
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertEqual(pecho['n_ejercicios'], 1)
        self.assertAlmostEqual(pecho['pct'], 10.0, places=1)

    def test_valores_extremos_no_cuentan_en_la_mediana(self):
        self._ej(120, 'Curl con barra', 30, 8, 'Bíceps')
        self._ej(10, 'Curl con barra', 33, 8, 'Bíceps')          # +10 %
        self._ej(120, 'Curl martillo', 10, 8, 'Bíceps')
        self._ej(10, 'Curl martillo', 11.5, 8, 'Bíceps')          # +15 %
        self._ej(120, 'Curl en polea', 5, 8, 'Bíceps')
        self._ej(10, 'Curl en polea', 15, 8, 'Bíceps')            # +200 %
        biceps = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'biceps')
        # El +200 % de un accesorio ligero se aparta; la mediana usa los demás.
        self.assertAlmostEqual(biceps['pct'], 12.5, places=1)
        self.assertEqual(biceps['mejor']['ejercicio'], 'Curl martillo')
        self.assertEqual([d['ejercicio'] for d in biceps['ligeros']], ['Curl en polea'])
        self.assertEqual(biceps['dudosos'], [])

    def test_franja_estable_de_mas_menos_cinco(self):
        self._ej(120, 'Press militar', 50, 8, 'Hombros')
        self._ej(10, 'Press militar', 48, 8, 'Hombros')            # -4 %
        self._ej(120, 'Remo con barra', 100, 8, 'Espalda')
        self._ej(10, 'Remo con barra', 94, 8, 'Espalda')           # -6 %
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        self.assertEqual(self._grupo(r, 'hombros')['estado'], 'estable')
        self.assertEqual(self._grupo(r, 'espalda')['estado'], 'retrocede')

    def test_retroceso_y_estable_no_se_esconden(self):
        self._ej(120, 'Remo con barra', 80, 8, 'Espalda')
        self._ej(10, 'Remo con barra', 70, 8, 'Espalda')            # -12.5 %
        self._ej(120, 'Press militar', 40, 8, 'Hombros')
        self._ej(10, 'Press militar', 41, 8, 'Hombros')            # +2.5 %
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        self.assertEqual(self._grupo(r, 'espalda')['estado'], 'retrocede')
        self.assertEqual(self._grupo(r, 'hombros')['estado'], 'estable')

    def test_ignora_cargas_de_recuperacion_incompletos_y_sin_peso(self):
        self._ej(120, 'Hip thrust', 100, 8, 'Glúteos')
        self._ej(10, 'Hip thrust', 110, 8, 'Glúteos')
        self._ej(5, 'Hip thrust', 40, 8, 'Glúteos', is_recovery_load=True)
        self._ej(4, 'Hip thrust', 300, 8, 'Glúteos', completado=False)
        self._ej(3, 'Hip thrust', 0, 8, 'Glúteos')
        gluteos = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'gluteos')
        self.assertAlmostEqual(gluteos['pct'], 10.0, places=1)

    def test_solo_un_periodo_no_permite_comparar(self):
        self._ej(10, 'Curl femoral', 40, 10, 'Isquios')
        isquios = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'isquios')
        self.assertIsNone(isquios['pct'])
        self.assertEqual(isquios['estado'], 'sin_datos')

    def test_respeta_el_periodo_pedido(self):
        self._ej(50, 'Press banca con barra', 80, 5, 'Pecho')
        self._ej(5, 'Press banca con barra', 88, 5, 'Pecho')
        r30 = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY, dias=30)
        self.assertEqual(r30['periodo_dias'], 30)
        self.assertAlmostEqual(self._grupo(r30, 'pecho')['pct'], 10.0, places=1)
        # Con 90 días ambas sesiones caen en la misma ventana: no hay "antes".
        r90 = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY, dias=90)
        self.assertIsNone(self._grupo(r90, 'pecho')['pct'])

    def test_resumen_global_y_orden(self):
        self._ej(120, 'Press francés', 20, 10, 'Tríceps')
        self._ej(10, 'Press francés', 32, 10, 'Tríceps')            # +60 %
        self._ej(120, 'Press banca con barra', 100, 5, 'Pecho')
        self._ej(10, 'Press banca con barra', 120, 5, 'Pecho')     # +20 %
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        self.assertEqual(r['n_con_datos'], 2)
        self.assertAlmostEqual(r['media_pct'], 40.0, places=1)
        self.assertEqual([g['zona'] for g in r['grupos'][:2]], ['triceps', 'pecho'])
        self.assertEqual(r['grupos'][0]['nombre'], 'Tríceps')
        self.assertEqual(r['lider']['zona'], 'triceps')
        self.assertEqual(r['estado_por_zona']['triceps'], 'progresa_mucho')
        self.assertEqual(r['estado_por_zona']['pecho'], 'progresa')
        self.assertEqual(r['estado_por_zona']['gemelos'], 'sin_datos')
        self.assertIn('poco volumen', r['grupos'][0]['lectura'])

    def test_series_por_semana_ultimas_cuatro_semanas(self):
        self._ej(3, 'Press francés', 20, 10, 'Tríceps')
        self._ej(10, 'Press francés', 20, 10, 'Triceps')
        self._ej(60, 'Press francés', 20, 10, 'Tríceps')  # fuera de las 4 semanas
        triceps = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'triceps')
        self.assertAlmostEqual(triceps['series_semana'], 1.5, places=1)  # 6 series / 4


class EvolucionRobustaTests(_DatosEntrenoMixin, TestCase):
    """Criterios de registro mezclados y saltos imposibles no deben falsear la zona."""

    def test_compara_por_unidad_aunque_cambie_el_criterio_de_registro(self):
        # Antes: solo el peso por mano (legacy). Ahora: por mano + multiplicador + total.
        self._ej(120, 'Curl martillo', 15, 8, 'Bíceps')
        self._ej(10, 'Curl martillo', 15, 8, 'Bíceps',
                 tipo_carga='por_mano', multiplicador_carga=2, peso_total_kg=30)
        biceps = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'biceps')
        self.assertEqual(biceps['pct'], 0.0)
        self.assertEqual(biceps['estado'], 'estable')

    def test_si_solo_hay_total_se_divide_por_el_multiplicador(self):
        self._ej(120, 'Prensa de piernas', 0, 10, 'Cuádriceps',
                 tipo_carga='por_lado', multiplicador_carga=2, peso_total_kg=200)
        self._ej(10, 'Prensa de piernas', 110, 10, 'Cuádriceps')
        cuads = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'cuadriceps')
        self.assertAlmostEqual(cuads['pct'], 10.0, places=1)

    def test_saltos_dudosos_quedan_fuera_de_la_mediana_y_se_listan(self):
        self._ej(120, 'Press francés', 20, 10, 'Tríceps')
        self._ej(10, 'Press francés', 22, 10, 'Tríceps')          # +10 %
        self._ej(120, 'Extensión en polea', 30, 10, 'Tríceps')
        self._ej(10, 'Extensión en polea', 33, 10, 'Tríceps')     # +10 %
        self._ej(120, 'Press cerrado', 60, 10, 'Tríceps')
        self._ej(10, 'Press cerrado', 20, 10, 'Tríceps')          # -67 % → dudoso
        self._ej(120, 'Fondos en banco', 40, 10, 'Tríceps')
        self._ej(10, 'Fondos en banco', 100, 10, 'Tríceps')       # +150 % → dudoso
        triceps = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'triceps')
        self.assertAlmostEqual(triceps['pct'], 10.0, places=1)
        self.assertEqual(triceps['n_ejercicios'], 2)
        self.assertEqual(sorted(d['ejercicio'] for d in triceps['dudosos']),
                         ['Fondos en banco', 'Press cerrado'])
        self.assertNotEqual(triceps['mejor']['ejercicio'], 'Fondos en banco')

    def test_zona_con_solo_saltos_dudosos_no_se_colorea(self):
        self._ej(120, 'Curl femoral sentado', 40, 10, 'Isquios')
        self._ej(10, 'Curl femoral sentado', 100, 10, 'Isquios')
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        isquios = self._grupo(r, 'isquios')
        self.assertIsNone(isquios['pct'])
        self.assertEqual(isquios['estado'], 'sin_datos')
        self.assertEqual(len(isquios['dudosos']), 1)
        self.assertIn('revisa cómo se registró', isquios['lectura'])
        self.assertEqual(r['n_dudosos'], 1)

    def test_accesorio_ligero_no_es_error_ni_arrastra_la_mediana(self):
        self._ej(120, 'Buenos días', 50, 8, 'Isquios')
        self._ej(10, 'Buenos días', 45, 5, 'Isquios')                 # -17 %
        self._ej(120, 'Curl femoral tumbado', 70, 3, 'Isquios')
        self._ej(10, 'Curl femoral tumbado', 55, 5, 'Isquios')        # -18 %
        self._ej(120, 'Hiperextensiones inversas', 5, 8, 'Isquios')
        self._ej(10, 'Hiperextensiones inversas', 15, 12, 'Isquios')  # +232 %, ligero
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        isquios = self._grupo(r, 'isquios')
        self.assertEqual(isquios['estado'], 'retrocede')
        self.assertEqual(isquios['n_ejercicios'], 2)
        self.assertEqual(isquios['dudosos'], [])
        self.assertEqual([d['ejercicio'] for d in isquios['ligeros']],
                         ['Hiperextensiones inversas'])
        self.assertEqual(r['n_dudosos'], 0)

    def test_zona_con_solo_accesorios_ligeros(self):
        self._ej(120, 'Hiperextensiones inversas', 5, 8, 'Isquios')
        self._ej(10, 'Hiperextensiones inversas', 15, 12, 'Isquios')
        isquios = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'isquios')
        self.assertIsNone(isquios['pct'])
        self.assertIn('accesorios ligeros', isquios['lectura'])


class GruposMuscularesCompatTests(TestCase):
    """El modelo de usuario mantiene su forma (rapidos/lentos) sobre el cálculo nuevo."""

    def test_forma_compatible(self):
        user = get_user_model().objects.create_user(username='compat', password='x')
        cliente = Cliente.objects.get(user=user)
        rutina = Rutina.objects.create(nombre='r')
        hoy = date(2026, 10, 10)
        for dias, peso in ((120, 20), (10, 32)):
            e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina,
                                                fecha=hoy - timedelta(days=dias))
            EjercicioRealizado.objects.bulk_create([EjercicioRealizado(
                entreno=e, nombre_ejercicio='Press francés', grupo_muscular='Tríceps',
                peso_kg=peso, repeticiones=10, series=3,
            )])
        r = _get_grupos_musculares(cliente, hoy)
        self.assertEqual(r['rapidos'], [{'grupo': 'Tríceps', 'pct': 60.0}])
        self.assertEqual(r['lentos'], [])
        self.assertIn('Tríceps', r['descripcion'])


class EvolucionDesdeSeriesTests(_DatosEntrenoMixin, TestCase):
    """Con series individuales guardadas, el e1RM sale de la mejor serie real."""

    def _sesion_con_series(self, dias_atras, nombre, grupo, series, recuperacion=False):
        """series: [(peso, reps, es_aproximacion)]. Crea el agregado (media) y las series."""
        from entrenos.models import SerieRealizada
        from rutinas.models import EjercicioBase
        base, _ = EjercicioBase.objects.get_or_create(nombre=nombre, defaults={'grupo_muscular': grupo})
        trabajo = [s for s in series if not s[2]]
        media_peso = sum(p for p, _, _ in trabajo) / len(trabajo)
        media_reps = sum(r for _, r, _ in trabajo) // len(trabajo)
        self._ej(dias_atras, nombre, media_peso, media_reps, grupo, is_recovery_load=recuperacion)
        entreno = self._entrenos[self.HOY - timedelta(days=dias_atras)]
        SerieRealizada.objects.bulk_create([
            SerieRealizada(entreno=entreno, ejercicio=base, serie_numero=i + 1,
                           peso_kg=p, repeticiones=r, es_aproximacion=aprox, completado=True)
            for i, (p, r, aprox) in enumerate(series)
        ])

    def test_piramide_usa_la_mejor_serie_no_la_media(self):
        # Antes: 80×5 en todas las series. Ahora pirámide 60×8, 70×6, 90×4.
        # Media de "ahora" = 73.3×6 (e1RM 88) → parecería +-; la mejor serie 90×4 = 102.
        self._sesion_con_series(120, 'Curl femoral tumbado', 'Isquios',
                                [(80, 5, False), (80, 5, False), (80, 5, False)])
        self._sesion_con_series(10, 'Curl femoral tumbado', 'Isquios',
                                [(60, 8, False), (70, 6, False), (90, 4, False)])
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        isquios = self._grupo(r, 'isquios')
        # 80×(1+5/30)=93.33 → 90×(1+4/30)=102.0 → +9.3 %
        self.assertAlmostEqual(isquios['pct'], 9.3, places=1)

    def test_las_series_de_aproximacion_no_cuentan(self):
        self._sesion_con_series(120, 'Press banca con barra', 'Pecho',
                                [(100, 5, False)])
        self._sesion_con_series(10, 'Press banca con barra', 'Pecho',
                                [(140, 1, True), (100, 5, False)])
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertEqual(pecho['pct'], 0.0)

    def test_entrenos_sin_series_usan_el_agregado(self):
        self._ej(120, 'Press banca con barra', 100, 5, 'Pecho')          # legacy, sin series
        self._sesion_con_series(10, 'Press banca con barra', 'Pecho', [(110, 5, False)])
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertAlmostEqual(pecho['pct'], 10.0, places=1)

    def test_series_de_un_ejercicio_de_recuperacion_no_cuentan(self):
        self._sesion_con_series(120, 'Hip thrust con barra', 'Glúteos', [(100, 8, False)])
        self._sesion_con_series(10, 'Hip thrust con barra', 'Glúteos', [(110, 8, False)])
        self._sesion_con_series(5, 'Hip thrust con barra', 'Glúteos', [(200, 8, False)],
                                recuperacion=True)
        gluteos = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'gluteos')
        self.assertAlmostEqual(gluteos['pct'], 10.0, places=1)

    def test_el_detalle_indica_la_fuente(self):
        self._ej(120, 'Press banca con barra', 100, 5, 'Pecho')
        self._sesion_con_series(10, 'Press banca con barra', 'Pecho', [(110, 5, False)])
        detalle = comparar_ejercicios(self.cliente, hoy=self.HOY)
        press = next(e for e in detalle if e['ejercicio'] == 'Press banca con barra')
        self.assertEqual(press['antes']['fuente'], 'media')
        self.assertEqual(press['ahora']['fuente'], 'serie')


class DiagnosticoEvolucionCommandTests(_DatosEntrenoMixin, TestCase):
    HOY = date.today()

    def test_lista_ejercicios_con_sus_dos_marcas_y_marca_los_dudosos(self):
        from io import StringIO
        from django.core.management import call_command

        self._ej(120, 'Curl martillo', 40, 8, 'Bíceps')
        self._ej(10, 'Curl martillo', 100, 8, 'Bíceps', tipo_carga='total')
        self._ej(120, 'Hiperextensiones inversas', 5, 8, 'Isquios')
        self._ej(10, 'Hiperextensiones inversas', 15, 12, 'Isquios')
        self._ej(120, 'Press francés', 20, 10, 'Tríceps')
        self._ej(10, 'Press francés', 22, 10, 'Tríceps')
        out = StringIO()
        call_command('diagnosticar_evolucion_muscular', cliente=self.cliente.pk, stdout=out)
        texto = out.getvalue()
        self.assertIn('== Bíceps', texto)
        self.assertIn('Curl martillo: +150.0 %  ⚠ DUDOSO', texto)
        self.assertIn('100 kg × 8 (total)', texto)
        self.assertIn('Press francés: +10.0 %', texto)
        self.assertIn('Hiperextensiones inversas: +231.6 %  · ACCESORIO LIGERO', texto)
        self.assertIn('3 ejercicios · 1 dudosos · 1 accesorios ligeros', texto)

        out = StringIO()
        call_command('diagnosticar_evolucion_muscular', cliente=self.cliente.pk,
                     solo_dudosos=True, stdout=out)
        self.assertNotIn('Press francés', out.getvalue())

    def test_cliente_inexistente(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('diagnosticar_evolucion_muscular', cliente=999999)
