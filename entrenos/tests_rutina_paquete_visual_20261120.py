"""Rutina, paquete visual del 20-nov-2026: un comportamiento por test.

Funcional: (F1) seleccionar un día solo cambia el detalle del día; «Preparar
entrenamiento» lleva a la vista previa (briefing), no al registro activo.
Visual: cuatro bloques, tres ejercicios + resto plegado, resumen de la semana.
"""
from datetime import date, timedelta
from html import escape
from unittest.mock import patch

from django.utils import translation

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

HOY = date(2026, 11, 19)  # jueves


def _ej(n):
    return {'nombre': f'Ejercicio {n}', 'series': 3, 'reps': '8-10', 'unidad': 'reps', 'peso': None}


def _semana(briefing):
    lunes = date(2026, 11, 16)
    dias = []
    for i in range(7):
        f = lunes + timedelta(days=i)
        if i < 3:
            p = {'tipo': 'hecha', 'etiqueta': 'Sesión hecha', 'titulo': f'Día {i + 1}',
                 'fecha_efectiva': f.isoformat(),
                 'ejercicios': [{'nombre': 'Sentadilla Hack', 'series': 4, 'reps': 'mejor 32,5 kg × 4', 'unidad': '', 'peso': None}],
                 'url': f'/cierre/{i}/', 'cta': 'Ver el cierre'}
        elif i == 3:
            p = {'tipo': 'sesion', 'etiqueta': 'Sesión de hoy', 'titulo': 'Día 4',
                 'fecha_efectiva': f.isoformat(), 'ejercicios': [_ej(n) for n in range(1, 9)],
                 'url': briefing, 'cta': 'Revisar sesión'}
        elif i == 4:
            p = {'tipo': 'sesion', 'etiqueta': 'Prevista', 'titulo': 'Día 5',
                 'fecha_efectiva': f.isoformat(), 'ejercicios': [_ej(1), _ej(2)],
                 'url': '/briefing-otro-dia/', 'cta': 'Revisar sesión'}
        else:
            p = {'tipo': 'descanso', 'etiqueta': 'Recuperación', 'titulo': 'Día de descanso',
                 'detalle': 'No hay sesión de fuerza prevista.', 'fecha_efectiva': f.isoformat(), 'ejercicios': []}
        dias.append({'fecha': f, 'numero': f.day, 'es_hoy': f == HOY, 'tipo': p['tipo'], 'preview': p})
    return dias


class RutinaPaqueteVisualTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='rutina-visual', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.url = reverse('entrenos:rutina_silenciosa_preview', args=[self.cliente.id])
        self.briefing = '/entrenos/briefing/?fecha=2026-11-19&rutina_nombre=Dia+4'
        self.client.force_login(self.user)

    def _get(self, hoy=HOY):
        ctx = {
            'fase': {'nombre': 'Fuerza — Hipertrofia', 'objetivo': '', 'rpe': '7', 'reps': '6-8', 'semana_texto': 'Semana 2 de 4'},
            'semana': _semana(self.briefing),
            'semana_inicio': date(2026, 11, 16),
            'hoy': {'tipo': 'sesion', 'titulo': 'Día 4', 'detalle': 'Tu sesión está preparada.',
                    'url': self.briefing, 'cta': 'Ver mi sesión'},
            'rms': [], 'insight': None,
            'resumen_semana': {'hechas': 3, 'total': 5},
        }
        with translation.override('es'), \
                patch('entrenos.views._obtener_contexto_rutina_silenciosa', return_value=ctx), \
                patch('entrenos.views.timezone.localdate', return_value=hoy):
            return self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='es')

    # --- Funcional F1 -------------------------------------------------
    def test_preparar_entrenamiento_lleva_a_la_vista_previa_no_al_registro(self):
        r = self._get()
        self.assertContains(r, 'Preparar entrenamiento')
        self.assertContains(r, f'href="{escape(self.briefing)}"')
        self.assertNotContains(r, 'entrenamiento-activo')

    def test_el_dia_abierto_al_entrar_es_hoy_y_dice_es_hoy(self):
        r = self._get()
        self.assertContains(r, 'Es hoy')
        self.assertContains(r, 'Hoy · Jueves 19/11')
        self.assertContains(r, 'aria-selected="true"', count=1)

    def test_el_texto_de_seleccion_no_promete_abrir_nada(self):
        r = self._get()
        self.assertContains(r, 'Seleccionado: ')
        self.assertNotContains(r, 'Abriendo')

    def test_consultar_otro_dia_solo_cambia_el_detalle_en_la_pagina(self):
        from pathlib import Path
        js = Path('entrenos/templates/entrenos/rutina_silenciosa_preview.html').read_text(encoding='utf-8')
        self.assertIn('function renderDetalle(preview)', js)
        self.assertIn("badge.textContent = esHoy ? 'Es hoy' : 'No es hoy';", js)
        # El bloque «Hoy» no se toca desde el selector de día.
        self.assertNotIn("data-bloque=\"hoy\"')", js)
        self.assertNotIn('today-title', js.split('<script>')[1])

    def test_el_bloque_hoy_no_depende_del_dia_seleccionado(self):
        r = self._get()
        html = r.content.decode()
        hoy = html.split('data-bloque="hoy"')[1].split('</section>')[0]
        self.assertIn('Día 4', hoy)
        self.assertIn('Preparar entrenamiento', hoy)

    # --- Visual -------------------------------------------------------
    def test_cuatro_bloques_en_orden(self):
        html = self._get().content.decode()
        pos = [html.index(f'data-bloque="{b}"') for b in ('hoy', 'semana', 'seleccionado', 'fase')]
        self.assertEqual(pos, sorted(pos))

    def test_resumen_de_la_semana_y_leyenda(self):
        r = self._get()
        self.assertContains(r, '3 de 5 completadas')
        for t in ('Hecha', 'Prevista', 'Movida', 'Descanso'):
            self.assertContains(r, f'</svg>{t}</span>')

    def test_hoy_se_marca_hoy_y_tiene_icono_de_estado(self):
        r = self._get()
        self.assertContains(r, '>Hoy</span><strong class="day-number">19</strong>')

    def test_tres_ejercicios_y_el_resto_plegado(self):
        html = self._get().content.decode()
        sel = html.split('data-bloque="seleccionado"')[1].split('</section>')[0]
        self.assertIn('5 ejercicios más', sel)
        self.assertIn('<details class="more">', sel)
        antes, despues = sel.split('<details class="more">')
        self.assertEqual(antes.count('class="ex"'), 3)
        self.assertEqual(despues.count('class="ex"'), 5)

    def test_fase_en_una_linea_enlaza_al_plan(self):
        r = self._get()
        self.assertContains(r, 'Semana 2 de 4')
        self.assertContains(r, f'class="phase-line" href="{reverse("clientes:trayectoria_plan")}"')

    def test_no_hay_ventana_emergente(self):
        r = self._get()
        self.assertNotContains(r, '<dialog')

    def test_semana_de_otra_fecha_abre_el_primer_dia_y_dice_no_es_hoy(self):
        # Si hoy no está en la semana mostrada, ningún día es «hoy».
        ctx_sem = _semana(self.briefing)
        for d in ctx_sem:
            d['es_hoy'] = False
        ctx = {
            'fase': {'nombre': 'X', 'semana_texto': ''}, 'semana': ctx_sem,
            'semana_inicio': date(2026, 11, 16),
            'hoy': {'tipo': 'sesion', 'titulo': 'Día 4', 'detalle': '', 'url': '/b/', 'cta': 'c'},
            'rms': [], 'insight': None,
        }
        with translation.override('es'), \
                patch('entrenos.views._obtener_contexto_rutina_silenciosa', return_value=ctx):
            r = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='es')
        self.assertContains(r, 'No es hoy')
        self.assertContains(r, 'Lunes 16/11')

    # --- Datos --------------------------------------------------------
    def test_semana_de_fase_texto(self):
        from entrenos.views import _semana_de_fase_texto
        f = {'_preview_inicio': date(2026, 11, 9), 'duracion': 4}
        self.assertEqual(_semana_de_fase_texto(f, date(2026, 11, 19)), 'Semana 2 de 4')
        self.assertEqual(_semana_de_fase_texto(f, date(2026, 12, 20)), '')
        self.assertEqual(_semana_de_fase_texto({}, HOY), '')

    def test_los_elementos_ocultos_no_se_muestran_aunque_tengan_display(self):
        """«Ver el cierre» tiene display:flex: sin esta regla se veía en días sin cierre."""
        from pathlib import Path
        t = Path('entrenos/templates/entrenos/rutina_silenciosa_preview.html').read_text(encoding='utf-8')
        self.assertIn('[hidden]{display:none !important}', t)

    def test_dia_sin_entreno_no_repite_titulo_y_etiqueta(self):
        """19/11 decía «Sin entreno · Sin entreno»."""
        from pathlib import Path
        t = Path('entrenos/templates/entrenos/rutina_silenciosa_preview.html').read_text(encoding='utf-8')
        self.assertIn('etiqueta === preview.titulo ? preview.titulo', t)
        self.assertIn('{% if p.etiqueta and p.etiqueta != p.titulo %}', t)
        v = Path('entrenos/views.py').read_text(encoding='utf-8')
        self.assertIn("'etiqueta': 'Sin entreno', 'titulo': 'Sin sesión registrada'", v)
