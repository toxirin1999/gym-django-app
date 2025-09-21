# ============================================================================
# COMANDO DE GESTIÓN DJANGO PARA GAMIFICACIÓN
# ============================================================================
# Archivo: logros/management/commands/gamificacion_debug.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import logging

logger = logging.getLogger('gamificacion')


class Command(BaseCommand):
    help = 'Herramientas avanzadas de debugging y gestión para el sistema de gamificación'

    def add_arguments(self, parser):
        parser.add_argument(
            'accion',
            type=str,
            help='Acción a realizar: diagnosticar, sincronizar, procesar_logros, validar_sistema, corregir_decimal'
        )
        parser.add_argument(
            '--cliente',
            type=int,
            help='ID del cliente específico'
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Aplicar acción a todos los clientes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )

    def handle(self, *args, **options):
        accion = options['accion']
        cliente_id = options.get('cliente')
        todos = options.get('todos', False)
        verbose = options.get('verbose', False)

        try:
            if accion == 'diagnosticar':
                self._diagnosticar(cliente_id, todos, verbose)

            elif accion == 'sincronizar':
                self._sincronizar(cliente_id, todos, verbose)

            elif accion == 'procesar_logros':
                self._procesar_logros(cliente_id, todos, verbose)

            elif accion == 'validar_sistema':
                self._validar_sistema(verbose)

            elif accion == 'corregir_decimal':
                self._corregir_error_decimal()

            else:
                self.stdout.write(
                    self.style.ERROR(
                        'Acción no válida. Acciones disponibles: '
                        'diagnosticar, sincronizar, procesar_logros, validar_sistema, corregir_decimal'
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error ejecutando comando: {e}'))
            raise CommandError(f'Error: {e}')

    def _diagnosticar(self, cliente_id, todos, verbose):
        """Diagnosticar perfiles de gamificación"""
        if todos:
            from logros.models import PerfilGamificacion
            perfiles = PerfilGamificacion.objects.all()

            self.stdout.write(f"🔍 Diagnosticando {perfiles.count()} perfiles...")

            for perfil in perfiles:
                resultado = self._diagnosticar_perfil(perfil.cliente_id, verbose)
                estado_color = self._get_estado_color(resultado.get('estado'))
                self.stdout.write(f"Cliente {perfil.cliente_id}: {estado_color}")

        elif cliente_id:
            resultado = self._diagnosticar_perfil(cliente_id, verbose)
            self._mostrar_diagnostico_detallado(resultado)

        else:
            self.stdout.write(self.style.ERROR("Especifica --cliente ID o --todos"))

    def _diagnosticar_perfil(self, cliente_id, verbose):
        """Diagnosticar un perfil específico"""
        try:
            from logros.services import GamificacionDebugService
            return GamificacionDebugService.diagnosticar_perfil_completo(cliente_id)
        except Exception as e:
            return {'error': str(e), 'estado': 'error'}

    def _mostrar_diagnostico_detallado(self, resultado):
        """Mostrar diagnóstico detallado"""
        if 'error' in resultado:
            self.stdout.write(self.style.ERROR(f"❌ Error: {resultado['error']}"))
            return

        cliente_id = resultado['cliente_id']
        estado = resultado['estado']

        self.stdout.write(f"\n🔍 DIAGNÓSTICO COMPLETO - Cliente {cliente_id}")
        self.stdout.write("=" * 50)

        # Estado general
        estado_color = self._get_estado_color(estado)
        self.stdout.write(f"Estado: {estado_color}")

        # Datos del perfil
        datos_perfil = resultado['datos_perfil']
        self.stdout.write(f"\n📊 DATOS DEL PERFIL:")
        self.stdout.write(f"  Nivel: {datos_perfil['nivel_actual']}")
        self.stdout.write(f"  Puntos: {datos_perfil['puntos_totales']}")
        self.stdout.write(f"  Entrenamientos: {datos_perfil['entrenos_totales']}")
        self.stdout.write(f"  Racha: {datos_perfil['racha_actual']}")

        # Datos reales
        datos_reales = resultado['datos_reales']
        self.stdout.write(f"\n📈 DATOS REALES:")
        self.stdout.write(f"  Entrenamientos BD: {datos_reales['entrenos_bd']}")
        self.stdout.write(f"  Logros completados: {datos_reales['logros_completados']}")
        self.stdout.write(f"  Puntos historial: {datos_reales['puntos_historial']}")

        # Inconsistencias
        inconsistencias = resultado.get('inconsistencias', [])
        if inconsistencias:
            self.stdout.write(f"\n⚠️  INCONSISTENCIAS DETECTADAS:")
            for inc in inconsistencias:
                severidad_color = self._get_severidad_color(inc['severidad'])
                self.stdout.write(f"  {severidad_color}: {inc['descripcion']}")

        # Logros potenciales
        logros_potenciales = resultado.get('logros_potenciales', [])
        if logros_potenciales:
            self.stdout.write(f"\n🎯 LOGROS PENDIENTES ({len(logros_potenciales)}):")
            for logro in logros_potenciales:
                self.stdout.write(f"  🏆 {logro['nombre']} ({logro['progreso']}/{logro['meta']}) +{logro['puntos']}pts")

        # Recomendaciones
        recomendaciones = resultado.get('recomendaciones', [])
        if recomendaciones:
            self.stdout.write(f"\n💡 RECOMENDACIONES:")
            for rec in recomendaciones:
                self.stdout.write(f"  • {rec}")

    def _sincronizar(self, cliente_id, todos, verbose):
        """Sincronizar datos de perfiles"""
        if todos:
            from logros.models import PerfilGamificacion
            perfiles = PerfilGamificacion.objects.all()

            self.stdout.write(f"🔄 Sincronizando {perfiles.count()} perfiles...")

            exitosos = 0
            errores = 0

            for perfil in perfiles:
                try:
                    from logros.services import GamificacionDebugService
                    resultado = GamificacionDebugService.sincronizar_datos_perfil(perfil.cliente_id)

                    if resultado['exito']:
                        exitosos += 1
                        if verbose:
                            self.stdout.write(f"✅ Cliente {perfil.cliente_id}: {resultado['puntos_actualizados']} pts")
                    else:
                        errores += 1
                        self.stdout.write(f"❌ Cliente {perfil.cliente_id}: {resultado['error']}")

                except Exception as e:
                    errores += 1
                    self.stdout.write(f"❌ Cliente {perfil.cliente_id}: {e}")

            self.stdout.write(f"\n📊 Resultado: {exitosos} exitosos, {errores} errores")

        elif cliente_id:
            from logros.services import GamificacionDebugService
            resultado = GamificacionDebugService.sincronizar_datos_perfil(cliente_id)

            if resultado['exito']:
                self.stdout.write(self.style.SUCCESS(f"✅ Sincronización exitosa para cliente {cliente_id}"))
                self.stdout.write(f"  Puntos: {resultado['puntos_actualizados']}")
                self.stdout.write(f"  Entrenamientos: {resultado['entrenos_actualizados']}")
                self.stdout.write(f"  Nivel: {resultado['nivel_actualizado']}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Error: {resultado['error']}"))

        else:
            self.stdout.write(self.style.ERROR("Especifica --cliente ID o --todos"))

    def _procesar_logros(self, cliente_id, todos, verbose):
        """Procesar logros pendientes"""
        if cliente_id:
            from logros.services import GamificacionDebugService
            resultado = GamificacionDebugService.procesar_logros_pendientes(cliente_id)

            if resultado['exito']:
                self.stdout.write(self.style.SUCCESS(f"✅ {resultado['total_logros']} logros procesados"))
                self.stdout.write(f"  Puntos ganados: {resultado['puntos_ganados']}")

                if verbose and resultado['logros_otorgados']:
                    self.stdout.write("  Logros otorgados:")
                    for logro in resultado['logros_otorgados']:
                        self.stdout.write(f"    🏆 {logro}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Error: {resultado['error']}"))

        else:
            self.stdout.write(self.style.ERROR("Especifica --cliente ID"))

    def _validar_sistema(self, verbose):
        """Validar integridad del sistema completo"""
        from logros.services import GamificacionDebugService
        resultado = GamificacionDebugService.validar_integridad_sistema()

        if 'error' in resultado:
            self.stdout.write(self.style.ERROR(f"❌ Error: {resultado['error']}"))
            return

        self.stdout.write("🔍 VALIDACIÓN DEL SISTEMA COMPLETO")
        self.stdout.write("=" * 40)
        self.stdout.write(f"Perfiles analizados: {resultado['perfiles_analizados']}")
        self.stdout.write(f"Perfiles saludables: {resultado['perfiles_saludables']}")
        self.stdout.write(f"Perfiles con problemas: {resultado['perfiles_con_problemas']}")

        if verbose and resultado['problemas_detectados']:
            self.stdout.write("\n⚠️  PROBLEMAS DETECTADOS:")
            for problema in resultado['problemas_detectados']:
                self.stdout.write(f"  Cliente {problema['cliente_id']}:")
                for inc in problema['problemas']:
                    self.stdout.write(f"    • {inc['descripcion']}")

        if resultado['recomendaciones_globales']:
            self.stdout.write("\n💡 RECOMENDACIONES GLOBALES:")
            for rec in resultado['recomendaciones_globales']:
                self.stdout.write(f"  • {rec}")

    def _corregir_error_decimal(self):
        """Corregir el error de Decimal en Desafío Aceptado"""
        self.stdout.write("🔧 Aplicando corrección para error de Decimal...")

        # Esta función mostraría las instrucciones para corregir el error
        self.stdout.write("\n📝 INSTRUCCIONES PARA CORREGIR ERROR DECIMAL:")
        self.stdout.write("1. Abre tu archivo services.py")
        self.stdout.write("2. Busca la línea con 'volumen_promedio * 1.2'")
        self.stdout.write("3. Cámbiala por 'float(volumen_promedio) * 1.2'")
        self.stdout.write("4. Guarda el archivo y reinicia el servidor")

        self.stdout.write(self.style.SUCCESS("\n✅ Instrucciones mostradas"))

    def _get_estado_color(self, estado):
        """Obtener color para el estado"""
        if estado == 'saludable':
            return self.style.SUCCESS('✅ Saludable')
        elif estado == 'necesita_atencion':
            return self.style.WARNING('⚠️  Necesita atención')
        elif estado == 'critico':
            return self.style.ERROR('❌ Crítico')
        else:
            return self.style.ERROR('❌ Error')

    def _get_severidad_color(self, severidad):
        """Obtener color para la severidad"""
        if severidad == 'alta':
            return self.style.ERROR('🔴 ALTA')
        elif severidad == 'media':
            return self.style.WARNING('🟡 MEDIA')
        else:
            return self.style.SUCCESS('🟢 BAJA')


# ============================================================================
# INSTRUCCIONES DE INSTALACIÓN
# ============================================================================

"""
PASOS PARA INSTALAR EL COMANDO:

1. Crear estructura de directorios:
   mkdir -p logros/management/commands

2. Crear archivos __init__.py:
   touch logros/management/__init__.py
   touch logros/management/commands/__init__.py

3. Crear el archivo del comando:
   Copia todo este código en: logros/management/commands/gamificacion_debug.py

4. Probar el comando:
   python manage.py gamificacion_debug diagnosticar --cliente 1

COMANDOS DISPONIBLES:
- python manage.py gamificacion_debug diagnosticar --cliente 1 --verbose
- python manage.py gamificacion_debug sincronizar --cliente 1
- python manage.py gamificacion_debug procesar_logros --cliente 1
- python manage.py gamificacion_debug validar_sistema --verbose
- python manage.py gamificacion_debug corregir_decimal
- python manage.py gamificacion_debug sincronizar --todos
"""
