# Ruta: logros/management/commands/paso_5_verificacion_final.py

import os
import sys
import time
import logging
from io import StringIO
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.conf import settings
from django.test.utils import get_runner

# Es mejor importar los modelos dentro de la clase o métodos para evitar
# que se carguen antes de que Django esté 100% listo, aunque en un comando
# de gestión suele ser seguro hacerlo aquí.
from logros.models import PerfilGamificacion, Logro
from entrenos.models import EntrenoRealizado

logger = logging.getLogger('gamificacion')


class Command(BaseCommand):
    help = 'PASO 5: Ejecuta una verificación final y completa de todo el sistema de gamificación.'

    def handle(self, *args, **kwargs):
        verificador = VerificacionFinalSistema(self.stdout, self.stderr, self.style)
        sistema_saludable = verificador.ejecutar_verificacion_completa()

        if sistema_saludable:
            self.stdout.write(
                self.style.SUCCESS("\n🚀 ¡FELICITACIONES! Tu sistema de gamificación está listo para producción."))
            sys.exit(0)
        else:
            self.stderr.write(
                self.style.ERROR("\n🔧 Tu sistema necesita algunas correcciones antes de estar completamente listo."))
            sys.exit(1)


class VerificacionFinalSistema:
    """
    Clase para realizar verificación completa del sistema de gamificación.
    Usa los métodos de salida del BaseCommand para imprimir en consola.
    """

    def __init__(self, stdout, stderr, style):
        self.stdout = stdout
        self.stderr = stderr
        self.style = style
        self.resultados = {'tests_pasados': 0, 'errores': [], 'warnings': []}

    def ejecutar_verificacion_completa(self):
        self.stdout.write(self.style.SUCCESS("🔍 VERIFICACIÓN FINAL DEL SISTEMA DE GAMIFICACIÓN"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        self._verificar_configuracion()
        self._verificar_base_datos()
        self._verificar_modelos()
        self._verificar_comandos()
        self._ejecutar_tests()

        return self._generar_reporte_final()

    def _verificar_configuracion(self):
        self.stdout.write(self.style.HTTP_INFO("\n📋 1. VERIFICANDO CONFIGURACIÓN..."))
        try:
            if 'logros' in settings.INSTALLED_APPS:
                self.stdout.write("✅ App 'logros' instalada: OK")
                self.resultados['tests_pasados'] += 1
            else:
                self.stderr.write(self.style.ERROR("❌ App 'logros' no instalada"))
                self.resultados['errores'].append("App 'logros' no en INSTALLED_APPS")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error verificando configuración: {e}"))
            self.resultados['errores'].append(f"Error en configuración: {e}")

    def _verificar_base_datos(self):
        self.stdout.write(self.style.HTTP_INFO("\n🗄️  2. VERIFICANDO BASE DE DATOS..."))
        try:
            tablas_requeridas = ['logros_perfilgamificacion', 'logros_logro', 'entrenos_entrenorealizado']
            tablas_existentes = connection.introspection.table_names()

            for tabla in tablas_requeridas:
                if tabla in tablas_existentes:
                    self.stdout.write(f"✅ Tabla {tabla}: OK")
                    self.resultados['tests_pasados'] += 1
                else:
                    self.stderr.write(self.style.ERROR(f"❌ Tabla {tabla}: FALTANTE"))
                    self.resultados['errores'].append(f"Tabla {tabla} no existe")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error verificando base de datos: {e}"))
            self.resultados['errores'].append(f"Error en base de datos: {e}")

    def _verificar_modelos(self):
        self.stdout.write(self.style.HTTP_INFO("\n📊 3. VERIFICANDO MODELOS..."))
        try:
            perfiles_count = PerfilGamificacion.objects.count()
            logros_count = Logro.objects.count()
            self.stdout.write(f"📈 Perfiles: {perfiles_count}, Logros: {logros_count}")
            if logros_count > 0:
                self.stdout.write("✅ Sistema tiene logros configurados: OK")
                self.resultados['tests_pasados'] += 1
            else:
                self.stdout.write(self.style.WARNING("⚠️  No hay logros configurados"))
                self.resultados['warnings'].append("Sistema sin logros configurados")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error verificando modelos: {e}"))
            self.resultados['errores'].append(f"Error en modelos: {e}")

    def _verificar_comandos(self):
        self.stdout.write(self.style.HTTP_INFO("\n🛠️  4. VERIFICANDO COMANDOS DE GESTIÓN..."))
        try:
            out = StringIO()
            call_command('help', 'paso_1_backup_y_correccion', stdout=out)
            self.stdout.write("✅ Comando 'paso_1_backup_y_correccion' ejecutable: OK")
            self.resultados['tests_pasados'] += 1
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Comando 'paso_1_backup_y_correccion' no ejecutable: {e}"))
            self.resultados['errores'].append("Comando 'paso_1_backup_y_correccion' no encontrado o con errores.")

    def _ejecutar_tests(self):
        self.stdout.write(self.style.HTTP_INFO("\n🧪 5. EJECUTANDO TESTS AUTOMATIZADOS..."))
        try:
            TestRunner = get_runner(settings)
            test_runner = TestRunner(verbosity=0, interactive=False)
            failures = test_runner.run_tests(["logros"])  # Asume que los tests están en la app 'logros'
            if failures == 0:
                self.stdout.write("✅ Todos los tests de la app 'logros' pasaron: OK")
                self.resultados['tests_pasados'] += 1
            else:
                self.stderr.write(self.style.ERROR(f"❌ {failures} tests de 'logros' fallaron."))
                self.resultados['errores'].append(f"{failures} tests fallaron")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  No se pudieron ejecutar los tests: {e}"))
            self.resultados['warnings'].append("No se pudieron ejecutar los tests automatizados.")

    def _generar_reporte_final(self):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 40))
        self.stdout.write(self.style.SUCCESS("📋 REPORTE FINAL"))
        self.stdout.write(self.style.SUCCESS("=" * 40))

        total_checks = self.resultados['tests_pasados'] + len(self.resultados['errores'])
        porcentaje_exito = (self.resultados['tests_pasados'] / max(total_checks, 1)) * 100

        self.stdout.write(f"✅ Checks pasados: {self.resultados['tests_pasados']}")
        self.stdout.write(f"❌ Errores críticos: {len(self.resultados['errores'])}")
        self.stdout.write(f"⚠️  Warnings: {len(self.resultados['warnings'])}")
        self.stdout.write(f"📈 Salud del sistema: {porcentaje_exito:.1f}%")

        if self.resultados['errores']:
            self.stderr.write(self.style.ERROR(f"\n❌ ERRORES CRÍTICOS:"))
            for error in self.resultados['errores']: self.stderr.write(f"  • {error}")

        if self.resultados['warnings']:
            self.stdout.write(self.style.WARNING(f"\n⚠️  WARNINGS:"))
            for warning in self.resultados['warnings']: self.stdout.write(f"  • {warning}")

        if not self.resultados['errores']:
            self.stdout.write(self.style.SUCCESS("\n🎉 ESTADO DEL SISTEMA: ✅ SALUDABLE"))
            return True
        else:
            self.stderr.write(self.style.ERROR("\n🔧 ESTADO DEL SISTEMA: ❌ NECESITA ATENCIÓN"))
            return False
