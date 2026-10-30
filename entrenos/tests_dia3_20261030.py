"""30-oct-2026 · Reparaciones del repaso del Día 3 (energía 5 y fútbol de anteayer)."""

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from entrenos.models import ActividadRealizada, EntrenoRealizado, SerieRealizada
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()


class RangoDePaso(SimpleTestCase):
    def test_nota13(self):
        from entrenos.services.plan_dinamico_service import rango_de_paso
        self.assertEqual(rango_de_paso(10, (15, 20)), (8, 12))
        self.assertEqual(rango_de_paso(12, (15, 20)), (12, 15))
        self.assertIsNone(rango_de_paso(15, (15, 20)))
        self.assertIsNone(rango_de_paso(9, (8, 12)))


class Sesion(Base):
    def _energia_habitual(self, valor=7):
        for d in (3, 4, 5):
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina,
                                            fecha=HOY - timedelta(days=d), energia_pre_sesion=valor)

    def test_nota13_sissy_rango_de_paso(self):
        from entrenos.services.plan_dinamico_service import _objetivo_sin_carga
        b = EjercicioBase.objects.create(nombre='Sissy Squat', grupo_muscular='Cuádriceps',
                                         tipo_progresion='progresion_reps')
        e = self.entreno(HOY - timedelta(days=5), {b.nombre: '15-20'})
        self.hacer(e, b, [(0, 10, 8), (0, 10, 8), (0, 10, 7)])
        ej = {'nombre': b.nombre, 'repeticiones': '15-20', 'tipo_progresion': 'progresion_reps'}
        _objetivo_sin_carga(self.cliente, ej, HOY)
        self.assertEqual(ej['reps_objetivo_hoy'], 11)
        self.assertEqual(ej['repeticiones'], '8-12')
        self.assertIn('Rango de paso 8-12', ej['progresion_motivo'])
        _objetivo_sin_carga(self.cliente, ej, HOY)  # idempotente
        self.assertEqual(ej['repeticiones'], '8-12')

    def test_nota20_margen_contra_lo_pedido_con_energia_baja(self):
        from entrenos.services.cerebro_carga_service import decidir_carga
        b = EjercicioBase.objects.create(nombre='Curl con Barra Z', grupo_muscular='Bíceps',
                                         tipo_progresion='peso_reps')
        self._energia_habitual(7)
        e = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        e.energia_pre_sesion = 5
        e.save(update_fields=['energia_pre_sesion'])
        self.hacer(e, b, [(25, 15, 8)] * 3)
        d = decidir_carga(self.cliente, {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': 9,
                                         'tipo_progresion': 'peso_reps', 'peso_kg': 25}, HOY)
        self.assertEqual(d['reps'], 16)

    def test_nota20_sin_energia_baja_sigue_el_margen(self):
        from entrenos.services.cerebro_carga_service import decidir_carga
        b = EjercicioBase.objects.create(nombre='Curl con Barra Z', grupo_muscular='Bíceps',
                                         tipo_progresion='peso_reps')
        e = self.entreno(HOY - timedelta(days=1), {b.nombre: '15-20'})
        self.hacer(e, b, [(25, 15, 8)] * 3)
        d = decidir_carga(self.cliente, {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': 9,
                                         'tipo_progresion': 'peso_reps', 'peso_kg': 25}, HOY)
        self.assertEqual(d['reps'], 17)

    def test_nota2_pierna_suave(self):
        from entrenos.services.pierna_suave_service import aplicar_pierna_suave
        EjercicioBase.objects.create(nombre='Curl Araña', grupo_muscular='Bíceps')
        EjercicioBase.objects.create(nombre='Zancadas con Kettlebell', grupo_muscular='Cuádriceps')
        EjercicioBase.objects.create(nombre='Hip Thrust con Barra', grupo_muscular='Glúteos')
        ActividadRealizada.objects.create(cliente=self.cliente, tipo='futbol', titulo='Partido',
                                          fecha=HOY - timedelta(days=2), duracion_minutos=79)
        ejs = [
            {'nombre': 'Hip Thrust con Barra', 'series': 3, 'tipo_ejercicio': 'compuesto_principal'},
            {'nombre': 'Zancadas con Kettlebell', 'series': 4},
            {'nombre': 'Curl Araña', 'series': 2},
        ]
        frase = aplicar_pierna_suave(self.cliente, ejs, HOY)
        self.assertEqual([e['nombre'] for e in ejs], ['Curl Araña', 'Hip Thrust con Barra', 'Zancadas con Kettlebell'])
        self.assertEqual(ejs[1]['series'], 2)
        self.assertEqual(ejs[2]['series'], 3)
        self.assertEqual(ejs[0]['series'], 2)
        self.assertIn('fútbol de anteayer (79 min)', frase)
        aplicar_pierna_suave(self.cliente, ejs, HOY)  # idempotente
        self.assertEqual(ejs[2]['series'], 3)

    def test_nota2_sin_futbol_no_toca(self):
        from entrenos.services.pierna_suave_service import aplicar_pierna_suave
        ejs = [{'nombre': 'Sentadilla Hack', 'series': 4}]
        self.assertIsNone(aplicar_pierna_suave(self.cliente, ejs, HOY))
        self.assertEqual(ejs[0]['series'], 4)

    def test_nota1_farmer_ultima_vez_en_briefing(self):
        from entrenos.services.ultima_sesion_service import anotar_ultima_vez
        b = EjercicioBase.objects.create(nombre='Farmer Walk (Paseo del Granjero)', grupo_muscular='Antebrazos',
                                         tipo_progresion='progresion_distancia')
        e = self.entreno(HOY - timedelta(days=7), {b.nombre: '55'})
        self.hacer(e, b, [(36, 1, 7), (36, 1, 7)])
        SerieRealizada.objects.filter(entreno=e).update(distancia_metros=55)
        ej = {'nombre': b.nombre, 'repeticiones': '56', 'tipo_progresion': 'progresion_distancia'}
        anotar_ultima_vez(self.cliente, ej, HOY)
        self.assertIn('55 m', ej.get('ultima_vez_texto', ''))

    def test_nota22_como_llegabas_nombra_la_energia(self):
        from entrenos.models import EjercicioRealizado, GymDecisionVersion
        from entrenos.services.recuperacion_service import comprobacion_cierre
        self._energia_habitual(7)
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY,
                                            energia_pre_sesion=5)
        e.gym_decision_version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=HOY, version=1, decision_id='d-hoy',
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
            postura='empujar', snapshot={'causa_principal': 'futbol_reciente'},
        )
        e.save(update_fields=['gym_decision_version'])
        prev = EntrenoRealizado.objects.filter(fecha=HOY - timedelta(days=3)).first()
        EjercicioRealizado.objects.create(entreno=prev, nombre_ejercicio='Remo', peso_kg=50, series=3,
                                          repeticiones=10, rpe=8, completado=True)
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio='Remo', peso_kg=50, series=3,
                                          repeticiones=10, rpe=8, completado=True)
        frase = comprobacion_cierre(self.cliente, e)
        self.assertIn('marcaste energía 5', frase)
        self.assertNotIn('fútbol', frase)  # no se rebajó la pierna (modo_reducido False)


class Tope(SimpleTestCase):
    def test_nota9_farmer_de_5_en_5(self):
        from entrenos.services.progreso_service import calcular_sugerencia_tope
        self.assertEqual(calcular_sugerencia_tope({'peso': 36, 'repeticiones': 56, 'es_tope_maquina': True,
                                                   'es_distancia': True}), (True, 61))
        self.assertEqual(calcular_sugerencia_tope({'peso': 60, 'repeticiones': 19, 'es_tope_maquina': True}),
                         (True, 20))
