from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from clientes.models import Cliente
from diario.models import ProsocheDiario, ProsocheMes, SeguimientoVires
from diario.services.senales_entrenamiento import categorias_entrenamiento_con_productor, obtener_senal_recuperacion_confirmada
from entrenos.models import SenalEntrenamientoAutorizada, SugerenciaPlan
from entrenos.services.sugerencias_service import SugerenciaNoVigente, aceptar_sugerencia


class PuenteDiario9BTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('puente9b')
        self.cliente = Cliente.objects.get(user=self.user)
        self.hoy = timezone.localdate()
        self.mes = ProsocheMes.objects.create(usuario=self.user, mes='Agosto', año=self.hoy.year)

    def dato(self, offset=0, confirmar=False, **campos):
        fecha = self.hoy - timedelta(days=offset)
        vires = SeguimientoVires.objects.create(usuario=self.user, fecha=fecha, **campos)
        if confirmar:
            ProsocheDiario.objects.create(prosoche_mes=self.mes, fecha=fecha,
                apertura_confirmada_en=timezone.now(), cierre_confirmado_en=timezone.now())
        return vires

    def test_solo_recuperacion_tiene_productor(self):
        self.assertEqual(categorias_entrenamiento_con_productor(), {
            'recuperacion': True, 'disponibilidad': False, 'continuidad': False,
            'relacion_entrenamiento': False})

    def test_energia_texto_habitos_y_checkbox_no_producen_senal(self):
        self.dato(confirmar=True, nivel_energia=1, nivel_estres=5, entrenamiento_realizado=True,
                  notas='privado', molestia_nota='privado', descripcion_entrenamiento='privado')
        self.assertEqual(obtener_senal_recuperacion_confirmada(self.user, fecha_ref=self.hoy), {'hay_senal': False})

    def test_vires_huerfano_no_produce_senal(self):
        for offset in (0, 1): self.dato(offset, cuerpo_cierre='dolorido', molestia_zona='rodilla')
        self.assertEqual(obtener_senal_recuperacion_confirmada(self.user, fecha_ref=self.hoy), {'hay_senal': False})

    def test_evidencia_confirmada_sostiene_recuperacion_sin_texto(self):
        for offset in (0, 1): self.dato(offset, confirmar=True, cuerpo_cierre='dolorido', molestia_zona='rodilla')
        resultado = obtener_senal_recuperacion_confirmada(self.user, fecha_ref=self.hoy)
        self.assertEqual((resultado['categoria'], resultado['intensidad']), ('recuperacion', 'alta'))
        self.assertNotIn('texto', repr(resultado).lower()); self.assertNotIn('nota', repr(resultado).lower())

    def test_aceptacion_publica_solo_evidencia_confirmada(self):
        for offset in (0, 1): self.dato(offset, confirmar=True, cuerpo_cierre='dolorido')
        sugerencia = SugerenciaPlan.objects.create(cliente=self.cliente, patron='diario_tendencia_corporal', texto='vigilar')
        aceptar_sugerencia(sugerencia, fecha_ref=self.hoy)
        senal = SenalEntrenamientoAutorizada.objects.get()
        self.assertEqual(senal.categoria, 'recuperacion')
        self.assertEqual(set(senal.evidencia_tecnica), {'seguimiento_vires_ids', 'fecha_clasificacion', 'codigo_clasificacion'})

    def test_aceptacion_rechaza_evidencia_no_confirmada(self):
        for offset in (0, 1): self.dato(offset, cuerpo_cierre='dolorido')
        sugerencia = SugerenciaPlan.objects.create(cliente=self.cliente, patron='diario_tendencia_corporal', texto='vigilar')
        with self.assertRaises(SugerenciaNoVigente): aceptar_sugerencia(sugerencia, fecha_ref=self.hoy)
