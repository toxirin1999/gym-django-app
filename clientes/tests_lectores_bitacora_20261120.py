"""20-nov-2026: los lectores de bitacora interpretan el dia entero y no cuentan filas dobles."""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.bitacora_dia import (
    combinada_del_dia, combinadas_por_dia, lectura_del_dia, filas_del_dia, serie_por_dia)
from clientes.models import BitacoraDiaria, Cliente

HOY = date(2026, 11, 20)


def _fila(cliente, dia, **kw):
    b = BitacoraDiaria.objects.create(cliente=cliente, **kw)
    BitacoraDiaria.objects.filter(pk=b.pk).update(fecha=dia)
    return b


class LectoresBitacoraTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.get(user=User.objects.create_user('lect-bit'))
        # hoy: pulso en una fila, sueno/HRV/energia en otra
        self.a = _fila(self.cliente, HOY, fc_reposo=52)
        self.b = _fila(self.cliente, HOY, horas_sueno=Decimal('7.5'), hrv_ms=130, energia_subjetiva=3,
                       salud_importado_en=timezone.now())
        # ayer: una sola fila
        _fila(self.cliente, HOY - timedelta(days=1), hrv_ms=60, energia_subjetiva=3)

    def test_combinada_une_campos_y_dice_de_que_fila(self):
        d = combinada_del_dia(self.cliente, HOY)
        self.assertEqual((d.fc_reposo, d.hrv_ms, d.energia_subjetiva), (52, 130, 3))
        self.assertEqual(d.fuentes['fc_reposo']['record_id'], self.a.pk)
        self.assertEqual(d.fuentes['hrv_ms']['record_id'], self.b.pk)
        self.assertEqual(d.filas_ids, [self.a.pk, self.b.pk])

    def test_la_hora_es_la_ultima_importacion_de_la_fila(self):
        d = combinada_del_dia(self.cliente, HOY)
        f = d.fuentes['hrv_ms']
        self.assertIn('ultima_importacion_de_la_fila', f)
        self.assertNotIn('importado_en', f)

    def test_series_cuentan_un_valor_por_dia(self):
        # dos filas de hoy con energia 3 no pesan doble
        _fila(self.cliente, HOY, energia_subjetiva=3)
        serie = serie_por_dia(self.cliente, 'energia_subjetiva', desde=HOY - timedelta(days=6), hasta=HOY)
        self.assertEqual(len(serie), 2)
        dias = combinadas_por_dia(self.cliente, desde=HOY - timedelta(days=14))
        bajos = [d for d in dias.values() if d.energia_subjetiva is not None and d.energia_subjetiva <= 4]
        self.assertEqual(len(bajos), 2)  # 2 dias, no 3 filas

    def test_hrv_media_por_dia(self):
        _fila(self.cliente, HOY, hrv_ms=130)  # duplicado del mismo dia
        vals = [v for _f, v in serie_por_dia(self.cliente, 'hrv_ms')]
        self.assertEqual(sorted(vals), [60, 130])

    def test_una_sola_fila_se_devuelve_tal_cual(self):
        d = combinada_del_dia(self.cliente, HOY - timedelta(days=1))
        self.assertIsInstance(d, BitacoraDiaria)

    def test_no_se_toca_ninguna_fila(self):
        combinada_del_dia(self.cliente, HOY)
        combinadas_por_dia(self.cliente)
        self.assertEqual(BitacoraDiaria.objects.filter(cliente=self.cliente).count(), 3)

    def test_hyrox_checkin_hoy_ve_el_pulso_aunque_este_en_otra_fila(self):
        from clientes.bitacora_dia import combinada_del_dia as c
        d = c(self.cliente, HOY)
        self.assertEqual(d.fc_reposo, 52)

    def test_bio_context_y_sesion_recomendada_leen_el_dia_combinado(self):
        from core import bio_context
        import inspect
        self.assertIn('combinada_del_dia', inspect.getsource(bio_context))
        from entrenos.services import sesion_recomendada
        self.assertIn('combinada_del_dia', inspect.getsource(sesion_recomendada))

    def test_senales_texto_no_dice_llego(self):
        from entrenos.services.senales_al_decidir_service import lineas_para_mostrar
        dec = SimpleNamespace(senales_al_decidir={'salud_hoy': {
            'hrv_ms': 130, 'horas_sueno': 7.5, 'disponible_desde': '2026-11-20T08:15:00+00:00'}})
        txt = ' '.join(lineas_para_mostrar(dec))
        self.assertIn('última importación de esa fila 2026-11-20 08:15', txt)
        self.assertNotIn('llegó', txt)
