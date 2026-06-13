"""
Phase Evolución UI 4B — Historial desde fuente real.

Cubre:
1. `SourcePriorityTest`: Historial deja de leer el snapshot
   `SesionEntrenamiento` como verdad cuando discrepa de
   `EntrenoRealizado`/`EjercicioRealizado` (caso real id=303).
2. `SesionNormalSinRegresionTest`: sesiones normales (snapshot y
   EntrenoRealizado coinciden) renderizan igual que en Phase 3.
3. `SesionIncompletaSigueOcultaTest`: sesiones incompletas (id=306)
   siguen mostrando el chip neutro, sin activar cálculos de
   duración/volumen/RPE.
4. `RpeFallbackDesdeEjercicioTest`: el RPE se calcula desde
   EjercicioRealizado cuando existe, aunque sesion_detalle.rpe_medio
   sea None.
5. `DuracionDesdeEntrenoTest`: la duración mostrada viene de
   entreno.duracion_minutos, no del snapshot desactualizado.
"""

from datetime import date, timedelta

from entrenos.models import EjercicioRealizado, EntrenoRealizado, SesionEntrenamiento
from entrenos.tests_dashboard_evolucion_historial import DashboardEvolucionHistorialBase


class SourcePriorityTest(DashboardEvolucionHistorialBase):
    """Test 1 (el más importante): EntrenoRealizado gana sobre un snapshot zombi."""

    def test_volumen_real_gana_sobre_snapshot_zombi(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=5, volumen_total_kg=9850,
            duracion_minutos=60,
        )
        for i in range(5):
            EjercicioRealizado.objects.create(
                entreno=entreno, nombre_ejercicio=f'Ejercicio {i}',
                peso_kg=100, series=4, repeticiones=5, rpe=8,
                completado=True, fuente_datos='manual',
            )

        # El post_save de creación de EntrenoRealizado recalcula
        # volumen_total_kg=0 (todavía sin EjercicioRealizado) y crea el
        # snapshot SesionEntrenamiento zombi (0/0/0/0) — igual que el
        # caso real id=303. Restauramos el volumen real en EntrenoRealizado
        # sin tocar el snapshot.
        entreno.volumen_total_kg = 9850
        entreno.save(update_fields=['volumen_total_kg'])

        sesion_detalle = SesionEntrenamiento.objects.get(entreno=entreno)
        self.assertEqual(sesion_detalle.volumen_sesion, 0)

        _, html = self._get_html()
        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        self.assertIn('9850', tab_historial)
        self.assertIn('5/5', tab_historial)
        self.assertIn('60 min', tab_historial)
        self.assertNotIn('fa-dumbbell"></i> 0/0', tab_historial)
        self.assertNotIn('fa-weight-hanging"></i> 0 kg', tab_historial)
        self.assertNotIn('fa-clock"></i> 0 min', tab_historial)


class SesionNormalSinRegresionTest(DashboardEvolucionHistorialBase):
    """Test 2: sesiones normales (snapshot y EntrenoRealizado coinciden) sin regresión."""

    def test_sesion_normal_muestra_chips_habituales(self):
        entreno = self._add_entreno_normal(dias_offset=0)
        # `_add_entreno_normal` solo fija la duración en el snapshot
        # (Phase 3). Para que snapshot y EntrenoRealizado "coincidan"
        # (caso de esta prueba), igualamos también entreno.duracion_minutos.
        entreno.duracion_minutos = 45
        entreno.save(update_fields=['duracion_minutos'])

        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        self.assertIn('fa-clock', tab_historial)
        self.assertIn('45 min', tab_historial)
        self.assertIn('fa-dumbbell', tab_historial)
        self.assertIn('1/1', tab_historial)
        self.assertIn('fa-weight-hanging', tab_historial)
        self.assertIn('RPE 7', tab_historial)
        self.assertNotIn('Sesión abierta sin ejercicios registrados', tab_historial)


class SesionIncompletaSigueOcultaTest(DashboardEvolucionHistorialBase):
    """Test 3: sesiones incompletas (id=306) siguen mostrando el chip neutro."""

    def test_sesion_incompleta_sigue_mostrando_chip_neutro(self):
        self._add_entreno_incompleto(dias_offset=0)
        _, html = self._get_html()

        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        self.assertIn('Sesión abierta sin ejercicios registrados', tab_historial)
        self.assertNotIn('0/0', tab_historial)
        self.assertNotIn('0 min', tab_historial)
        self.assertNotIn('fa-dumbbell', tab_historial)
        self.assertNotIn('fa-weight-hanging', tab_historial)


class RpeFallbackDesdeEjercicioTest(DashboardEvolucionHistorialBase):
    """Test 4: RPE calculado desde EjercicioRealizado cuando sesion_detalle.rpe_medio es None."""

    def test_rpe_calculado_desde_ejercicio_realizado(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=2, volumen_total_kg=500,
            duracion_minutos=50,
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
        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={
                'duracion_minutos': 50,
                'ejercicios_completados': 2,
                'ejercicios_totales': 2,
                'volumen_sesion': 500,
                'rpe_medio': None,
            },
        )

        _, html = self._get_html()
        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        # Promedio de RPE 8 y 6 = 7.0
        self.assertIn('RPE 7', tab_historial)


class DuracionDesdeEntrenoTest(DashboardEvolucionHistorialBase):
    """Test 5: la duración mostrada viene de entreno.duracion_minutos, no del snapshot."""

    def test_duracion_viene_de_entreno_no_de_snapshot(self):
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=date.today(),
            fuente_datos='manual', numero_ejercicios=1, volumen_total_kg=120,
            duracion_minutos=75,
        )
        EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio='Remo',
            peso_kg=40, series=3, repeticiones=10, rpe=7,
            completado=True, fuente_datos='manual',
        )
        SesionEntrenamiento.objects.update_or_create(
            entreno=entreno,
            defaults={
                'duracion_minutos': 30,
                'ejercicios_completados': 1,
                'ejercicios_totales': 1,
                'volumen_sesion': 120,
                'rpe_medio': 7,
            },
        )

        _, html = self._get_html()
        tab_historial = self._extraer_tab(html, 'rb-tab-historial')

        self.assertIn('75 min', tab_historial)
        self.assertNotIn('30 min', tab_historial)
