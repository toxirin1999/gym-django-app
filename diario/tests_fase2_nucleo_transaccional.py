"""
Fase 2 del CONTRATO_ANALIZADOR_GESTOS.md — persistir_nucleo_cierre().

Estos tests verifican justo lo que motivó la extracción: que un fallo a
mitad del núcleo no deja un cierre a medias (rollback parcial), y que
cerrar dos veces el mismo día no desplaza cierre_confirmado_en
(idempotencia). También cubren que el comportamiento "feliz" (todo
correcto) sigue siendo exactamente el mismo de antes de la extracción.
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Gesto, ProsocheDiario, ProsocheMes, RegistroGesto, SeguimientoVires
from .services.cierre_service import persistir_nucleo_cierre
from .services.habitos_service import HabitosService


class NucleoCierreCasoFelizTestCase(TestCase):
    """El camino sin errores persiste las cuatro piezas y marca el cierre."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.hoy = timezone.localdate()
        self.mes, _ = ProsocheMes.objects.get_or_create(
            usuario=self.user, mes=self.hoy.strftime('%B'), año=self.hoy.year
        )
        self.entrada, _ = ProsocheDiario.objects.get_or_create(
            prosoche_mes=self.mes, fecha=self.hoy
        )
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )

    def test_persiste_reflexion_vires_registro_y_marca_cierre(self):
        persistir_nucleo_cierre(
            usuario=self.user,
            fecha=self.hoy,
            entrada=self.entrada,
            texto_libre='Hoy fue un buen día.',
            friccion_raw='3',
            cuerpo_raw='ligero',
            habitos_completados_raw=f'[{self.gesto.id}]',
            gestos_activos=Gesto.objects.filter(usuario=self.user, estado='activo'),
        )

        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.reflexiones_dia, 'Hoy fue un buen día.')
        self.assertIsNotNone(self.entrada.cierre_confirmado_en)
        self.assertTrue(self.entrada.esta_cerrado)

        vires = SeguimientoVires.objects.get(usuario=self.user, fecha=self.hoy)
        self.assertEqual(vires.nivel_estres, 3)
        self.assertEqual(vires.cuerpo_cierre, 'ligero')

        self.assertTrue(
            RegistroGesto.objects.filter(
                gesto=self.gesto, fecha=self.hoy, estado='cumplido'
            ).exists()
        )

    def test_friccion_no_numerica_no_bloquea_el_resto_del_nucleo(self):
        """Igual que antes de la extracción: un valor de fricción inválido
        no debe abortar reflexión ni hábitos. get_or_create() ya persiste
        la fila de SeguimientoVires antes del int(friccion_raw) que falla
        — por eso la fila SÍ existe (comportamiento previo sin cambios),
        pero nivel_estres se queda sin asignar porque la conversión nunca
        llega a completarse."""
        persistir_nucleo_cierre(
            usuario=self.user,
            fecha=self.hoy,
            entrada=self.entrada,
            texto_libre='Reflexión de todas formas.',
            friccion_raw='no-es-un-numero',
            cuerpo_raw='',
            habitos_completados_raw=f'[{self.gesto.id}]',
            gestos_activos=Gesto.objects.filter(usuario=self.user, estado='activo'),
        )

        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.reflexiones_dia, 'Reflexión de todas formas.')
        self.assertIsNotNone(self.entrada.cierre_confirmado_en)
        vires = SeguimientoVires.objects.get(usuario=self.user, fecha=self.hoy)
        self.assertIsNone(vires.nivel_estres)
        self.assertTrue(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())

    def test_json_habitos_malformado_no_bloquea_el_resto_del_nucleo(self):
        """Un JSON de hábitos corrupto se trata como lista vacía, igual
        que antes de la extracción — no debe abortar reflexión ni vires."""
        persistir_nucleo_cierre(
            usuario=self.user,
            fecha=self.hoy,
            entrada=self.entrada,
            texto_libre='Reflexión con JSON roto.',
            friccion_raw='2',
            cuerpo_raw='',
            habitos_completados_raw='{esto no es json valido',
            gestos_activos=Gesto.objects.filter(usuario=self.user, estado='activo'),
        )

        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.reflexiones_dia, 'Reflexión con JSON roto.')
        self.assertIsNotNone(self.entrada.cierre_confirmado_en)
        self.assertTrue(SeguimientoVires.objects.filter(usuario=self.user, fecha=self.hoy).exists())
        self.assertFalse(RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy).exists())


class NucleoCierreRollbackParcialTestCase(TestCase):
    """Un fallo inesperado a mitad del núcleo debe revertir TODO lo
    escrito en esa llamada, incluida la escritura que ya había ocurrido
    físicamente en la base de datos antes del fallo."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.hoy = timezone.localdate()
        self.mes, _ = ProsocheMes.objects.get_or_create(
            usuario=self.user, mes=self.hoy.strftime('%B'), año=self.hoy.year
        )
        self.entrada, _ = ProsocheDiario.objects.get_or_create(
            prosoche_mes=self.mes, fecha=self.hoy
        )
        self.gesto_1 = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )
        self.gesto_2 = Gesto.objects.create(
            usuario=self.user, nombre='Leer', tipo='cultivo', estado='activo'
        )

    def test_fallo_en_segundo_gesto_revierte_vires_reflexion_y_primer_registro(self):
        toggle_original = HabitosService.toggle_dia
        llamadas = {'n': 0}

        def toggle_que_falla_en_el_segundo(gesto, fecha):
            llamadas['n'] += 1
            if llamadas['n'] == 2:
                raise RuntimeError('fallo simulado a mitad de la sincronización')
            # La primera llamada sí ejecuta el toggle real — el registro
            # llega a existir físicamente en la base de datos antes de
            # que la segunda llamada haga saltar el rollback.
            return toggle_original(gesto, fecha)

        gestos_activos = Gesto.objects.filter(usuario=self.user, estado='activo').order_by('id')

        with patch.object(HabitosService, 'toggle_dia', side_effect=toggle_que_falla_en_el_segundo):
            with self.assertRaises(RuntimeError):
                persistir_nucleo_cierre(
                    usuario=self.user,
                    fecha=self.hoy,
                    entrada=self.entrada,
                    texto_libre='Esta reflexión no debería sobrevivir al fallo.',
                    friccion_raw='5',
                    cuerpo_raw='pesado',
                    habitos_completados_raw=f'[{self.gesto_1.id}, {self.gesto_2.id}]',
                    gestos_activos=gestos_activos,
                )

        # Nada de lo escrito en esta llamada debe sobrevivir, incluido el
        # RegistroGesto del primer gesto que sí llegó a ejecutarse.
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.reflexiones_dia, '')
        self.assertIsNone(self.entrada.cierre_confirmado_en)
        self.assertFalse(self.entrada.esta_cerrado)
        self.assertFalse(SeguimientoVires.objects.filter(usuario=self.user, fecha=self.hoy).exists())
        self.assertFalse(RegistroGesto.objects.filter(gesto=self.gesto_1, fecha=self.hoy).exists())
        self.assertFalse(RegistroGesto.objects.filter(gesto=self.gesto_2, fecha=self.hoy).exists())


class NucleoCierreIdempotenciaTestCase(TestCase):
    """Cerrar dos veces el mismo día no debe desplazar cierre_confirmado_en,
    aunque el resto del contenido sí se actualice."""

    def setUp(self):
        self.user = User.objects.create_user(username='david', password='x')
        self.hoy = timezone.localdate()
        self.mes, _ = ProsocheMes.objects.get_or_create(
            usuario=self.user, mes=self.hoy.strftime('%B'), año=self.hoy.year
        )
        self.entrada, _ = ProsocheDiario.objects.get_or_create(
            prosoche_mes=self.mes, fecha=self.hoy
        )
        self.gesto = Gesto.objects.create(
            usuario=self.user, nombre='Meditar', tipo='cultivo', estado='activo'
        )

    def test_segundo_cierre_mismo_dia_no_desplaza_el_marcador(self):
        gestos_activos = Gesto.objects.filter(usuario=self.user, estado='activo')

        persistir_nucleo_cierre(
            usuario=self.user, fecha=self.hoy, entrada=self.entrada,
            texto_libre='Primera versión del cierre.', friccion_raw='2', cuerpo_raw='',
            habitos_completados_raw='[]', gestos_activos=gestos_activos,
        )
        self.entrada.refresh_from_db()
        primer_marcador = self.entrada.cierre_confirmado_en
        self.assertIsNotNone(primer_marcador)

        persistir_nucleo_cierre(
            usuario=self.user, fecha=self.hoy, entrada=self.entrada,
            texto_libre='Segunda versión, el usuario editó el cierre.',
            friccion_raw='2', cuerpo_raw='',
            habitos_completados_raw=f'[{self.gesto.id}]', gestos_activos=gestos_activos,
        )
        self.entrada.refresh_from_db()

        self.assertEqual(self.entrada.cierre_confirmado_en, primer_marcador)
        self.assertEqual(self.entrada.reflexiones_dia, 'Segunda versión, el usuario editó el cierre.')
        self.assertTrue(
            RegistroGesto.objects.filter(gesto=self.gesto, fecha=self.hoy, estado='cumplido').exists()
        )
