"""20-nov-2026 (D12) · 8 reps en un rango 6-8 son la misma prescripción.

Antes, `son_rangos_compatibles` comparaba las reps hechas con el bucket del
primer número del rango (6 → fuerza) y 8 reps (hipertrofia) en 6-8 parecían
un cambio de familia: la regla recalculaba desde el e1RM y podía pedir menos
reps sin subir el peso («Mantengo 35 kg… con 8 en todas las series, subo el
peso»). Ahora las reps dentro del rango completo siguen la regla C; los
cambios reales de prescripción (9 en 6-8, 3 → 10-15, descarga) recalculan.
"""

from datetime import date, timedelta

from entrenos.models import EjercicioRealizado, EntrenoRealizado, GymDecisionVersion, SerieRealizada
from entrenos.services.cerebro_carga_service import decidir_carga, proxima_vez_texto
from entrenos.services.sesion_descarga_service import ajustar_a_descarga
from entrenos.services.ultima_sesion_service import aplicar_techo
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = date(2026, 11, 20)
SIG = HOY + timedelta(days=1)
NOMBRE = 'Buenos Días (Good Mornings)'


class _Ayudas(Base):
    def setUp(self):
        super().setUp()
        self.bd = EjercicioBase.objects.create(nombre=NOMBRE, grupo_muscular='x', tipo_progresion='peso_reps')

    def _sesion(self, series, rango='6-8', rpe_obj=7):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY)
        e.gym_decision_version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=HOY, version=1, decision_id=f'd-{EntrenoRealizado.objects.count()}',
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64, postura='sostener',
            snapshot={'entrenamiento': {'ejercicios': [
                {'nombre': self.bd.nombre, 'repeticiones': rango, 'repeticiones_plan': rango, 'rpe_objetivo': rpe_obj}]}})
        e.save(update_fields=['gym_decision_version'])
        self.hacer(e, self.bd, series)
        return e

    def _ej(self, rango='6-8', **extra):
        return dict({'nombre': NOMBRE, 'repeticiones': rango, 'rpe_objetivo': 7, 'tipo_progresion': 'peso_reps'}, **extra)

    def _limpiar(self):
        SerieRealizada.objects.all().delete()
        EjercicioRealizado.objects.all().delete()
        EntrenoRealizado.objects.all().delete()
        GymDecisionVersion.objects.all().delete()

    def _decision(self, reps, rpe=7):
        self._limpiar()
        self._sesion([(35, reps, rpe), (35, reps, rpe)])
        return decidir_carga(self.cliente, self._ej(), SIG)


class FronteraRango(_Ayudas):
    # ---- regla única / cierre ----
    def test_objetivo_de_reps_no_decrece_hasta_el_tope(self):
        d6, d7, d8 = self._decision(6), self._decision(7), self._decision(8)
        self.assertEqual((d6['peso'], d6['reps'], d6['regla']), (35.0, 7, 'mantener'))
        self.assertEqual((d7['peso'], d7['reps'], d7['regla']), (35.0, 8, 'mantener'))
        # Al tope del rango: un salto arriba y vuelta al mínimo (regla C), no «mantener a por 6».
        self.assertEqual((d8['peso'], d8['reps'], d8['regla']), (39.0, 6, 'subir'))

    def test_cierre_con_8_reps_no_se_contradice(self):
        self._limpiar()
        e = self._sesion([(35, 8, 7), (35, 8, 7)])
        texto, accion, _ = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps', con_efecto=True)
        self.assertEqual(accion, 'Subir peso')
        self.assertIn('subo a 39 kg', texto)
        self.assertNotIn('Mantengo 35 kg', texto)
        # Sin predicción de reps que contradiga el objetivo («a por 6» y «calculo unas 3»): queda la
        # salvaguarda de esfuerzo.
        self.assertNotIn('calculo unas', texto)
        self.assertIn('si llegas al RPE 7 antes de las 6 reps, para ahí y apúntalo', texto)

    def test_caso_real_del_20_11_buenos_dias_30_y_35_a_rpe_6(self):
        self._limpiar()
        e = self._sesion([(30, 8, 6), (35, 8, 6)])
        d = decidir_carga(self.cliente, self._ej(), SIG)
        self.assertEqual((d['peso'], d['reps'], d['regla']), (39.0, 6, 'subir'))
        texto, accion = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps')
        self.assertEqual(accion, 'Subir peso')
        self.assertNotIn('Mantengo 35 kg', texto)

    def test_por_encima_del_rango_sigue_recalculando(self):
        d = self._decision(9)
        # Escala anclada en la última carga real (35 + 4n): el recálculo cae en 39 kg.
        self.assertEqual((d['peso'], d['reps'], d['regla']), (39.0, 6, 'recalcular'))

    def test_cambio_real_de_familia_sigue_recalculando(self):
        e = self._sesion([(100, 3, 8), (100, 3, 8)], rango='4-6')
        d = decidir_carga(self.cliente, self._ej(rango='10-15'), SIG)
        self.assertEqual(d['regla'], 'recalcular')
        self.assertEqual((d['peso'], d['reps']), (80.0, 10))

    # ---- plan ----
    def test_plan_techo_trata_igual_8_que_7_reps(self):
        resultados = []
        for reps in (7, 8):
            self._limpiar()
            self._sesion([(35, reps, 7), (35, reps, 7)])
            ej = self._ej(peso_kg=30, repeticiones_plan='6-8')
            cambio = aplicar_techo(self.cliente, ej, SIG)
            resultados.append((ej['peso_kg'], bool(cambio), (cambio or {}).get('tipo')))
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(resultados[1], (35.0, True, 'progresion_pospuesta'))

    # ---- entrenamiento activo ----
    def test_activo_8_reps_no_dice_que_cambia_de_fase(self):
        from analytics.planificador_helms.calculo.compatibilidad_fase import resolver_peso_objetivo
        r = resolver_peso_objetivo(peso_anterior=35.0, reps_anteriores=8, rpe_anterior=7,
                                   rep_range_hoy='6-8', rpe_objetivo_hoy=7)
        self.assertFalse(r['aplica'])
        self.assertIsNone(r['motivo_tipo'])

    # ---- descarga ----
    def test_descarga_con_rango_de_otra_familia_no_cambia(self):
        """Semana de descarga con su rango propio (10-15): 8 reps hechas siguen igual."""
        from unittest.mock import patch
        import analytics.planificador_helms.calculo.compatibilidad_fase as cf
        from analytics.planificador_helms.calculo.compatibilidad_fase import _bucket_desde_reps, _primer_numero

        def previa(reps, rango):
            return reps is not None and _bucket_desde_reps(int(reps)) == _bucket_desde_reps(_primer_numero(rango))

        self._limpiar()
        self._sesion([(35, 8, 7), (35, 8, 7)])

        def correr():
            ej = self._ej(rango='10-15', rpe_objetivo=6, repeticiones_plan='10-15', peso_kg=35, peso_recomendado_kg=35)
            frase = ajustar_a_descarga(self.cliente, ej, SIG)
            return ej.get('peso_kg'), ej.get('reps_objetivo_hoy'), frase

        nuevo = correr()
        with patch.object(cf, 'son_rangos_compatibles', previa):
            previo = correr()
        self.assertEqual(nuevo, previo)

    def test_descarga_con_8_reps_en_6_8_usa_la_misma_rama_que_con_7(self):
        resultados = []
        for reps in (7, 8):
            self._limpiar()
            self._sesion([(35, reps, 7), (35, reps, 7)])
            ej = self._ej(rpe_objetivo=6, repeticiones_plan='6-8', peso_kg=35, peso_recomendado_kg=35)
            ajustar_a_descarga(self.cliente, ej, SIG)
            resultados.append((ej.get('peso_kg'), ej.get('reps_objetivo_hoy')))
        self.assertEqual(resultados[0][0], resultados[1][0])


class PendienteFiltroAncla(_Ayudas):
    """PENDIENTE DELIMITADO (no se corrige en este parche).

    La compatibilidad ya trata 7 y 8 reps como la misma prescripción en 6-8, pero
    el ancla suavizada (`obtener_ancla_ejercicio`, y el equivalente de
    `analytics/planificador_helms/core.py` ~877) sigue filtrando por bucket de
    fase contra las reps de la referencia: con referencia de 8 reps (hipertrofia)
    descarta una sesión reciente de 7 reps (fuerza/potencia) que la compatibilidad
    corregida considera válida. Si algún día se unifican los criterios, este test
    debe cambiar de expectativa (lo dice su último assert).
    """

    def test_el_ancla_descarta_una_referencia_de_7_reps_que_la_compatibilidad_da_por_valida(self):
        from datetime import timedelta as td
        from analytics.planificador_helms.calculo.compatibilidad_fase import (
            _bucket_desde_reps, resolver_ancla_historica, son_rangos_compatibles,
        )
        from entrenos.views import obtener_ancla_ejercicio

        self._limpiar()
        antes = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=HOY - td(days=7))
        self.hacer(antes, self.bd, [(40, 7, 7), (40, 7, 7)])
        self._sesion([(35, 8, 6), (35, 8, 6)])

        # La compatibilidad corregida: 7 y 8 reps valen para 6-8.
        self.assertTrue(son_rangos_compatibles(7, '6-8'))
        self.assertTrue(son_rangos_compatibles(8, '6-8'))
        # ...pero caen en buckets distintos, que es lo que usa el ancla.
        self.assertNotEqual(_bucket_desde_reps(7), _bucket_desde_reps(8))

        referencia = {'peso': 35.0, 'repeticiones': 8, 'rpe': 6.0}
        ancla = obtener_ancla_ejercicio(self.cliente.id, NOMBRE, SIG, referencia)

        solo_8 = resolver_ancla_historica([{'peso': 35.0, 'reps': 8, 'rpe': 6.0, 'fecha': HOY}], ahora=SIG)
        con_ambas = resolver_ancla_historica([
            {'peso': 35.0, 'reps': 8, 'rpe': 6.0, 'fecha': HOY},
            {'peso': 40.0, 'reps': 7, 'rpe': 7.0, 'fecha': HOY - td(days=7)},
        ], ahora=SIG)
        self.assertNotEqual(solo_8['peso'], con_ambas['peso'])  # el caso distingue de verdad
        # Comportamiento actual (el pendiente): la sesión de 7 reps se ignora.
        self.assertEqual(ancla['peso'], solo_8['peso'])


class CoherenciaCierrePlanProxima(_Ayudas):
    """20-nov-2026 (D12): cierre, Plan y próxima sesión dan la misma prescripción para Buenos Días, y
    ninguna escribe una predicción de reps por debajo del objetivo (el estimador se queda corto)."""

    def _plan_final(self, series, propuesto):
        from entrenos.services.cerebro_carga_service import aplicar_decision_carga
        from entrenos.services.ultima_sesion_service import ajustar_escala_y_reps
        self._limpiar()
        e = self._sesion(series)
        ej = self._ej(peso_kg=propuesto, peso_recomendado_kg=propuesto, repeticiones_plan='6-8')
        aplicar_techo(self.cliente, ej, SIG)
        ajustar_escala_y_reps(self.cliente, ej, SIG)
        d = decidir_carga(self.cliente, ej, SIG)
        aplicar_decision_carga(ej, d)
        return e, ej, d

    def test_mismo_peso_y_reps_en_cierre_plan_y_regla(self):
        for series in ([(30, 8, 6), (35, 8, 6)], [(35, 8, 7), (35, 8, 7)], [(35, 7, 7), (35, 7, 7)], [(35, 6, 7), (35, 6, 7)]):
            for propuesto in (40, 36, 30):
                e, ej, d = self._plan_final(series, propuesto)
                texto, accion = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps')
                self.assertEqual((ej['peso_kg'], ej['reps_objetivo_hoy']), (d['peso'], d['reps']), (series, propuesto))
                kg = f"{d['peso']:g}".replace('.', ',')
                self.assertIn(f'{kg} kg', texto, (series, propuesto, texto))
                self.assertIn(f"{d['reps']} reps", texto, (series, propuesto, texto))

    def test_sin_prediccion_que_contradiga_el_objetivo(self):
        e, ej, d = self._plan_final([(35, 8, 7), (35, 8, 7)], 40)
        texto, _ = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps')
        for t in (texto, d['frase'], ej.get('progresion_motivo') or ''):
            self.assertNotIn('calculo unas', t)
        self.assertIn('si llegas al RPE 7 antes de las 6 reps, para ahí y apúntalo', texto)

    def test_caso_real_20_11_cierre_y_plan_39_kg_a_por_6(self):
        e, ej, d = self._plan_final([(30, 8, 6), (35, 8, 6)], 35)
        texto, accion = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps')
        self.assertEqual((ej['peso_kg'], ej['reps_objetivo_hoy']), (39.0, 6))
        self.assertIn('subo a 39 kg, a por 6 reps', texto)
        self.assertEqual(accion, 'Subir peso')

    def test_salto_de_buenos_dias_es_el_confirmado_y_no_cambia_otras_barras(self):
        from entrenos.services.maquina_service import salto_fisico
        self.assertEqual(salto_fisico('Buenos Días (Good Mornings)'), 4.0)
        self.assertEqual(salto_fisico('Good Morning'), 4.0)
        self.assertEqual(salto_fisico('Press de banca con barra'), 5.0)
        self.assertEqual(salto_fisico('Peso Muerto'), 5.0)

    def test_escala_anclada_en_la_ultima_carga_real(self):
        # 21-nov-2026: 35 kg es una carga montable y se añaden 2 kg por lado: 35 → 39 → 43 (no 32/36/40).
        from entrenos.services.maquina_service import a_escala, salto_carga
        self._limpiar(); self._sesion([(35, 8, 7), (35, 8, 7)])
        salto = salto_carga(self.cliente, NOMBRE)
        self.assertEqual((float(salto), salto.ancla), (4.0, 35.0))
        self.assertEqual([a_escala(p, salto) for p in (35, 38, 39, 40, 43, 31, 33)], [35, 39, 39, 39, 43, 31, 31])
        # sin la ancla, escala desde cero (el resto de ejercicios no cambia)
        self.assertEqual(a_escala(35, 5.0), 35.0)
        self.assertEqual(a_escala(39, 4.0), 40.0)

    def test_siguiente_salto_desde_39_es_43_y_bajar_desde_35_es_31(self):
        self._limpiar(); e = self._sesion([(39, 8, 7), (39, 8, 7)])
        texto, accion = proxima_vez_texto(self.cliente, e, NOMBRE, 'peso_reps')
        self.assertIn('subo a 43 kg', texto)
        d = decidir_carga(self.cliente, self._ej(), SIG)
        self.assertEqual((d['peso'], d['regla']), (43.0, 'subir'))

    def test_mantener_35_no_se_mueve_de_escala(self):
        # El peso real usado se respeta («mantengo 35 kg»): la escala parte de él.
        d = self._decision(7)
        self.assertEqual((d['peso'], d['regla']), (35.0, 'mantener'))
