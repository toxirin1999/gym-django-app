import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from joi.models import ManualDavid, RevisionManualDavidOperacion


class ManualPodaAuthorityTests(TestCase):
    """La poda legacy es inventario; F1/F2 son la única vía de decisión."""

    def setUp(self):
        self.user = User.objects.create_user('manual-secundario')
        self.other = User.objects.create_user('manual-secundario-ajeno')

    def _manual(self, *, user=None, origen='patron_detectado', tipo='hipotesis', entrada='Nota'):
        manual = ManualDavid.objects.create(
            user=user or self.user,
            entrada=entrada,
            origen=origen,
            tipo=tipo,
            estado='activa',
            activa=True,
            confianza=0.7,
        )
        ManualDavid.objects.filter(pk=manual.pk).update(
            creado_en=timezone.now() - datetime.timedelta(days=60),
        )
        manual.refresh_from_db()
        return manual

    def test_manual_es_superficie_informativa_y_deriva_a_habitacion(self):
        elegible = self._manual(entrada='Hipótesis revisable')
        estable = self._manual(
            origen='feedback_error', tipo='dato', entrada='Corrección estable',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('joi:joi_manual'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hipótesis revisable')
        self.assertContains(response, 'Corrección estable')
        self.assertContains(response, reverse('joi:joi_habitacion'))
        self.assertContains(response, 'Las revisiones se hacen en la habitación')
        self.assertNotContains(response, 'ya no es verdad')
        self.assertNotContains(response, '/desactivar/')
        self.assertNotContains(response, '<form', html=False)
        self.assertNotContains(response, 'fetch(')

        elegible.refresh_from_db()
        estable.refresh_from_db()
        self.assertTrue(elegible.activa)
        self.assertTrue(estable.activa)
        self.assertFalse(RevisionManualDavidOperacion.objects.exists())

    def test_ruta_legacy_no_acepta_get_post_csrf_ni_memoria_ajena(self):
        own = self._manual(entrada='Propia')
        foreign = self._manual(user=self.other, entrada='Ajena')
        self.client.force_login(self.user)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        for manual in (own, foreign):
            url = f'/joi/manual/{manual.pk}/desactivar/'
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url).status_code, 404)
            self.assertEqual(csrf_client.post(url).status_code, 404)

        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertTrue(own.activa)
        self.assertTrue(foreign.activa)
        self.assertFalse(RevisionManualDavidOperacion.objects.exists())

