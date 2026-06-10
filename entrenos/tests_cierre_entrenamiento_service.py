"""
Phase 62F — Cierre de entrenamiento.

construir_contexto_cierre(cliente, entreno) arma el contexto de la pantalla
de cierre post-entreno: resumen de la sesión, lectura del plan (solo si hubo
freno), cambios relevantes por ejercicio frente a la sesión anterior, qué
esperar la próxima vez, PRs establecidos y el mensaje JOI del día (si existe).

Checklist:
1. Resumen con sesion_detalle (SesionEntrenamiento) → usa sus campos.
2. Resumen sin sesion_detalle → fallback a EntrenoRealizado + ejercicios.
3. Cambios relevantes: mantenida / subida / bajada / tope de máquina / sin anterior.
4. lectura_plan y proxima_vez: presentes solo si accion != progresion_permitida.
5. prs: solo records con superado=False.
6. joi_mensaje: presente solo si hay MensajeJOI trigger=entreno_completado del día.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, EjercicioRealizado, SesionEntrenamiento, RecordPersonal
from entrenos.services.cierre_entrenamiento_service import construir_contexto_cierre
from joi.models import MensajeJOI
from rutinas.models import Rutina


def _permiso(accion, motivo='ok'):
    return {
        'accion': accion,
        'motivo': motivo,
        'mensaje': '',
        'aplica_a_principales': accion == 'mantener_carga',
        'aplica_a_accesorios': accion in ('mantener_carga', 'reducir_accesorios'),
        'hay_datos_semana': True,
    }


class CierreEntrenamientoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester_cierre62f', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestCierre62F', 'dias_disponibles': 4},
        )
        self.rutina = Rutina.objects.create(nombre='Push Day')

    def _crear_entreno(self, fecha, **extra):
        defaults = {'cliente': self.cliente, 'rutina': self.rutina, 'fecha': fecha}
        defaults.update(extra)
        return EntrenoRealizado.objects.create(**defaults)

    def _crear_ejercicio(self, entreno, **extra):
        defaults = {
            'entreno': entreno,
            'nombre_ejercicio': 'Press banca',
            'grupo_muscular': 'pecho',
            'peso_kg': 60.0,
            'series': 4,
            'repeticiones': 8,
            'orden': 0,
            'completado': True,
        }
        defaults.update(extra)
        return EjercicioRealizado.objects.create(**defaults)


# ── Caso 1-2: resumen de sesión ───────────────────────────────────────────────

class TestResumenSesion(CierreEntrenamientoBase):
    def test_resumen_usa_sesion_detalle_si_existe(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)
        # La señal de gamificación ya creó sesion_detalle con ceros al guardar
        # el entreno; la actualizamos como lo haría guardar_entrenamiento_activo.
        SesionEntrenamiento.objects.filter(entreno=entreno).update(
            duracion_minutos=55,
            series_completadas=16,
            series_totales=16,
            ejercicios_completados=4,
            ejercicios_totales=4,
            rpe_medio=7.5,
            volumen_sesion=1920,
        )
        entreno = EntrenoRealizado.objects.get(pk=entreno.pk)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        resumen = ctx['resumen']
        self.assertEqual(resumen['titulo'], 'Push Day')
        self.assertEqual(resumen['n_ejercicios'], 4)
        self.assertEqual(resumen['n_series'], 16)
        self.assertEqual(resumen['rpe_medio'], 7.5)
        self.assertEqual(resumen['duracion_minutos'], 55)
        self.assertEqual(resumen['volumen_kg'], 1920.0)

    def test_resumen_sin_sesion_detalle_usa_fallback(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, series=4, repeticiones=8)
        self._crear_ejercicio(entreno, nombre_ejercicio='Remo', series=3, repeticiones=10)
        # Caso defensivo: sin sesion_detalle (p.ej. la señal de gamificación falló)
        SesionEntrenamiento.objects.filter(entreno=entreno).delete()
        EntrenoRealizado.objects.filter(pk=entreno.pk).update(duracion_minutos=40, volumen_total_kg=480)
        entreno = EntrenoRealizado.objects.get(pk=entreno.pk)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        resumen = ctx['resumen']
        self.assertEqual(resumen['titulo'], 'Push Day')
        self.assertEqual(resumen['n_ejercicios'], 2)
        self.assertEqual(resumen['n_series'], 7)
        self.assertIsNone(resumen['rpe_medio'])
        self.assertEqual(resumen['duracion_minutos'], 40)
        self.assertEqual(resumen['volumen_kg'], 480.0)


# ── Caso 3: cambios relevantes ────────────────────────────────────────────────

class TestCambiosRelevantes(CierreEntrenamientoBase):
    def test_carga_mantenida(self):
        anterior = self._crear_entreno(date(2026, 5, 25))
        self._crear_ejercicio(anterior, peso_kg=60.0)
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, peso_kg=60.0)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        cambios = ctx['cambios_relevantes']
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0]['nombre'], 'Press banca')
        self.assertEqual(cambios[0]['tipo'], 'mantenida')

    def test_carga_subida(self):
        anterior = self._crear_entreno(date(2026, 5, 25))
        self._crear_ejercicio(anterior, peso_kg=60.0)
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, peso_kg=62.5)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        cambios = ctx['cambios_relevantes']
        self.assertEqual(cambios[0]['tipo'], 'subida')
        self.assertEqual(cambios[0]['detalle'], '+2.5 kg')

    def test_carga_bajada(self):
        anterior = self._crear_entreno(date(2026, 5, 25))
        self._crear_ejercicio(anterior, peso_kg=60.0)
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, peso_kg=57.5)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        cambios = ctx['cambios_relevantes']
        self.assertEqual(cambios[0]['tipo'], 'bajada')
        self.assertEqual(cambios[0]['detalle'], '-2.5 kg')

    def test_tope_de_maquina(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, es_tope_maquina=True)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        cambios = ctx['cambios_relevantes']
        self.assertEqual(cambios[0]['tipo'], 'tope')

    def test_sin_sesion_anterior_no_aparece(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, nombre_ejercicio='Ejercicio nuevo')

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertEqual(ctx['cambios_relevantes'], [])

    def test_ejercicios_no_completados_no_aparecen(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno, completado=False)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertEqual(ctx['cambios_relevantes'], [])


# ── Caso 4: lectura del plan / próxima vez ───────────────────────────────────

class TestLecturaPlanYProximaVez(CierreEntrenamientoBase):
    def test_progresion_permitida_no_genera_lectura_ni_proxima_vez(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida', 'ok')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIsNone(ctx['lectura_plan'])
        self.assertIsNone(ctx['proxima_vez'])

    def test_retorno_pausa_genera_lectura_y_proxima_vez(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('mantener_carga', 'retorno_pausa')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIn('pausa', ctx['lectura_plan'].lower())
        self.assertIsNotNone(ctx['proxima_vez'])

    def test_motivo_sin_proxima_vez_definida_devuelve_none(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('mantener_carga', 'motivo_inexistente')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIsNone(ctx['lectura_plan'])
        self.assertIsNone(ctx['proxima_vez'])


# ── Caso 5: PRs ────────────────────────────────────────────────────────────────

class TestPRs(CierreEntrenamientoBase):
    def test_prs_no_superados_aparecen(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)
        RecordPersonal.objects.create(
            cliente=self.cliente, entreno=entreno, ejercicio_nombre='Press banca',
            tipo_record='peso_maximo', valor=62.5, superado=False,
        )
        RecordPersonal.objects.create(
            cliente=self.cliente, entreno=entreno, ejercicio_nombre='Sentadilla',
            tipo_record='peso_maximo', valor=100, superado=True,
        )

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIn('Press banca', ctx['prs'])
        self.assertNotIn('Sentadilla', ctx['prs'])

    def test_sin_records_devuelve_lista_vacia(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertEqual(ctx['prs'], [])


# ── Caso 6: mensaje JOI del día ──────────────────────────────────────────────

class TestJoiMensaje(CierreEntrenamientoBase):
    def _set_creado_en(self, msg, fecha):
        MensajeJOI.objects.filter(id=msg.id).update(
            creado_en=timezone.make_aware(datetime.combine(fecha, time(8, 0)))
        )

    def test_mensaje_joi_del_dia_aparece(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)
        msg = MensajeJOI.objects.create(
            user=self.user, trigger='entreno_completado', mensaje='Hoy aguantaste algo más.',
        )
        self._set_creado_en(msg, entreno.fecha)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertEqual(ctx['joi_mensaje'], 'Hoy aguantaste algo más.')

    def test_sin_mensaje_joi_devuelve_none(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIsNone(ctx['joi_mensaje'])

    def test_mensaje_joi_de_otro_dia_no_aparece(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)
        msg = MensajeJOI.objects.create(
            user=self.user, trigger='entreno_completado', mensaje='Mensaje de ayer.',
        )
        self._set_creado_en(msg, entreno.fecha - timedelta(days=1))

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIsNone(ctx['joi_mensaje'])

    def test_mensaje_joi_de_otro_trigger_no_aparece(self):
        entreno = self._crear_entreno(date(2026, 6, 1))
        self._crear_ejercicio(entreno)
        msg = MensajeJOI.objects.create(
            user=self.user, trigger='resumen_semanal', mensaje='Resumen semanal.',
        )
        self._set_creado_en(msg, entreno.fecha)

        with patch('entrenos.services.cierre_entrenamiento_service.evaluar_permiso_progresion',
                   return_value=_permiso('progresion_permitida')):
            ctx = construir_contexto_cierre(self.cliente, entreno)

        self.assertIsNone(ctx['joi_mensaje'])
