"""
Fase 4 del CONTRATO_ANALIZADOR_GESTOS.md — analizador canónico de Gesto.

Primero reproduce el dataset de referencia del §6 del contrato (Hábitos
A/B/C/D, ventana 2026-06-15 a 2026-07-15) y verifica las cifras que el
propio contrato calcula a mano. Después cubre los casos límite pedidos
explícitamente para la Fase 4.

No hay ninguna superficie visual implicada — se llama al servicio
directamente, exactamente como pidió la fase.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Gesto, PausaGesto, ProsocheDiario, ProsocheMes, RegistroGesto
from .services import analizador_gestos as az


def _confirmar_cierre(usuario, fecha):
    mes, _ = ProsocheMes.objects.get_or_create(usuario=usuario, mes=fecha.strftime('%B'), año=fecha.year)
    ProsocheDiario.objects.get_or_create(
        prosoche_mes=mes, fecha=fecha, defaults={'cierre_confirmado_en': timezone.now()}
    )


def _confirmar_cierres_en_rango(usuario, desde, hasta, excepto=()):
    fecha = desde
    while fecha <= hasta:
        if fecha not in excepto:
            _confirmar_cierre(usuario, fecha)
        fecha += timedelta(days=1)


def _marcar_cumplido(gesto, fecha):
    RegistroGesto.objects.create(gesto=gesto, fecha=fecha, estado='cumplido')


FECHA_REFERENCIA = date(2026, 7, 15)
VENTANA_DESDE = date(2026, 6, 15)
VENTANA_HASTA = date(2026, 7, 15)
NO_OBSERVADOS = (date(2026, 7, 5), date(2026, 7, 6))


class DatasetReferenciaTestCase(TestCase):
    """Reproduce el §6 del contrato completo: Hábitos A (diaria), B
    (semanal), C (dias_concretos), D (libre)."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        _confirmar_cierres_en_rango(self.user, VENTANA_DESDE, VENTANA_HASTA, excepto=NO_OBSERVADOS)

        # Hábito A — Meditar, diaria, sin pausas.
        self.gesto_a = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=VENTANA_DESDE,
        )
        fallos_a = {date(2026, 6, 20), date(2026, 6, 27)}
        fecha = VENTANA_DESDE
        while fecha <= VENTANA_HASTA:
            if fecha not in fallos_a and fecha not in NO_OBSERVADOS:
                _marcar_cumplido(self.gesto_a, fecha)
            fecha += timedelta(days=1)

        # Hábito B — Gimnasio, semanal objetivo=4, pausa [22 jun, 1 jul).
        self.gesto_b = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4,
            fecha_inicio=VENTANA_DESDE,
        )
        PausaGesto.objects.create(gesto=self.gesto_b, fecha_inicio=date(2026, 6, 22), fecha_fin=date(2026, 7, 1))
        for f in (date(2026, 6, 15), date(2026, 6, 17), date(2026, 6, 19),
                  date(2026, 7, 2), date(2026, 7, 4), date(2026, 7, 9), date(2026, 7, 12)):
            _marcar_cumplido(self.gesto_b, f)

        # Hábito C — Llamar a mis padres, dias_concretos=[domingo].
        self.gesto_c = Gesto.objects.create(
            usuario=self.user, nombre='Llamar a mis padres', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIAS_CONCRETOS, dias_semana_objetivo=['domingo'],
            fecha_inicio=VENTANA_DESDE,
        )
        for f in (date(2026, 6, 21), date(2026, 7, 12)):
            _marcar_cumplido(self.gesto_c, f)

        # Hábito D — Leer, libre.
        self.gesto_d = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=VENTANA_DESDE,
        )
        for f in (date(2026, 6, 16), date(2026, 6, 19), date(2026, 6, 24), date(2026, 6, 30),
                  date(2026, 7, 8), date(2026, 7, 14)):
            _marcar_cumplido(self.gesto_d, f)

    # -- Hábito A: diaria --

    def test_a_ledger_clasifica_no_observado_y_fallos_correctamente(self):
        ledger = az.construir_ledger_diario(self.gesto_a, VENTANA_DESDE, VENTANA_HASTA)
        por_fecha = {d['fecha']: d['estado'] for d in ledger}
        self.assertEqual(por_fecha[date(2026, 7, 5)], az.EstadoDia.NO_OBSERVADO)
        self.assertEqual(por_fecha[date(2026, 7, 6)], az.EstadoDia.NO_OBSERVADO)
        self.assertEqual(por_fecha[date(2026, 6, 20)], az.EstadoDia.PREVISTO_NO_CUMPLIDO)
        self.assertEqual(por_fecha[date(2026, 6, 27)], az.EstadoDia.PREVISTO_NO_CUMPLIDO)
        self.assertEqual(por_fecha[date(2026, 6, 21)], az.EstadoDia.PREVISTO_CUMPLIDO)

    def test_a_m1_apariciones_ultimos_14_dias(self):
        resultado = az.apariciones(self.gesto_a, date(2026, 7, 2), date(2026, 7, 15))
        self.assertEqual(resultado['valor'], 12)
        self.assertEqual(resultado['confianza'], 'alta')

    def test_a_m13_recuperacion_diaria(self):
        resultado = az.recuperacion(self.gesto_a, FECHA_REFERENCIA)
        self.assertEqual(resultado['valor']['recuperaciones'], [1, 1])
        self.assertIsNone(resultado['valor']['incumplimiento_pendiente_de_recuperar'])

    # -- Hábito B: semanal --

    def test_b_pausa_cubre_9_dias_no_21(self):
        pausa = self.gesto_b.pausas.get()
        dias_pausado = (pausa.fecha_fin - pausa.fecha_inicio).days
        self.assertEqual(dias_pausado, 9)

    def test_b_semana_22_28_junio_no_evaluable(self):
        semana = az._clasificar_semana(self.gesto_b, date(2026, 6, 22), date(2026, 6, 28), FECHA_REFERENCIA)
        self.assertEqual(semana['clasificacion'], 'semana_no_evaluable')
        self.assertEqual(semana['dias_activos_disponibles'], 0)

    def test_b_semana_29jun_5jul_parcial_alcanzable_no_cumplida(self):
        semana = az._clasificar_semana(self.gesto_b, date(2026, 6, 29), date(2026, 7, 5), FECHA_REFERENCIA)
        self.assertEqual(semana['clasificacion'], 'semana_parcial_alcanzable')
        self.assertEqual(semana['dias_activos_disponibles'], 5)
        self.assertEqual(semana['cumplidos'], 2)
        self.assertFalse(semana['cumplida'])

    def test_b_semana_6_12_julio_parcial_por_no_observado_sin_pausa(self):
        semana = az._clasificar_semana(self.gesto_b, date(2026, 7, 6), date(2026, 7, 12), FECHA_REFERENCIA)
        self.assertEqual(semana['clasificacion'], 'semana_parcial_alcanzable')
        self.assertEqual(semana['dias_activos_disponibles'], 7)
        self.assertEqual(semana['cumplidos'], 2)

    def test_b_semana_13_15_julio_en_curso(self):
        semana = az._clasificar_semana(self.gesto_b, date(2026, 7, 13), date(2026, 7, 19), FECHA_REFERENCIA)
        self.assertEqual(semana['clasificacion'], 'semana_en_curso')

    def test_b_m11_tasa_principal_solo_semana_completa(self):
        resultado = az.evaluacion_semanal(self.gesto_b, FECHA_REFERENCIA)
        self.assertEqual(resultado['valor']['semanas_completas'], 1)
        self.assertEqual(resultado['valor']['semanas_cumplidas'], 0)
        self.assertEqual(resultado['valor']['tasa_principal'], 0.0)
        self.assertEqual(len(resultado['valor']['semanas_parciales_alcanzables']), 2)
        self.assertEqual(len(resultado['valor']['semanas_no_evaluables']), 1)
        self.assertEqual(resultado['confianza'], 'insuficiente')

    def test_b_m13_recuperacion_semanal_sin_recuperar_aun(self):
        resultado = az.recuperacion(self.gesto_b, FECHA_REFERENCIA)
        self.assertEqual(resultado['valor']['recuperaciones'], [])
        self.assertEqual(resultado['valor']['incumplimiento_pendiente_de_recuperar'], 2)

    # -- Hábito C: dias_concretos --

    def test_c_domingo_5_julio_no_cuenta_como_oportunidad(self):
        ledger = az.construir_ledger_diario(self.gesto_c, VENTANA_DESDE, VENTANA_HASTA)
        por_fecha = {d['fecha']: d['estado'] for d in ledger}
        self.assertEqual(por_fecha[date(2026, 7, 5)], az.EstadoDia.NO_OBSERVADO)

    def test_c_m8_m9_m10(self):
        m8 = az.oportunidades_previstas(self.gesto_c, FECHA_REFERENCIA)
        m9 = az.oportunidades_cumplidas(self.gesto_c, FECHA_REFERENCIA)
        self.assertEqual(m8['valor'], 3)
        self.assertEqual(m9['valor'], 2)
        m10 = az.adherencia(self.gesto_c, FECHA_REFERENCIA)
        self.assertIsNone(m10['valor'])  # M8=3 < umbral de 4

    def test_c_m13_recuperacion_dias_concretos_salta_no_observado(self):
        resultado = az.recuperacion(self.gesto_c, FECHA_REFERENCIA)
        self.assertEqual(resultado['valor']['recuperaciones'], [1])
        self.assertIsNone(resultado['valor']['incumplimiento_pendiente_de_recuperar'])

    # -- Hábito D: libre --

    def test_d_m1_m2(self):
        m1 = az.apariciones(self.gesto_d, VENTANA_DESDE, VENTANA_HASTA)
        m2 = az.densidad_sobre_dias_observados_activos(self.gesto_d, VENTANA_DESDE, VENTANA_HASTA)
        self.assertEqual(m1['valor'], 6)
        self.assertAlmostEqual(m2['valor'], 6 / 29, places=4)

    def test_d_m3_m4_mediana_y_maximo(self):
        # Intervalo activo = nº de días *estrictamente entre* dos
        # apariciones que no son pausado/fuera_de_vida — sin pausas (caso
        # de D), eso es un día menos que el delta natural entre fechas,
        # no el delta en sí. Gaps naturales [3,5,6,8,6] → activos [2,4,5,7,5].
        m3 = az.intervalo_mediano_activo(self.gesto_d, VENTANA_DESDE, VENTANA_HASTA)
        m4 = az.intervalo_maximo_activo(self.gesto_d, VENTANA_DESDE, VENTANA_HASTA)
        self.assertEqual(m3['valor'], 5)
        self.assertEqual(m4['valor'], 7)
        self.assertEqual(m4['explicacion']['intervalos_naturales_auxiliar'], [3, 5, 6, 8, 6])

    def test_d_m12_m13_no_calculables_para_libre(self):
        m12 = az.incumplimientos_observados(self.gesto_d, FECHA_REFERENCIA)
        m13 = az.recuperacion(self.gesto_d, FECHA_REFERENCIA)
        self.assertEqual(m12['motivo_no_calculable'], az.MotivoNoCalculable.CADENCIA_LIBRE)
        self.assertEqual(m13['motivo_no_calculable'], az.MotivoNoCalculable.CADENCIA_LIBRE)


class IntervaloAtraviesaPausaTestCase(TestCase):
    """Ejemplo literal del contrato: intervalo natural 21 días, activo 1 día."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Correr', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=date(2026, 6, 1),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), date(2026, 7, 15))
        PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 21), fecha_fin=date(2026, 7, 10))
        _marcar_cumplido(self.gesto, date(2026, 6, 20))
        _marcar_cumplido(self.gesto, date(2026, 7, 11))

    def test_intervalo_activo_excluye_pausa_natural_no(self):
        m4 = az.intervalo_maximo_activo(self.gesto, date(2026, 6, 1), date(2026, 7, 15))
        self.assertEqual(m4['valor'], 1)
        self.assertEqual(m4['explicacion']['intervalos_naturales_auxiliar'], [21])


class RegistroDentroDePausaTestCase(TestCase):
    """Un RegistroGesto que cae dentro de una pausa (p. ej. una pausa
    retroactiva) no debe contar como aparición ni como previsto_cumplido."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 6, 1),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), date(2026, 6, 30))
        _marcar_cumplido(self.gesto, date(2026, 6, 10))
        # Pausa retroactiva que cubre el 10 de junio, creada después del registro.
        PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 5), fecha_fin=date(2026, 6, 15))

    def test_ledger_clasifica_como_pausado_no_previsto_cumplido(self):
        ledger = az.construir_ledger_diario(self.gesto, date(2026, 6, 1), date(2026, 6, 30))
        estado_10 = next(d['estado'] for d in ledger if d['fecha'] == date(2026, 6, 10))
        self.assertEqual(estado_10, az.EstadoDia.PAUSADO)

    def test_m1_no_cuenta_el_registro_pausado_como_aparicion(self):
        resultado = az.apariciones(self.gesto, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(resultado['valor'], 0)


class RegistroPosteriorACierreTestCase(TestCase):
    """Un RegistroGesto en una fecha >= fecha_cierre (dato residual o
    manipulado) debe quedar fuera_de_vida, no contar en ninguna métrica."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Viejo hábito', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 5, 1),
            estado='cerrado', fecha_cierre=date(2026, 6, 1),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 5, 1), date(2026, 6, 10))
        _marcar_cumplido(self.gesto, date(2026, 5, 15))
        _marcar_cumplido(self.gesto, date(2026, 6, 5))  # posterior a fecha_cierre

    def test_dia_posterior_a_cierre_es_fuera_de_vida(self):
        ledger = az.construir_ledger_diario(self.gesto, date(2026, 5, 1), date(2026, 6, 10))
        estado = next(d['estado'] for d in ledger if d['fecha'] == date(2026, 6, 5))
        self.assertEqual(estado, az.EstadoDia.FUERA_DE_VIDA)

    def test_dia_de_cierre_mismo_ya_es_fuera_de_vida(self):
        ledger = az.construir_ledger_diario(self.gesto, date(2026, 5, 1), date(2026, 6, 10))
        estado = next(d['estado'] for d in ledger if d['fecha'] == date(2026, 6, 1))
        self.assertEqual(estado, az.EstadoDia.FUERA_DE_VIDA)

    def test_m1_solo_cuenta_la_aparicion_previa_al_cierre(self):
        resultado = az.apariciones(self.gesto, date(2026, 5, 1), date(2026, 6, 10))
        self.assertEqual(resultado['valor'], 1)


class CadenciaNoConfiguradaTestCase(TestCase):
    """Hábito histórico migrado a libre, cadencia_configurada_en=null:
    las métricas de cumplimiento no son calculables; las observacionales sí."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo', fecha_inicio=date(2026, 6, 1),
        )
        self.assertIsNone(self.gesto.cadencia_configurada_en)
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), date(2026, 6, 30))
        _marcar_cumplido(self.gesto, date(2026, 6, 10))

    def test_m8_no_calculable_por_cadencia_no_configurada(self):
        self.gesto.tipo_cadencia = Gesto.CADENCIA_DIARIA
        self.gesto.save()  # sin pasar por configurar_cadencia(): sigue sin cadencia_configurada_en
        resultado = az.oportunidades_previstas(self.gesto, date(2026, 6, 30))
        self.assertEqual(resultado['motivo_no_calculable'], az.MotivoNoCalculable.CADENCIA_NO_CONFIGURADA)

    def test_m1_si_es_calculable_sin_cadencia_configurada(self):
        resultado = az.apariciones(self.gesto, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(resultado['valor'], 1)


class CambioDeCadenciaCorteDelPasadoTestCase(TestCase):
    """Cambiar la cadencia reinicia cadencia_configurada_en a hoy — las
    métricas de cumplimiento no deben ver nada anterior a ese cambio."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Entrenar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 1, 1),
        )
        # Meses de historial bajo la cadencia original.
        _confirmar_cierres_en_rango(self.user, date(2026, 1, 1), date(2026, 3, 31))
        fecha = date(2026, 1, 1)
        while fecha <= date(2026, 3, 31):
            _marcar_cumplido(self.gesto, fecha)
            fecha += timedelta(days=1)

        self.gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=3)
        _confirmar_cierres_en_rango(self.user, timezone.localdate() - timedelta(days=3), timezone.localdate())

    def test_cadencia_configurada_en_se_reinicia_a_hoy(self):
        self.assertEqual(self.gesto.cadencia_configurada_en, timezone.localdate())

    def test_m11_no_incluye_meses_previos_al_cambio(self):
        resultado = az.evaluacion_semanal(self.gesto, timezone.localdate())
        total_semanas = (
            resultado['valor']['semanas_completas']
            + len(resultado['valor']['semanas_parciales_alcanzables'])
            + len(resultado['valor']['semanas_no_evaluables'])
            + (1 if resultado['valor']['semana_en_curso'] else 0)
        )
        # Como mucho un par de semanas (la actual, quizá la de alrededor
        # del cambio) — nunca los tres meses de historial bajo 'diaria'.
        self.assertLessEqual(total_semanas, 2)

    def test_m1_observacional_si_puede_ver_el_historial_completo(self):
        resultado = az.apariciones(self.gesto, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(resultado['valor'], 90)


class SemanaParcialAlcanzableQueCumpleTestCase(TestCase):
    """Ejemplo literal del contrato: objetivo 2, reactivación jueves,
    cumplido jueves y sábado → parcial alcanzable, sí cumple."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        # Semana lunes 2026-06-15 a domingo 2026-06-21.
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Yoga', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=2,
            fecha_inicio=date(2026, 6, 1),
        )
        self.gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=2)
        PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 15), fecha_fin=date(2026, 6, 18))
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 15), date(2026, 6, 21))
        _marcar_cumplido(self.gesto, date(2026, 6, 18))  # jueves
        _marcar_cumplido(self.gesto, date(2026, 6, 20))  # sábado

    def test_semana_parcial_alcanzable_cumplida(self):
        semana = az._clasificar_semana(self.gesto, date(2026, 6, 15), date(2026, 6, 21), date(2026, 6, 22))
        self.assertEqual(semana['clasificacion'], 'semana_parcial_alcanzable')
        self.assertEqual(semana['dias_activos_disponibles'], 4)  # jue, vie, sab, dom
        self.assertTrue(semana['cumplida'])


class SemanaParcialNoAlcanzableTestCase(TestCase):
    """Ejemplo literal del contrato: objetivo 4, reactivación viernes →
    solo 3 días activos → semana_no_evaluable, no 'incumplida'."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Gimnasio', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4,
            fecha_inicio=date(2026, 6, 1),
        )
        self.gesto.configurar_cadencia(Gesto.CADENCIA_SEMANAL, frecuencia_semanal_objetivo=4)
        # Semana lunes 2026-06-15 a domingo 2026-06-21; pausa hasta el viernes.
        PausaGesto.objects.create(gesto=self.gesto, fecha_inicio=date(2026, 6, 15), fecha_fin=date(2026, 6, 19))
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 15), date(2026, 6, 21))
        _marcar_cumplido(self.gesto, date(2026, 6, 19))
        _marcar_cumplido(self.gesto, date(2026, 6, 20))
        _marcar_cumplido(self.gesto, date(2026, 6, 21))

    def test_semana_no_evaluable_aunque_cumplio_los_dias_disponibles(self):
        semana = az._clasificar_semana(self.gesto, date(2026, 6, 15), date(2026, 6, 21), date(2026, 6, 22))
        self.assertEqual(semana['dias_activos_disponibles'], 3)
        self.assertEqual(semana['clasificacion'], 'semana_no_evaluable')
        self.assertIsNone(semana['cumplida'])


class DoblesVentanasCoberturaDistintaTestCase(TestCase):
    """M7 debe bajar la confianza a 'baja' cuando la cobertura de las
    dos ventanas difiere en más de 20 puntos, aunque los conteos brutos
    parezcan comparables."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=date(2026, 6, 1),
        )
        hoy = date(2026, 7, 1)
        # Ventana reciente (18-jun a 1-jul, 14 días): cobertura total.
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 18), hoy)
        for f in (date(2026, 6, 19), date(2026, 6, 22), date(2026, 6, 25), date(2026, 6, 28)):
            _marcar_cumplido(self.gesto, f)
        # Ventana anterior (4-jun a 17-jun): cobertura muy baja, solo 2 días observados.
        _confirmar_cierre(self.user, date(2026, 6, 5))
        _confirmar_cierre(self.user, date(2026, 6, 6))
        _marcar_cumplido(self.gesto, date(2026, 6, 5))
        self.hoy = hoy

    def test_m7_confianza_baja_por_diferencia_de_cobertura(self):
        resultado = az.comparacion_entre_periodos(self.gesto, self.hoy, dias_ventana=14)
        self.assertIn(resultado['confianza'], ('baja', 'insuficiente'))
        self.assertEqual(resultado['valor']['reciente']['apariciones'], 4)


class HabitoLibreCeroCierresTestCase(TestCase):
    """Un Gesto libre sin ningún cierre confirmado en toda su vida: dato
    bruto calculable (0), pero confianza insuficiente — nunca None
    silencioso ni una interpretación implícita."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=date(2026, 6, 1),
        )
        # Ningún ProsocheDiario con cierre_confirmado_en para este usuario.

    def test_m1_devuelve_cero_con_confianza_insuficiente(self):
        resultado = az.apariciones(self.gesto, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(resultado['valor'], 0)
        self.assertEqual(resultado['confianza'], 'insuficiente')

    def test_m2_no_calculable_no_cero_falso(self):
        resultado = az.densidad_sobre_dias_observados_activos(self.gesto, date(2026, 6, 1), date(2026, 6, 30))
        self.assertIsNone(resultado['valor'])
        self.assertEqual(resultado['motivo_no_calculable'], az.MotivoNoCalculable.MUESTRA_INSUFICIENTE)


class TipoSueltoRechazadoTestCase(TestCase):
    """Ninguna métrica de este módulo se calcula para tipo='suelto' —
    ese dominio sigue siendo de TriggerHabito/TriggersService."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Fumar', tipo='suelto',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2026, 6, 1),
        )
        _confirmar_cierres_en_rango(self.user, date(2026, 6, 1), date(2026, 6, 30))
        _marcar_cumplido(self.gesto, date(2026, 6, 10))

    def test_todas_las_metricas_rechazan_tipo_suelto(self):
        hoy = date(2026, 6, 30)
        for resultado in (
            az.apariciones(self.gesto, date(2026, 6, 1), hoy),
            az.densidad_sobre_dias_observados_activos(self.gesto, date(2026, 6, 1), hoy),
            az.oportunidades_previstas(self.gesto, hoy),
            az.evaluacion_semanal(self.gesto, hoy),
            az.recuperacion(self.gesto, hoy),
            az.metrica_contextual(self.gesto, 'facilitador'),
        ):
            self.assertIsNone(resultado['valor'])
            self.assertEqual(resultado['motivo_no_calculable'], az.MotivoNoCalculable.TIPO_NO_CULTIVO)
