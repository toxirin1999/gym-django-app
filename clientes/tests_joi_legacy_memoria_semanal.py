"""
Phase 59E.2 — Retirar memoria semanal JOI fósil visible.

Contexto (auditoría 59E.2A): el productor de EstadoSemanal.mensaje_joi
(crear_estado_semanal) no tenía callers, y las pantallas que lo mostraban
estaban huérfanas de navegación. La pantalla "Memorias semanales con Joi"
presentaba dato fósil como voz JOI viva y duplicaba la habitación JOI.

Regla madre de esta fase:
    Ninguna pantalla legacy puede presentar una lectura antigua como si
    fuera JOI viva. Si una pantalla no es JOI, no lleva decoración JOI fósil.

Esta fase NO decide el futuro del historial de entrenos ni toca el modelo
EstadoSemanal (limpieza de modelo aplazada).

Checklist:
1.  La URL clientes:recuerdos_semanales ya no resuelve.
2.  La vista recuerdos_semanales ya no existe en el módulo.
3.  La función productora crear_estado_semanal ya no existe.
4.  historial_cliente NO renderiza la línea mensaje_joi (voz JOI fósil).
5.  El modelo EstadoSemanal se conserva (no se elimina en esta fase).
"""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from clientes import views


class TestMemoriaSemanalJoiRetirada(TestCase):
    def test_url_recuerdos_semanales_no_resuelve(self):
        with self.assertRaises(NoReverseMatch):
            reverse('clientes:recuerdos_semanales')

    def test_vista_recuerdos_semanales_eliminada(self):
        self.assertFalse(
            hasattr(views, 'recuerdos_semanales'),
            "La vista recuerdos_semanales debe estar eliminada",
        )

    def test_productor_crear_estado_semanal_eliminado(self):
        self.assertFalse(
            hasattr(views, 'crear_estado_semanal'),
            "El productor muerto crear_estado_semanal debe estar eliminado",
        )

    def test_modelo_estado_semanal_se_conserva(self):
        # La limpieza de modelo se aplaza: EstadoSemanal sigue importable.
        from clientes.models import EstadoSemanal  # noqa: F401

    def test_historial_no_renderiza_voz_joi_fosil(self):
        # historial.html ya no debe renderizar la variable mensaje_joi.
        # (Se busca el acceso real a la variable, no la palabra en un comentario.)
        with open(
            'clientes/templates/clientes/historial.html', encoding='utf-8'
        ) as f:
            tpl = f.read()
        self.assertNotIn('.mensaje_joi }}', tpl,
                         "historial.html no debe renderizar la voz JOI fósil mensaje_joi")
        self.assertNotIn('mensaje_joi }}', tpl)
