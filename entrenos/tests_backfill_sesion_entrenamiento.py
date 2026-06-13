"""
Phase Evolución/Data 5 — Backfill controlado de SesionEntrenamiento.

Cubre:
1. `ZombieSnapshotBackfillTest`: snapshot zombi (0/0/0/0/None) con
   EntrenoRealizado real (caso id=303) → el comando corrige
   duracion_minutos, ejercicios_completados/totales,
   series_completadas/totales, volumen_sesion y rpe_medio.
2. `SnapshotCorrectoSinCambiosTest`: snapshot ya correcto no se modifica.
3. `SesionIncompletaNoSeCorrigeTest`: sesión incompleta real (caso id=306)
   mantiene su snapshot 0/0/0/0/None — no se "corrige" a valores falsos.
4. `DryRunNoEscribeTest`: --dry-run no modifica la BD, solo reporta.
5. `FiltroClienteIdTest`: --cliente-id limita el alcance a un cliente.
"""

from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SesionEntrenamiento
from rutinas.models import Rutina


class BackfillSesionEntrenamientoTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_backfill_data5', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestBackfillData5', 'dias_disponibles': 3},
        )
        self.rutina, _ = Rutina.objects.get_or_create(nombre='_test_backfill_data5')

    def _run_command(self, *args):
        out = StringIO()
        call_command('backfill_sesion_entrenamiento', *args, stdout=out)
        return out.getvalue()


class ZombieSnapshotBackfillTest(BackfillSesionEntrenamientoTestBase):
    """Test 1 (el más importante): snapshot zombi se corrige con datos reales (caso id=303)."""

    def test_snapshot_zombi_se_corrige_con_datos_reales(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Sentadilla',
            peso_kg=100, series=3, repeticiones=5, rpe=8,
            completado=True, fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press militar',
            peso_kg=40, series=3, repeticiones=8, rpe=6,
            completado=True, fuente_datos='manual',
        )

        # Como en el caso real id=303: el post_save de creación deja un
        # snapshot zombi (0/0/0/0/None) antes de que existan los
        # EjercicioRealizado. Los datos reales (duración, volumen, número
        # de ejercicios) llegan después, sin re-disparar el snapshot.
        entreno.numero_ejercicios = 2
        entreno.volumen_total_kg = 900
        entreno.duracion_minutos = 55
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 0)
        self.assertEqual(sesion.volumen_sesion, 0)
        self.assertEqual(sesion.ejercicios_totales, 0)
        self.assertEqual(sesion.series_totales, 0)
        self.assertIsNone(sesion.rpe_medio)

        salida = self._run_command()

        sesion.refresh_from_db()
        self.assertEqual(sesion.duracion_minutos, 55)
        self.assertEqual(sesion.ejercicios_completados, 2)
        self.assertEqual(sesion.ejercicios_totales, 2)
        self.assertEqual(sesion.series_completadas, 6)
        self.assertEqual(sesion.series_totales, 6)
        self.assertEqual(int(sesion.volumen_sesion), 900)
        self.assertEqual(sesion.rpe_medio, 7.0)
        self.assertIn('Corregidos: 1', salida)


class SnapshotCorrectoSinCambiosTest(BackfillSesionEntrenamientoTestBase):
    """Test 2: snapshot que ya coincide con EntrenoRealizado no se modifica."""

    def test_snapshot_correcto_no_se_modifica(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Remo',
            peso_kg=50, series=4, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 200
        entreno.duracion_minutos = 40
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={
                'duracion_minutos': 40,
                'ejercicios_completados': 1,
                'ejercicios_totales': 1,
                'series_completadas': 4,
                'series_totales': 4,
                'volumen_sesion': 200,
                'rpe_medio': 7.0,
            },
        )

        salida = self._run_command()

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 40)
        self.assertEqual(int(sesion.volumen_sesion), 200)
        self.assertEqual(sesion.rpe_medio, 7.0)
        self.assertIn('Corregidos: 0', salida)


class SesionIncompletaNoSeCorrigeTest(BackfillSesionEntrenamientoTestBase):
    """Test 3: sesión incompleta real (caso id=306) mantiene su snapshot 0/0/0/0/None."""

    def test_sesion_incompleta_no_se_corrige(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=0, volumen_total_kg=0,
        )
        self.assertTrue(entreno.es_sesion_incompleta)

        salida = self._run_command()

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 0)
        self.assertEqual(sesion.ejercicios_totales, 0)
        self.assertEqual(sesion.ejercicios_completados, 0)
        self.assertEqual(sesion.series_totales, 0)
        self.assertEqual(sesion.series_completadas, 0)
        self.assertEqual(int(sesion.volumen_sesion), 0)
        self.assertIsNone(sesion.rpe_medio)
        self.assertIn('Omitidos (incompletos): 1', salida)


class DryRunNoEscribeTest(BackfillSesionEntrenamientoTestBase):
    """Test 4: --dry-run no modifica la BD, solo reporta."""

    def test_dry_run_no_modifica_bd(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Curl',
            peso_kg=20, series=3, repeticiones=12, rpe=6,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 300
        entreno.duracion_minutos = 30
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        salida = self._run_command('--dry-run')

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.volumen_sesion, 0)
        self.assertEqual(sesion.duracion_minutos, 0)
        self.assertIsNone(sesion.rpe_medio)
        self.assertIn('Se corregirían: 1', salida)


class FiltroClienteIdTest(BackfillSesionEntrenamientoTestBase):
    """Test 5: --cliente-id limita el alcance a un cliente."""

    def test_filtro_cliente_id_limita_alcance(self):
        otro_user = User.objects.create_user(username='tester_backfill_data5_otro', password='x')
        otro_cliente, _ = Cliente.objects.get_or_create(
            user=otro_user, defaults={'nombre': 'TestBackfillData5Otro', 'dias_disponibles': 3},
        )

        entreno_propio = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_propio, nombre_ejercicio='Curl',
            peso_kg=20, series=3, repeticiones=12, rpe=6,
            completado=True, fuente_datos='manual',
        )
        entreno_propio.numero_ejercicios = 1
        entreno_propio.volumen_total_kg = 150
        entreno_propio.duracion_minutos = 20
        entreno_propio.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        entreno_ajeno = EntrenoRealizado.objects.create(
            cliente=otro_cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_ajeno, nombre_ejercicio='Press',
            peso_kg=40, series=4, repeticiones=8, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno_ajeno.numero_ejercicios = 1
        entreno_ajeno.volumen_total_kg = 400
        entreno_ajeno.duracion_minutos = 50
        entreno_ajeno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        salida = self._run_command('--cliente-id', str(self.cliente.id))

        sesion_propia = SesionEntrenamiento.objects.get(entreno=entreno_propio)
        sesion_ajena = SesionEntrenamiento.objects.get(entreno=entreno_ajeno)

        self.assertEqual(int(sesion_propia.volumen_sesion), 150)
        self.assertEqual(sesion_ajena.volumen_sesion, 0)
        self.assertIn('Revisados: 1', salida)


class InformeImpactoClasificacionTest(BackfillSesionEntrenamientoTestBase):
    """Test 6: --informe-impacto clasifica snapshots en zombi completo / mixto / solo series."""

    def test_clasificacion_zombi_mixto_solo_series(self):
        # Zombi completo: snapshot 0/0/0/0/None, EntrenoRealizado con datos reales.
        entreno_zombi = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_zombi, nombre_ejercicio='Sentadilla',
            peso_kg=100, series=3, repeticiones=5, rpe=8,
            completado=True, fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_zombi, nombre_ejercicio='Press militar',
            peso_kg=40, series=3, repeticiones=8, rpe=6,
            completado=True, fuente_datos='manual',
        )
        entreno_zombi.numero_ejercicios = 2
        entreno_zombi.volumen_total_kg = 900
        entreno_zombi.duracion_minutos = 55
        entreno_zombi.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        # Mixto: duracion ya correcta (como id=303), el resto desincronizado.
        entreno_mixto = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_mixto, nombre_ejercicio='Curl',
            peso_kg=20, series=4, repeticiones=12, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno_mixto.numero_ejercicios = 1
        entreno_mixto.volumen_total_kg = 300
        entreno_mixto.duracion_minutos = 30
        entreno_mixto.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        sesion_mixto = SesionEntrenamiento.objects.get(entreno=entreno_mixto)
        sesion_mixto.duracion_minutos = 30  # ya correcto, no debe contar como cambio
        sesion_mixto.save(update_fields=['duracion_minutos'])

        # Solo series: todo correcto salvo series_completadas/series_totales.
        entreno_series = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_series, nombre_ejercicio='Remo',
            peso_kg=50, series=4, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno_series.numero_ejercicios = 1
        entreno_series.volumen_total_kg = 200
        entreno_series.duracion_minutos = 40
        entreno_series.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        sesion_series = SesionEntrenamiento.objects.get(entreno=entreno_series)
        sesion_series.duracion_minutos = 40
        sesion_series.ejercicios_totales = 1
        sesion_series.ejercicios_completados = 1
        sesion_series.volumen_sesion = 200
        sesion_series.rpe_medio = 7.0
        sesion_series.series_totales = 0
        sesion_series.series_completadas = 0
        sesion_series.save(update_fields=[
            'duracion_minutos', 'ejercicios_totales', 'ejercicios_completados',
            'volumen_sesion', 'rpe_medio', 'series_totales', 'series_completadas',
        ])

        salida = self._run_command('--informe-impacto')

        self.assertIn('Corregibles: 3', salida)
        self.assertIn('zombis completos: 1', salida)
        self.assertIn('mixtos: 1', salida)
        self.assertIn('solo series: 1', salida)


class InformeImpactoSesionesPerfectasTest(BackfillSesionEntrenamientoTestBase):
    """Test 7: el informe calcula sesiones_perfectas y porcentaje_perfeccion antes/después."""

    def test_sesiones_perfectas_antes_despues(self):
        # Dos sesiones zombi (0/0/0/0/None): "perfectas" antes (0==0), pero con
        # un ejercicio no completado, NO serán perfectas después (3 != 6).
        for _ in range(2):
            entreno = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
                fuente_datos='manual',
            )
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio='Sentadilla',
                peso_kg=100, series=3, repeticiones=5, rpe=8,
                completado=True, fuente_datos='manual',
            )
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio='Press militar',
                peso_kg=40, series=3, repeticiones=8, rpe=6,
                completado=False, fuente_datos='manual',
            )
            entreno.numero_ejercicios = 2
            entreno.volumen_total_kg = 900
            entreno.duracion_minutos = 55
            entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        # Una sesión ya correcta y perfecta (series_completadas == series_totales > 0).
        entreno_ok = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_ok, nombre_ejercicio='Remo',
            peso_kg=50, series=4, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno_ok.numero_ejercicios = 1
        entreno_ok.volumen_total_kg = 200
        entreno_ok.duracion_minutos = 40
        entreno_ok.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        SesionEntrenamiento.objects.filter(entreno=entreno_ok).update(
            duracion_minutos=40, ejercicios_completados=1, ejercicios_totales=1,
            series_completadas=4, series_totales=4, volumen_sesion=200, rpe_medio=7.0,
        )

        salida = self._run_command('--informe-impacto')

        # antes: 3/3 (los 2 zombis 0==0, mas la correcta 4==4) = 100.0%
        # despues: 1/3 (los zombis pasan a 3!=6, solo queda la correcta) = 33.3%
        self.assertIn('antes: 3/3 = 100.0%', salida)
        self.assertIn('despues: 1/3 = 33.3%', salida)


class InformeImpactoPorClienteTest(BackfillSesionEntrenamientoTestBase):
    """Test 8: el informe desglosa corregibles y sesiones_perfectas por cliente."""

    def test_desglose_por_cliente(self):
        otro_user = User.objects.create_user(username='tester_backfill_data5a_otro', password='x')
        otro_cliente, _ = Cliente.objects.get_or_create(
            user=otro_user, defaults={'nombre': 'TestBackfillData5AOtro', 'dias_disponibles': 3},
        )

        # Cliente propio: 1 sesión zombi corregible.
        entreno_propio = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_propio, nombre_ejercicio='Curl',
            peso_kg=20, series=3, repeticiones=12, rpe=6,
            completado=True, fuente_datos='manual',
        )
        entreno_propio.numero_ejercicios = 1
        entreno_propio.volumen_total_kg = 150
        entreno_propio.duracion_minutos = 20
        entreno_propio.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        # Cliente ajeno: 1 sesión ya correcta (no corregible).
        entreno_ajeno = EntrenoRealizado.objects.create(
            cliente=otro_cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_ajeno, nombre_ejercicio='Press',
            peso_kg=40, series=4, repeticiones=8, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno_ajeno.numero_ejercicios = 1
        entreno_ajeno.volumen_total_kg = 400
        entreno_ajeno.duracion_minutos = 50
        entreno_ajeno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        SesionEntrenamiento.objects.filter(entreno=entreno_ajeno).update(
            duracion_minutos=50, ejercicios_completados=1, ejercicios_totales=1,
            series_completadas=4, series_totales=4, volumen_sesion=400, rpe_medio=8.0,
        )

        salida = self._run_command('--informe-impacto')

        self.assertIn(f'cliente_id={self.cliente.id}: corregibles=1', salida)
        self.assertIn(f'cliente_id={otro_cliente.id}: corregibles=0', salida)


class InformeImpactoTopCambiosTest(BackfillSesionEntrenamientoTestBase):
    """Test 9: el informe lista transiciones de perfección y mayores cambios de volumen/RPE."""

    def test_top_cambios_perfeccion_y_volumen(self):
        # Pierde perfección: zombi (0==0 antes) con un ejercicio no completado
        # → 3/6 después, no perfecta.
        entreno_pierde = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_pierde, nombre_ejercicio='Sentadilla',
            peso_kg=100, series=3, repeticiones=5, rpe=8,
            completado=True, fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_pierde, nombre_ejercicio='Press militar',
            peso_kg=40, series=3, repeticiones=8, rpe=6,
            completado=False, fuente_datos='manual',
        )
        entreno_pierde.numero_ejercicios = 2
        entreno_pierde.volumen_total_kg = 900
        entreno_pierde.duracion_minutos = 55
        entreno_pierde.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        # Gana perfección: snapshot dice series 2/4 (no perfecta), real es 4/4
        # (único ejercicio completado con 4 series).
        entreno_gana = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno_gana, nombre_ejercicio='Remo',
            peso_kg=50, series=4, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno_gana.numero_ejercicios = 1
        entreno_gana.volumen_total_kg = 200
        entreno_gana.duracion_minutos = 40
        entreno_gana.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        sesion_gana = SesionEntrenamiento.objects.get(entreno=entreno_gana)
        sesion_gana.duracion_minutos = 40
        sesion_gana.ejercicios_totales = 1
        sesion_gana.ejercicios_completados = 1
        sesion_gana.volumen_sesion = 200
        sesion_gana.rpe_medio = 7.0
        sesion_gana.series_totales = 4
        sesion_gana.series_completadas = 2
        sesion_gana.save(update_fields=[
            'duracion_minutos', 'ejercicios_totales', 'ejercicios_completados',
            'volumen_sesion', 'rpe_medio', 'series_totales', 'series_completadas',
        ])

        salida = self._run_command('--informe-impacto')

        self.assertIn('Pierden perfeccion', salida)
        self.assertIn(f'entreno_id={entreno_pierde.id}', salida)
        self.assertIn('Ganan perfeccion', salida)
        self.assertIn(f'entreno_id={entreno_gana.id}', salida)
        self.assertIn('Mayor cambio de volumen', salida)
        self.assertIn(
            f'entreno_id={entreno_pierde.id} cliente={self.cliente.id} '
            f'fecha={entreno_pierde.fecha}: volumen 0 -> 900',
            salida,
        )
        self.assertIn('Mayor cambio de RPE', salida)


class InformeImpactoNoEscribeTest(BackfillSesionEntrenamientoTestBase):
    """Test 10: --informe-impacto no modifica la BD, incluso sin --dry-run explícito."""

    def test_informe_impacto_no_modifica_bd(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Sentadilla',
            peso_kg=100, series=3, repeticiones=5, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 300
        entreno.duracion_minutos = 30
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        salida = self._run_command('--informe-impacto')

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 0)
        self.assertEqual(sesion.volumen_sesion, 0)
        self.assertEqual(sesion.ejercicios_totales, 0)
        self.assertEqual(sesion.series_totales, 0)
        self.assertIsNone(sesion.rpe_medio)
        self.assertIn('=== Informe de impacto', salida)
