"""25-oct-2026 · Paso 1 del panel: estado de carga a la sombra + parada declarada."""

import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from entrenos.models import ActividadRealizada, ParadaDeclarada
from entrenos.services import estado_carga_service as ec
from entrenos.services.porque_decision_service import construir_porque
from entrenos.tests_recuperacion_20261024 import ConCliente

HOY = timezone.localdate()


class Base(ConCliente):
    def actividad(self, dias_atras, carga, minutos=60, tipo='gym'):
        return ActividadRealizada.objects.create(
            cliente=self.cliente, tipo=tipo, titulo='x', fecha=HOY - timedelta(days=dias_atras),
            duracion_minutos=minutos, carga_ua=carga,
        )

    def semanas_normales(self, carga_dia=400):
        # 4 semanas anteriores (días 7..34) con 4 sesiones por semana.
        for semana in range(4):
            for d in (0, 2, 4, 6):
                self.actividad(7 + semana * 7 + d, carga_dia)

    def cuerpo(self, niveles):
        """niveles[i] = cómo amaneció hace i días: 'bien' o 'mal'. Con media de 28 días detrás."""
        for d in range(len(niveles), 40):
            self.reloj(d, hrv=50, fc=52, sueno=7.5)
        for i, n in enumerate(niveles):
            if n == 'mal':
                self.reloj(i, hrv=40, fc=59, sueno=5.5)
            elif n == 'bien':
                self.reloj(i, hrv=50, fc=52, sueno=7.5)


class Carga(Base):
    def test_semana_frente_a_la_normal(self):
        self.semanas_normales(400)          # 1600 por semana
        for d in (0, 2, 4):
            self.actividad(d, 800)          # 2400 esta semana
        c = ec.lectura_carga(self.cliente, HOY)
        self.assertEqual((c['semana'], c['normal'], c['ratio']), (2400, 1600, 1.5))

    def test_cronometro_olvidado_no_cuenta(self):
        self.semanas_normales(400)
        self.actividad(1, 9999, minutos=2525)
        self.assertEqual(ec.lectura_carga(self.cliente, HOY)['semana'], 0)


class Respuestas(Base):
    def test_conociendote_con_pocos_dias_de_reloj(self):
        self.semanas_normales()
        self.reloj(0, hrv=50, fc=52, sueno=7.5)
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'conociendote')
        self.assertIn('Te estoy conociendo', e['frase'])

    def test_descansa(self):
        self.semanas_normales()
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        self.cuerpo(['mal', 'mal', 'bien', 'mal', 'bien'])
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'descansa')
        self.assertIn('Llevas 3 de los últimos 5 días', e['frase'])

    def test_te_pasas(self):
        self.semanas_normales(400)
        for d in (0, 1, 2, 3):
            self.actividad(d, 600)            # 2400 frente a 1600: +50 %
        self.cuerpo(['mal', 'bien', 'mal', 'bien', 'bien'])
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'te_pasas')
        self.assertIn('un 50 % más de carga', e['frase'])

    def test_puedes_dar_mas(self):
        self.semanas_normales(400)
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        self.cuerpo(['bien'] * 14)
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'dar_mas')
        self.assertIn('Te veo para más', e['frase'])

    def test_molestia_frena_el_dar_mas(self):
        from entrenos.models import EntrenoRealizado, SensacionZonaGym
        from rutinas.models import Rutina
        self.semanas_normales(400)
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        self.cuerpo(['bien'] * 14)
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=Rutina.objects.create(nombre='Dia 1'),
                                            fecha=HOY - timedelta(days=1))
        SensacionZonaGym.objects.create(cliente=self.cliente, entreno=e, zona='cuadriceps', molestia=1)
        self.assertEqual(ec.estado_carga(self.cliente, HOY)['respuesta'], 'vas_bien')

    def test_vas_bien(self):
        self.semanas_normales(400)
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        # 5 días malos repartidos en 14: ni descansa (2 en 5) ni puedes dar más (9 buenos de 14).
        self.cuerpo(['bien', 'mal', 'bien', 'bien', 'mal', 'bien', 'mal', 'bien', 'mal', 'bien', 'mal',
                     'bien', 'bien', 'bien'])
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'vas_bien')
        self.assertIn('como en tus semanas normales', e['frase'])
        json.dumps(e)


class Parada(Base):
    def test_parada_abierta_manda(self):
        self.semanas_normales()
        self.cuerpo(['mal'] * 5)
        ec.declarar_parada(self.cliente, 'enfermo', HOY - timedelta(days=2))
        e = ec.estado_carga(self.cliente, HOY)
        self.assertEqual(e['respuesta'], 'parada')
        self.assertIn('Estás enfermo desde el', e['frase'])

    def test_dias_de_parada_no_cuentan_como_malos(self):
        self.semanas_normales()
        for d in (0, 2, 4):
            self.actividad(d, 400)
        self.cuerpo(['bien', 'mal', 'mal', 'mal', 'bien', 'bien'])
        ParadaDeclarada.objects.create(cliente=self.cliente, tipo='enfermo',
                                       inicio=HOY - timedelta(days=3), fin=HOY - timedelta(days=1))
        e = ec.estado_carga(self.cliente, HOY)
        self.assertNotEqual(e['respuesta'], 'descansa')
        self.assertEqual(e['malos_5'], 0)

    def test_marcar_y_desmarcar_el_mismo_dia_no_deja_rastro(self):
        ec.declarar_parada(self.cliente, 'enfermo', HOY)
        ec.terminar_parada(self.cliente, HOY)
        self.assertFalse(ParadaDeclarada.objects.exists())

    def test_terminar_cierra_ayer(self):
        p = ec.declarar_parada(self.cliente, 'parada', HOY - timedelta(days=4))
        ec.terminar_parada(self.cliente, HOY)
        p.refresh_from_db()
        self.assertEqual(p.fin, HOY - timedelta(days=1))
        self.assertIsNone(ec.parada_en(self.cliente, HOY))

    def test_interruptor_en_la_pagina(self):
        self.client.force_login(self.user)
        url = reverse('clientes:parada_declarada')
        self.client.post(url, {'accion': 'enfermo'})
        self.assertEqual(ParadaDeclarada.objects.get(cliente=self.cliente).tipo, 'enfermo')
        r = self.client.get(reverse('clientes:salud_iphone'))
        self.assertContains(r, 'Ya he vuelto')
        self.client.post(url, {'accion': 'terminar'})
        r = self.client.get(reverse('clientes:salud_iphone'))
        self.assertContains(r, 'Estoy enfermo')
        self.assertEqual(self.client.get(url).status_code, 405)


class LecturaNormal(Base):
    def test_dia_normal_con_media(self):
        from entrenos.services.recuperacion_service import lectura_recuperacion
        self.base()
        self.reloj(0, hrv=50, fc=52, sueno=6.8)
        r = lectura_recuperacion(self.cliente, HOY)
        self.assertEqual(r['nivel'], 'normal')
        self.assertTrue(r['frase'].startswith('Llegas como siempre'))


class PorqueNormal(SimpleTestCase):
    def test_el_porque_dice_llegas_como_siempre(self):
        d = {'causa_principal': 'sesion_hoy', 'estado': 'entrenar',
             'contexto_fisico': {'recuperacion': {'nivel': 'normal', 'frase': 'Llegas como siempre: x.'}}}
        self.assertEqual(construir_porque(d), 'Llegas como siempre: x.')


class Comando(Base):
    def test_solo_lectura(self):
        self.semanas_normales()
        self.cuerpo(['bien'] * 6)
        antes = ActividadRealizada.objects.count()
        out = StringIO()
        call_command('ver_estado_carga', str(self.cliente.id), '--dias', '5', stdout=out)
        call_command('ver_estado_carga', str(self.cliente.id), '--hoy', stdout=out)
        self.assertIn('(No se ha guardado nada.)', out.getvalue())
        self.assertIn('Carga: semana', out.getvalue())
        self.assertEqual(antes, ActividadRealizada.objects.count())


class Panel(Base):
    def _get(self):
        self.client.force_login(self.user)
        return self.client.get(reverse('clientes:cuerpo'))

    def test_panel_sin_datos(self):
        r = self._get()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Cómo responde tu cuerpo')
        self.assertContains(r, 'Te estoy conociendo')
        self.assertContains(r, 'Aún no hay actividades con carga')
        self.assertContains(r, 'Aún no ha llegado ninguna medida de variabilidad')

    def test_panel_con_datos(self):
        import os
        self.semanas_normales(400)
        for d in (0, 1, 2, 3):
            self.actividad(d, 600)
        self.cuerpo(['bien', 'mal', 'bien', 'bien', 'bien', 'bien'])
        r = self._get()
        self.assertContains(r, 'Tus tres preguntas')
        self.assertContains(r, '¿Me estoy pasando?')
        self.assertContains(r, 'Carga alta')           # +50 % y el cuerpo aguanta
        self.assertContains(r, '<polyline')
        self.assertContains(r, 'lo normal en ti, unos 50 ms')
        self.assertContains(r, 'class="punto rojo"')
        from entrenos.services.panel_cuerpo_service import fecha_texto
        self.assertContains(r, fecha_texto(HOY).capitalize())
        if os.environ.get('VOLCAR_PANEL'):
            open(os.environ['VOLCAR_PANEL'], 'w').write(r.content.decode())

    def test_preguntas_dar_mas(self):
        from entrenos.services.panel_cuerpo_service import tres_preguntas
        self.semanas_normales(400)
        for d in (0, 2, 4, 6):
            self.actividad(d, 400)
        self.cuerpo(['bien'] * 14)
        p = tres_preguntas(ec.estado_carga(self.cliente, HOY))
        self.assertEqual([x['respuesta'] for x in p], ['No', 'No', 'Sí'])

    def test_parada_desde_el_panel_vuelve_al_panel(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse('clientes:parada_declarada'), {'accion': 'parada', 'volver': 'cuerpo'})
        self.assertRedirects(r, reverse('clientes:cuerpo'), fetch_redirect_response=False)
        self.assertContains(self._get(), 'Ya he vuelto')
        self.assertContains(self._get(), 'En pausa')

    def test_enlace_desde_ahora(self):
        from pathlib import Path
        plantilla = Path('clientes/templates/clientes/dashboard_silencioso_preview.html').read_text(encoding='utf-8')
        self.assertIn("{% url 'clientes:cuerpo' %}", plantilla)
