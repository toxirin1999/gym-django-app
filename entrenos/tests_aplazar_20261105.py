"""5-nov-2026 · Aplazar la sesión de hoy: Ahora, Rutina y Plan leen lo mismo.

Prueba de aceptación de David: aplazar el Día 4 del jueves al viernes.
- Ahora: «Hoy descansas: pasaste el Día 4 a mañana».
- Rutina: el jueves, descanso con ese motivo; el viernes, el Día 4.
- Plan: el Día 4 pasa al viernes y es el próximo hito; el Día 5 se recoloca
  según la regla semanal (una por día, también en fin de semana) y, si ya no
  cabe, se dice.
- Un descanso previsto sigue con su texto de siempre.
"""

from datetime import timedelta

from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.tests_semana_rutina import LUNES, Base
from rutinas.models import Rutina

JUEVES = LUNES + timedelta(days=3)
VIERNES, SABADO, DOMINGO = LUNES + timedelta(days=4), LUNES + timedelta(days=5), LUNES + timedelta(days=6)
DIA4, DIA5 = 'Dia 4 - Hipertrofia — Metabólica', 'Dia 5 - Hipertrofia — Metabólica'


class AplazarJuevesAViernes(Base):
    def setUp(self):
        super().setUp()
        # Día 1 el martes (Base); Día 2 y Día 3 el miércoles, al día.
        for n, fecha in ((2, LUNES + timedelta(days=2)), (3, LUNES + timedelta(days=2))):
            rutina, _ = Rutina.objects.get_or_create(nombre=f'Dia {n} - Hipertrofia — Metabólica')
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=fecha)

    def _aplazar(self, hoy, hasta):
        SesionProgramada.objects.create(cliente=self.cliente, fecha_prevista=hoy, nombre_sesion=DIA4,
                                        pospuesta_hasta=hasta)

    def test_rutina_y_plan_siguen_la_sesion_aplazada(self):
        from entrenos.services.semana_rutina_service import semana_segun_cola, sesiones_para_plan
        from entrenos.services.trayectoria_plan_service import _proximo_hito
        self._aplazar(JUEVES, VIERNES)
        s = semana_segun_cola(self.cliente, JUEVES)
        self.assertEqual(s['dias'][JUEVES]['tipo'], 'descanso')
        self.assertEqual(s['dias'][JUEVES]['aplazada'], DIA4)
        self.assertEqual(s['dias'][VIERNES]['nombre'], DIA4)
        self.assertEqual(s['dias'][SABADO]['nombre'], DIA5)  # el Día 5, recolocado
        self.assertEqual(s['fuera'], [])

        sesiones, _ = sesiones_para_plan(self.cliente, JUEVES)
        dia4 = next(x for x in sesiones if x['nombre'] == DIA4)
        self.assertEqual(dia4['fecha_efectiva'], VIERNES)
        self.assertFalse(any(x['fecha_efectiva'] == JUEVES and not x['realizada'] for x in sesiones))
        hito = _proximo_hito(JUEVES, {'sesiones': sesiones, 'evaluacion': None}, None, None)
        self.assertEqual((hito['etiqueta'], hito['fecha']), (DIA4, VIERNES))

    def test_si_ya_no_cabe_se_dice(self):
        from entrenos.services.semana_rutina_service import nota_semana, semana_segun_cola
        # Sábado: quedan el Día 4 y el Día 5; aplazado al domingo, el Día 5 no entra.
        SesionProgramada.objects.create(cliente=self.cliente, fecha_prevista=SABADO, nombre_sesion=DIA4,
                                        pospuesta_hasta=DOMINGO)
        s = semana_segun_cola(self.cliente, SABADO)
        self.assertEqual(s['dias'][SABADO]['tipo'], 'descanso')
        self.assertEqual(s['dias'][DOMINGO]['nombre'], DIA4)
        self.assertEqual(len(s['fuera']), 1)
        self.assertIn('no entra Día 5', nota_semana(s))

    def test_rutina_pantalla(self):
        from django.urls import reverse
        from unittest.mock import patch
        self._aplazar(JUEVES, VIERNES)
        self.client.force_login(self.user)
        with patch('django.utils.timezone.localdate', return_value=JUEVES):
            html = self.client.get(reverse('entrenos:rutina_silenciosa_preview', args=[self.cliente.id])).content.decode()
        self.assertIn('Hoy descansas: pasaste el Día 4 a mañana.', html)
        self.assertNotIn('Tu sesión está preparada', html)


class Textos(Base):
    def setUp(self):
        super().setUp()
        from unittest.mock import patch
        p = patch('core.organismo._sesion_gym_hecha_hoy', return_value=False)
        p.start()
        self.addCleanup(p.stop)

    def test_texto_aplazada(self):
        from entrenos.services.semana_rutina_service import texto_aplazada
        self.assertEqual(texto_aplazada(DIA4, VIERNES, JUEVES), 'Hoy descansas: pasaste el Día 4 a mañana.')
        self.assertEqual(texto_aplazada(DIA4, SABADO, JUEVES), 'Hoy descansas: pasaste el Día 4 al sábado 17.')

    def test_ahora_usa_el_motivo_del_aplazamiento(self):
        from core.organismo import _estado_silencio, estado_operativo_visible
        decision = {'estado': 'descanso', 'causa_principal': 'pospuesto_usuario',
                    'mensaje': 'Hoy descansas: pasaste el Día 4 a mañana.'}
        estado = _estado_silencio(self.user, decision)
        self.assertEqual(estado['texto'], 'Hoy descansas: pasaste el Día 4 a mañana.')
        self.assertEqual(estado_operativo_visible('SILENCIO', estado['motivo']), 'DESCANSAR')

    def test_descanso_previsto_sigue_igual(self):
        from core.organismo import _estado_silencio
        estado = _estado_silencio(self.user, {'estado': 'descanso', 'causa_principal': 'descanso_planificado',
                                              'mensaje': 'Hoy el plan marca descanso.'})
        self.assertEqual(estado['texto'], 'Hoy el plan marca descanso.')
        from entrenos.services.semana_rutina_service import semana_segun_cola
        s = semana_segun_cola(self.cliente, DOMINGO)
        self.assertNotIn('aplazada', s['dias'][DOMINGO])
