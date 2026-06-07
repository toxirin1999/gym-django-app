"""
Fix de coherencia — el briefing no promete "subir peso" cuando el motor congela.

Bug (hallado en verificación navegador): con RPE medio ≤ 6.0, get_briefing_gym
decía "Puedes intentar subir peso en el primer ejercicio" aunque la progresión
estuviera congelada (pausa/carga alta/intervención) → contradicción con el freno
mostrado por-ejercicio en la misma pantalla.

Fix: si evaluar_permiso_progresion congela los principales, reemplazar por un
mensaje coherente ("tendrías margen, pero hoy el plan mantiene la carga (razón)").

Checklist:
1. Con freno → el mensaje 'carga' NO dice "subir peso"; dice "mantiene la carga"
   + la razón; pasa el contrato de lenguaje.
2. Sin freno → se conserva el mensaje original "Puedes intentar subir peso".
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from rutinas.models import Rutina
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from entrenos.services.briefing_service import get_briefing_gym
from core.continuidad import auditar_lenguaje_continuidad

HOY = date(2026, 6, 7)

_FROZEN = {'accion': 'mantener_carga', 'motivo': 'retorno_pausa',
           'aplica_a_principales': True, 'aplica_a_accesorios': True,
           'mensaje': '', 'hay_datos_semana': True}
_LIBRE = {'accion': 'progresion_permitida', 'motivo': 'ok',
          'aplica_a_principales': False, 'aplica_a_accesorios': False,
          'mensaje': '', 'hay_datos_semana': True}


class BriefingFrenoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester_brief', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.rutina = Rutina.objects.create(nombre='Rutina test')
        # RPE medio bajo (≤6) en las últimas 2 semanas → dispara el branch.
        for d in (3, 6):
            e = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=self.rutina, fecha=HOY - timedelta(days=d),
            )
            EjercicioRealizado.objects.create(
                entreno=e, nombre_ejercicio='Press Banca con Mancuernas', rpe=6,
            )

    def _carga_text(self):
        b = get_briefing_gym(
            self.cliente,
            [{'nombre': 'Press Banca con Mancuernas', 'tipo_ejercicio': 'compuesto_principal'}],
            HOY,
        )
        return ' '.join(m['texto'] for m in b['mensajes'] if m['tipo'] == 'carga')

    def _patch(self, permiso):
        return patch(
            'entrenos.services.progresion_contextual_service.evaluar_permiso_progresion',
            return_value=permiso,
        )


class TestBriefingConFreno(BriefingFrenoBase):
    def test_no_promete_subir_peso(self):
        with self._patch(_FROZEN):
            txt = self._carga_text()
        self.assertNotIn('subir peso', txt.lower(),
                         "no debe prometer subir peso cuando el motor congela")
        self.assertIn('mantiene la carga', txt)
        self.assertIn('vienes de una pausa', txt)

    def test_mensaje_pasa_contrato_lenguaje(self):
        with self._patch(_FROZEN):
            txt = self._carga_text()
        self.assertEqual(auditar_lenguaje_continuidad(txt), [])


class TestBriefingSinFreno(BriefingFrenoBase):
    def test_conserva_mensaje_original(self):
        with self._patch(_LIBRE):
            txt = self._carga_text()
        self.assertIn('Puedes intentar subir peso', txt)
