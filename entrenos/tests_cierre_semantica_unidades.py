from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    EntrenoRealizado,
    EjercicioRealizado,
    GymAdaptationProfile,
    GymDecisionLog,
    SerieRealizada,
)
from entrenos.services.cierre_entrenamiento_service import (
    _cambios_relevantes,
    _decisiones_entrenador,
    _resumen_sesion,
)
from entrenos.services.decision_log_service import (
    _decidir_accion,
    generar_decisiones_para_entreno,
)
from rutinas.models import EjercicioBase, Rutina


class CierreSemanticaUnidadesTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='cierre_unidades')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=user, defaults={'nombre': 'Cierre unidades'},
        )
        self.rutina = Rutina.objects.create(nombre='Tirón')
        self.dead_hang = EjercicioBase.objects.create(
            nombre='Dead Hang', grupo_muscular='antebrazos',
            tipo_progresion='progresion_tiempo',
        )
        self.curl = EjercicioBase.objects.create(
            nombre='Curl bíceps', grupo_muscular='biceps',
            tipo_progresion='peso_reps',
        )
        self.jalon = EjercicioBase.objects.create(
            nombre='Jalón al pecho', grupo_muscular='espalda',
            tipo_progresion='peso_reps',
        )
        self.farmer = EjercicioBase.objects.create(
            nombre='Farmer Walk', grupo_muscular='full_body',
            tipo_progresion='progresion_distancia',
        )

    def _entreno(self, fecha):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
        )

    def _ejercicio(self, entreno, base, *, peso=0, series=2, reps=10):
        return EjercicioRealizado.objects.create(
            entreno=entreno, nombre_ejercicio=base.nombre, peso_kg=peso,
            series=series, repeticiones=reps, completado=True,
        )

    def _serie(self, entreno, base, numero, *, reps, peso=0, distancia=None):
        return SerieRealizada.objects.create(
            entreno=entreno, ejercicio=base, serie_numero=numero,
            repeticiones=reps, peso_kg=peso, distancia_metros=distancia,
            completado=True,
        )

    def test_resumen_separa_repeticiones_segundos_y_distancia_desde_series(self):
        entreno = self._entreno(date(2026, 9, 22))
        self._ejercicio(entreno, self.dead_hang, reps=36)
        self._ejercicio(entreno, self.curl, peso=12, series=3, reps=10)
        self._ejercicio(entreno, self.jalon, peso=50, series=3, reps=10)
        self._ejercicio(entreno, self.farmer, peso=24, reps=20)

        self._serie(entreno, self.dead_hang, 1, reps=36)
        self._serie(entreno, self.dead_hang, 2, reps=31)
        for numero in range(1, 4):
            self._serie(entreno, self.curl, numero, reps=10, peso=12)
            self._serie(entreno, self.jalon, numero, reps=10, peso=50)
        self._serie(entreno, self.farmer, 1, reps=999, peso=24, distancia=20)
        self._serie(entreno, self.farmer, 2, reps=999, peso=24, distancia=25)

        resumen = _resumen_sesion(
            entreno, list(entreno.ejercicios_realizados.all()),
        )

        self.assertEqual(resumen['repeticiones_totales'], 60)
        self.assertEqual(resumen['segundos_totales'], 67)
        self.assertEqual(resumen['distancia_metros_total'], 45)

    def test_resumen_legacy_sin_series_respeta_tipo_de_progresion(self):
        entreno = self._entreno(date(2026, 9, 22))
        self._ejercicio(entreno, self.dead_hang, series=2, reps=30)
        self._ejercicio(entreno, self.curl, peso=12, series=3, reps=10)

        resumen = _resumen_sesion(
            entreno, list(entreno.ejercicios_realizados.all()),
        )

        self.assertEqual(resumen['repeticiones_totales'], 30)
        self.assertEqual(resumen['segundos_totales'], 60)
        self.assertEqual(resumen['distancia_metros_total'], 0)

    def test_cambios_usan_peso_representativo_de_series_no_promedio_legacy(self):
        anterior = self._entreno(date(2026, 9, 15))
        anterior_ej = self._ejercicio(anterior, self.curl, peso=20.92, reps=10)
        self._serie(anterior, self.curl, 1, reps=10, peso=12)
        self._serie(anterior, self.curl, 2, reps=10, peso=12)

        actual = self._entreno(date(2026, 9, 22))
        actual_ej = self._ejercicio(actual, self.curl, peso=12, reps=10)
        self._serie(actual, self.curl, 1, reps=10, peso=12)
        self._serie(actual, self.curl, 2, reps=10, peso=12)

        cambios = _cambios_relevantes(self.cliente, actual, [actual_ej])

        self.assertEqual(cambios, [{
            'nombre': 'Curl bíceps', 'tipo': 'mantenida',
            'detalle': 'carga mantenida',
        }])
        self.assertNotEqual(anterior_ej.peso_kg, actual_ej.peso_kg)

    def test_progresion_tiempo_avanza_un_segundo_no_peso(self):
        perfil = GymAdaptationProfile(incremento_peso_pct=5, reduccion_peso_pct=10)
        actual = EjercicioRealizado(rpe=7, fallo_muscular=False)
        anterior = EjercicioRealizado(rpe=7, fallo_muscular=False)

        accion, valor, _ = _decidir_accion(
            actual, [anterior], perfil, 7, False, False,
            tipo_progresion='progresion_tiempo',
        )

        self.assertEqual(accion, 'subir_reps')
        self.assertEqual(valor, 1)

    def test_generacion_real_de_tiempo_nunca_crea_subida_de_peso(self):
        anterior = self._entreno(date(2026, 9, 15))
        self._ejercicio(anterior, self.dead_hang, reps=30)
        EjercicioRealizado.objects.filter(entreno=anterior).update(rpe=7)
        actual = self._entreno(date(2026, 9, 22))
        self._ejercicio(actual, self.dead_hang, reps=31)
        EjercicioRealizado.objects.filter(entreno=actual).update(rpe=7)

        generar_decisiones_para_entreno(actual)

        decision = GymDecisionLog.objects.get(
            entreno_origen=actual, ejercicio_normalizado='dead hang',
        )
        self.assertEqual(decision.accion, 'subir_reps')
        self.assertEqual(decision.valor_cambio, 1)

    def test_efecto_temporal_usa_segundos_y_porcentaje_no_finge_kg(self):
        entreno = self._entreno(date(2026, 9, 22))
        GymDecisionLog.objects.create(
            cliente=self.cliente, entreno_origen=entreno,
            ejercicio='dead hang', ejercicio_normalizado='dead hang',
            accion='subir_reps', valor_cambio=1, motivo='Progresión temporal',
        )
        GymDecisionLog.objects.create(
            cliente=self.cliente, entreno_origen=entreno,
            ejercicio='curl bíceps', ejercicio_normalizado='curl bíceps',
            accion='subir_peso', valor_cambio=5, motivo='Progresión de carga',
        )

        efectos = {
            item['ejercicio']: item['efecto']
            for item in _decisiones_entrenador(self.cliente, entreno)
        }

        self.assertEqual(efectos['dead hang'], 'Añadirá 1 s')
        self.assertEqual(efectos['curl bíceps'], 'Aumentará la carga un 5%')
