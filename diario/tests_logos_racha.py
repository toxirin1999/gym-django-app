import uuid
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from diario.models import RachaEscritura, ReflexionLibre
from diario.services.cierre_service import (
    ejecutar_cierre_nocturno,
    ejecutar_enriquecimiento_cierre,
)


class RachaEscrituraContratoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logos-racha",
            password="test-password",
        )
        self.client.force_login(self.user)

    def _reflexion_en_fecha(self, fecha, contenido):
        reflexion = ReflexionLibre.objects.create(
            usuario=self.user,
            contenido=contenido,
        )
        instante = timezone.make_aware(datetime.combine(fecha, time(hour=12)))
        ReflexionLibre.objects.filter(pk=reflexion.pk).update(fecha=instante)
        return reflexion

    def test_primera_entrada_deja_racha_maxima_al_menos_igual_a_actual(self):
        racha = self.user.racha_escritura

        racha.actualizar_racha(timezone.localdate())

        racha.refresh_from_db()
        self.assertEqual(racha.dias_consecutivos, 1)
        self.assertEqual(racha.racha_maxima, 1)
        self.assertGreaterEqual(racha.racha_maxima, racha.dias_consecutivos)

    def test_dashboard_repara_racha_desde_dias_unicos_de_reflexion(self):
        hoy = timezone.localdate()
        for desplazamiento, contenido in (
            (-6, "A"),
            (-5, "B"),
            (-2, "C"),
            (-1, "D"),
            (0, "E"),
            (0, "Otra reflexión el mismo día"),
        ):
            self._reflexion_en_fecha(hoy + timedelta(days=desplazamiento), contenido)

        RachaEscritura.objects.filter(usuario=self.user).update(
            dias_consecutivos=99,
            racha_maxima=1,
            total_dias_escritos=99,
            fecha_ultima_entrada=None,
        )
        response = self.client.get(reverse("diario:logos_dashboard"))

        self.assertEqual(response.status_code, 200)
        racha = response.context["racha"]
        self.assertEqual(racha.total_dias_escritos, 5)
        self.assertEqual(racha.dias_consecutivos, 3)
        self.assertEqual(racha.racha_maxima, 3)
        self.assertEqual(racha.fecha_ultima_entrada, hoy)
        self.assertEqual(response.context["total_reflexiones"], 6)

    def test_racha_actual_caduca_pero_conserva_maxima_y_total_historicos(self):
        hoy = timezone.localdate()
        self._reflexion_en_fecha(hoy - timedelta(days=20), "Primer día")
        self._reflexion_en_fecha(hoy - timedelta(days=19), "Segundo día")
        self._reflexion_en_fecha(hoy - timedelta(days=10), "Último día antiguo")

        self.client.get(reverse("diario:logos_dashboard"))

        racha = self.user.racha_escritura
        racha.refresh_from_db()
        self.assertEqual(racha.dias_consecutivos, 0)
        self.assertEqual(racha.racha_maxima, 2)
        self.assertEqual(racha.total_dias_escritos, 3)
        self.assertEqual(racha.fecha_ultima_entrada, hoy - timedelta(days=10))

    def test_racha_que_termina_ayer_sigue_viva(self):
        hoy = timezone.localdate()
        self._reflexion_en_fecha(hoy - timedelta(days=2), "Anteayer")
        self._reflexion_en_fecha(hoy - timedelta(days=1), "Ayer")

        self.client.get(reverse("diario:logos_dashboard"))

        racha = self.user.racha_escritura
        racha.refresh_from_db()
        self.assertEqual(racha.dias_consecutivos, 2)
        self.assertEqual(racha.racha_maxima, 2)
        self.assertEqual(racha.total_dias_escritos, 2)


class RachaEscrituraCierreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cierre-racha")
        self.fecha = timezone.localdate()

    def _operacion(self, texto, expected):
        return ejecutar_cierre_nocturno(
            usuario=self.user,
            fecha=self.fecha,
            payload={
                "reflexion_libre": texto,
                "friccion_no": 3,
                "cuerpo_cierre": "",
                "estado_animo_noche": 4,
                "habitos_completados": [],
                "simbiosis_respuesta": "",
                "analisis_cierre": {
                    "estado": "ok",
                    "parseo": {"personas": [], "etiquetas": []},
                    "enriquecido": {"titulo_logos": "Cierre", "interacciones": []},
                },
            },
            idempotency_key=uuid.uuid4(),
            expected_version=expected,
        ).operacion

    def _enriquecer(self, operacion):
        with patch("joi.services.generar_respuesta_cierre", return_value="Lectura"):
            return ejecutar_enriquecimiento_cierre(operacion.pk)

    def test_reflexion_nocturna_proyectada_cuenta_como_dia_escrito(self):
        self._enriquecer(self._operacion("Cierre real", 0))

        racha = self.user.racha_escritura
        racha.refresh_from_db()
        self.assertEqual(racha.total_dias_escritos, 1)
        self.assertEqual(racha.dias_consecutivos, 1)
        self.assertEqual(racha.racha_maxima, 1)

    def test_reflexion_nocturna_historica_cuenta_en_la_fecha_del_cierre(self):
        self.fecha = timezone.localdate() - timedelta(days=10)

        self._enriquecer(self._operacion("Cierre histórico", 0))

        reflexion = ReflexionLibre.objects.get(usuario=self.user)
        self.assertEqual(timezone.localtime(reflexion.fecha).date(), self.fecha)
        racha = self.user.racha_escritura
        racha.refresh_from_db()
        self.assertEqual(racha.fecha_ultima_entrada, self.fecha)
        self.assertEqual(racha.total_dias_escritos, 1)

    def test_edicion_y_reintento_del_cierre_no_duplican_actividad(self):
        primera = self._operacion("Versión A", 0)
        self._enriquecer(primera)
        self._enriquecer(primera)
        segunda = self._operacion("Versión B", 1)
        self._enriquecer(segunda)

        self.assertEqual(ReflexionLibre.objects.filter(usuario=self.user).count(), 1)
        racha = self.user.racha_escritura
        racha.refresh_from_db()
        self.assertEqual(racha.total_dias_escritos, 1)
        self.assertEqual(racha.dias_consecutivos, 1)
        self.assertEqual(racha.racha_maxima, 1)
