# logros/management/commands/inicializar_rankings.py

import sys
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from logros.models import Liga, Temporada, TituloEspecial

# --- ¡IMPORTANTE! Asegúrate de que la codificación es correcta ---
# Esta línea ayuda a manejar correctamente los caracteres especiales y emojis.
sys.stdout.reconfigure(encoding='utf-8')


class Command(BaseCommand):
    help = 'Inicializa el sistema de Rankings: crea Ligas, Temporada actual y Títulos especiales.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando la inicialización del sistema de Rankings y Leaderboard...")

        self.inicializar_ligas()
        self.crear_temporada_actual()
        self.crear_titulos_especiales()

        self.stdout.write(self.style.SUCCESS("\n✅ ¡Sistema de Rankings y Leaderboard inicializado correctamente!"))
        self.stdout.write("   • 7 Ligas competitivas (Bronce → Leyenda)")
        self.stdout.write("   • Temporada mensual automática creada")
        self.stdout.write("   • 3 Títulos especiales épicos creados")
        self.stdout.write(
            "\n👉 Próximo paso: Ejecuta 'python manage.py actualizar_rankings' para poblar las tablas de posiciones.")

    def inicializar_ligas(self):
        self.stdout.write("  - Creando o actualizando Ligas...")
        ligas_default = [
            {'nombre': 'bronce', 'puntos_minimos': 0, 'puntos_maximos': 9999, 'icono': '🥉', 'color_hex': '#CD7F32'},
            {'nombre': 'plata', 'puntos_minimos': 10000, 'puntos_maximos': 24999, 'icono': '🥈', 'color_hex': '#C0C0C0'},
            {'nombre': 'oro', 'puntos_minimos': 25000, 'puntos_maximos': 49999, 'icono': '🥇', 'color_hex': '#FFD700'},
            {'nombre': 'platino', 'puntos_minimos': 50000, 'puntos_maximos': 99999, 'icono': '💎',
             'color_hex': '#E5E4E2'},
            {'nombre': 'diamante', 'puntos_minimos': 100000, 'puntos_maximos': 249999, 'icono': '💍',
             'color_hex': '#B9F2FF'},
            {'nombre': 'maestro', 'puntos_minimos': 250000, 'puntos_maximos': 499999, 'icono': '👑',
             'color_hex': '#FF6B35'},
            {'nombre': 'leyenda', 'puntos_minimos': 500000, 'puntos_maximos': 999999999, 'icono': '🏆',
             'color_hex': '#FF0000'},
        ]

        for liga_data in ligas_default:
            liga, created = Liga.objects.get_or_create(nombre=liga_data['nombre'], defaults=liga_data)
            if created:
                self.stdout.write(f"    ✔️ Creada: {liga.get_nombre_display()}")
            else:
                # Opcional: actualizar si ya existe
                Liga.objects.filter(nombre=liga_data['nombre']).update(**liga_data)

        self.stdout.write(self.style.SUCCESS("    👍 Ligas inicializadas."))

    def crear_temporada_actual(self):
        self.stdout.write("  - Creando temporada actual...")
        ahora = timezone.now()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if inicio_mes.month == 12:
            fin_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1) - timedelta(seconds=1)
        else:
            fin_mes = inicio_mes.replace(month=inicio_mes.month + 1) - timedelta(seconds=1)

        temporada, created = Temporada.objects.get_or_create(
            tipo='mensual',
            fecha_inicio__year=inicio_mes.year,
            fecha_inicio__month=inicio_mes.month,
            defaults={
                'nombre': f'Temporada {inicio_mes.strftime("%B %Y")}',
                'fecha_inicio': inicio_mes,
                'fecha_fin': fin_mes,
                'activa': True,
                'descripcion': f'Competencia mensual de {inicio_mes.strftime("%B %Y")}',
                'premio_descripcion': 'Reconocimiento especial y puntos bonus'
            }
        )
        if created:
            self.stdout.write(f"    ✔️ Temporada creada: {temporada.nombre}")
        else:
            self.stdout.write(f"    ✔️ Temporada '{temporada.nombre}' ya existía.")

        self.stdout.write(self.style.SUCCESS("    👍 Temporada lista."))

    def crear_titulos_especiales(self):
        self.stdout.write("  - Creando Títulos Especiales...")
        titulos_default = [
            {'nombre': 'Señor de la Leyenda', 'descripcion': 'Alcanzó la Liga de Leyendas', 'icono': '🏆',
             'color_hex': '#FF0000', 'condicion_tipo': 'liga', 'condicion_valor': 500000, 'es_temporal': False,
             'puntos_bonus': 5000},
            {'nombre': 'Cazador de Récords', 'descripcion': 'Ha superado 10 récords personales', 'icono': '🎯',
             'color_hex': '#00FF00', 'condicion_tipo': 'records_totales', 'condicion_valor': 10, 'es_temporal': False,
             'puntos_bonus': 800},
            {'nombre': 'El Invencible', 'descripcion': '#1 en puntos totales por 7 días consecutivos', 'icono': '🛡️',
             'color_hex': '#4169E1', 'condicion_tipo': 'ranking_top_dias', 'condicion_valor': 7, 'es_temporal': True,
             'puntos_bonus': 3000},
        ]

        for titulo_data in titulos_default:
            titulo, created = TituloEspecial.objects.get_or_create(nombre=titulo_data['nombre'], defaults=titulo_data)
            if created:
                self.stdout.write(f"    ✔️ Creado: {titulo.nombre}")

        self.stdout.write(self.style.SUCCESS("    👍 Títulos especiales creados."))
