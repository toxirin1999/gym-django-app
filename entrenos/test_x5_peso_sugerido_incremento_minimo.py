# entrenos/test_x5_peso_sugerido_incremento_minimo.py
"""
Bug real de producción: GymDecisionLog.peso_sugerido redondea al múltiplo de
2.5kg más cercano. Con pesos bajos (accesorios/aislamiento, ej. Pallof Press
a 12.5-20kg), un incremento del 5% (o reducción del 10%) es menor que 1.25kg
(la mitad del paso de redondeo), así que el redondeo devuelve el MISMO valor
que peso_anterior. Resultado: una decisión 'subir_peso' que no cambia nada,
o peor, una decisión 'bajar_peso' de seguridad (RPE alto/fallo) que no reduce
la carga real.

Confirmado en producción: 13 de 77 decisiones subir_peso del usuario no
cambiaron el peso. Ejemplos reales verificados vía consola Django:
  Pallof Press: peso_anterior=20.0, valor_cambio=5.0 -> peso_sugerido=20.0
  Pallof Press: peso_anterior=15.0, valor_cambio=5.0 -> peso_sugerido=15.0
  Pallof Press: peso_anterior=12.5, valor_cambio=5.0 -> peso_sugerido=12.5
  Sentadilla hack: peso_anterior=20.0, valor_cambio=5.0 -> peso_sugerido=20.0
  Press francés con barra Z: peso_anterior=22.5, valor_cambio=5.0 -> peso_sugerido=22.5
  Hiperextensiones inversas/zancadas: peso_anterior=5.0, valor_cambio=5.0 -> peso_sugerido=5.0

Fix: si el candidato redondeado no representa un cambio real en la dirección
esperada, forzar el siguiente múltiplo de 2.5kg en esa dirección
(peso_anterior +/- 2.5).
"""

from django.contrib.auth.models import User
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import GymDecisionLog


class PesoSugeridoIncrementoMinimoBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_x5_incr_min', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(
            user=self.user, defaults={'nombre': 'TestX5', 'dias_disponibles': 4}
        )

    def _log(self, **kwargs):
        defaults = dict(
            cliente=self.cliente,
            ejercicio='Test X5 Ejercicio',
            accion='subir_peso',
            valor_cambio=5.0,
            peso_anterior=20.0,
            reps_anteriores=10,
            rpe_anterior=7.0,
            motivo='test',
        )
        defaults.update(kwargs)
        return GymDecisionLog.objects.create(**defaults)


# ── 6 casos reales de producción: subir_peso con peso_anterior bajo ─────────

class TestCasosRealesSubirPesoBajo(PesoSugeridoIncrementoMinimoBase):
    def test_pallof_press_20kg(self):
        log = self._log(ejercicio='Pallof Press', peso_anterior=20.0, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 22.5)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)

    def test_pallof_press_15kg(self):
        log = self._log(ejercicio='Pallof Press', peso_anterior=15.0, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 17.5)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)

    def test_pallof_press_12_5kg(self):
        log = self._log(ejercicio='Pallof Press', peso_anterior=12.5, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 15.0)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)

    def test_sentadilla_hack_20kg(self):
        log = self._log(ejercicio='Sentadilla hack', peso_anterior=20.0, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 22.5)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)

    def test_press_frances_barra_z_22_5kg(self):
        log = self._log(ejercicio='Press francés con barra Z', peso_anterior=22.5, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 25.0)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)

    def test_hiperextensiones_inversas_zancadas_5kg(self):
        log = self._log(ejercicio='Hiperextensiones inversas/zancadas', peso_anterior=5.0, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 7.5)
        self.assertGreater(log.peso_sugerido, log.peso_anterior)


# ── Caso simétrico: bajar_peso con peso ligero ───────────────────────────────

class TestCasoSimetricoBajarPesoLigero(PesoSugeridoIncrementoMinimoBase):
    def test_bajar_peso_5kg_no_se_congela(self):
        """
        bajar_peso es una intervención de seguridad (RPE alto/fallo). Si el
        redondeo no reduce de verdad, el usuario sigue expuesto a la carga
        que causó el problema.
        """
        log = self._log(accion='bajar_peso', peso_anterior=5.0, valor_cambio=10.0)
        self.assertEqual(log.peso_sugerido, 2.5)
        self.assertLess(log.peso_sugerido, log.peso_anterior)


# ── Regresión: pesos ya no afectados por el bug siguen igual que antes ──────

class TestRegresionSinCambioDeComportamiento(PesoSugeridoIncrementoMinimoBase):
    def test_subir_peso_100kg_sigue_dando_105(self):
        log = self._log(accion='subir_peso', peso_anterior=100.0, valor_cambio=5.0)
        self.assertEqual(log.peso_sugerido, 105.0)

    def test_bajar_peso_caso_real_fallida_54_575kg_sigue_dando_50(self):
        """
        Caso real de producción: único log marcado 'fallida' del usuario.
        No debe cambiar con este fix.
        """
        log = self._log(accion='bajar_peso', peso_anterior=54.575, valor_cambio=10.0, resultado='fallida')
        self.assertEqual(log.peso_sugerido, 50.0)


# ── peso_sugerido_para_fase hereda el fix cuando el bucket es compatible ────

class TestPesoSugeridoParaFaseHeredaFix(PesoSugeridoIncrementoMinimoBase):
    def test_bucket_compatible_hereda_incremento_minimo(self):
        """
        Con bucket compatible (mismo rango de reps), peso_sugerido_para_fase
        cae a self.peso_sugerido (aplica=False en resolver_peso_objetivo).
        El fix debe verse reflejado también por esta vía, que es la que usa
        plan_dinamico_service para fijar el peso de la sesión siguiente.
        """
        log = self._log(
            ejercicio='Pallof Press', accion='subir_peso',
            peso_anterior=20.0, valor_cambio=5.0,
            reps_anteriores=10, rpe_anterior=7.0,
        )
        peso, motivo = log.peso_sugerido_para_fase(
            rep_range_hoy='10-12', rpe_objetivo_hoy=7, es_descarga_hoy=False,
        )
        self.assertEqual(peso, 22.5)
        self.assertIsNone(motivo)
