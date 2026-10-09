"""Contract tests for public entry points and production-safe errors."""

from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, resolve, reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class PublicRoutingSafetyTests(SimpleTestCase):
    def test_nutrition_has_a_canonical_public_entry(self):
        self.assertEqual(reverse('nutricion_app_django:dashboard_nutricional'), '/nutricion/')

        response = self.client.get('/nutricion/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_legacy_nutrition_pyramid_is_not_publicly_mounted(self):
        with self.assertRaises(Resolver404):
            resolve('/nutricion/legacy/piramide/')

    @override_settings(DEBUG=False)
    def test_unknown_urls_do_not_expose_django_technical_details(self):
        response = self.client.get('/this-route-does-not-exist/')

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Exception Value', status_code=404)
        self.assertNotContains(response, 'URLconf', status_code=404)
