"""
Management command: Auditoría de rendimiento de las vistas principales.

Golpea las vistas clave con el test Client (login como 'david'), cuenta
queries SQL y mide tiempo de respuesta. Sin dependencias nuevas (no usa
django-debug-toolbar ni silk) — solo django.test.utils.CaptureQueriesContext.

Usage:
    python3 manage.py audit_perf --settings=gymproject.settings_local
"""
import time
from collections import Counter

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse


class Command(BaseCommand):
    help = "Auditar queries SQL y tiempo de respuesta de las vistas principales"

    def add_arguments(self, parser):
        parser.add_argument('--top', type=int, default=10, help='Cuántas queries repetidas mostrar por vista')

    def handle(self, *args, **options):
        try:
            usuario = User.objects.get(username='david')
        except User.DoesNotExist:
            usuario = User.objects.first()
            if not usuario:
                self.stdout.write(self.style.ERROR('No hay usuarios en la BD'))
                return

        cliente_id = getattr(getattr(usuario, 'cliente', None), 'id', None) or 2

        client = Client()
        client.force_login(usuario)

        objetivos = [
            ('panel (dashboard)', reverse('dashboard')),
            ('mi-panel (panel_cliente)', reverse('panel_cliente')),
            ('joi habitación', reverse('joi:joi_habitacion')),
            ('hyrox dashboard', reverse('hyrox:dashboard')),
            ('diario dashboard', reverse('diario:dashboard_diario')),
            ('analytics dashboard cliente', reverse('analytics:dashboard_cliente', args=[cliente_id])),
        ]

        self.stdout.write(self.style.SUCCESS(f"\n📊 AUDITORÍA DE RENDIMIENTO — Usuario: {usuario.username}\n"))
        resultados = []

        for nombre, url in objetivos:
            try:
                with CaptureQueriesContext(connection) as ctx:
                    t0 = time.perf_counter()
                    resp = client.get(url, SERVER_NAME='localhost')
                    elapsed = time.perf_counter() - t0
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ {nombre} ({url}) → EXCEPCIÓN: {e}"))
                continue

            n_queries = len(ctx.captured_queries)
            resultados.append((nombre, url, resp.status_code, n_queries, elapsed))

            color = self.style.SUCCESS if resp.status_code == 200 else self.style.WARNING
            self.stdout.write(color(
                f"{'✓' if resp.status_code == 200 else '⚠'} {nombre:32s} status={resp.status_code}  "
                f"queries={n_queries:4d}  tiempo={elapsed*1000:7.1f}ms"
            ))

            if n_queries:
                sql_counter = Counter(q['sql'] for q in ctx.captured_queries)
                repetidas = [(sql, c) for sql, c in sql_counter.items() if c > 1]
                repetidas.sort(key=lambda x: -x[1])
                for sql, c in repetidas[:options['top']]:
                    snippet = sql[:110].replace('\n', ' ')
                    self.stdout.write(f"      ×{c:<3d} {snippet}")

        self.stdout.write(self.style.SUCCESS("\n" + "═" * 70))
        self.stdout.write(self.style.SUCCESS("RESUMEN (ordenado por nº de queries)"))
        self.stdout.write(self.style.SUCCESS("═" * 70))
        for nombre, url, status, n_queries, elapsed in sorted(resultados, key=lambda r: -r[3]):
            self.stdout.write(f"{nombre:32s} queries={n_queries:4d}  tiempo={elapsed*1000:7.1f}ms  {url}")
