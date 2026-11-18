"""18-nov-2026 · «Tu semana por músculo»: referencia por versión seguida y línea del entrenador."""

from collections import Counter
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionVersion, SerieRealizada
from entrenos.services import marcador_semanal_service as m
from rutinas.models import EjercicioBase, Rutina

LUNES = date(2026, 11, 16)
HOY = LUNES + timedelta(days=2)  # miércoles


class Base(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='panel_movil', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'P'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 3 - Hipertrofia')
        mk = lambda n, g: EjercicioBase.objects.create(nombre=n, grupo_muscular=g, tipo_progresion='peso_reps')
        self.sissy = mk('Sissy Squat', 'Cuádriceps')
        self.hack = mk('Hack Squat', 'Cuádriceps')
        self.arnold = mk('Press Arnold', 'Hombros')
        self.hip = mk('Hip Thrust con Barra', 'Glúteos')

    def entreno(self, snapshot, hechos, sustituye=None, fecha=HOY):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        if snapshot is not None:
            e.gym_decision_version = GymDecisionVersion.objects.create(
                cliente=self.cliente, fecha=fecha, version=1, decision_id=f'd-{fecha}',
                origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
                postura='empujar', snapshot=snapshot)
            e.save(update_fields=['gym_decision_version'])
        for base, n in hechos:
            EjercicioRealizado.objects.create(
                entreno=e, nombre_ejercicio=base.nombre, peso_kg=30, series=n, repeticiones=10, completado=True,
                sustituye_a=(sustituye or {}).get(base.nombre, ''))
            for i in range(n):
                SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=i + 1, repeticiones=10,
                                              peso_kg=30, completado=True)
        return e

    def marcador(self, plan_ejercicios, extra_pendiente=None):
        """Plan vigente (planificador de hoy) de la sesión Día 3, más una sesión pendiente opcional."""
        por_grupo, series = {}, Counter()
        for nombre, grupo, n in plan_ejercicios:
            for g, peso in m.grupos_de_serie(nombre, grupo):
                por_grupo.setdefault(g, []).append((nombre, n * peso))
                series[g] += n * peso
        sesiones = [{'nombre': 'Dia 3 - Hipertrofia', 'grupos': set(), 'series': dict(series), 'ejercicios': por_grupo}]
        plan = Counter(series)
        if extra_pendiente:
            sp = {'nombre': 'Dia 4 - Fuerza', 'grupos': set(), 'series': {'isquios': 5},
                  'ejercicios': {'isquios': [('Curl femoral sentado', 3), ('Buenos días', 2)]}}
            sesiones.append(sp)
            plan['isquios'] += 5
        with patch.object(m, 'series_plan_semana', return_value=(plan, sesiones)):
            return m.marcador_semanal(self.cliente, HOY)


SNAP = {'estado': 'entrenar', 'entrenamiento': {'ejercicios': [
    {'nombre': 'Sissy Squat', 'series': 3, 'grupo_muscular': 'cuadriceps'},
    {'nombre': 'Press Arnold', 'series': 2, 'grupo_muscular': 'hombros'},
]}}


class ReferenciaSeguida(Base):
    def test_la_sustitucion_se_mide_contra_la_version_seguida_y_va_a_la_linea_del_entrenador(self):
        self.entreno(SNAP, [(self.hack, 3), (self.arnold, 2)], sustituye={'Hack Squat': 'Sissy Squat'})
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3), ('Hip Thrust con Barra', 'Glúteos', 3)])
        self.assertIn('sustitución Sissy → Hack', r['linea_entrenador'])
        self.assertTrue(r['linea_entrenador'].startswith('Completaste la sesión'))
        cuad = next(f for f in r['filas'] if f['clave'] == 'cuádriceps')
        self.assertEqual(cuad['detalle']['hechas'], 3)
        self.assertEqual(cuad['objetivo'], 3)  # el Hack ocupa el lugar del Sissy: nada quedó sin hacer
        self.assertEqual(cuad['bar_hechas'], 100)

    def test_lo_que_el_plan_actual_pide_y_la_version_no_traia_no_es_un_incumplimiento(self):
        self.entreno(SNAP, [(self.hack, 3), (self.arnold, 2)], sustituye={'Hack Squat': 'Sissy Squat'})
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3), ('Hip Thrust con Barra', 'Glúteos', 3)])
        glu = next(f for f in r['filas'] if f['clave'] == 'glúteos')
        textos = [d['texto'] for d in glu['detalle']['diferencias']]
        self.assertTrue(any('no traía Hip Thrust con Barra' in t for t in textos))
        # El objetivo aplicable no exige el Hip Thrust que esa versión no traía.
        self.assertLess(glu['objetivo'], glu['plan'])
        self.assertEqual(glu['diferencia_plan'], glu['objetivo'] - glu['plan'])

    def test_sin_version_guardada_no_se_comprueba_nada(self):
        self.entreno(None, [(self.hack, 3)])
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)])
        self.assertIn('Sin versión histórica para comprobar', r['linea_entrenador'])
        cuad = next(f for f in r['filas'] if f['clave'] == 'cuádriceps')
        self.assertEqual(cuad['objetivo'], cuad['detalle']['hechas'])
        self.assertEqual(cuad['detalle']['diferencias'], [])
        self.assertTrue(r['sesiones_detalle'][0]['sin_version'])

    def test_las_pendientes_son_el_plan_vigente_y_provisionales(self):
        self.entreno(SNAP, [(self.hack, 3)], sustituye={'Hack Squat': 'Sissy Squat'})
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)], extra_pendiente=True)
        isq = next(f for f in r['filas'] if f['clave'] == 'isquios')
        self.assertEqual(isq['detalle']['pendientes'], 5)
        self.assertEqual(isq['detalle']['hechas'], 0)
        self.assertEqual([e['nombre'] for e in isq['detalle']['pendientes_detalle'][0]['ejercicios']],
                         ['Curl femoral sentado', 'Buenos días'])
        self.assertEqual(r['sesiones_detalle'][-1]['estado'], 'pendiente')

    def test_sin_ajustes_y_completa_no_hay_linea_del_entrenador(self):
        self.entreno(SNAP, [(self.sissy, 3), (self.arnold, 2)])
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)])
        self.assertIsNone(r['linea_entrenador'])

    def test_la_regeneracion_posterior_no_cambia_la_referencia(self):
        e = self.entreno(SNAP, [(self.hack, 3)], sustituye={'Hack Squat': 'Sissy Squat'})
        GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=HOY, version=2, decision_id='d-2', origen=GymDecisionVersion.ORIGEN_MOTOR,
            fingerprint='c' * 64, base_fingerprint='b' * 64, postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [{'nombre': 'Hip Thrust con Barra', 'series': 3}] * 10}})
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)])
        s = r['sesiones_detalle'][0]
        self.assertEqual(s['regenerada']['ejercicios'], 10)
        glu = next(f for f in r['filas'] if f['clave'] == 'cuádriceps')
        self.assertEqual(glu['objetivo'], 3)  # medido con la versión seguida (v1), no con la v2


class PlantillaMovil(Base):
    def test_el_panel_pinta_filas_compactas_y_un_solo_ver_detalle(self):
        from django.urls import reverse
        self.entreno(SNAP, [(self.hack, 3)], sustituye={'Hack Squat': 'Sissy Squat'})
        datos = self.marcador([('Sissy Squat', 'Cuádriceps', 3)], extra_pendiente=True)
        self.client.force_login(self.cliente.user)
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value=datos):
            r = self.client.get(reverse('clientes:trayectoria_plan'))
        html = r.content.decode()
        self.assertContains(r, '3 hechas · sin pendientes')
        self.assertContains(r, '0 hechas · 5 pendientes')
        self.assertContains(r, 'sustitución Sissy → Hack')
        self.assertEqual(html.count('>Ver detalle<'), 1)
        self.assertContains(r, 'Cómo se cuenta')
        self.assertContains(r, 'Sesiones y versión')
        self.assertNotContains(r, 'Distinto del plan en sesiones ya hechas')


class PrescritaSinCompletar(Base):
    def test_una_serie_prescrita_sin_completar_se_queda_en_el_objetivo(self):
        # La versión seguida pedía Sissy 3 + Press Arnold 2; solo se hizo el Sissy.
        self.entreno(SNAP, [(self.sissy, 3)])
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3), ('Press Arnold', 'Hombros', 2)])
        hom = next(f for f in r['filas'] if f['clave'] == 'hombros')
        self.assertEqual(hom['objetivo'], 2)          # el objetivo conserva lo prescrito
        self.assertEqual(hom['detalle']['hechas'], 0)  # y no se da por hecho
        self.assertEqual(hom['bar_hechas'], 0)
        ej = hom['detalle']['sesiones_hechas'][0]['ejercicios'][0]
        self.assertTrue(ej['sin_hacer'])
        # No se afirma que se completó la sesión.
        self.assertFalse(r['sesiones_detalle'][0]['n_hechos'] == r['sesiones_detalle'][0]['n_prescritos'])
        self.assertIsNone(r['linea_entrenador'])  # sin ajustes que contar

    def test_la_linea_no_dice_completaste_si_falto_algo_de_la_version_seguida(self):
        self.entreno(SNAP, [(self.hack, 3)], sustituye={'Hack Squat': 'Sissy Squat'})  # falta el Arnold
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)])
        self.assertNotIn('Completaste', r['linea_entrenador'])
        self.assertIn('sustitución Sissy → Hack', r['linea_entrenador'])


class AvisoDeRegeneracion(Base):
    def test_no_avisa_si_la_regeneracion_trae_los_mismos_ejercicios(self):
        self.entreno(SNAP, [(self.sissy, 3), (self.arnold, 2)])
        GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=HOY, version=2, decision_id='d-2', origen=GymDecisionVersion.ORIGEN_MOTOR,
            fingerprint='c' * 64, base_fingerprint='b' * 64, postura='empujar', snapshot=SNAP)
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3)])
        self.assertIsNone(r['sesiones_detalle'][0]['regenerada'])


class DiferenciasPorEjercicio(Base):
    def test_la_reduccion_nombra_el_ejercicio(self):
        snap = {'estado': 'version_reducida', 'entrenamiento': {'ejercicios': [
            {'nombre': 'Sissy Squat', 'series': 2}, {'nombre': 'Hack Squat', 'series': 2}]}}
        self.entreno(snap, [(self.sissy, 2), (self.hack, 2)])
        r = self.marcador([('Sissy Squat', 'Cuádriceps', 3), ('Hack Squat', 'Cuádriceps', 3)])
        cuad = next(f for f in r['filas'] if f['clave'] == 'cuádriceps')
        textos = [d['texto'] for d in cuad['detalle']['diferencias']]
        self.assertEqual(len(textos), 2)
        self.assertTrue(any(t.startswith('Sissy Squat: versión reducida') for t in textos))
        self.assertTrue(any(t.startswith('Hack Squat: versión reducida') for t in textos))
