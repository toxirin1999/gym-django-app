from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente

from .models import RegistroDisponibilidad
from .services import (
    _aplicar_ingesta,
    _deduplicar_ingestas,
    calcular_recursos_disponibles,
    TECHO_NIVEL,
)


class MomentoEfectivoTests(TestCase):
    """momento_ingesta (cuándo ocurrió) no debe confundirse con timestamp (cuándo se guardó)."""

    def setUp(self):
        self.user = User.objects.create_user('disp_momento', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_momento_efectivo_usa_momento_ingesta_si_existe(self):
        ahora = timezone.now()
        r = RegistroDisponibilidad.objects.create(
            cliente=self.cliente, nivel='B', timestamp=ahora, momento_ingesta=ahora - timedelta(hours=3),
        )
        self.assertEqual(r.momento_efectivo, ahora - timedelta(hours=3))

    def test_momento_efectivo_cae_a_timestamp_sin_momento_ingesta(self):
        ahora = timezone.now()
        r = RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='B', timestamp=ahora)
        self.assertEqual(r.momento_efectivo, ahora)

    def test_dos_registros_guardados_a_la_vez_no_colapsan_si_ocurrieron_en_momentos_distintos(self):
        """Bug reportado: dos ingestas registradas retroactivamente en el mismo minuto
        (mismo timestamp de guardado) pero de comidas reales separadas por horas no deben
        tratarse como una corrección duplicada — deben conservarse ambas, en su orden real."""
        guardado = timezone.now()
        r_tarde = RegistroDisponibilidad.objects.create(
            cliente=self.cliente, nivel='C', timestamp=guardado, momento_ingesta=guardado - timedelta(hours=5),
        )
        r_reciente = RegistroDisponibilidad.objects.create(
            cliente=self.cliente, nivel='B', timestamp=guardado, momento_ingesta=guardado - timedelta(minutes=10),
        )
        resultado = _deduplicar_ingestas([r_reciente, r_tarde])  # orden de llegada invertido a propósito
        self.assertEqual(len(resultado), 2, msg='Separados por horas reales: no deben colapsar aunque compartan timestamp de guardado.')
        self.assertEqual(resultado[0].pk, r_tarde.pk)
        self.assertEqual(resultado[1].pk, r_reciente.pk)

    def test_dos_registros_a_menos_de_5_min_reales_si_colapsan(self):
        base = timezone.now() - timedelta(hours=2)
        r1 = RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='C', momento_ingesta=base)
        r2 = RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='B', momento_ingesta=base + timedelta(minutes=2))
        resultado = _deduplicar_ingestas([r1, r2])
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].pk, r2.pk, msg='Prevalece la más reciente (corrección).')


class AplicarIngestaTests(TestCase):

    def test_evento_sube_hacia_el_techo_con_retornos_decrecientes(self):
        score = _aplicar_ingesta(55.0, 'B')
        self.assertAlmostEqual(score, 55.0 + (TECHO_NIVEL['B'] - 55.0) * 0.5)

    def test_evento_no_mueve_score_si_ya_esta_en_o_sobre_su_techo(self):
        score = _aplicar_ingesta(80.0, 'C')  # techo C = 45, score ya muy por encima
        self.assertEqual(score, 80.0)

    def test_completa_es_el_unico_que_puede_llegar_a_banda_alta(self):
        score = 74.0
        self.assertEqual(_aplicar_ingesta(score, 'B'), score, msg='Techo B=70 < 74: no mueve.')
        self.assertGreater(_aplicar_ingesta(score, 'A'), score, msg='Techo A=100 > 74: sí mueve.')


class CalcularRecursosDisponiblesTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('disp_calculo', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        cache.clear()  # calcular_recursos_disponibles cachea por cliente.id — evita fugas entre tests

    def test_sin_registros_devuelve_sin_datos(self):
        resultado = calcular_recursos_disponibles(self.cliente)
        self.assertEqual(resultado, {'score': None, 'banda': None, 'motivo': 'sin_datos'})

    def test_repetir_suficiente_converge_sin_saturar_a_alta(self):
        ahora = timezone.now()
        for i in range(6):
            RegistroDisponibilidad.objects.create(
                cliente=self.cliente, nivel='B', momento_ingesta=ahora - timedelta(hours=(6 - i) * 3),
            )
        resultado = calcular_recursos_disponibles(self.cliente)
        self.assertLess(resultado['score'], 75, msg='Sin ninguna Completa, no debe alcanzar la banda Alta.')

    def test_erosion_real_se_aplica_entre_ingestas_registradas_a_la_vez(self):
        """Reproduce el caso reportado: dos ingestas guardadas en el mismo instante
        pero con momento_ingesta separado por horas deben erosionar el score entre
        medias, no tratarse como un único salto sin paso de tiempo."""
        guardado = timezone.now()
        RegistroDisponibilidad.objects.create(
            cliente=self.cliente, nivel='B', timestamp=guardado, momento_ingesta=guardado - timedelta(hours=8),
        )
        RegistroDisponibilidad.objects.create(
            cliente=self.cliente, nivel='B', timestamp=guardado, momento_ingesta=guardado - timedelta(hours=1),
        )
        con_separacion = calcular_recursos_disponibles(self.cliente)['score']

        # Mismo par de eventos pero sin separación real (momento_ingesta = guardado en ambos)
        cache.clear()  # el borrado/recreado es directo por ORM, no pasa por la vista que invalida el caché
        self.cliente.registros_disponibilidad.all().delete()
        RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='B', timestamp=guardado, momento_ingesta=guardado)
        RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='B', timestamp=guardado, momento_ingesta=guardado)
        sin_separacion = calcular_recursos_disponibles(self.cliente)['score']

        self.assertNotEqual(con_separacion, sin_separacion, msg='8h de separación real deben erosionar el score de forma distinta a registrarlas juntas.')

    def test_segunda_llamada_se_sirve_desde_cache(self):
        RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='B')
        primero = calcular_recursos_disponibles(self.cliente)
        # Cambio directo por ORM que normalmente cambiaría el resultado —
        # si la segunda llamada sigue devolviendo lo mismo, viene de caché.
        RegistroDisponibilidad.objects.create(cliente=self.cliente, nivel='A')
        segundo = calcular_recursos_disponibles(self.cliente)
        self.assertEqual(primero, segundo)


class RegistrarViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('disp_view', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.client = Client()
        self.client.login(username='disp_view', password='x')
        cache.clear()

    def test_registrar_sin_hace_horas_deja_momento_ingesta_null(self):
        self.client.post(reverse('disponibilidad:registrar', kwargs={'cliente_id': self.cliente.id}), {'nivel': 'B'})
        registro = RegistroDisponibilidad.objects.get(cliente=self.cliente)
        self.assertIsNone(registro.momento_ingesta)

    def test_registrar_con_hace_horas_fija_momento_ingesta_en_el_pasado(self):
        antes = timezone.now()
        self.client.post(
            reverse('disponibilidad:registrar', kwargs={'cliente_id': self.cliente.id}),
            {'nivel': 'C', 'hace_horas': '3'},
        )
        registro = RegistroDisponibilidad.objects.get(cliente=self.cliente)
        self.assertIsNotNone(registro.momento_ingesta)
        delta = antes - registro.momento_ingesta
        self.assertAlmostEqual(delta.total_seconds(), 3 * 3600, delta=5)

    def test_hace_horas_fuera_de_rango_es_rechazado(self):
        response = self.client.post(
            reverse('disponibilidad:registrar', kwargs={'cliente_id': self.cliente.id}),
            {'nivel': 'C', 'hace_horas': '48'},
        )
        self.assertEqual(response.status_code, 400)

    def test_registrar_invalida_el_cache_de_recursos_disponibles(self):
        from .services import calcular_recursos_disponibles
        primero = calcular_recursos_disponibles(self.cliente)  # cachea 'sin_datos'
        self.client.post(reverse('disponibilidad:registrar', kwargs={'cliente_id': self.cliente.id}), {'nivel': 'A'})
        segundo = calcular_recursos_disponibles(self.cliente)
        self.assertNotEqual(primero, segundo, msg='Tras registrar, el caché debe invalidarse y reflejar el nuevo registro.')
