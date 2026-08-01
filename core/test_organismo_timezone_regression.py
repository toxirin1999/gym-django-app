"""
Regresión: "SISTEMA HOY" seguía en EN_MARGEN tras completar el gym (jul-2026).

Causa raíz confirmada por lectura de código:
_check_en_margen() (core/organismo.py) usaba `date.today()` (reloj OS, no
timezone-aware) en vez de `timezone.localdate()` (respeta TIME_ZONE=
'Europe/Madrid') en dos sitios relacionados:

1. Check 6 — detectar si ya existe un EntrenoRealizado hoy.
2. La construcción de `accion_url` del botón "Empezar entrenamiento", que
   embebe esa fecha en la URL → briefing_entrenamiento → entrenamiento_activo
   → guardar_entrenamiento_activo, donde se usa tal cual como
   EntrenoRealizado.fecha (entrenos/views.py línea ~4145).

Si el reloj del servidor no está en Europe/Madrid (p. ej. UTC, típico en
PaaS), ambos usos de `date.today()` divergen de `timezone.localdate()`
durante la ventana horaria en que ambas fechas no coinciden (entrenar de
madrugada en Madrid), y la sesión terminaba guardándose con la fecha
equivocada — por lo que un Check 6 posterior (aunque corrigiera solo su
propio uso) podía seguir sin encontrarla.

El fix normaliza todo el archivo a timezone.localdate(), incluida la URL.

Además, se confirma un segundo gap real: el registro rápido de actividad
(`entrenos/views.py::registrar_actividad_libre`) permite tipo='gym' sin pasar
por EntrenoRealizado, y el Check 6 original solo miraba EntrenoRealizado.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, ActividadRealizada
from rutinas.models import Rutina
from core.organismo import resolver_estado_sistema_hoy, _check_en_margen


class TestOrganismoUrlAccionUsaLocaldate(TestCase):
    """La fecha embebida en accion_url debe ser timezone.localdate(), no date.today()."""

    def setUp(self):
        self.user = User.objects.create_user('test_org_tz', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_accion_url_en_margen_lleva_fecha_localdate(self):
        decision_gym_viable = {
            'estado': 'entrenar',
            'entrenamiento': {
                'ejercicios': [{'nombre': 'Sentadilla'}],
                'rutina_nombre': 'Rutina Test TZ',
            },
        }
        estado = _check_en_margen(self.user, decision_gym=decision_gym_viable)

        self.assertIsNotNone(estado, "Debe resolver EN_MARGEN con esta decisión sintética")
        fecha_esperada = timezone.localdate().strftime('%Y-%m-%d')
        self.assertIn(
            f'fecha={fecha_esperada}',
            estado['accion_url'],
            "La URL de 'Empezar entrenamiento' debe llevar la fecha de "
            "timezone.localdate(), la misma que usará guardar_entrenamiento_activo "
            "para crear el EntrenoRealizado — si diverge, Check 6 nunca lo encuentra."
        )

    def test_entreno_realizado_con_localdate_bloquea_en_margen(self):
        """
        Caso base: EntrenoRealizado guardado con timezone.localdate() (la fecha
        real que usa el resto del proyecto) debe bloquear EN_MARGEN.
        decision_gym se pasa ya calculado para aislar Check 6 del resto del
        pipeline de obtener_sesion_recomendada_hoy.
        """
        rutina = Rutina.objects.create(nombre='Rutina Test TZ base', programa=None)
        EntrenoRealizado.objects.create(
            cliente=self.cliente,
            rutina=rutina,
            fecha=timezone.localdate(),
            duracion_minutos=45,
            volumen_total_kg=1000.0,
        )
        decision_gym_viable = {
            'estado': 'entrenar',
            'entrenamiento': {
                'ejercicios': [{'nombre': 'Sentadilla'}],
                'rutina_nombre': 'Rutina Test TZ base',
            },
        }
        estado = resolver_estado_sistema_hoy(self.user, decision_gym=decision_gym_viable)

        self.assertNotEqual(estado['estado'], 'EN_MARGEN')


class TestOrganismoActividadRealizadaGymDirecta(TestCase):
    """
    Gap real: registrar_actividad_libre permite tipo='gym' sin EntrenoRealizado.
    Check 6 debe cubrir también este camino.
    """

    def setUp(self):
        self.user = User.objects.create_user('test_org_act', password='x')
        self.cliente = Cliente.objects.get(user=self.user)

    def test_actividad_realizada_gym_sin_entreno_bloquea_en_margen(self):
        ActividadRealizada.objects.create(
            cliente=self.cliente,
            tipo='gym',
            titulo='Gym registrado rápido',
            fecha=timezone.localdate(),
            fuente='manual',
        )

        decision_gym_viable = {
            'estado': 'entrenar',
            'entrenamiento': {
                'ejercicios': [{'nombre': 'Sentadilla'}],
                'rutina_nombre': 'Rutina Test',
            },
        }
        estado = resolver_estado_sistema_hoy(self.user, decision_gym=decision_gym_viable)

        self.assertNotEqual(
            estado['estado'],
            'EN_MARGEN',
            "Un registro rápido de gym (ActividadRealizada sin EntrenoRealizado) "
            "también debe considerarse 'sesión ya completada hoy'."
        )
