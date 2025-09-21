# gymproject/logros/management/commands/script_correccion_logros.py

# Ya no necesitas os, sys, o django aquí, BaseCommand se encarga de todo.
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from logros.models import PerfilGamificacion, LogroUsuario, Nivel, Logro
from clientes.models import Cliente
from entrenos.models import EntrenoRealizado
import traceback


# --- TODAS TUS FUNCIONES AUXILIARES VAN AQUÍ ---
# No necesitan cambios, así que las copiamos tal cual.

def calcular_nivel_correcto(puntos_totales):
    """
    Calcula el nivel correcto basándose en los puntos totales
    Sistema: cada 1000 puntos = 1 nivel
    """
    if puntos_totales < 1000:
        nivel_numero = 1
        puntos_requeridos = 0
    else:
        nivel_numero = (puntos_totales // 1000) + 1
        puntos_requeridos = (nivel_numero - 1) * 1000

    nombres_niveles = {
        1: 'Principiante', 2: 'Novato', 3: 'Intermedio', 4: 'Avanzado',
        5: 'Experto', 6: 'Maestro', 7: 'Leyenda'
    }
    nombre = nombres_niveles.get(nivel_numero, f'Leyenda Nivel {nivel_numero}')

    return {'numero': nivel_numero, 'nombre': nombre, 'puntos_requeridos': puntos_requeridos}


def calcular_progreso_logro(perfil, logro):
    """
    Calcula el progreso actual para un logro específico
    """
    cliente = perfil.cliente
    nombre_logro = logro.nombre.lower()

    try:
        if "liftin" in nombre_logro and "principiante" in nombre_logro:
            return EntrenoRealizado.objects.filter(cliente=cliente, fuente_datos='liftin').count()
        if "quemador" in nombre_logro or "calorias" in nombre_logro:
            if "300" in nombre_logro or logro.meta_valor == 300:
                return EntrenoRealizado.objects.filter(cliente=cliente, calorias_quemadas__gte=300).count()
        if "hito" in nombre_logro or "entrenamientos" in nombre_logro:
            return perfil.entrenos_totales
        if "racha" in nombre_logro:
            return perfil.racha_actual
    except Exception as e:
        # Usamos self.stderr para reportar errores en un comando
        # print(f"Error calculando progreso para {logro.nombre}: {e}")
        pass
        return 0
    return 0


# --- CLASE PRINCIPAL DEL COMANDO ---

class Command(BaseCommand):
    help = 'Script de Corrección de Datos del Sistema de Logros. Recalcula puntos, niveles y progreso.'

    # El método handle es el que se ejecuta cuando llamas al comando
    def handle(self, *args, **options):
        try:
            self.stdout.write(self.style.SUCCESS("Iniciando script de corrección de logros..."))

            # 1. Corregir datos inconsistentes
            self.corregir_datos_logros()

            # 2. Verificar logros pendientes
            self.verificar_logros_pendientes()

            # 3. Mostrar estadísticas generales
            self.mostrar_estadisticas_generales()

            self.stdout.write(self.style.SUCCESS("\n🎉 ¡Script completado exitosamente!"))
            self.stdout.write(self.style.NOTICE("💡 Ahora puedes refrescar tu dashboard para ver los datos corregidos."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error ejecutando el script: {e}"))
            traceback.print_exc()

    # --- TODAS TUS FUNCIONES PRINCIPALES AHORA SON MÉTODOS DE LA CLASE ---
    # Añadimos 'self' como primer argumento.

    def corregir_datos_logros(self):
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("INICIANDO CORRECCIÓN DE DATOS DEL SISTEMA DE LOGROS"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        perfiles = PerfilGamificacion.objects.all()
        self.stdout.write(f"Perfiles encontrados: {perfiles.count()}")

        if perfiles.count() == 0:
            self.stdout.write("No se encontraron perfiles de gamificación.")
            return

        with transaction.atomic():
            for perfil in perfiles:
                self.stdout.write(self.style.HTTP_INFO(f"\n--- Procesando perfil de: {perfil.cliente.nombre} ---"))

                puntos_reales = LogroUsuario.objects.filter(perfil=perfil, completado=True).aggregate(
                    total=Sum('logro__puntos_recompensa'))['total'] or 0
                self.stdout.write(f"Puntos en BD: {perfil.puntos_totales} | Puntos reales calculados: {puntos_reales}")
                if perfil.puntos_totales != puntos_reales:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  INCONSISTENCIA DETECTADA: {perfil.puntos_totales} -> {puntos_reales}"))
                    perfil.puntos_totales = puntos_reales
                    self.stdout.write("  ✅ Puntos corregidos")

                entrenamientos_reales = EntrenoRealizado.objects.filter(cliente=perfil.cliente).count()
                self.stdout.write(
                    f"Entrenamientos en perfil: {perfil.entrenos_totales} | Entrenamientos reales: {entrenamientos_reales}")
                if perfil.entrenos_totales != entrenamientos_reales:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  INCONSISTENCIA EN ENTRENAMIENTOS: {perfil.entrenos_totales} -> {entrenamientos_reales}"))
                    perfil.entrenos_totales = entrenamientos_reales
                    self.stdout.write("  ✅ Entrenamientos corregidos")

                nivel_correcto = calcular_nivel_correcto(puntos_reales)
                if perfil.nivel_actual is None or perfil.nivel_actual.numero != nivel_correcto['numero']:
                    nivel_obj, _ = Nivel.objects.get_or_create(numero=nivel_correcto['numero'],
                                                               defaults={'nombre': nivel_correcto['nombre'],
                                                                         'puntos_requeridos': nivel_correcto[
                                                                             'puntos_requeridos']})
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  INCONSISTENCIA EN NIVEL: {perfil.nivel_actual.numero if perfil.nivel_actual else 'None'} -> Nivel {nivel_correcto['numero']}"))
                    perfil.nivel_actual = nivel_obj
                    self.stdout.write("  ✅ Nivel corregido")

                perfil.save()

                logros_completados = LogroUsuario.objects.filter(perfil=perfil, completado=True).count()
                self.stdout.write(self.style.SUCCESS("  📊 RESUMEN FINAL:"))
                self.stdout.write(
                    f"     - Puntos: {perfil.puntos_totales}, Nivel: {perfil.nivel_actual.numero}, Entrenamientos: {perfil.entrenos_totales}")

    def verificar_logros_pendientes(self):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("VERIFICANDO LOGROS PENDIENTES"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        for perfil in PerfilGamificacion.objects.all():
            self.stdout.write(self.style.HTTP_INFO(f"\n--- Logros pendientes para: {perfil.cliente.nombre} ---"))
            logros_pendientes = Logro.objects.exclude(usuarios__perfil=perfil, usuarios__completado=True)
            self.stdout.write(f"Logros pendientes: {logros_pendientes.count()}")

            for logro in logros_pendientes[:3]:
                progreso_actual = calcular_progreso_logro(perfil, logro)
                porcentaje = (progreso_actual / logro.meta_valor) * 100 if logro.meta_valor > 0 else 0
                self.stdout.write(
                    f"  📋 {logro.nombre} | Progreso: {progreso_actual}/{logro.meta_valor} ({porcentaje:.1f}%)")

    def mostrar_estadisticas_generales(self):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("ESTADÍSTICAS GENERALES DEL SISTEMA"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        total_perfiles = PerfilGamificacion.objects.count()
        total_logros = Logro.objects.count()
        total_logros_completados = LogroUsuario.objects.filter(completado=True).count()

        self.stdout.write(
            f"📊 Perfiles: {total_perfiles} | 🏆 Logros: {total_logros} | ✅ Completados: {total_logros_completados}")

        if total_perfiles > 0:
            self.stdout.write(f"📈 Promedio de logros por usuario: {total_logros_completados / total_perfiles:.1f}")

        self.stdout.write(self.style.SUCCESS("\n🥇 TOP 3 USUARIOS CON MÁS PUNTOS:"))
        top_usuarios = PerfilGamificacion.objects.order_by('-puntos_totales')[:3]
        for i, perfil in enumerate(top_usuarios, 1):
            logros_count = LogroUsuario.objects.filter(perfil=perfil, completado=True).count()
            self.stdout.write(f"  {i}. {perfil.cliente.nombre}: {perfil.puntos_totales} puntos ({logros_count} logros)")
