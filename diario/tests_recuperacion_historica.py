"""
Enmienda de recuperación histórica — §5.1 del CONTRATO_ANALIZADOR_GESTOS.md
(2026-07-18, posterior a la Fase 5C, motivada por datos reales).

Antes de esta enmienda, todo día anterior al despliegue de
cierre_confirmado_en quedaba no_observado, ocultando meses de
RegistroGesto reales. Cubre: cada señal de evidencia por separado, que
la recuperación cruza entre gestos del mismo usuario, y que la mera
existencia de ProsocheDiario sin ninguna señal sigue sin bastar (no se
ha debilitado el principio original).
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Gesto, ProsocheDiario, ProsocheMes, RegistroGesto
from .services import analizador_gestos as az


def _prosoche_diario(usuario, fecha, **kwargs):
    mes, _ = ProsocheMes.objects.get_or_create(usuario=usuario, mes=fecha.strftime('%B'), año=fecha.year)
    return ProsocheDiario.objects.create(prosoche_mes=mes, fecha=fecha, **kwargs)


class SoloProsocheDiarioSinSenalNoBastaTestCase(TestCase):
    """Control negativo: una fila de ProsocheDiario sin ninguna señal
    (el caso de abrir la página sin enviar el cierre) sigue sin contar
    como observado — no se ha debilitado el principio original."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo', fecha_inicio=date(2025, 10, 1))

    def test_prosoche_diario_sin_senales_sigue_siendo_no_observado(self):
        _prosoche_diario(self.user, date(2025, 10, 10))  # sin cierre_confirmado_en, sin reflexión, sin JOI
        ledger = az.construir_ledger_diario(self.gesto, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.NO_OBSERVADO)


class RegistroGestoComoEvidenciaTestCase(TestCase):
    """Un RegistroGesto(cumplido) de cualquier gesto del usuario ese día
    basta para marcar el día como observado — también para OTROS gestos
    que ese día no se marcaron."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto_a = Gesto.objects.create(usuario=self.user, nombre='Meditar', tipo='cultivo', fecha_inicio=date(2025, 10, 1))
        self.gesto_b = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2025, 10, 1),
        )

    def test_registro_del_propio_gesto_marca_el_dia_observado(self):
        RegistroGesto.objects.create(gesto=self.gesto_a, fecha=date(2025, 10, 10), estado='cumplido')
        ledger = az.construir_ledger_diario(self.gesto_a, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.OBSERVADO_MARCADO)

    def test_registro_de_otro_gesto_del_mismo_usuario_tambien_marca_el_dia_observado(self):
        # Se marcó Meditar ese día, pero no Leer — Leer debe pasar a
        # previsto_no_cumplido (evidencia real), no quedarse no_observado.
        RegistroGesto.objects.create(gesto=self.gesto_a, fecha=date(2025, 10, 10), estado='cumplido')
        ledger = az.construir_ledger_diario(self.gesto_b, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.PREVISTO_NO_CUMPLIDO)

    def test_registro_de_otro_usuario_no_cuenta(self):
        otro_usuario = User.objects.create_user(username='ana', password='x')
        otro_gesto = Gesto.objects.create(usuario=otro_usuario, nombre='Meditar', tipo='cultivo', fecha_inicio=date(2025, 10, 1))
        RegistroGesto.objects.create(gesto=otro_gesto, fecha=date(2025, 10, 10), estado='cumplido')
        ledger = az.construir_ledger_diario(self.gesto_a, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.NO_OBSERVADO)


class ReflexionYRespuestaJoiComoEvidenciaTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_DIARIA, fecha_inicio=date(2025, 10, 1),
        )

    def test_reflexion_no_vacia_marca_el_dia_observado(self):
        _prosoche_diario(self.user, date(2025, 10, 10), reflexiones_dia='Hoy fue un día largo.')
        ledger = az.construir_ledger_diario(self.gesto, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.PREVISTO_NO_CUMPLIDO)

    def test_respuesta_joi_generada_marca_el_dia_observado(self):
        _prosoche_diario(self.user, date(2025, 10, 10), respuesta_joi_cierre_generada_en=timezone.now())
        ledger = az.construir_ledger_diario(self.gesto, date(2025, 10, 10), date(2025, 10, 10))
        self.assertEqual(ledger[0]['estado'], az.EstadoDia.PREVISTO_NO_CUMPLIDO)


class RecuperacionContraDatasetRealTestCase(TestCase):
    """Reproduce en miniatura el caso que motivó la enmienda: meses de
    RegistroGesto reales sin cierre_confirmado_en (todo migrado a null
    en Fase 1) deben seguir contando en M1."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Alimedución', tipo='cultivo',
            tipo_cadencia=Gesto.CADENCIA_LIBRE, fecha_inicio=date(2025, 10, 17),
        )
        # Igual que en producción: ProsocheDiario histórico sin cierre_confirmado_en.
        for fecha in (date(2025, 10, 17), date(2025, 11, 20), date(2026, 1, 5)):
            _prosoche_diario(self.user, fecha)
            RegistroGesto.objects.create(gesto=self.gesto, fecha=fecha, estado='cumplido')

    def test_m1_recupera_apariciones_historicas_sin_cierre_confirmado(self):
        resultado = az.apariciones(self.gesto, date(2025, 10, 17), date(2026, 7, 18))
        self.assertEqual(resultado['valor'], 3)
