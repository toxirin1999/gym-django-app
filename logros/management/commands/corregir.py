# Ruta: logros/management/commands/corregir.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from logros.models import PerfilGamificacion, PruebaUsuario, PruebaLegendaria, HistorialPuntos
from entrenos.models import EntrenoRealizado


class Command(BaseCommand):
    help = 'Analiza y desbloquea automáticamente las pruebas legendarias que un usuario debería tener completadas.'

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

        # 3. Obtener todas las pruebas legendarias disponibles y las ya completadas
        todas_pruebas = PruebaLegendaria.objects.all().order_by('puntos_recompensa')
        pruebas_completadas_ids = set(
            PruebaUsuario.objects.filter(perfil=perfil, completada=True).values_list('prueba_id', flat=True))

        self.stdout.write(f"🏆 Pruebas disponibles: {todas_pruebas.count()}")
        self.stdout.write(f"✅ Pruebas ya completadas: {len(pruebas_completadas_ids)}")

        # 4. Analizar qué pruebas deberían estar desbloqueadas
        pruebas_a_desbloquear = []
        puntos_a_sumar = 0

        for prueba in todas_pruebas:
            if prueba.id in pruebas_completadas_ids:
                continue

            if self.evaluar_prueba(prueba, total_entrenamientos):
                pruebas_a_desbloquear.append(prueba)
                puntos_a_sumar += prueba.puntos_recompensa

        if not pruebas_a_desbloquear:
            self.stdout.write(
                self.style.SUCCESS("\n✅ ¡El perfil del usuario ya está actualizado! No se necesitan correcciones."))
            return

        self.stdout.write(self.style.WARNING(f"\n🎯 PRUEBAS A DESBLOQUEAR: {len(pruebas_a_desbloquear)}"))
        self.stdout.write(f"💎 Puntos adicionales: {puntos_a_sumar}")
        self.stdout.write(f"💰 Puntos totales después: {perfil.puntos_totales + puntos_a_sumar}")

        self.stdout.write(self.style.HTTP_INFO("\n📋 DETALLE DE PRUEBAS A DESBLOQUEAR:"))
        for prueba in pruebas_a_desbloquear:
            self.stdout.write(f"  ✅ {prueba.nombre} (+{prueba.puntos_recompensa} pts)")

        # 5. Aplicar correcciones con una transacción atómica
        with transaction.atomic():
            for prueba in pruebas_a_desbloquear:
                # Obtenemos o creamos la instancia de PruebaUsuario
                prueba_usuario, created = PruebaUsuario.objects.get_or_create(
                    perfil=perfil,
                    prueba=prueba,
                    defaults={'progreso_actual': 0}  # Valor inicial
                )

                # Actualizamos la instancia
                prueba_usuario.completada = True
                prueba_usuario.progreso_actual = prueba.meta_valor
                prueba_usuario.fecha_completada = timezone.now()
                prueba_usuario.save()

                # Agregar entrada al historial de puntos
                HistorialPuntos.objects.create(
                    perfil=perfil,
                    prueba_legendaria=prueba,
                    puntos=prueba.puntos_recompensa,
                    descripcion=f"Prueba legendaria desbloqueada: {prueba.nombre}"
                )
                self.stdout.write(f"  - Desbloqueado: {prueba.nombre}")

            # 6. Actualizar perfil de gamificación (puntos + nivel/arquetipo)
            puntos_actuales = perfil.puntos_totales
            perfil.puntos_totales += puntos_a_sumar
            perfil.save(update_fields=['puntos_totales'])

            # El nivel (Arquetipo) es contenido narrativo pre-sembrado (nombre_personaje,
            # filosofía) — no se auto-crea uno nuevo aquí. actualizar_nivel() ya
            # implementa la lógica correcta: busca el Arquetipo con mayor
            # puntos_requeridos <= puntos_totales.
            perfil.actualizar_nivel()

            self.stdout.write(self.style.SUCCESS("\n🎉 ¡CORRECCIÓN COMPLETADA EXITOSAMENTE!"))
            self.stdout.write(f"✅ Pruebas desbloqueadas: {len(pruebas_a_desbloquear)}")
            self.stdout.write(f"💰 Puntos actualizados: {puntos_actuales} → {perfil.puntos_totales}")
            nombre_nivel = perfil.nivel_actual.titulo_arquetipo if perfil.nivel_actual else '(sin arquetipo asignado)'
            self.stdout.write(f"📈 Nivel actualizado a: {nombre_nivel}")

    def evaluar_prueba(self, prueba, total_entrenamientos):
        nombre_lower = prueba.nombre.lower()

        # Lógica de evaluación (simplificada para el ejemplo)
        if "liftin" in nombre_lower:
            if "principiante" in nombre_lower and total_entrenamientos >= 5: return True
            if "intermedio" in nombre_lower and total_entrenamientos >= 10: return True
            if "avanzado" in nombre_lower and total_entrenamientos >= 20: return True

        if "hito" in nombre_lower or "entrenamientos" in prueba.descripcion.lower():
            if total_entrenamientos >= prueba.meta_valor: return True

        # Añade aquí más reglas de evaluación según necesites
        return False
