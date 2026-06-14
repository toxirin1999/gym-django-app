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

Phase Evolución Data 5A — Informe de impacto:
6-10. Ver clases `InformeImpacto*` para clasificación, sesiones_perfectas,
desglose por cliente, top cambios y verificación de no-escritura.

Phase Evolución Data 5A.1 — Auditoría de perfección antes de backfill:
11. `AuditoriaPerfeccionNoEscribeTest`: --auditoria-perfeccion no modifica BD.
12. `AuditoriaPerfeccionPatronCeroNTest`: sesión 0/N -> N/N con
    numero_ejercicios coherente → veredicto "completa".
13. `AuditoriaPerfeccionVeredictoDudosaTest`: sesión que gana perfección
    pero numero_ejercicios no coincide con EjercicioRealizado reales →
    veredicto "dudosa".
14. `AuditoriaPerfeccionControlTest`: sesión ya perfecta antes y después →
    aparece en la sección de control.
15. `AuditoriaPerfeccionResumenTest`: el resumen final cuenta
    auditadas/completas/dudosas/incompletas correctamente.

Phase Evolución Data 5B — Backfill completo (--aplicar):
16. `AplicarBackfillZombiCompletoTest`: --aplicar corrige un snapshot zombi
    completo y muestra la línea [aplicado] + el informe de impacto.
17. `AplicarBackfillMixtoTest`: --aplicar corrige un snapshot mixto
    (duracion ya correcta, resto desincronizado).
18. `AplicarBackfillSoloSeriesTest`: --aplicar corrige solo
    series_completadas/series_totales cuando es lo único desincronizado.
19. `AplicarBackfillIdempotenteTest`: una segunda ejecución de --aplicar
    no vuelve a corregir nada (Corregidos: 0).
20. `AplicarConDryRunNoEscribeTest`: --aplicar --dry-run no escribe en BD
    (--dry-run tiene prioridad) pero muestra el informe de impacto.
21. `InformeAntesDespuesCoherenteTest`: el porcentaje "despues" del informe
    tras --aplicar coincide con una consulta real a la BD.
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

    def _crear_entreno_gana_perfeccion(self, cliente=None, numero_ejercicios=1, fecha=None):
        """EntrenoRealizado con 1 EjercicioRealizado (4 series, completado) y
        snapshot con series_completadas=0 (resto correcto): el backfill lo
        pasaría de series 0/4 a 4/4, ganando perfección."""
        cliente = cliente or self.cliente
        fecha = fecha or date.today()
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=self.rutina, fecha=fecha,
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Remo',
            peso_kg=50, series=4, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = numero_ejercicios
        entreno.volumen_total_kg = 200
        entreno.duracion_minutos = 40
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        sesion.duracion_minutos = 40
        sesion.ejercicios_totales = 1
        sesion.ejercicios_completados = 1
        sesion.volumen_sesion = 200
        sesion.rpe_medio = 7.0
        sesion.series_totales = 4
        sesion.series_completadas = 0
        sesion.save(update_fields=[
            'duracion_minutos', 'ejercicios_totales', 'ejercicios_completados',
            'volumen_sesion', 'rpe_medio', 'series_totales', 'series_completadas',
        ])
        return entreno

    def _crear_entreno_control_perfecto(self, cliente=None, fecha=None):
        """EntrenoRealizado cuyo snapshot ya es perfecto antes y después
        (series_completadas == series_totales > 0, sin cambios)."""
        cliente = cliente or self.cliente
        fecha = fecha or date.today()
        entreno = EntrenoRealizado.objects.create(
            cliente=cliente, rutina=self.rutina, fecha=fecha,
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Press',
            peso_kg=40, series=4, repeticiones=8, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 160
        entreno.duracion_minutos = 35
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        SesionEntrenamiento.objects.filter(entreno=entreno).update(
            duracion_minutos=35, ejercicios_completados=1, ejercicios_totales=1,
            series_completadas=4, series_totales=4, volumen_sesion=160, rpe_medio=8.0,
        )
        return entreno


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


class AuditoriaPerfeccionNoEscribeTest(BackfillSesionEntrenamientoTestBase):
    """Test 11: --auditoria-perfeccion no modifica la BD."""

    def test_auditoria_no_modifica_bd(self):
        entreno = self._crear_entreno_gana_perfeccion()

        salida = self._run_command('--auditoria-perfeccion')

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.series_completadas, 0)
        self.assertEqual(sesion.series_totales, 4)
        self.assertIn('=== Auditoría de perfección', salida)


class AuditoriaPerfeccionPatronCeroNTest(BackfillSesionEntrenamientoTestBase):
    """Test 12: sesión 0/N -> N/N con numero_ejercicios coherente → veredicto completa."""

    def test_patron_cero_n_veredicto_completa(self):
        entreno = self._crear_entreno_gana_perfeccion(numero_ejercicios=1)

        salida = self._run_command('--auditoria-perfeccion')

        self.assertIn('Patrón 0/N -> N/N', salida)
        self.assertIn(f'entreno_id={entreno.id}', salida)
        self.assertIn('series: 0/4 -> 4/4', salida)
        self.assertIn('veredicto: completa', salida)


class AuditoriaPerfeccionVeredictoDudosaTest(BackfillSesionEntrenamientoTestBase):
    """Test 13: gana perfección pero numero_ejercicios no coincide con
    EjercicioRealizado reales → veredicto dudosa."""

    def test_numero_ejercicios_no_coincide_veredicto_dudosa(self):
        # numero_ejercicios=2 pero solo hay 1 EjercicioRealizado registrado.
        entreno = self._crear_entreno_gana_perfeccion(numero_ejercicios=2)

        salida = self._run_command('--auditoria-perfeccion')

        self.assertIn(f'entreno_id={entreno.id}', salida)
        self.assertIn('numero_ejercicios=2 ejercicios_realizados=1', salida)
        self.assertIn('veredicto: dudosa', salida)


class AuditoriaPerfeccionControlTest(BackfillSesionEntrenamientoTestBase):
    """Test 14: sesión ya perfecta antes y después aparece como control."""

    def test_sesion_ya_perfecta_aparece_en_control(self):
        entreno = self._crear_entreno_control_perfecto()

        salida = self._run_command('--auditoria-perfeccion')

        self.assertIn('Control — ya perfectas antes', salida)
        self.assertIn(f'entreno_id={entreno.id}', salida)
        self.assertIn('control: ya era perfecta y sigue siéndolo', salida)


class AuditoriaPerfeccionResumenTest(BackfillSesionEntrenamientoTestBase):
    """Test 15: el resumen final cuenta auditadas/completas/dudosas/incompletas."""

    def test_resumen_cuenta_veredictos(self):
        self._crear_entreno_gana_perfeccion(numero_ejercicios=1)  # completa
        self._crear_entreno_gana_perfeccion(numero_ejercicios=2)  # dudosa
        self._crear_entreno_control_perfecto()  # control, completa

        salida = self._run_command('--auditoria-perfeccion')

        self.assertIn('Auditadas: 3', salida)
        self.assertIn('Completas: 2', salida)
        self.assertIn('Dudosas: 1', salida)
        self.assertIn('Incompletas: 0', salida)


class AplicarBackfillZombiCompletoTest(BackfillSesionEntrenamientoTestBase):
    """Test 16: --aplicar corrige un snapshot zombi completo (caso id=303) y
    muestra la línea [aplicado] + el informe de impacto."""

    def test_aplicar_corrige_zombi_completo(self):
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
        entreno.numero_ejercicios = 2
        entreno.volumen_total_kg = 900
        entreno.duracion_minutos = 55
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        salida = self._run_command('--aplicar')

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 55)
        self.assertEqual(sesion.series_completadas, 6)
        self.assertEqual(sesion.series_totales, 6)
        self.assertEqual(int(sesion.volumen_sesion), 900)
        self.assertEqual(sesion.rpe_medio, 7.0)
        self.assertIn('Corregidos: 1', salida)
        self.assertIn(f'[aplicado] entreno_id={entreno.id}', salida)
        self.assertIn('=== Informe de impacto', salida)


class AplicarBackfillMixtoTest(BackfillSesionEntrenamientoTestBase):
    """Test 17: --aplicar corrige un snapshot mixto (duracion ya correcta,
    resto desincronizado)."""

    def test_aplicar_corrige_mixto(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual',
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Curl',
            peso_kg=20, series=4, repeticiones=12, rpe=8,
            completado=True, fuente_datos='manual',
        )
        entreno.numero_ejercicios = 1
        entreno.volumen_total_kg = 300
        entreno.duracion_minutos = 30
        entreno.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])
        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        sesion.duracion_minutos = 30  # ya correcto, no debe contar como cambio
        sesion.save(update_fields=['duracion_minutos'])

        salida = self._run_command('--aplicar')

        sesion.refresh_from_db()
        self.assertEqual(sesion.duracion_minutos, 30)
        self.assertEqual(sesion.ejercicios_totales, 1)
        self.assertEqual(sesion.ejercicios_completados, 1)
        self.assertEqual(sesion.series_totales, 4)
        self.assertEqual(sesion.series_completadas, 4)
        self.assertEqual(int(sesion.volumen_sesion), 300)
        self.assertEqual(sesion.rpe_medio, 8.0)
        self.assertIn('Corregidos: 1', salida)
        self.assertIn('mixtos: 1', salida)


class AplicarBackfillSoloSeriesTest(BackfillSesionEntrenamientoTestBase):
    """Test 18: --aplicar corrige solo series_completadas/series_totales
    cuando es lo único desincronizado."""

    def test_aplicar_corrige_solo_series(self):
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
        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        sesion.duracion_minutos = 40
        sesion.ejercicios_totales = 1
        sesion.ejercicios_completados = 1
        sesion.volumen_sesion = 200
        sesion.rpe_medio = 7.0
        sesion.series_totales = 0
        sesion.series_completadas = 0
        sesion.save(update_fields=[
            'duracion_minutos', 'ejercicios_totales', 'ejercicios_completados',
            'volumen_sesion', 'rpe_medio', 'series_totales', 'series_completadas',
        ])

        salida = self._run_command('--aplicar')

        sesion.refresh_from_db()
        self.assertEqual(sesion.duracion_minutos, 40)
        self.assertEqual(sesion.ejercicios_totales, 1)
        self.assertEqual(sesion.ejercicios_completados, 1)
        self.assertEqual(int(sesion.volumen_sesion), 200)
        self.assertEqual(sesion.rpe_medio, 7.0)
        self.assertEqual(sesion.series_totales, 4)
        self.assertEqual(sesion.series_completadas, 4)
        self.assertIn('Corregidos: 1', salida)
        self.assertIn('solo series: 1', salida)


class AplicarBackfillIdempotenteTest(BackfillSesionEntrenamientoTestBase):
    """Test 19: una segunda ejecución de --aplicar no vuelve a corregir nada."""

    def test_segunda_ejecucion_no_corrige_nada(self):
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

        primera = self._run_command('--aplicar')
        self.assertIn('Corregidos: 1', primera)

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        valores_tras_primera = (
            sesion.duracion_minutos, sesion.ejercicios_totales,
            sesion.ejercicios_completados, sesion.series_totales,
            sesion.series_completadas, int(sesion.volumen_sesion), sesion.rpe_medio,
        )

        segunda = self._run_command('--aplicar')
        self.assertIn('Corregidos: 0', segunda)

        sesion.refresh_from_db()
        valores_tras_segunda = (
            sesion.duracion_minutos, sesion.ejercicios_totales,
            sesion.ejercicios_completados, sesion.series_totales,
            sesion.series_completadas, int(sesion.volumen_sesion), sesion.rpe_medio,
        )
        self.assertEqual(valores_tras_primera, valores_tras_segunda)


class AplicarConDryRunNoEscribeTest(BackfillSesionEntrenamientoTestBase):
    """Test 20: --aplicar --dry-run no escribe en BD (--dry-run tiene
    prioridad) pero muestra el informe de impacto."""

    def test_aplicar_con_dry_run_no_escribe(self):
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

        salida = self._run_command('--aplicar', '--dry-run')

        sesion = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion.duracion_minutos, 0)
        self.assertEqual(sesion.volumen_sesion, 0)
        self.assertIsNone(sesion.rpe_medio)
        self.assertIn('Se corregirían: 1', salida)
        self.assertIn('=== Informe de impacto', salida)
        self.assertNotIn('[aplicado]', salida)


class InformeAntesDespuesCoherenteTest(BackfillSesionEntrenamientoTestBase):
    """Test 21: el porcentaje "despues" del informe tras --aplicar coincide
    con una consulta real a la BD."""

    def test_porcentaje_despues_coincide_con_bd(self):
        from django.db.models import F

        # Zombi (0==0 antes) con un ejercicio no completado → 3/6 después,
        # no perfecta.
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
            completado=False, fuente_datos='manual',
        )
        entreno_zombi.numero_ejercicios = 2
        entreno_zombi.volumen_total_kg = 900
        entreno_zombi.duracion_minutos = 55
        entreno_zombi.save(update_fields=['numero_ejercicios', 'volumen_total_kg', 'duracion_minutos'])

        # Sesión ya correcta y perfecta (series_completadas == series_totales > 0).
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

        salida = self._run_command('--aplicar')

        # antes: 2/2 (0==0 y 4==4) = 100.0% | despues: 1/2 (solo entreno_ok) = 50.0%
        self.assertIn('antes: 2/2 = 100.0%', salida)
        self.assertIn('despues: 1/2 = 50.0%', salida)

        perfectas_reales = SesionEntrenamiento.objects.filter(
            entreno__cliente=self.cliente,
            series_completadas=F('series_totales'),
        ).count()
        total_reales = SesionEntrenamiento.objects.filter(
            entreno__cliente=self.cliente,
        ).count()
        self.assertEqual(perfectas_reales, 1)
        self.assertEqual(total_reales, 2)
