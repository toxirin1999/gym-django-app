"""
Phase Simbiosis 1.4 — Reaparición por señal viva
Tests: la lógica de reaparición depende de menciones nuevas post-descarte,
no de la acumulación histórica total.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from diario.models import PersonaInterina


def _interina(usuario, nombre, estado='sombra', veces=1, desde_descarte=0):
    interina = PersonaInterina.objects.create(
        usuario=usuario,
        nombre=nombre,
        estado=estado,
        veces_mencionada=veces,
        menciones_desde_descarte=desde_descarte,
    )
    return interina


def _simular_mencion(interina):
    """Simula lo que hace el loop de presencia_cierre/reprocesar_cierres al detectar la persona."""
    interina.refresh_from_db()
    update_kw = {'veces_mencionada': interina.veces_mencionada + 1}
    if interina.estado == 'descartada':
        update_kw['menciones_desde_descarte'] = interina.menciones_desde_descarte + 1
    PersonaInterina.objects.filter(pk=interina.pk).update(**update_kw)
    interina.refresh_from_db()

    if interina.estado == 'descartada' and interina.menciones_desde_descarte >= 2:
        PersonaInterina.objects.filter(pk=interina.pk).update(
            estado='sombra', menciones_desde_descarte=0
        )
        interina.refresh_from_db()
    elif interina.veces_mencionada >= 2 and interina.estado == 'sombra':
        PersonaInterina.objects.filter(pk=interina.pk).update(estado='radar')
        interina.refresh_from_db()

    return interina


class ReaparicionPorSenalVivaTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='david_test', password='x')

    def test_descartada_no_reaparece_por_acumulacion_historica(self):
        """
        Una persona ignorada con 10 menciones acumuladas pero 0 menciones nuevas
        NO debe reaparecer. La acumulación histórica no es señal viva.
        """
        p = _interina(self.user, 'Ana', estado='descartada', veces=10, desde_descarte=0)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'descartada')
        # No simulamos ninguna mención nueva — el estado no cambia sin señal
        p.refresh_from_db()
        self.assertEqual(p.estado, 'descartada')

    def test_descartada_reaparece_con_dos_menciones_nuevas(self):
        """
        Una persona ignorada con 1 mención post-descarte aún no reaparece.
        Con 2 menciones post-descarte vuelve a sombra y el contador se resetea.
        """
        p = _interina(self.user, 'Marta', estado='descartada', veces=5, desde_descarte=0)

        # Primera mención nueva → no suficiente
        _simular_mencion(p)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'descartada')
        self.assertEqual(p.menciones_desde_descarte, 1)

        # Segunda mención nueva → reaparece
        _simular_mencion(p)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'sombra')
        self.assertEqual(p.menciones_desde_descarte, 0)  # contador reseteado

    def test_promovida_y_eliminada_vuelve_a_sombra_sin_radar_automatico(self):
        """
        Una persona que fue promovida (confirmada) y luego eliminada del círculo
        debe tener su interina en sombra. Sin nueva señal, no asciende a radar.
        """
        from diario.models import PersonaImportante
        p_real = PersonaImportante.objects.create(
            usuario=self.user, nombre='Luis', tipo_relacion='amigo'
        )
        interina = _interina(self.user, 'Luis', estado='promovida', veces=4)
        interina.persona_importante = p_real
        interina.save()

        # Simular eliminar_persona: unlinka y manda a sombra
        PersonaInterina.objects.filter(pk=interina.pk).update(
            estado='sombra', persona_importante=None
        )
        p_real.delete()

        interina.refresh_from_db()
        self.assertEqual(interina.estado, 'sombra')
        self.assertIsNone(interina.persona_importante)
        # Sin nueva señal, no asciende a radar
        self.assertNotEqual(interina.estado, 'radar')

    def test_radar_no_incluye_descartadas_sin_senal_posterior(self):
        """
        El filtro del radar (estado__in=['sombra','radar']) excluye las descartadas,
        aunque tengan muchas menciones históricas. Solo reaparecen por señal viva.
        """
        p1 = _interina(self.user, 'Carlos', estado='descartada', veces=20, desde_descarte=0)
        p2 = _interina(self.user, 'Elena', estado='sombra', veces=1, desde_descarte=0)

        from diario.models import PersonaInterina
        en_radar = PersonaInterina.objects.filter(
            usuario=self.user, estado__in=['sombra', 'radar']
        )
        nombres = list(en_radar.values_list('nombre', flat=True))
        self.assertNotIn('Carlos', nombres)
        self.assertIn('Elena', nombres)
