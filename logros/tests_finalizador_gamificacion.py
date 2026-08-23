from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado
from logros.models import HistorialPuntos, Notificacion, PerfilGamificacion
from rutinas.models import Rutina


class FinalizarGamificacionEntrenoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="finalizador", password="x")
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user,
            defaults={"nombre": "Finalizador"},
        )
        self.rutina = Rutina.objects.create(nombre="Rutina finalizador")

    def _crear_entreno(self):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 23),
            fuente_datos="manual",
        )

    def test_crear_solo_el_padre_no_puntua(self):
        entreno = self._crear_entreno()

        self.assertFalse(entreno.procesado_gamificacion)
        self.assertFalse(HistorialPuntos.objects.filter(entreno=entreno).exists())
        self.assertFalse(
            PerfilGamificacion.objects.filter(
                cliente=self.cliente, puntos_totales__gt=0,
            ).exists()
        )

    def test_finaliza_tras_hijos_y_usa_el_latch_una_sola_vez(self):
        from entrenos.services.finalizacion_gamificacion_service import (
            finalizar_gamificacion_entreno,
        )

        entreno = self._crear_entreno()
        EjercicioRealizado.objects.create(
            entreno=entreno,
            nombre_ejercicio="Press banca",
            series=3,
            repeticiones=8,
            peso_kg=60,
            completado=True,
        )

        primero = finalizar_gamificacion_entreno(entreno)
        perfil = PerfilGamificacion.objects.get(cliente=self.cliente)
        puntos = perfil.puntos_totales
        ledger = HistorialPuntos.objects.filter(entreno=entreno).count()

        entreno.refresh_from_db()
        self.assertTrue(entreno.procesado_gamificacion)
        self.assertFalse(primero["already_processed"])
        self.assertGreater(puntos, 0)
        self.assertEqual(ledger, 1)

        segundo = finalizar_gamificacion_entreno(entreno.pk)
        perfil.refresh_from_db()
        self.assertTrue(segundo["already_processed"])
        self.assertEqual(perfil.puntos_totales, puntos)
        self.assertEqual(HistorialPuntos.objects.filter(entreno=entreno).count(), ledger)

    def test_fallo_revierte_puntos_ledger_y_deja_latch_abierto(self):
        from entrenos.services.finalizacion_gamificacion_service import (
            finalizar_gamificacion_entreno,
        )

        entreno = self._crear_entreno()

        def mutar_y_fallar(entreno_bloqueado):
            perfil, _ = PerfilGamificacion.objects.get_or_create(cliente=self.cliente)
            perfil.puntos_totales = 999
            perfil.save(update_fields=["puntos_totales"])
            HistorialPuntos.objects.create(
                perfil=perfil, entreno=entreno_bloqueado, puntos=999, descripcion="rollback",
            )
            raise RuntimeError("fallo deliberado")

        with patch(
            "logros.services.CodiceService.procesar_entreno_completo",
            side_effect=mutar_y_fallar,
        ), self.assertRaisesMessage(RuntimeError, "fallo deliberado"):
            finalizar_gamificacion_entreno(entreno)

        entreno.refresh_from_db()
        self.assertFalse(entreno.procesado_gamificacion)
        self.assertFalse(HistorialPuntos.objects.filter(entreno=entreno).exists())
        self.assertFalse(
            PerfilGamificacion.objects.filter(
                cliente=self.cliente, puntos_totales=999,
            ).exists()
        )


class SuperficiesGamificacionSegurasTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner-gam", password="x")
        self.other = User.objects.create_user(username="other-gam", password="x")
        self.staff = User.objects.create_user(
            username="staff-gam", password="x", is_staff=True,
        )
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.owner, defaults={"nombre": "Owner gam"},
        )
        self.otro_cliente, _ = Cliente.objects.get_or_create(
            user=self.other, defaults={"nombre": "Other gam"},
        )
        self.rutina = Rutina.objects.create(nombre="Seguridad gam")
        self.entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=self.rutina,
            fecha=date(2026, 8, 23),
            fuente_datos="manual",
        )

    def test_endpoint_manual_no_puede_mutar_ni_reprocesar(self):
        from entrenos.services.finalizacion_gamificacion_service import (
            finalizar_gamificacion_entreno,
        )

        finalizar_gamificacion_entreno(self.entreno)
        perfil = PerfilGamificacion.objects.get(cliente=self.cliente)
        puntos = perfil.puntos_totales
        ledger = HistorialPuntos.objects.filter(entreno=self.entreno).count()
        self.client.force_login(self.owner)
        url = reverse("logros:procesar_entreno", args=[self.entreno.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        perfil.refresh_from_db()
        self.assertEqual(perfil.puntos_totales, puntos)
        self.assertEqual(HistorialPuntos.objects.filter(entreno=self.entreno).count(), ledger)

    def test_tercero_no_puede_usar_cierres_de_otro_cliente(self):
        self.client.force_login(self.other)

        self.assertEqual(
            self.client.post(
                reverse("entrenos:guardar_entrenamiento_activo", args=[self.cliente.pk]),
                {},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("clientes:guardar_entrenamiento_activo", args=[self.cliente.pk]),
                {},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("analytics:api_marcar_completado", args=[self.cliente.pk]),
                data="{}",
                content_type="application/json",
            ).status_code,
            404,
        )

    def test_notificacion_ajena_es_404_y_staff_puede_leerla(self):
        perfil = PerfilGamificacion.objects.create(cliente=self.cliente)
        notificacion = Notificacion.objects.create(
            perfil=perfil, tipo="general", titulo="Privada", mensaje="Solo owner",
        )
        url = reverse("logros:marcar_notificacion_leida", args=[notificacion.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        notificacion.refresh_from_db()
        self.assertFalse(notificacion.leida)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url).status_code, 200)
        notificacion.refresh_from_db()
        self.assertTrue(notificacion.leida)

    @override_settings(LIFTIN_UI_ENABLED=True)
    def test_import_liftin_conservado_finaliza_una_vez(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("entrenos:importar_liftin_completo"),
            {
                "cliente": self.cliente.pk,
                "fecha": "2026-08-22",
                "rutina": self.rutina.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        entreno = EntrenoRealizado.objects.get(
            cliente=self.cliente, fuente_datos="liftin",
        )
        self.assertTrue(entreno.procesado_gamificacion)
        self.assertEqual(HistorialPuntos.objects.filter(entreno=entreno).count(), 1)
