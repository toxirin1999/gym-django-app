"""
JOI Phase 59E — Narrativa con bisturí.

Objetivo: que NarrativaActiva influya en JOI sin convertir hipótesis en
sentencia. JOI puede confrontar, pero solo desde evidencia concreta. Si la
señal es parcial, el lenguaje debe ser parcial. Si no hay señal suficiente,
silencio o tono bajo.

Extiende _bloque_marco_narrativo() (Phase 59D.0.1 ya cubría 'cero'/'nunca'/
'todo'/'nada' genéricos y la regla bisturí/no-martillo). Esta fase añade:

1. Frases absolutas específicas prohibidas ('siempre', 'no haces nada',
   'estás evitando todo', 'cero límites', 'cero hábitos').
2. Categorías de evidencia explícitas requeridas antes de confrontar.
3. Instrucción de silencio/tono bajo si no hay evidencia suficiente.
4. Regla de no-contradicción: la narrativa no anula un dato positivo del día.
5. MODO BAJO: si NarrativaActiva tiene confianza baja (<0.5) o está en
   estado 'borrador', el marco exige lenguaje tentativo ('puede que',
   'parece que', 'hay una tensión', 'no lo tomaría como conclusión todavía')
   y desactiva la confrontación directa.
6. El validador semántico (validador_semantico.py) detecta como red de
   seguridad de salida las frases absolutas más graves ('cero hábitos',
   'cero límites', 'no haces nada', 'estás evitando todo').
"""

from django.contrib.auth.models import User
from django.test import TestCase

from joi.services import _bloque_marco_narrativo
from joi.models import NarrativaActiva
from joi.validador_semantico import validar_semantica_joi


class TestFrasesAbsolutasEspecificas(TestCase):
    """1. El marco lista frases absolutas específicas como prohibidas."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_frases', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.7,
            capa_corta='Algo concreto.',
        )

    def test_lista_frases_absolutas_prohibidas(self):
        resultado = _bloque_marco_narrativo(self.user)
        for frase in ("'siempre'", "'no haces nada'", "'estás evitando todo'",
                       "'cero límites'", "'cero hábitos'"):
            self.assertIn(frase, resultado,
                          f"El marco debe prohibir explícitamente la frase {frase}")


class TestCategoriasDeEvidencia(TestCase):
    """2. El marco exige una de cuatro categorías de evidencia antes de confrontar."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_evidencia', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.7,
            capa_corta='Algo concreto.',
        )

    def test_categorias_de_evidencia_explicitas(self):
        resultado = _bloque_marco_narrativo(self.user).lower()
        self.assertIn('hábito concreto no ejecutado', resultado)
        self.assertIn('patrón repetido real', resultado)
        self.assertIn('dato fisiológico o de entrenamiento reciente', resultado)
        self.assertIn('diario o cierre del día', resultado)


class TestSilencioSiNoHaySenal(TestCase):
    """3. Sin evidencia en ninguna categoría, JOI debe callar o bajar el tono."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_silencio', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.7,
            capa_corta='Algo concreto.',
        )

    def test_instruccion_de_silencio_si_falta_evidencia(self):
        resultado = _bloque_marco_narrativo(self.user).lower()
        self.assertIn('no confrontes', resultado)
        self.assertIn('guarda silencio', resultado)
        self.assertIn('tono bajo', resultado)


class TestNoContradiceDatosPositivos(TestCase):
    """4. La narrativa no debe forzar una lectura negativa sobre un dato positivo del día."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_positivos', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.7,
            capa_corta='Algo concreto.',
        )

    def test_regla_no_contradiccion_presente(self):
        resultado = _bloque_marco_narrativo(self.user).lower()
        self.assertIn('no contradicción', resultado)
        self.assertIn('dato bueno del día', resultado)


class TestModoBajoConConfianzaBaja(TestCase):
    """5a. Confianza < 0.5 → modo bajo obligatorio con lenguaje tentativo."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_modobajo', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.3,
            capa_corta='Hipótesis poco consolidada.',
        )

    def test_modo_bajo_presente_con_confianza_baja(self):
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('MODO BAJO', resultado)
        for frase in ('puede que', 'parece que', 'hay una tensión',
                       'no lo tomaría como conclusión todavía'):
            self.assertIn(frase, resultado.lower())


class TestModoBajoConEstadoBorrador(TestCase):
    """5b. estado='borrador' → modo bajo obligatorio aunque la confianza no sea baja."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_borrador', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='borrador', confianza=0.7,
            capa_corta='Postura en construcción.',
        )

    def test_modo_bajo_presente_en_borrador(self):
        resultado = _bloque_marco_narrativo(self.user)
        self.assertIn('MODO BAJO', resultado)


class TestSinModoBajoConConfianzaAltaYActiva(TestCase):
    """5c. confianza >= 0.5 y estado='activa' → sin bloque MODO BAJO forzado."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester_bisturi_alta', password='x')
        NarrativaActiva.objects.create(
            user=self.user, estado='activa', confianza=0.8,
            capa_corta='Postura consolidada.',
        )

    def test_sin_modo_bajo_con_confianza_alta(self):
        resultado = _bloque_marco_narrativo(self.user)
        self.assertNotIn('MODO BAJO', resultado)


class TestValidadorDetectaAbsolutosNarrativos(TestCase):
    """6. Red de seguridad de salida: el validador detecta frases absolutas graves."""

    def test_cero_habitos_detectado(self):
        r = validar_semantica_joi("Tienes cero hábitos de movilidad.", modulo='gym')
        self.assertFalse(r['valida'])
        self.assertTrue(any('absoluto_narrativo' in v for v in r['violaciones']))

    def test_cero_limites_detectado(self):
        r = validar_semantica_joi("Llevas cero límites en la alimentación.", modulo='gym')
        self.assertFalse(r['valida'])
        self.assertTrue(any('absoluto_narrativo' in v for v in r['violaciones']))

    def test_no_haces_nada_detectado(self):
        r = validar_semantica_joi("No haces nada para cuidar la espalda.", modulo='gym')
        self.assertFalse(r['valida'])
        self.assertTrue(any('absoluto_narrativo' in v for v in r['violaciones']))

    def test_estas_evitando_todo_detectado(self):
        r = validar_semantica_joi("Estás evitando todo lo que te incomoda.", modulo='diario')
        self.assertFalse(r['valida'])
        self.assertTrue(any('absoluto_narrativo' in v for v in r['violaciones']))

    def test_observacion_concreta_no_se_marca(self):
        """Una observación con tiempo concreto no debe disparar el validador."""
        r = validar_semantica_joi("Llevas 5 días sin trabajar movilidad de cadera.", modulo='gym')
        self.assertTrue(r['valida'], msg=f"Violaciones inesperadas: {r['violaciones']}")
