from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from entrenos.models import EntrenoRealizado
from rutinas.models import Rutina


class HistorialDetalladoEmptyStateTests(TestCase):
    def test_sin_entrenamientos_explicita_el_estado_y_lleva_al_panel(self):
        user = User.objects.create_user('historial_vacio', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Todavía no hay entrenamientos registrados')
        self.assertContains(
            response,
            'Cuando completes una sesión aparecerá aquí con sus series y esfuerzo.',
        )
        self.assertContains(response, 'Ver rutina de hoy')
        self.assertContains(
            response,
            reverse('clientes:dashboard_silencioso_preview'),
        )

    def test_requires_login(self):
        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertEqual(response.status_code, 302)

    def test_regular_user_only_sees_own_history(self):
        owner = User.objects.create_user('historial_owner', password='x')
        other = User.objects.create_user('historial_other', password='x')
        rutina = Rutina.objects.create(nombre='Rutina historial')
        EntrenoRealizado.objects.create(cliente=owner.cliente_perfil, rutina=rutina)
        EntrenoRealizado.objects.create(cliente=other.cliente_perfil, rutina=rutina)
        self.client.force_login(owner)

        response = self.client.get(reverse('entrenos:historial_entrenos'))

        self.assertContains(response, owner.cliente_perfil.nombre)
        self.assertNotContains(response, other.cliente_perfil.nombre)
        self.assertNotContains(response, 'Filtrar')


class HistorialDetalladoContenidoTests(TestCase):
    def setUp(self):
        from rutinas.models import EjercicioBase
        self.user = User.objects.create_user('historial_contenido', password='x')
        self.cliente = self.user.cliente_perfil
        self.base = EjercicioBase.objects.create(nombre='Press historial')
        self.client.force_login(self.user)

    def _entreno(self, **kwargs):
        from entrenos.models import SerieRealizada
        entreno = EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=Rutina.objects.create(nombre='Día 2'), **kwargs,
        )
        for n in (1, 2):
            SerieRealizada.objects.create(
                entreno=entreno, ejercicio=self.base, serie_numero=n,
                repeticiones=10, peso_kg=50, completado=True,
            )
        SerieRealizada.objects.create(
            entreno=entreno, ejercicio=self.base, serie_numero=3,
            repeticiones=10, peso_kg=20, completado=True, es_aproximacion=True,
        )
        return entreno

    def test_volumen_en_kg_sin_aproximaciones_y_estado_real(self):
        self._entreno(volumen_total_kg=0, estado_cierre=EntrenoRealizado.ESTADO_PARCIAL, motivo_cierre='tiempo')
        response = self.client.get(reverse('entrenos:historial_entrenos'))
        entreno = response.context['entrenos'][0]
        self.assertEqual(entreno.volumen_kg, 1000)
        self.assertEqual(entreno.n_series, 2)
        self.assertRegex(response.content.decode(), r'1[.,\s\u00a0]?000 kg')
        self.assertContains(response, 'Parcial')
        self.assertNotContains(response, 'Entreno perfecto')
        self.assertNotContains(response, ' reps</')
        self.assertContains(response, 'bottom-nav-std')

    def test_paginacion_visible(self):
        for _ in range(11):
            self._entreno()
        response = self.client.get(reverse('entrenos:historial_entrenos'))
        self.assertContains(response, 'Página 1 de 2')
        self.assertContains(response, '?page=2')

    def test_ordena_por_el_dia_en_que_se_hizo(self):
        from datetime import date
        tarde = self._entreno(fecha=date(2026, 10, 8), fecha_ejecucion=date(2026, 10, 11))
        normal = self._entreno(fecha=date(2026, 10, 10), fecha_ejecucion=date(2026, 10, 10))
        response = self.client.get(reverse('entrenos:historial_entrenos'))
        self.assertEqual([e.id for e in response.context['entrenos']], [tarde.id, normal.id])
