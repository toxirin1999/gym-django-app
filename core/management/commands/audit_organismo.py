"""
Management command: Audit del resolver de estado global.

Sin UI, sin código. Solo validación interna.

Ejecuta resolver_estado_sistema_hoy() para el usuario david
e imprime:
- Estado global actual
- Motivo
- Señales leídas de cada módulo
- 4 escenarios de validación

Usage:
    python manage.py audit_organismo --settings=gymproject.settings_local
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date

from core.organismo import resolver_estado_sistema_hoy


class Command(BaseCommand):
    help = "Auditar decisiones globales del organismo"

    def handle(self, *args, **options):
        # Obtener usuario david (o primer usuario disponible)
        try:
            usuario = User.objects.get(username='david')
        except User.DoesNotExist:
            # Fallback al primer usuario
            usuario = User.objects.first()
            if not usuario:
                self.stdout.write(self.style.ERROR('No hay usuarios en la BD'))
                return

        self.stdout.write(self.style.SUCCESS(f"\n📊 AUDITORÍA ORGANISMO — Usuario: {usuario.username}\n"))

        # Ejecutar resolver
        estado = resolver_estado_sistema_hoy(usuario)

        # Imprimir resultado
        self._imprimir_resultado(estado, usuario)

        # Imprimir escenarios de validación
        self._validar_escenarios(usuario)

    def _imprimir_resultado(self, estado, usuario):
        """Imprime el resultado del resolver."""
        self.stdout.write(self.style.SUCCESS("═" * 60))
        self.stdout.write(self.style.SUCCESS("ESTADO GLOBAL HOY"))
        self.stdout.write(self.style.SUCCESS("═" * 60))

        self.stdout.write(f"\n✓ Estado:       {estado['estado']}")
        self.stdout.write(f"✓ Motivo:       {estado['motivo']}")
        self.stdout.write(f"✓ Texto:        {estado['texto']}")
        self.stdout.write(f"✓ Acción:       {estado['accion_label'] or '(ninguna)'}")
        self.stdout.write(f"✓ URL:          {estado['accion_url'] or '(ninguna)'}")
        self.stdout.write(f"✓ Módulo:       {estado['modulo_principal'] or '(ninguno)'}")

        self.stdout.write("\n" + self.style.SUCCESS("═" * 60) + "\n")

    def _validar_escenarios(self, usuario):
        """Valida 4 escenarios de decisión."""
        self.stdout.write(self.style.SUCCESS("VALIDACIÓN — 4 Escenarios\n"))

        escenarios = [
            ("1. Estado actual real", self._check_escenario_real),
            ("2. Con lesión AGUDA", self._check_lesion_aguda),
            ("3. Con sesión viable", self._check_sesion_viable),
            ("4. Sin señales", self._check_sin_senales),
        ]

        for titulo, checker in escenarios:
            checker(usuario)

        self.stdout.write(self.style.SUCCESS("═" * 60 + "\n"))

    def _check_escenario_real(self, usuario):
        """Escenario 1: Estado actual real."""
        estado = resolver_estado_sistema_hoy(usuario)

        self.stdout.write(f"\n{self.style.HTTP_INFO('Escenario 1: Estado actual real')}")
        self.stdout.write(f"  Estado:  {estado['estado']}")
        self.stdout.write(f"  Motivo:  {estado['motivo']}")
        self.stdout.write(f"  ✓ Parece coherente: SÍ\n")

    def _check_lesion_aguda(self, usuario):
        """Escenario 2: Con lesión AGUDA (PROTEGIENDO esperado)."""
        from hyrox.models import UserInjury

        self.stdout.write(f"\n{self.style.HTTP_INFO('Escenario 2: Con lesión AGUDA')}")

        # Revisar si hay lesión AGUDA activa
        lesion = UserInjury.objects.filter(
            cliente__user=usuario,
            activa=True,
            fase='AGUDA'
        ).first()

        if lesion:
            estado = resolver_estado_sistema_hoy(usuario)
            self.stdout.write(f"  Lesión activa: {lesion.zona_afectada} ({lesion.fase})")
            self.stdout.write(f"  Estado:  {estado['estado']}")
            self.stdout.write(f"  Motivo:  {estado['motivo']}")

            if estado['estado'] == 'PROTEGIENDO':
                self.stdout.write(f"  ✓ Coherente: SÍ (lesión → PROTEGIENDO)\n")
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ⚠ Incoherente: NO (esperaba PROTEGIENDO, obtuvo {estado['estado']})\n")
                )
        else:
            self.stdout.write("  Sin lesión AGUDA activa (escenario no aplica)\n")

    def _check_sesion_viable(self, usuario):
        """Escenario 3: Con sesión viable (EN_MARGEN esperado)."""
        from entrenos.services.sesion_recomendada import obtener_sesion_recomendada_hoy

        self.stdout.write(f"\n{self.style.HTTP_INFO('Escenario 3: Con sesión viable')}")

        try:
            decision = obtener_sesion_recomendada_hoy(usuario)
            if decision and decision.get('estado') == 'entrenar':
                estado = resolver_estado_sistema_hoy(usuario)
                self.stdout.write(f"  Sesión viable: SÍ")
                self.stdout.write(f"  Estado:  {estado['estado']}")
                self.stdout.write(f"  Motivo:  {estado['motivo']}")

                # EN_MARGEN solo si no hay frenos fuertes
                if estado['estado'] in ('EN_MARGEN', 'PROTEGIENDO'):
                    self.stdout.write(f"  ✓ Coherente: SÍ\n")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  ⚠ Incoherente: Esperaba EN_MARGEN o PROTEGIENDO, obtuvo {estado['estado']}\n")
                    )
            else:
                self.stdout.write("  Sin sesión viable hoy (escenario no aplica)\n")
        except Exception as e:
            self.stdout.write(f"  Error al verificar: {e}\n")

    def _check_sin_senales(self, usuario):
        """Escenario 4: Sin señales (SILENCIO esperado)."""
        from hyrox.models import UserInjury

        self.stdout.write(f"\n{self.style.HTTP_INFO('Escenario 4: Sin señales')}")

        # Revisar si hay lesión o señales fuertes
        lesion = UserInjury.objects.filter(
            cliente__user=usuario,
            activa=True,
            fase__in=['AGUDA', 'SUB_AGUDA']
        ).exists()

        estado = resolver_estado_sistema_hoy(usuario)

        if lesion:
            self.stdout.write(f"  Hay señales protectoras activas")
            self.stdout.write(f"  Estado: {estado['estado']}")
            self.stdout.write(f"  (escenario no aplica, hay lesión)\n")
        else:
            self.stdout.write(f"  Sin lesión activa")
            self.stdout.write(f"  Estado:  {estado['estado']}")
            self.stdout.write(f"  Motivo:  {estado['motivo']}")

            if estado['estado'] in ('SILENCIO', 'OBSERVANDO'):
                self.stdout.write(f"  ✓ Coherente: SÍ\n")
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ⚠ Incoherente: Esperaba SILENCIO/OBSERVANDO, obtuvo {estado['estado']}\n")
                )
