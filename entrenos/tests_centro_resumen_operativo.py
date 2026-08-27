from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EstrategiaSemanalGym,
    SesionProgramada,
)
from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro


class ResumenOperativoCentroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('centro-operativo')
        self.cliente = Cliente.objects.get(user=self.user)
        self.fecha = date(2026, 8, 27)
        self.lunes = date(2026, 8, 24)
        self.estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=self.lunes, aprobado_por=self.user,
        )
        self.bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            semana_inicio=self.lunes, semanas_previstas=4,
            semana_fin_prevista=self.lunes + timedelta(days=27), estrategia=self.estrategia,
            objetivo_sesiones=5, minimo_valido=3, objetivo_principal='fuerza',
            objetivos_secundarios=[], limites_snapshot={}, motor_nombre='Helms',
            motor_version='actual', fingerprint='centro-operativo-bloque',
        )

    def construir(self, analisis=None, bloque=True):
        return construir_resumen_operativo_centro(
            self.cliente,
            {'bloque': self.bloque, 'card': {}} if bloque else {'bloque': None, 'card': None},
            analisis,
            self.fecha,
        )

    def test_contrato_actual_cuenta_solo_estado_completada(self):
        contrato = ContratoSemanalGym.objects.create(
            cliente=self.cliente, estrategia=self.estrategia, bloque=self.bloque,
            indice_semana_bloque=1, semana=self.lunes, objetivo_sesiones=5, minimo_valido=3,
        )
        for indice, estado in enumerate([
            SesionProgramada.ESTADO_COMPLETADA,
            SesionProgramada.ESTADO_COMPLETADA,
            SesionProgramada.ESTADO_PENDIENTE,
            SesionProgramada.ESTADO_SALTADA_USUARIO,
        ]):
            SesionProgramada.objects.create(
                cliente=self.cliente, contrato_semanal=contrato,
                fecha_prevista=self.lunes + timedelta(days=indice), estado=estado,
                nombre_sesion=f'Sesión {indice + 1}',
            )

        resumen = self.construir()

        self.assertEqual(resumen['bloque'], {'estado': 'activo', 'semana_actual': 1, 'semanas_total': 4})
        self.assertEqual(resumen['semana'], {
            'estado': 'materializada', 'completadas': 2, 'objetivo': 5, 'minimo': 3,
        })

    def test_sin_contrato_no_infiere_progreso(self):
        resumen = self.construir()
        self.assertEqual(resumen['semana'], {
            'estado': 'desconocido', 'completadas': None, 'objetivo': None, 'minimo': None,
        })

    def test_proxima_sesion_usa_fecha_efectiva_y_no_mezcla_fechas(self):
        SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.fecha,
            pospuesta_hasta=self.fecha + timedelta(days=3),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Pospuesta',
        )
        inmediata = SesionProgramada.objects.create(
            cliente=self.cliente, fecha_prevista=self.fecha + timedelta(days=1),
            estado=SesionProgramada.ESTADO_PENDIENTE, nombre_sesion='Canónica',
        )

        proxima = self.construir()['proxima_sesion']

        self.assertEqual(proxima, {
            'estado': 'disponible', 'nombre': 'Canónica',
            'fecha': inmediata.fecha_prevista, 'es_pospuesta': False,
        })
        self.assertNotIn('fecha_prevista', proxima)
        self.assertNotIn('pospuesta_hasta', proxima)

    def test_carga_alta_solo_explica_causas_autorizadas(self):
        por_rpe = self.construir({
            'carga_alta_objetiva': True, 'motivo_carga': 'rpe_alto', 'rpe_medio_semana': 8.4,
        })['carga']
        por_bloque = self.construir({
            'carga_alta_objetiva': True, 'motivo_carga': 'bloque_incompleto',
        })['carga']
        desconocida = self.construir({
            'carga_alta_objetiva': True, 'motivo_carga': 'texto_privado',
        })['carga']

        self.assertEqual(por_rpe['causa_codigo'], 'rpe_alto')
        self.assertIn('RPE medio 8,4', por_rpe['explicacion'])
        self.assertEqual(por_bloque['causa_codigo'], 'bloque_incompleto')
        self.assertIn('bloque principal', por_bloque['explicacion'])
        self.assertEqual(desconocida, {'estado': 'desconocido', 'causa_codigo': None, 'explicacion': None})

    def test_dto_es_allowlist_y_no_expone_modelos_o_snapshots(self):
        resumen = self.construir()
        self.assertEqual(set(resumen), {'bloque', 'semana', 'proxima_sesion', 'carga'})
        self.assertNotIn('fingerprint', str(resumen))
        self.assertNotIn('limites_snapshot', str(resumen))

