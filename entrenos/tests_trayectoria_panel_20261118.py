"""18-nov-2026 · Paquete de trayectoria y panel.

Comparabilidad (tramo de reps y bloque como filtros, con fechas y referencias), pesos con
decimales comprobados por su origen, «evidencia limitada», propuestas de subir volumen en
espera, panel «Tu semana por músculo» con el mismo periodo para lo hecho y lo previsto, y el
registro «Qué sabía al decidir» con las entradas y la versión del planificador.
"""

from collections import Counter
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from entrenos.models import EjercicioRealizado, EntrenoRealizado, PropuestaZonaGym, SerieRealizada
from entrenos.services import comparabilidad_service as comp
from entrenos.services.evolucion_muscular_service import calcular_evolucion_por_grupo, comparar_ejercicios
from entrenos.tests_evolucion_muscular import _DatosEntrenoMixin
from entrenos.tests_cola_semanal import LUNES, ColaSemanalBase
from rutinas.models import EjercicioBase


def _bloques(por_fecha, defecto='hipertrofia'):
    """Parche de Bloques.de: {fecha: familia}; lo demás, `defecto`."""
    def de(fecha):
        familia = por_fecha.get(fecha, defecto)
        return {'familia': familia, 'nombre': f'Bloque {familia}', 'semana_plan': 1, 'origen': 'prueba'}
    return patch('entrenos.services.comparabilidad_service.Bloques.de', side_effect=de)


class _Base(_DatosEntrenoMixin, TestCase):
    """Como la base de evolución, pero con la exigencia real de evidencia (2 ejercicios o 3 sesiones)."""

    def setUp(self):
        super().setUp()
        for nombre, valor in (('EJERCICIOS_PARA_TENDENCIA', 2), ('SESIONES_PARA_TENDENCIA', 3)):
            p = patch(f'entrenos.services.evolucion_muscular_service.{nombre}', valor)
            p.start()
            self.addCleanup(p.stop)

    def _con_series(self, dias_atras, nombre, grupo, series):
        """series: [(peso, reps)]. Crea el agregado y las series reales."""
        base, _ = EjercicioBase.objects.get_or_create(nombre=nombre, defaults={'grupo_muscular': grupo})
        media_peso = sum(p for p, _ in series) / len(series)
        self._ej(dias_atras, nombre, media_peso, series[0][1], grupo)
        entreno = self._entrenos[self.HOY - timedelta(days=dias_atras)]
        SerieRealizada.objects.bulk_create([
            SerieRealizada(entreno=entreno, ejercicio=base, serie_numero=i + 1, peso_kg=p, repeticiones=r,
                           completado=True)
            for i, (p, r) in enumerate(series)])


class TramoYBloque(_Base):
    def test_distinto_tramo_de_reps_no_se_compara(self):
        self._ej(120, 'Press banca con barra', 80, 5, 'Pecho')
        self._ej(10, 'Press banca con barra', 80, 12, 'Pecho')
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertIsNone(e['pct'])
        self.assertEqual(e['evidencia'], 'sin_comparable')
        self.assertEqual(e['sin_comparable_motivo'], 'tramo de reps distinto')

    def test_mismo_tramo_y_bloque_se_compara_y_enseña_su_criterio(self):
        self._ej(120, 'Press banca con barra', 80, 10, 'Pecho')
        self._ej(10, 'Press banca con barra', 80, 14, 'Pecho')
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertEqual(e['evidencia'], 'suficiente')
        self.assertEqual(e['criterio']['tramo'], 'medio')
        self.assertEqual(e['criterio']['familia'], 'hipertrofia')
        self.assertEqual(e['antes']['fecha'], self.HOY - timedelta(days=120))
        self.assertEqual(e['ahora']['fecha'], self.HOY - timedelta(days=10))

    def test_distinto_bloque_no_se_compara_aunque_el_tramo_coincida(self):
        antes, ahora = self.HOY - timedelta(days=120), self.HOY - timedelta(days=10)
        self._ej(120, 'Remo con barra', 80, 5, 'Espalda')
        self._ej(10, 'Remo con barra', 90, 5, 'Espalda')
        with _bloques({antes: 'fuerza', ahora: 'hipertrofia'}):
            e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertIsNone(e['pct'])
        self.assertEqual(e['sin_comparable_motivo'], 'bloque distinto')

    def test_la_semana_de_descarga_no_se_compara_con_nada(self):
        antes, ahora = self.HOY - timedelta(days=120), self.HOY - timedelta(days=10)
        self._ej(120, 'Remo con barra', 80, 8, 'Espalda')
        self._ej(10, 'Remo con barra', 60, 8, 'Espalda')
        with _bloques({ahora: 'descarga'}):
            e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertIsNone(e['ahora'])
        self.assertIsNone(e['pct'])

    def test_la_zona_enseña_las_fechas_y_referencias_usadas(self):
        self._ej(120, 'Press banca con barra', 80, 10, 'Pecho')
        self._ej(10, 'Press banca con barra', 88, 10, 'Pecho')
        self._ej(120, 'Press inclinado', 60, 10, 'Pecho')
        self._ej(10, 'Press inclinado', 66, 10, 'Pecho')
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertEqual(len(pecho['referencias']), 2)
        ref = pecho['referencias'][0]['referencia']
        self.assertEqual(ref['antes']['fecha'], self.HOY - timedelta(days=120))
        self.assertEqual(ref['ahora']['fecha'], self.HOY - timedelta(days=10))
        self.assertEqual(ref['criterio']['tramo'], 'medio')
        self.assertTrue(ref['ahora']['bloque'])

    def test_el_mapa_enseña_las_marcas_comparadas(self):
        from pathlib import Path
        src = (Path(__file__).parents[1] / 'clientes' / 'templates' / 'clientes' / 'partials'
               / '_mapa_evolucion_muscular.html').read_text(encoding='utf-8')
        self.assertIn('Marcas comparadas', src)
        self.assertIn('Evidencia limitada', src)
        self.assertIn('Peso a comprobar', src)


class PesosConDecimales(SimpleTestCase):
    def test_en_escala_vale_aunque_sea_distinto_de_otra_serie(self):
        self.assertEqual(comp.revisar_peso('Curl femoral', 25, [20, 25], 'serie', None)['estado'], 'ok')

    def test_decimal_con_la_sesion_en_saltos_de_la_escala_es_desfase_constante(self):
        r = comp.revisar_peso('Curl femoral tumbado', 71.3, [61.3, 66.3, 71.3], 'serie', None)
        self.assertEqual(r['estado'], 'desfase_constante')
        self.assertIn('otra máquina o tara', r['nota'])
        self.assertIn('no está confirmado', r['nota'])

    def test_decimal_suelto_se_comprueba_no_se_descarta(self):
        r = comp.revisar_peso('Curl femoral tumbado', 71.3, [71.3], 'serie', None)
        self.assertEqual(r['estado'], 'a_comprobar')
        for pista in ('origen', 'unidad', 'máquina'):
            self.assertIn(pista, r['nota'])

    def test_media_de_series_no_se_excluye_por_decimales(self):
        r = comp.revisar_peso('Curl femoral tumbado', 71.3, [71.3], 'media', None)
        self.assertEqual(r['estado'], 'ok')
        self.assertIn('media', r['nota'])


class PesosConDecimalesEnLaZona(_Base):
    def test_desfase_constante_cuenta_y_lleva_su_nota(self):
        self._con_series(120, 'Curl femoral tumbado', 'Isquios', [(60, 12), (65, 12), (70, 12)])
        self._con_series(10, 'Curl femoral tumbado', 'Isquios', [(61.3, 12), (66.3, 12), (71.3, 12)])
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertEqual(e['evidencia'], 'suficiente')
        self.assertEqual(e['ahora']['revision']['estado'], 'desfase_constante')
        self.assertIsNotNone(e['pct'])

    def test_decimal_suelto_queda_a_comprobar_y_no_manda(self):
        self._con_series(120, 'Curl femoral tumbado', 'Isquios', [(70, 12)])
        self._con_series(10, 'Curl femoral tumbado', 'Isquios', [(71.3, 12)])
        e = comparar_ejercicios(self.cliente, hoy=self.HOY)[0]
        self.assertEqual(e['evidencia'], 'a_comprobar')
        isquios = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'isquios')
        self.assertEqual(len(isquios['a_comprobar']), 1)
        self.assertIsNone(isquios['pct'])


class EvidenciaLimitada(_Base):
    def test_un_ejercicio_con_dos_sesiones_es_evidencia_limitada(self):
        self._ej(120, 'Press banca con barra', 80, 10, 'Pecho')
        self._ej(10, 'Press banca con barra', 88, 10, 'Pecho')
        r = calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY)
        pecho = self._grupo(r, 'pecho')
        self.assertEqual(pecho['estado'], 'limitada')
        self.assertTrue(pecho['evidencia_limitada'])
        self.assertTrue(pecho['lectura'].startswith('Evidencia limitada'))
        self.assertIsNone(r['media_pct'])
        self.assertIsNone(r['lider'])

    def test_dos_ejercicios_apoyan_una_tendencia(self):
        for nombre, antes, ahora in (('Press banca con barra', 80, 88), ('Press inclinado', 60, 66)):
            self._ej(120, nombre, antes, 10, 'Pecho')
            self._ej(10, nombre, ahora, 10, 'Pecho')
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertFalse(pecho['evidencia_limitada'])
        self.assertEqual(pecho['estado'], 'progresa')

    def test_tres_sesiones_comparables_apoyan_una_tendencia(self):
        self._ej(120, 'Press banca con barra', 80, 10, 'Pecho')
        self._ej(30, 'Press banca con barra', 84, 10, 'Pecho')
        self._ej(10, 'Press banca con barra', 88, 10, 'Pecho')
        pecho = self._grupo(calcular_evolucion_por_grupo(self.cliente, hoy=self.HOY), 'pecho')
        self.assertFalse(pecho['evidencia_limitada'])
        self.assertEqual(pecho['n_sesiones'], 3)


class SubirVolumenEnEspera(TestCase):
    """Con pocos datos no se activa solo una propuesta de subir volumen: queda en espera."""

    def setUp(self):
        from clientes.models import Cliente
        self.user = get_user_model().objects.create_user('subir-espera', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()
        p = patch('entrenos.services.comparabilidad_service.Bloques.de', return_value={
            'familia': 'hipertrofia', 'nombre': 'Prueba', 'semana_plan': 1, 'origen': 'prueba'})
        p.start()
        self.addCleanup(p.stop)

    def _sesion(self, dias, nombre, peso, reps):
        from rutinas.models import Rutina
        fecha = self.hoy - timedelta(days=dias)
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'{nombre}{dias}'),
                                            fecha=fecha)
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=nombre, grupo_muscular='Isquios',
                                          peso_kg=peso, repeticiones=reps, series=3, completado=True)

    def _isquios_caen(self):
        self._sesion(120, 'Buenos días', 50, 8)
        self._sesion(10, 'Buenos días', 45, 5)
        self._sesion(120, 'Curl femoral tumbado', 70, 6)
        self._sesion(10, 'Curl femoral tumbado', 55, 5)

    def _pendiente_subir(self):
        return PropuestaZonaGym.objects.create(
            cliente=self.cliente, zona='isquios', ejercicios=['Buenos días'], series_extra=2,
            direccion=PropuestaZonaGym.DIRECCION_SUBIR, texto='Isquios: te propongo +2 series semanales de Isquios')

    def test_el_interruptor_esta_apagado(self):
        from entrenos.services import propuesta_zona_service as pz
        self.assertFalse(pz.SUBIR_VOLUMEN_ACTIVO)

    def test_no_genera_propuesta_de_subir(self):
        from entrenos.services.propuesta_zona_service import generar_propuesta_si_procede
        self._isquios_caen()
        self.assertIsNone(generar_propuesta_si_procede(self.cliente, self.hoy))
        self.assertFalse(PropuestaZonaGym.objects.filter(cliente=self.cliente).exists())

    def test_la_pendiente_sigue_pendiente_pero_no_se_enseña_ni_se_acepta(self):
        from entrenos.services.propuesta_zona_service import PropuestaNoVigente, aceptar_propuesta, propuesta_visible
        p = self._pendiente_subir()
        self.assertIsNone(propuesta_visible(self.cliente, self.hoy))
        with self.assertRaises(PropuestaNoVigente) as ctx:
            aceptar_propuesta(p, self.hoy)
        self.assertIn('en espera', str(ctx.exception))
        p.refresh_from_db()
        self.assertEqual(p.estado, PropuestaZonaGym.ESTADO_PENDIENTE)

    def test_la_pendiente_en_espera_no_bloquea_una_de_bajar(self):
        from entrenos.services import propuesta_zona_service as pz
        self._pendiente_subir()
        filas = [{'clave': 'tríceps', 'grupo': 'Tríceps', 'hechas': 14, 'plan': 9, 'pendientes': 3,
                  'proyectadas': 17}]
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value={'filas': filas}), \
                patch('entrenos.services.marcador_semanal_service.series_hechas_detalle',
                      return_value=(Counter({'tríceps': 16}), Counter(), Counter())):
            p = pz.generar_propuesta_si_procede(self.cliente, self.hoy)
        self.assertEqual(p.direccion, PropuestaZonaGym.DIRECCION_BAJAR)

    def test_por_encima_del_plan_necesita_el_margen(self):
        from entrenos.services import propuesta_zona_service as pz
        filas = [{'clave': 'tríceps', 'grupo': 'Tríceps', 'hechas': 8, 'plan': 9, 'pendientes': 3,
                  'proyectadas': 11}]   # 11 ≤ 9 + 4
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value={'filas': filas}), \
                patch('entrenos.services.marcador_semanal_service.series_hechas_detalle',
                      return_value=(Counter({'tríceps': 16}), Counter(), Counter())):
            self.assertEqual(pz.zonas_por_encima_del_maximo(self.cliente, self.hoy), {})


class PanelDeLaSemana(ColaSemanalBase):
    def _marcador(self, plan, hechas, pendientes, descarga=False):
        from entrenos.services import marcador_semanal_service as m
        with patch.object(m, 'series_plan_semana', return_value=(Counter(plan), [{'nombre': 'Dia 1', 'series': {}}])), \
                patch.object(m, 'series_hechas_detalle',
                             return_value=(Counter(hechas), Counter(hechas), Counter())), \
                patch.object(m, '_pendientes', return_value=pendientes):
            return m.marcador_semanal(self.cliente, LUNES + timedelta(days=2))

    def test_lo_hecho_y_lo_previsto_usan_la_misma_semana(self):
        from entrenos.services import marcador_semanal_service as m
        llamadas = []

        def hechas(cliente, desde, hasta):
            llamadas.append((desde, hasta))
            return Counter(), Counter(), Counter()
        with patch.object(m, 'series_plan_semana', return_value=(Counter({'pecho': 8}), [])), \
                patch.object(m, 'series_hechas_detalle', side_effect=hechas), \
                patch.object(m, '_pendientes', return_value=[]):
            r = m.marcador_semanal(self.cliente, LUNES + timedelta(days=2))
        self.assertEqual(llamadas, [(LUNES, LUNES + timedelta(days=2))])
        self.assertIn(f'{LUNES:%d/%m}–{LUNES + timedelta(days=6):%d/%m}', r['periodo'])
        self.assertIn('hecho hasta hoy', r['periodo'])
        self.assertIn(f'{LUNES:%d/%m}–{LUNES + timedelta(days=6):%d/%m}', r['referencia']['texto'])

    def test_cubren_solo_las_sesiones_pendientes_que_trabajan_el_musculo(self):
        pend = [{'nombre': 'Dia 4 - Hipertrofia', 'series': {'pecho': 4}},
                {'nombre': 'Dia 5 - Hipertrofia', 'series': {'espalda': 6}}]
        r = self._marcador({'pecho': 10, 'espalda': 6}, {'pecho': 2}, pend)
        filas = {f['clave']: f for f in r['filas']}
        pecho = filas['pecho']
        self.assertEqual((pecho['hechas'], pecho['pendientes'], pecho['proyectadas']), (2, 4, 6))
        self.assertEqual(len(pecho['aportan']), 1)
        self.assertEqual(pecho['estado'], 'falta')
        self.assertIn('quedarías en 6', r['frase'])
        self.assertEqual(filas['espalda']['pendientes'], 6)
        self.assertEqual(filas['espalda']['estado'], 'cubierto')

    def test_supera_el_plan_con_lo_previsto(self):
        pend = [{'nombre': 'Dia 4 - Hipertrofia', 'series': {'pecho': 8}}]
        r = self._marcador({'pecho': 10}, {'pecho': 8}, pend)
        fila = r['filas'][0]
        self.assertEqual((fila['proyectadas'], fila['estado']), (16, 'supera'))
        self.assertIn('el plan de la semana pide 10', r['frase'])

    def test_referencia_del_plan_identificada_y_sin_rangos(self):
        r = self._marcador({'pecho': 10}, {}, [])
        self.assertIn('según el planificador', r['referencia']['texto'])
        for fila in r['filas']:
            for clave in ('minimo', 'maximo', 'pct_min'):
                self.assertNotIn(clave, fila)

    def test_ningun_texto_dice_que_las_series_no_suman_solo_cansan(self):
        from pathlib import Path
        raiz = Path(__file__).parents[1]
        for ruta in ('entrenos/services/marcador_semanal_service.py', 'entrenos/services/propuesta_zona_service.py',
                     'clientes/templates/clientes/trayectoria_plan.html'):
            texto = (raiz / ruta).read_text(encoding='utf-8')
            self.assertNotIn('solo cansan', texto, ruta)
            self.assertNotIn('no suman', texto, ruta)


class QueSabiaAlDecidir(TestCase):
    """«Qué sabía al decidir» guarda las entradas y la versión del planificador de la sesión de origen."""

    def setUp(self):
        from clientes.models import Cliente
        from rutinas.models import Rutina
        user = get_user_model().objects.create_user('sad2', password='x')
        self.cliente = Cliente.objects.get(user=user)
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='Dia 3'), fecha=timezone.localdate())
        from entrenos.models import GymDecisionVersion
        self.version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=self.entreno.fecha, version=2, decision_id='gym-x', schema_version=2,
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='f' * 64, base_fingerprint='f' * 64,
            postura='entrenar',
            snapshot={'physical_snapshot_fingerprint': 'abc123',
                      'cambios_materializados': [{'tipo': 'deload', 'ejercicio': 'Jalon'}],
                      'entrenamiento': {'rutina_nombre': 'Dia 3', 'dia': 3, 'bloque': 'Hipertrofia',
                                        'ejercicios': [{'nombre': 'Jalon', 'repeticiones': '12-15',
                                                        'reps_objetivo': 15, 'rpe_objetivo': 8, 'series': 3}]}})
        EntrenoRealizado.objects.filter(pk=self.entreno.pk).update(gym_decision_version=self.version)
        self.entreno.refresh_from_db()
        p = patch('entrenos.services.comparabilidad_service.Bloques.de', return_value={
            'familia': 'hipertrofia', 'nombre': 'Hipertrofia — Prueba', 'semana_plan': 3, 'origen': 'prueba'})
        p.start()
        self.addCleanup(p.stop)

    def _log(self, ejercicio='Jalon', origen=True):
        from entrenos.models import GymDecisionLog
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=ejercicio, ejercicio_normalizado=ejercicio.casefold(),
            entreno_origen=self.entreno if origen else None, accion='mantener', motivo='x',
            peso_anterior=60, reps_anteriores=6, rpe_anterior=7)
        log.refresh_from_db()
        return log

    def test_guarda_version_del_planificador_y_de_la_decision(self):
        from entrenos.services.senales_al_decidir_service import PLANIFICADOR_VERSION
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        self.assertEqual(p['planificador_version'], PLANIFICADOR_VERSION)
        self.assertEqual(p['autoridad_schema_version'], 2)
        v = p['version_de_decision']
        self.assertEqual((v['version'], v['fingerprint'], v['origen']), (2, 'f' * 64, 'motor'))
        self.assertEqual(p['estado_fisico_fingerprint'], 'abc123')

    def test_guarda_las_entradas_para_reconstruir_la_sesion(self):
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        self.assertEqual(p['bloque']['semana_plan'], 3)
        self.assertEqual(p['sesion_planificada']['ejercicios'], ['Jalon'])
        self.assertEqual(p['cambios_materializados'], [{'tipo': 'deload', 'ejercicio': 'Jalon'}])
        self.assertIn('perfil', p)
        self.assertIn('dias_disponibles', p['perfil'])
        self.assertEqual(p['fecha_plan'], self.entreno.fecha.isoformat())

    def test_guarda_el_objetivo_con_el_que_se_monto_el_ejercicio(self):
        o = self._log().senales_al_decidir['plan_de_la_sesion']['objetivo_ejercicio']
        self.assertEqual((o['fuente'], o['repeticiones'], o['rpe_objetivo']), ('version_de_decision', '12-15', 8))

    def test_un_sustituto_guarda_el_objetivo_heredado_no_el_de_otro_dia(self):
        EjercicioRealizado.objects.create(
            entreno=self.entreno, nombre_ejercicio='Hack Squat', sustituye_a='Sissy Squat', peso_kg=30,
            repeticiones=8, series=3, completado=True,
            objetivo_asignado={'rango': '12-15', 'reps_objetivo': 15, 'rpe_objetivo': 8, 'hereda_de': 'Sissy Squat'})
        p = self._log('Hack Squat').senales_al_decidir['plan_de_la_sesion']
        self.assertEqual(p['objetivo_ejercicio']['fuente'], 'objetivo_asignado_al_sustituto')
        self.assertEqual(p['objetivo_ejercicio']['rango'], '12-15')
        self.assertNotIn('objetivo_del_ejercicio', p['faltan'])

    def test_lo_que_no_consta_se_lista(self):
        p = self._log('Ejercicio sin plan').senales_al_decidir['plan_de_la_sesion']
        self.assertIn('objetivo_del_ejercicio', p['faltan'])
        sin_origen = self._log(origen=False).senales_al_decidir['plan_de_la_sesion']
        self.assertIn('sesion_de_origen', sin_origen['faltan'])

    def test_sin_version_de_decision_lo_dice(self):
        EntrenoRealizado.objects.filter(pk=self.entreno.pk).update(gym_decision_version=None)
        self.entreno.refresh_from_db()
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        self.assertIn('version_de_decision', p['faltan'])

    def test_el_detalle_lo_muestra(self):
        from entrenos.services.senales_al_decidir_service import lineas_para_mostrar
        lineas = lineas_para_mostrar(self._log())
        plan = next(l for l in lineas if l.startswith('Plan de la sesión'))
        self.assertIn('planificador 2026-11-18', plan)
        self.assertIn('objetivo 12-15 · RPE 8', plan)
        self.assertIn('versión 2 de la decisión del día', plan)

    def test_no_se_sobrescribe_un_registro_ya_guardado(self):
        from entrenos.services.senales_al_decidir_service import registrar_senales
        log = self._log()
        antes = dict(log.senales_al_decidir)
        EntrenoRealizado.objects.filter(pk=self.entreno.pk).update(gym_decision_version=None)
        registrar_senales(log)
        log.refresh_from_db()
        self.assertEqual(antes, log.senales_al_decidir)


class SesionesMovidasDeFecha(ColaSemanalBase):
    """``fecha`` es el día del plan; ``fecha_ejecucion``, el día real. Lo hecho y lo pendiente cuentan por el real."""

    def _hacer(self, plan, real, nombre, grupo='Cuádriceps', n=4):
        from entrenos.models import EntrenoRealizado
        from rutinas.models import Rutina
        rutina, _ = Rutina.objects.get_or_create(nombre=nombre)
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=plan, fecha_ejecucion=real)
        base, _ = EjercicioBase.objects.get_or_create(
            nombre=f'Ej {nombre}', defaults={'grupo_muscular': grupo, 'tipo_progresion': 'peso_reps'})
        for i in range(n):
            SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=i + 1, repeticiones=10,
                                          peso_kg=50, rpe_real=8, completado=True)
        return e

    def test_sesion_de_la_semana_pasada_hecha_esta_semana_suma_series_esta_semana(self):
        from entrenos.services.marcador_semanal_service import series_hechas_detalle
        self._hacer(plan=LUNES - timedelta(days=3), real=LUNES + timedelta(days=1), nombre='Dia 4 - Hipertrofia')
        total, _, _ = series_hechas_detalle(self.cliente, LUNES, LUNES + timedelta(days=6))
        self.assertEqual(total['cuádriceps'], 4)
        anterior, _, _ = series_hechas_detalle(self.cliente, LUNES - timedelta(days=7), LUNES - timedelta(days=1))
        self.assertEqual(anterior['cuádriceps'], 0)

    def test_sesion_planificada_esta_semana_pero_hecha_la_siguiente_no_cuenta_aun(self):
        from entrenos.services.marcador_semanal_service import series_hechas_detalle
        self._hacer(plan=LUNES + timedelta(days=5), real=LUNES + timedelta(days=8), nombre='Dia 5 - Hipertrofia')
        total, _, _ = series_hechas_detalle(self.cliente, LUNES, LUNES + timedelta(days=6))
        self.assertEqual(total['cuádriceps'], 0)

    def test_la_atrasada_no_cubre_la_pendiente_de_esta_semana_con_el_mismo_nombre(self):
        from entrenos.services import marcador_semanal_service as m
        self._hacer(plan=LUNES - timedelta(days=3), real=LUNES + timedelta(days=1), nombre='Dia 4 - Hipertrofia')
        sesiones = [{'nombre': 'Dia 4 - Hipertrofia', 'series': {'cuádriceps': 4}}]
        pend = m._pendientes(self.cliente, LUNES + timedelta(days=2), sesiones)
        self.assertEqual(len(pend), 1)

    def test_la_de_esta_semana_hecha_en_otro_dia_si_cubre_su_hueco(self):
        from entrenos.services import marcador_semanal_service as m
        self._hacer(plan=LUNES + timedelta(days=3), real=LUNES + timedelta(days=1), nombre='Dia 4 - Hipertrofia')
        sesiones = [{'nombre': 'Dia 4 - Hipertrofia', 'series': {'cuádriceps': 4}}]
        self.assertEqual(m._pendientes(self.cliente, LUNES + timedelta(days=2), sesiones), [])


class DiferenciaPlanFrenteAHechasMasPendientes(SesionesMovidasDeFecha):
    """Qué ejercicios de las sesiones ya hechas explican que hechas + pendientes no lleguen al plan."""

    def test_los_desvios_nombran_los_ejercicios(self):
        from entrenos.services import marcador_semanal_service as m
        hoy = LUNES + timedelta(days=2)
        self._hacer(LUNES + timedelta(days=2), hoy, 'Dia 3 - Hipertrofia', grupo='Glúteos', n=2)  # 'Ej Dia 3 - ...'
        zan = EjercicioBase.objects.get(nombre='Ej Dia 3 - Hipertrofia')
        plan_sesion = {'nombre': 'Dia 3 - Hipertrofia', 'grupos': set(), 'series': {},
                       'ejercicios': {}}
        r = None
        with patch.object(m, 'series_plan_semana') as sp:
            from entrenos.services.marcador_semanal_service import grupos_de_serie
            g = grupos_de_serie(zan.nombre, 'Glúteos')[0][0]
            plan_sesion['series'] = {g: 5}
            plan_sesion['ejercicios'] = {g: [('Hip Thrust con Barra', 3), (zan.nombre, 2)]}
            sp.return_value = (Counter({g: 5}), [plan_sesion])
            r = m.marcador_semanal(self.cliente, hoy)
        fila = r['filas'][0]
        self.assertEqual(fila['hechas'], 2)
        self.assertEqual(fila['proyectadas'], 2)
        self.assertEqual(fila['desvios'], [{'dia': 'Día 3', 'ejercicio': 'Hip Thrust con Barra', 'plan': 3, 'hecho': 0}])

    def test_un_ejercicio_hecho_que_no_estaba_en_el_plan_aparece_como_de_mas(self):
        from entrenos.services import marcador_semanal_service as m
        hoy = LUNES + timedelta(days=2)
        self._hacer(LUNES + timedelta(days=2), hoy, 'Dia 3 - Hipertrofia', grupo='Glúteos', n=2)
        extra = EjercicioBase.objects.get(nombre='Ej Dia 3 - Hipertrofia')
        g = m.grupos_de_serie(extra.nombre, 'Glúteos')[0][0]
        sesion = {'nombre': 'Dia 3 - Hipertrofia', 'grupos': set(), 'series': {g: 3},
                  'ejercicios': {g: [('Hip Thrust con Barra', 3)]}}
        with patch.object(m, 'series_plan_semana', return_value=(Counter({g: 3}), [sesion])):
            r = m.marcador_semanal(self.cliente, hoy)
        nombres = {d['ejercicio']: (d['plan'], d['hecho']) for d in r['filas'][0]['desvios']}
        self.assertEqual(nombres['Hip Thrust Con Barra'.title()] if 'Hip Thrust Con Barra' in nombres else nombres['Hip Thrust con Barra'], (3, 0))
        self.assertTrue(any(plan == 0 and hecho == 2 for plan, hecho in nombres.values()))

    def test_sin_diferencias_no_hay_desvios(self):
        from entrenos.services import marcador_semanal_service as m
        hoy = LUNES + timedelta(days=2)
        self._hacer(LUNES + timedelta(days=2), hoy, 'Dia 3 - Hipertrofia', grupo='Glúteos', n=3)
        base = EjercicioBase.objects.get(nombre='Ej Dia 3 - Hipertrofia')
        g = m.grupos_de_serie(base.nombre, 'Glúteos')[0][0]
        sesion = {'nombre': 'Dia 3 - Hipertrofia', 'grupos': set(), 'series': {g: 3}, 'ejercicios': {g: [(base.nombre, 3)]}}
        with patch.object(m, 'series_plan_semana', return_value=(Counter({g: 3}), [sesion])):
            r = m.marcador_semanal(self.cliente, hoy)
        self.assertEqual(r['filas'][0]['desvios'], [])

    def test_la_plantilla_los_enseña(self):
        from pathlib import Path
        src = (Path(__file__).parents[1] / 'clientes' / 'templates' / 'clientes' / 'trayectoria_plan.html').read_text(
            encoding='utf-8')
        # 18-nov-2026: el panel móvil rediseñado deja el detalle bajo «Ver detalle».
        self.assertIn('Ver detalle', src)
        self.assertIn('Sin versión histórica para comprobarlo', src)
        self.assertIn('Objetivo frente al plan semanal', src)


class BajarVolumenRespetaDescarga(SubirVolumenEnEspera):
    """Las señales que autorizan bajar volumen no cuentan descargas."""

    def test_por_encima_del_plan_no_se_activa_en_semana_de_descarga(self):
        from entrenos.services import propuesta_zona_service as pz
        filas = [{'clave': 'tríceps', 'grupo': 'Tríceps', 'hechas': 14, 'plan': 9, 'pendientes': 3,
                  'proyectadas': 17}]
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado',
                   return_value={'filas': filas, 'descarga': True}), \
                patch('entrenos.services.marcador_semanal_service.series_hechas_detalle',
                      return_value=(Counter({'tríceps': 16}), Counter(), Counter())):
            self.assertEqual(pz.zonas_por_encima_del_maximo(self.cliente, self.hoy), {})

    def test_por_encima_del_plan_no_se_activa_si_la_semana_anterior_fue_descarga(self):
        from entrenos.models import SemanaPlanGym
        from entrenos.services import propuesta_zona_service as pz
        lunes = self.hoy - timedelta(days=self.hoy.weekday())
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=lunes - timedelta(days=7), semana_plan=44,
                                     descarga=True, origen='descarga_programada')
        filas = [{'clave': 'tríceps', 'grupo': 'Tríceps', 'hechas': 14, 'plan': 9, 'pendientes': 3,
                  'proyectadas': 17}]
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value={'filas': filas}), \
                patch('entrenos.services.marcador_semanal_service.series_hechas_detalle',
                      return_value=(Counter({'tríceps': 16}), Counter(), Counter())):
            self.assertEqual(pz.zonas_por_encima_del_maximo(self.cliente, self.hoy), {})

    def _fatiga(self, nombre, entreno, motivo='rpe_alto_sostenido'):
        from entrenos.models import GymDecisionLog
        return GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=nombre, ejercicio_normalizado=nombre.casefold(),
            entreno_origen=entreno, accion='bajar_peso', motivo='x', motivo_codigo=motivo)

    def _entreno(self, dias):
        from entrenos.models import EntrenoRealizado
        from rutinas.models import Rutina
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre=f'f{dias}'),
            fecha=self.hoy - timedelta(days=dias))

    def test_fatiga_con_dos_ejercicios_autoriza(self):
        from entrenos.services.propuesta_zona_service import detectar_zona_con_fatiga
        e = self._entreno(2)
        self._fatiga('Curl femoral tumbado', e)
        self._fatiga('Buenos días', e)
        self.assertEqual(detectar_zona_con_fatiga(self.cliente, self.hoy)['zona'], 'isquios')

    def test_fatiga_en_sesion_de_descarga_no_cuenta(self):
        from entrenos.services.propuesta_zona_service import detectar_zona_con_fatiga
        e = self._entreno(2)
        self._fatiga('Curl femoral tumbado', e)
        self._fatiga('Buenos días', e)
        with patch('entrenos.services.sesion_descarga_service.es_sesion_descarga', return_value=True):
            self.assertIsNone(detectar_zona_con_fatiga(self.cliente, self.hoy))

    def test_fatiga_de_un_solo_ejercicio_no_basta(self):
        from entrenos.services.propuesta_zona_service import detectar_zona_con_fatiga
        self._fatiga('Curl femoral tumbado', self._entreno(2))
        self.assertIsNone(detectar_zona_con_fatiga(self.cliente, self.hoy))


class RegistroConValoresCopiados(QueSabiaAlDecidir):
    def test_guarda_los_ejercicios_con_sus_valores_y_no_solo_huellas(self):
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        det = p['sesion_planificada']['ejercicios_detalle']
        self.assertEqual((det[0]['nombre'], det[0]['repeticiones'], det[0]['rpe_objetivo']), ('Jalon', '12-15', 8))

    def test_guarda_copia_del_estado_fisico_si_cabe(self):
        snap = self.version.snapshot
        snap['physical_snapshot'] = {'fingerprint': 'abc123', 'readiness': {'energia': 7}}
        type(self.version).objects.filter(pk=self.version.pk).update(snapshot=snap)
        self.entreno.refresh_from_db()
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        self.assertEqual(p['estado_fisico']['readiness'], {'energia': 7})

    def test_estado_fisico_demasiado_grande_se_anota_como_no_copiado(self):
        snap = self.version.snapshot
        snap['physical_snapshot'] = {'x': 'a' * 30000}
        type(self.version).objects.filter(pk=self.version.pk).update(snapshot=snap)
        p = self._log().senales_al_decidir['plan_de_la_sesion']
        self.assertNotIn('estado_fisico', p)
        self.assertTrue(any(f.startswith('estado_fisico') for f in p['faltan']))

    def test_se_captura_al_crear_la_decision_no_despues(self):
        log = self._log()
        antes = log.senales_al_decidir['plan_de_la_sesion']['planificador_version']
        with patch('entrenos.services.senales_al_decidir_service.PLANIFICADOR_VERSION', 'otra'):
            log.refresh_from_db()
        self.assertEqual(log.senales_al_decidir['plan_de_la_sesion']['planificador_version'], antes)
