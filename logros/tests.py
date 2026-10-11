from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Quest, TipoQuest


class ListaMisionesUITests(TestCase):
    def test_cada_mision_es_un_enlace_semantico_navegable_con_teclado(self):
        """Una tarjeta accionable no puede depender únicamente de onclick."""
        plantilla = Path('logros/templates/logros/lista_misiones.html').read_text()

        self.assertIn('<a class="mission-card" href="{% url \'logros:detalle_mision\' mision.id %}">', plantilla)
        self.assertNotIn('<div class="mission-card" onclick=', plantilla)

    def test_lista_misiones_agrupa_y_entrega_las_misiones_activas_a_la_plantilla(self):
        usuario = get_user_model().objects.create_user(username='misiones-ui', password='secreto')
        tipo = TipoQuest.objects.create(nombre='Constancia')
        mision = Quest.objects.create(
            nombre='Completa tu sesión', descripcion='Registra el entrenamiento de hoy.',
            tipo=tipo, periodo='diario', puntos_recompensa=10, activa=True,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse('logros:lista_misiones'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['categorias']['Constancia']), [mision])
        self.assertContains(response, 'Completa tu sesión')
        self.assertContains(response, 'Misión activa')

    def test_lista_misiones_sin_contenido_explicita_que_no_hay_misiones_activas(self):
        usuario = get_user_model().objects.create_user(username='misiones-vacias', password='secreto')
        self.client.force_login(usuario)

        response = self.client.get(reverse('logros:lista_misiones'))

        self.assertContains(response, 'No hay misiones activas ahora mismo.')
