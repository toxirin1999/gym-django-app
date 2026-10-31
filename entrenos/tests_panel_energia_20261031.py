"""31-oct-2026 · Panel del cuerpo: la energía al empezar cuenta como señal."""

from datetime import timedelta

from entrenos.models import EntrenoRealizado
from entrenos.services import estado_carga_service as ec
from entrenos.tests_estado_carga_20261025 import HOY, Base
from rutinas.models import Rutina


class EnergiaComoSenal(Base):
    def setUp(self):
        super().setUp()
        self.rutina = Rutina.objects.create(nombre='Dia 1')

    def energia(self, dias_atras, valor):
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina,
                                        fecha=HOY - timedelta(days=dias_atras), energia_pre_sesion=valor)

    def test_te_pasas_con_energia_baja_aunque_el_reloj_aun_no_compare(self):
        # Como la semana del 26-oct: carga +50 %, reloj sin media, energía 5
        # frente a 7 habitual el martes y el viernes.
        self.semanas_normales(400)
        for d in (0, 1, 2, 3):
            self.actividad(d, 600)
        for d in (8, 9, 10):
            self.energia(d, 7)
        self.energia(0, 5)
        self.energia(3, 5)
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'te_pasas')
        self.assertIn('2 con tu energía baja al empezar', e['frase'])

    def test_un_solo_dia_de_energia_baja_no_basta(self):
        self.semanas_normales(400)
        for d in (0, 1, 2, 3):
            self.actividad(d, 600)
        for d in (8, 9, 10):
            self.energia(d, 7)
        self.energia(0, 5)
        self.assertEqual(ec.estado_carga(self.cliente, HOY)['respuesta'], 'conociendote')

    def test_energia_baja_suma_al_reloj_para_descansa(self):
        self.semanas_normales()
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        self.cuerpo(['mal', 'bien', 'bien', 'mal', 'bien'])
        for d in (8, 9, 10):
            self.energia(d, 7)
        self.energia(2, 4)
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'descansa')
        self.assertIn('2 según el reloj y 1 con tu energía baja', e['frase'])

    def test_el_dia_sale_en_ambar_en_el_panel(self):
        from entrenos.services.panel_cuerpo_service import dias_recientes
        for d in (8, 9, 10):
            self.energia(d, 7)
        self.energia(1, 5)
        dias = dias_recientes(ec.estado_carga(self.cliente, HOY))
        ayer = dias[-2]
        self.assertEqual(ayer['nivel'], 'ambar')
        self.assertIn('Energía 5 al empezar', ayer['nombre'])
