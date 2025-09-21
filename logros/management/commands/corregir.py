# Ruta: logros/management/commands/corregir_logros.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from logros.models import PerfilGamificacion, LogroUsuario, Nivel, Logro, HistorialPuntos
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
import traceback


class Command(BaseCommand):
    help = 'Analiza y desbloquea automáticamente los logros que un usuario debería tener completados.'

    def add_arguments(self, parser):
        # Añadimos un argumento para especificar el ID del cliente a corregir.
        parser.add_argument('cliente_id', type=int, help='El ID del cliente para el cual corregir los logros.')

    def handle(self, *args, **kwargs):
        cliente_id = kwargs['cliente_id']
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("INICIANDO CORRECCIÓN AUTOMÁTICA DE LOGROS (VERSIÓN DJANGO)"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

        try:
            # 1. Obtener datos del usuario usando el ORM de Django
            perfil = PerfilGamificacion.objects.select_related('cliente', 'nivel_actual').get(cliente_id=cliente_id)
            cliente = perfil.cliente
        except PerfilGamificacion.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"❌ No se encontró perfil de gamificación para el cliente con ID {cliente_id}."))
            return

        self.stdout.write(f"👤 Usuario: {cliente.nombre} (Cliente ID: {cliente.id}, Perfil ID: {perfil.id})")
        self.stdout.write(f"💰 Puntos actuales: {perfil.puntos_totales}")

        # 2. Obtener entrenamientos del usuario
        total_entrenamientos = EntrenoRealizado.objects.filter(cliente=cliente).count()
        self.stdout.write(f"🏋️ Entrenamientos totales: {total_entrenamientos}")

        # 3. Obtener todos los logros disponibles y los ya completados
        todos_logros = Logro.objects.all().order_by('puntos_recompensa')
        logros_completados_ids = set(
            LogroUsuario.objects.filter(perfil=perfil, completado=True).values_list('logro_id', flat=True))

        self.stdout.write(f"🏆 Logros disponibles: {todos_logros.count()}")
        self.stdout.write(f"✅ Logros ya completados: {len(logros_completados_ids)}")

        # 4. Analizar qué logros deberían estar desbloqueados
        logros_a_desbloquear = []
        puntos_a_sumar = 0

        for logro in todos_logros:
            if logro.id in logros_completados_ids:
                continue

            if self.evaluar_logro(logro, total_entrenamientos):
                logros_a_desbloquear.append(logro)
                puntos_a_sumar += logro.puntos_recompensa

        if not logros_a_desbloquear:
            self.stdout.write(
                self.style.SUCCESS("\n✅ ¡El perfil del usuario ya está actualizado! No se necesitan correcciones."))
            return

        self.stdout.write(self.style.WARNING(f"\n🎯 LOGROS A DESBLOQUEAR: {len(logros_a_desbloquear)}"))
        self.stdout.write(f"💎 Puntos adicionales: {puntos_a_sumar}")
        self.stdout.write(f"💰 Puntos totales después: {perfil.puntos_totales + puntos_a_sumar}")

        self.stdout.write(self.style.HTTP_INFO(f"\n📋 DETALLE DE LOGROS A DESBLOQUEAR:"))
        for logro in logros_a_desbloquear:
            self.stdout.write(f"  ✅ {logro.nombre} (+{logro.puntos_recompensa} pts)")

        # 5. Aplicar correcciones con una transacción atómica
        with transaction.atomic():
            for logro in logros_a_desbloquear:
                # Obtenemos o creamos la instancia de LogroUsuario
                logro_usuario, created = LogroUsuario.objects.get_or_create(
                    perfil=perfil,
                    logro=logro,
                    defaults={'progreso_actual': 0}  # Valor inicial
                )

                # Actualizamos la instancia
                logro_usuario.completado = True
                logro_usuario.progreso_actual = logro.meta_valor
                logro_usuario.fecha_desbloqueo = timezone.now()
                logro_usuario.save()

                # Agregar entrada al historial de puntos
                HistorialPuntos.objects.create(
                    perfil=perfil,
                    logro=logro,
                    puntos=logro.puntos_recompensa,
                    descripcion=f"Logro desbloqueado: {logro.nombre}"
                )
                self.stdout.write(f"  - Desbloqueado: {logro.nombre}")

            # 6. Actualizar perfil de gamificación
            puntos_actuales = perfil.puntos_totales
            perfil.puntos_totales += puntos_a_sumar

            # Actualizar nivel
            nuevo_nivel_num = self.calcular_nivel(perfil.puntos_totales)
            puntos_para_nivel = (nuevo_nivel_num - 1) * 1000  # Calculamos los puntos necesarios

            nivel_obj, _ = Nivel.objects.get_or_create(
                numero=nuevo_nivel_num,
                defaults={
                    'nombre': f'Nivel {nuevo_nivel_num}',
                    'puntos_requeridos': puntos_para_nivel  # <-- ¡Añadido!
                }
            )
            perfil.nivel_actual = nivel_obj

            perfil.save()

            self.stdout.write(self.style.SUCCESS("\n🎉 ¡CORRECCIÓN COMPLETADA EXITOSAMENTE!"))
            self.stdout.write(f"✅ Logros desbloqueados: {len(logros_a_desbloquear)}")
            self.stdout.write(f"💰 Puntos actualizados: {puntos_actuales} → {perfil.puntos_totales}")
            self.stdout.write(f"📈 Nivel actualizado a: {perfil.nivel_actual.nombre}")

    def evaluar_logro(self, logro, total_entrenamientos):
        nombre_lower = logro.nombre.lower()

        # Lógica de evaluación (simplificada para el ejemplo)
        if "liftin" in nombre_lower:
            if "principiante" in nombre_lower and total_entrenamientos >= 5: return True
            if "intermedio" in nombre_lower and total_entrenamientos >= 10: return True
            if "avanzado" in nombre_lower and total_entrenamientos >= 20: return True

        if "hito" in nombre_lower or "entrenamientos" in logro.descripcion.lower():
            if total_entrenamientos >= logro.meta_valor: return True

        # Añade aquí más reglas de evaluación según necesites
        return False

    def calcular_nivel(self, puntos_totales):
        if puntos_totales < 1000:
            return 1
        else:
            # Asumiendo que los niveles se crean dinámicamente
            return (puntos_totales // 1000) + 1
