# Ruta: logros/management/commands/paso_1_backup_y_correccion.py

import os
import shutil
import sys
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.db.models import Sum, Max  # <-- CORRECCIÓN
from django.conf import settings
from django.utils import timezone  # <-- CORRECCIÓN
from logros.models import PerfilGamificacion, LogroUsuario, Logro, HistorialPuntos
from entrenos.models import EntrenoRealizado


class Command(BaseCommand):
    help = 'PASO 1: Realiza un backup de la BD y corrige los datos de gamificación.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("🚀 PASO 1: Backup y Corrección de Datos"))
        self.stdout.write(self.style.SUCCESS("=" * 50))

        if not self.crear_backup():
            self.stderr.write(self.style.ERROR("❌ No se pudo crear backup. Abortando."))
            sys.exit(1)

        self.analizar_estado_actual()

        respuesta = input("\n¿Proceder con las correcciones? (s/N): ")
        if respuesta.lower() != 's':
            self.stdout.write(self.style.WARNING("❌ Operación cancelada por el usuario."))
            sys.exit(0)

        try:
            self.aplicar_correcciones()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error aplicando correcciones: {e}"))
            import traceback
            traceback.print_exc()
            sys.exit(1)

        if self.validar_resultados():
            self.stdout.write(self.style.SUCCESS("\n🎉 ¡Corrección completada exitosamente!"))
        else:
            self.stderr.write(self.style.ERROR("\n❌ La corrección no se completó correctamente."))
            sys.exit(1)

    def crear_backup(self):
        self.stdout.write(self.style.HTTP_INFO("🔄 Creando backup de la base de datos..."))
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f"❌ No se encontró la base de datos en: {db_path}"))
            return False

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'backup_gamificacion_{timestamp}.sqlite3'

        try:
            shutil.copy2(db_path, backup_path)
            self.stdout.write(self.style.SUCCESS(f"✅ Backup creado: {backup_path}"))
            return True
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error creando backup: {e}"))
            return False

    def analizar_estado_actual(self):
        self.stdout.write(self.style.HTTP_INFO("\n📊 Analizando estado actual..."))
        for perfil in PerfilGamificacion.objects.all():
            puntos_calculados = LogroUsuario.objects.filter(perfil=perfil, completado=True).aggregate(
                total=Sum('logro__puntos_recompensa'))['total'] or 0
            self.stdout.write(
                f"👤 Cliente {perfil.cliente.id}: Puntos en perfil: {perfil.puntos_totales}, Puntos calculados: {puntos_calculados}. Consistente: {'✅' if perfil.puntos_totales == puntos_calculados else '❌'}")

    def aplicar_correcciones(self):
        self.stdout.write(self.style.HTTP_INFO("\n🔧 Aplicando correcciones..."))
        with transaction.atomic():
            for perfil in PerfilGamificacion.objects.all():
                self.stdout.write(f"\n👤 Procesando cliente {perfil.cliente.id}...")
                logros_a_desbloquear = self.corregir_logros_usuario(perfil)

                if not logros_a_desbloquear:
                    self.stdout.write("   No hay nuevos logros que desbloquear.")
                    continue

                for logro in logros_a_desbloquear:
                    logro_usuario, created = LogroUsuario.objects.get_or_create(perfil=perfil, logro=logro)
                    if not logro_usuario.completado:
                        logro_usuario.completado = True
                        logro_usuario.progreso_actual = logro.meta_valor
                        logro_usuario.fecha_desbloqueo = timezone.now()
                        logro_usuario.save()

                        HistorialPuntos.objects.create(
                            perfil=perfil,
                            puntos=logro.puntos_recompensa,
                            descripcion=f"Logro desbloqueado (script): {logro.nombre}",
                            logro=logro
                        )
                        self.stdout.write(f"   ✅ Desbloqueado: {logro.nombre} (+{logro.puntos_recompensa} puntos)")

                puntos_reales = LogroUsuario.objects.filter(perfil=perfil, completado=True).aggregate(
                    total=Sum('logro__puntos_recompensa'))['total'] or 0
                perfil.puntos_totales = puntos_reales
                perfil.save()
                self.stdout.write(f"   💰 Puntos totales actualizados a: {puntos_reales}")

    def corregir_logros_usuario(self, perfil):
        entrenamientos = EntrenoRealizado.objects.filter(cliente=perfil.cliente)
        total_entrenamientos = entrenamientos.count()
        entrenamientos_liftin = entrenamientos.filter(fuente_datos='liftin').count()
        max_calorias = entrenamientos.aggregate(max_cal=Max('calorias_quemadas'))['max_cal'] or 0

        logros_a_desbloquear = []
        logros_ya_completados = set(
            LogroUsuario.objects.filter(perfil=perfil, completado=True).values_list('logro_id', flat=True))

        for logro in Logro.objects.all():
            if logro.id in logros_ya_completados:
                continue
            if self.evaluar_logro(logro, total_entrenamientos, entrenamientos_liftin, max_calorias):
                logros_a_desbloquear.append(logro)
        return logros_a_desbloquear

    def evaluar_logro(self, logro, total_entrenamientos, entrenamientos_liftin, max_calorias):
        nombre = logro.nombre.lower()
        meta = logro.meta_valor

        if 'liftin' in nombre:
            if 'principiante' in nombre and entrenamientos_liftin >= meta: return True
            if 'intermedio' in nombre and entrenamientos_liftin >= meta: return True
            if 'avanzado' in nombre and entrenamientos_liftin >= meta: return True
        elif 'quemador' in nombre:
            if 'principiante' in nombre and max_calorias >= meta: return True
            if 'intermedio' in nombre and max_calorias >= meta: return True
        elif 'hito' in nombre or 'entrenamientos' in nombre:
            if total_entrenamientos >= meta: return True
        return False

    def validar_resultados(self):
        self.stdout.write(self.style.HTTP_INFO("\n✅ Validando resultados..."))
        problemas = 0
        for perfil in PerfilGamificacion.objects.all():
            puntos_calculados = LogroUsuario.objects.filter(perfil=perfil, completado=True).aggregate(
                total=Sum('logro__puntos_recompensa'))['total'] or 0
            if perfil.puntos_totales != puntos_calculados:
                self.stderr.write(self.style.ERROR(
                    f"❌ Cliente {perfil.cliente.id}: Inconsistencia! Perfil: {perfil.puntos_totales}, Calculado: {puntos_calculados}"))
                problemas += 1
            else:
                self.stdout.write(
                    f"✅ Cliente {perfil.cliente.id}: Datos consistentes ({perfil.puntos_totales} puntos).")

        if problemas == 0:
            self.stdout.write(self.style.SUCCESS("\n🎉 ¡Todos los datos están consistentes!"))
        else:
            self.stderr.write(self.style.ERROR(f"\n⚠️  Se encontraron {problemas} problemas."))
        return problemas == 0
