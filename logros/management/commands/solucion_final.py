# Ruta: logros/management/commands/solucion_final.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum, Max
from logros.models import PerfilGamificacion, LogroUsuario, Nivel, Logro, TipoLogro
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
import traceback


# La clase DEBE llamarse 'Command' y heredar de 'BaseCommand'
class Command(BaseCommand):
    help = 'Script de Diagnóstico y Corrección Final para el sistema de gamificación.'

    # El método 'handle' es el punto de entrada que Django ejecuta.
    def handle(self, *args, **kwargs):
        try:
            # 1. Diagnosticar problema
            self.diagnosticar_problema()

            # 2. Crear logros de ejemplo si es necesario
            self.crear_logros_ejemplo()

            # 3. Corregir datos
            self.corregir_datos_final()

            # 4. Verificar resultado final
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("VERIFICACIÓN FINAL"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.diagnosticar_problema()

            self.stdout.write(self.style.SUCCESS("\n🎉 ¡Corrección completada!"))
            self.stdout.write(self.style.NOTICE("💡 Reinicia el servidor Django y refresca el dashboard."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error: {e}"))
            traceback.print_exc()

    # --- MÉTODOS AUXILIARES ---
    # He convertido tus funciones en métodos de la clase, añadiendo 'self'.
    # También he reemplazado print() por self.stdout.write() para un mejor formato.

    def diagnosticar_problema(self):
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("DIAGNÓSTICO DEL PROBLEMA ACTUAL"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        try:
            cliente = Cliente.objects.get(nombre__icontains='david')
            self.stdout.write(f"✅ Cliente encontrado: {cliente.nombre} (ID: {cliente.id})")
        except Cliente.DoesNotExist:
            self.stderr.write("❌ No se encontró cliente 'david'")
            cliente = Cliente.objects.first()
            if not cliente:
                self.stderr.write("❌ No hay clientes en la base de datos. Abortando diagnóstico.")
                return
            self.stdout.write(f"Usando primer cliente disponible: {cliente.nombre}")

        try:
            perfil = PerfilGamificacion.objects.get(cliente=cliente)
            self.stdout.write(self.style.HTTP_INFO("\n📊 PERFIL DE GAMIFICACIÓN:"))
            self.stdout.write(
                f"  - Puntos: {perfil.puntos_totales}, Entrenos: {perfil.entrenos_totales}, Racha: {perfil.racha_actual}, Nivel: {perfil.nivel_actual}")
        except PerfilGamificacion.DoesNotExist:
            self.stderr.write("❌ No se encontró perfil de gamificación para este cliente.")
            return

        logros_completados = LogroUsuario.objects.filter(perfil=perfil, completado=True)
        self.stdout.write(self.style.HTTP_INFO(f"\n🏆 LOGROS COMPLETADOS: {logros_completados.count()}"))
        for lu in logros_completados:
            self.stdout.write(f"  - {lu.logro.nombre}: {lu.logro.puntos_recompensa} puntos")

        puntos_reales = logros_completados.aggregate(total=Sum('logro__puntos_recompensa'))['total'] or 0
        self.stdout.write(self.style.HTTP_INFO("\n💰 PUNTOS:"))
        self.stdout.write(
            f"  - En perfil: {perfil.puntos_totales} | Calculados: {puntos_reales} | Diferencia: {puntos_reales - perfil.puntos_totales}")

        entrenamientos_reales = EntrenoRealizado.objects.filter(cliente=cliente).count()
        self.stdout.write(self.style.HTTP_INFO("\n🏋️ ENTRENAMIENTOS:"))
        self.stdout.write(f"  - Total reales: {entrenamientos_reales} | En perfil: {perfil.entrenos_totales}")

    def corregir_datos_final(self):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("APLICANDO CORRECCIÓN FINAL"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        with transaction.atomic():
            for perfil in PerfilGamificacion.objects.all():
                self.stdout.write(self.style.HTTP_INFO(f"\n--- Corrigiendo: {perfil.cliente.nombre} ---"))

                puntos_reales = LogroUsuario.objects.filter(perfil=perfil, completado=True).aggregate(
                    total=Sum('logro__puntos_recompensa'))['total'] or 0
                entrenamientos_reales = EntrenoRealizado.objects.filter(cliente=perfil.cliente).count()

                perfil.puntos_totales = puntos_reales
                perfil.entrenos_totales = entrenamientos_reales

                nivel_numero = (puntos_reales // 1000) + 1 if puntos_reales >= 1000 else 1
                nivel_obj, _ = Nivel.objects.get_or_create(numero=nivel_numero,
                                                           defaults={'nombre': f'Nivel {nivel_numero}',
                                                                     'puntos_requeridos': (nivel_numero - 1) * 1000})

                perfil.nivel_actual = nivel_obj
                perfil.save()

                self.stdout.write(
                    f"  ✅ Puntos: {puntos_reales}, Entrenamientos: {entrenamientos_reales}, Nivel: {nivel_numero}")

    def crear_logros_ejemplo(self):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("VERIFICANDO/CREANDO LOGROS DE EJEMPLO"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        tipo_liftin, _ = TipoLogro.objects.get_or_create(nombre="Liftin", defaults={'categoria': 'especial',
                                                                                    'descripcion': 'Logros de Liftin'})

        logros_ejemplo = [
            ("Liftin Principiante", "Completa 5 entrenamientos de Liftin", 5, 200),
            ("Liftin Intermedio", "Completa 10 entrenamientos de Liftin", 10, 300),
            ("Quemador Principiante", "Quema 300 calorías en un entrenamiento", 300, 150),
        ]

        for nombre, descripcion, meta_valor, puntos in logros_ejemplo:
            _, created = Logro.objects.get_or_create(nombre=nombre,
                                                     defaults={'descripcion': descripcion, 'tipo': tipo_liftin,
                                                               'meta_valor': meta_valor, 'puntos_recompensa': puntos})
            if created:
                self.stdout.write(f"  ✅ Creado: {nombre}")
            else:
                self.stdout.write(f"  ℹ️  Ya existe: {nombre}")
