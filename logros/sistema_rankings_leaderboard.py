# SISTEMA DE RANKINGS Y LEADERBOARD PARA EL CÓDICE DE LAS LEYENDAS
# Sistema competitivo épico para motivar a los clientes

"""
OBJETIVO: Crear un sistema de clasificación y competencia que permita a los clientes
ver cómo se comparan con otros usuarios del gimnasio, añadiendo motivación competitiva
al Códice de las Leyendas.

CARACTERÍSTICAS:
1. Rankings por diferentes métricas
2. Leaderboards dinámicos
3. Temporadas y competencias
4. Títulos y reconocimientos especiales
5. Estadísticas comparativas
6. Sistema de ligas/divisiones
"""

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from logros.models import PerfilGamificacion, Arquetipo
from clientes.models import Cliente

# =============================================================================
# NUEVOS MODELOS PARA EL SISTEMA DE RANKINGS
# =============================================================================

class Liga(models.Model):
    """
    Sistema de ligas para dividir a los usuarios por nivel de experiencia
    """
    TIPOS_LIGA = [
        ('bronce', 'Liga de Bronce'),
        ('plata', 'Liga de Plata'),
        ('oro', 'Liga de Oro'),
        ('platino', 'Liga de Platino'),
        ('diamante', 'Liga de Diamante'),
        ('maestro', 'Liga de Maestros'),
        ('leyenda', 'Liga de Leyendas'),
    ]
    
    nombre = models.CharField(max_length=50, choices=TIPOS_LIGA, unique=True)
    puntos_minimos = models.IntegerField(help_text="Puntos mínimos para acceder a esta liga")
    puntos_maximos = models.IntegerField(help_text="Puntos máximos de esta liga")
    icono = models.CharField(max_length=10, default="🏆")
    color_hex = models.CharField(max_length=7, default="#FFD700")
    descripcion = models.TextField(blank=True)
    
    class Meta:
        ordering = ['puntos_minimos']
    
    def __str__(self):
        return f"{self.get_nombre_display()}"

class Temporada(models.Model):
    """
    Temporadas de competencia (mensual, trimestral, anual)
    """
    TIPOS_TEMPORADA = [
        ('semanal', 'Semanal'),
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('anual', 'Anual'),
        ('especial', 'Evento Especial'),
    ]
    
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS_TEMPORADA)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)
    premio_descripcion = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"
    
    @property
    def esta_activa(self):
        ahora = timezone.now()
        return self.activa and self.fecha_inicio <= ahora <= self.fecha_fin

class RankingEntry(models.Model):
    """
    Entrada individual en el ranking
    """
    TIPOS_RANKING = [
        ('puntos_totales', 'Puntos Totales'),
        ('entrenamientos_mes', 'Entrenamientos del Mes'),
        ('racha_actual', 'Racha Actual'),
        ('volumen_total', 'Volumen Total Levantado'),
        ('pruebas_completadas', 'Pruebas Completadas'),
        ('nivel_arquetipo', 'Nivel de Arquetipo'),
        ('constancia_semanal', 'Constancia Semanal'),
        ('records_personales', 'Récords Personales'),
    ]
    
    perfil = models.ForeignKey(PerfilGamificacion, on_delete=models.CASCADE)
    temporada = models.ForeignKey(Temporada, on_delete=models.CASCADE)
    tipo_ranking = models.CharField(max_length=30, choices=TIPOS_RANKING)
    valor = models.FloatField(help_text="Valor de la métrica para este ranking")
    posicion = models.IntegerField(help_text="Posición en el ranking")
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['perfil', 'temporada', 'tipo_ranking']
        ordering = ['posicion']
    
    def __str__(self):
        return f"{self.perfil.cliente.nombre} - {self.get_tipo_ranking_display()} - Pos #{self.posicion}"

class TituloEspecial(models.Model):
    """
    Títulos especiales que se otorgan por logros excepcionales
    """
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    icono = models.CharField(max_length=10, default="👑")
    color_hex = models.CharField(max_length=7, default="#FFD700")
    condicion_tipo = models.CharField(max_length=50, help_text="Tipo de condición para obtener el título")
    condicion_valor = models.FloatField(help_text="Valor requerido para la condición")
    es_temporal = models.BooleanField(default=False, help_text="Si el título se puede perder")
    puntos_bonus = models.IntegerField(default=0, help_text="Puntos bonus por tener este título")
    
    def __str__(self):
        return f"{self.icono} {self.nombre}"

class PerfilTitulo(models.Model):
    """
    Relación entre perfiles y títulos obtenidos
    """
    perfil = models.ForeignKey(PerfilGamificacion, on_delete=models.CASCADE)
    titulo = models.ForeignKey(TituloEspecial, on_delete=models.CASCADE)
    fecha_obtencion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['perfil', 'titulo']
    
    def __str__(self):
        return f"{self.perfil.cliente.nombre} - {self.titulo.nombre}"

# =============================================================================
# SERVICIOS PARA EL SISTEMA DE RANKINGS
# =============================================================================

class RankingService:
    """
    Servicio principal para manejar rankings y leaderboards
    """
    
    @staticmethod
    def inicializar_ligas():
        """
        Crea las ligas por defecto del sistema
        """
        ligas_default = [
            {
                'nombre': 'bronce',
                'puntos_minimos': 0,
                'puntos_maximos': 999,
                'icono': '🥉',
                'color_hex': '#CD7F32',
                'descripcion': 'Liga de Bronce - Para guerreros que inician su camino'
            },
            {
                'nombre': 'plata',
                'puntos_minimos': 1000,
                'puntos_maximos': 4999,
                'icono': '🥈',
                'color_hex': '#C0C0C0',
                'descripcion': 'Liga de Plata - Para luchadores experimentados'
            },
            {
                'nombre': 'oro',
                'puntos_minimos': 5000,
                'puntos_maximos': 14999,
                'icono': '🥇',
                'color_hex': '#FFD700',
                'descripcion': 'Liga de Oro - Para campeones dedicados'
            },
            {
                'nombre': 'platino',
                'puntos_minimos': 15000,
                'puntos_maximos': 39999,
                'icono': '💎',
                'color_hex': '#E5E4E2',
                'descripcion': 'Liga de Platino - Para élites del entrenamiento'
            },
            {
                'nombre': 'diamante',
                'puntos_minimos': 40000,
                'puntos_maximos': 99999,
                'icono': '💠',
                'color_hex': '#B9F2FF',
                'descripcion': 'Liga de Diamante - Para maestros legendarios'
            },
            {
                'nombre': 'maestro',
                'puntos_minimos': 100000,
                'puntos_maximos': 499999,
                'icono': '⭐',
                'color_hex': '#FF6B35',
                'descripcion': 'Liga de Maestros - Para los más poderosos'
            },
            {
                'nombre': 'leyenda',
                'puntos_minimos': 500000,
                'puntos_maximos': 999999999,
                'icono': '👑',
                'color_hex': '#FF0000',
                'descripcion': 'Liga de Leyendas - Para los inmortales'
            }
        ]
        
        for liga_data in ligas_default:
            Liga.objects.get_or_create(
                nombre=liga_data['nombre'],
                defaults=liga_data
            )
        
        print("✅ Ligas inicializadas correctamente")
    
    @staticmethod
    def crear_temporada_actual():
        """
        Crea la temporada mensual actual si no existe
        """
        ahora = timezone.now()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Calcular fin de mes
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
            print(f"✅ Temporada creada: {temporada.nombre}")
        
        return temporada
    
    @staticmethod
    def actualizar_rankings():
        """
        Actualiza todos los rankings para la temporada actual
        """
        temporada = RankingService.crear_temporada_actual()
        
        # Obtener todos los perfiles activos
        perfiles = PerfilGamificacion.objects.select_related('cliente').all()
        
        # Actualizar cada tipo de ranking
        tipos_ranking = [
            'puntos_totales',
            'entrenamientos_mes',
            'racha_actual',
            'volumen_total',
            'pruebas_completadas',
            'nivel_arquetipo'
        ]
        
        for tipo in tipos_ranking:
            RankingService._actualizar_ranking_especifico(temporada, tipo, perfiles)
        
        print(f"✅ Rankings actualizados para {temporada.nombre}")
    
    @staticmethod
    def _actualizar_ranking_especifico(temporada, tipo_ranking, perfiles):
        """
        Actualiza un tipo específico de ranking
        """
        # Calcular valores para cada perfil
        datos_ranking = []
        
        for perfil in perfiles:
            valor = RankingService._calcular_valor_ranking(perfil, tipo_ranking, temporada)
            if valor is not None:
                datos_ranking.append({
                    'perfil': perfil,
                    'valor': valor
                })
        
        # Ordenar por valor (descendente)
        datos_ranking.sort(key=lambda x: x['valor'], reverse=True)
        
        # Actualizar posiciones
        for posicion, datos in enumerate(datos_ranking, 1):
            RankingEntry.objects.update_or_create(
                perfil=datos['perfil'],
                temporada=temporada,
                tipo_ranking=tipo_ranking,
                defaults={
                    'valor': datos['valor'],
                    'posicion': posicion
                }
            )
    
    @staticmethod
    def _calcular_valor_ranking(perfil, tipo_ranking, temporada):
        """
        Calcula el valor específico para un tipo de ranking
        """
        try:
            if tipo_ranking == 'puntos_totales':
                return perfil.puntos_totales or 0
            
            elif tipo_ranking == 'racha_actual':
                return perfil.racha_dias_consecutivos or 0
            
            elif tipo_ranking == 'nivel_arquetipo':
                if perfil.nivel_actual:
                    # Buscar el arquetipo y devolver su orden
                    try:
                        arquetipo = Arquetipo.objects.get(titulo=perfil.nivel_actual)
                        return arquetipo.puntos_requeridos or 0
                    except Arquetipo.DoesNotExist:
                        return 0
                return 0
            
            elif tipo_ranking == 'entrenamientos_mes':
                # Contar entrenamientos en el mes actual
                inicio_mes = temporada.fecha_inicio
                fin_mes = temporada.fecha_fin
                
                from entrenos.models import EntrenoRealizado
                count = EntrenoRealizado.objects.filter(
                    cliente=perfil.cliente,
                    fecha__range=[inicio_mes.date(), fin_mes.date()]
                ).count()
                return count
            
            elif tipo_ranking == 'volumen_total':
                # Calcular volumen total levantado
                from entrenos.models import EjercicioRealizado
                total = EjercicioRealizado.objects.filter(
                    entreno__cliente=perfil.cliente,
                    completado=True
                ).aggregate(
                    total=models.Sum(
                        models.F('peso_kg') * models.F('series') * models.F('repeticiones')
                    )
                )['total'] or 0
                return total
            
            elif tipo_ranking == 'pruebas_completadas':
                from logros.models import PruebaUsuario
                count = PruebaUsuario.objects.filter(
                    perfil=perfil,
                    completada=True
                ).count()
                return count
            
            else:
                return 0
                
        except Exception as e:
            print(f"Error calculando {tipo_ranking} para {perfil.cliente.nombre}: {e}")
            return 0
    
    @staticmethod
    def obtener_liga_usuario(perfil):
        """
        Determina la liga del usuario basada en sus puntos
        """
        puntos = perfil.puntos_totales or 0
        
        liga = Liga.objects.filter(
            puntos_minimos__lte=puntos,
            puntos_maximos__gte=puntos
        ).first()
        
        return liga or Liga.objects.filter(nombre='bronce').first()
    
    @staticmethod
    def obtener_top_rankings(tipo_ranking='puntos_totales', limite=10):
        """
        Obtiene el top N del ranking especificado
        """
        temporada = Temporada.objects.filter(activa=True).first()
        if not temporada:
            return []
        
        return RankingEntry.objects.filter(
            temporada=temporada,
            tipo_ranking=tipo_ranking
        ).select_related('perfil__cliente').order_by('posicion')[:limite]
    
    @staticmethod
    def obtener_posicion_usuario(perfil, tipo_ranking='puntos_totales'):
        """
        Obtiene la posición específica de un usuario en un ranking
        """
        temporada = Temporada.objects.filter(activa=True).first()
        if not temporada:
            return None
        
        try:
            entry = RankingEntry.objects.get(
                perfil=perfil,
                temporada=temporada,
                tipo_ranking=tipo_ranking
            )
            return entry.posicion
        except RankingEntry.DoesNotExist:
            return None

# =============================================================================
# TÍTULOS ESPECIALES POR DEFECTO
# =============================================================================

def crear_titulos_especiales():
    """
    Crea títulos especiales épicos para el sistema
    """
    titulos_default = [
        {
            'nombre': 'El Imparable',
            'descripcion': 'Mantiene una racha de 30 días consecutivos',
            'icono': '🔥',
            'color_hex': '#FF4500',
            'condicion_tipo': 'racha_dias',
            'condicion_valor': 30,
            'es_temporal': True,
            'puntos_bonus': 1000
        },
        {
            'nombre': 'Maestro del Volumen',
            'descripcion': 'Ha levantado más de 100,000kg en total',
            'icono': '💪',
            'color_hex': '#8B4513',
            'condicion_tipo': 'volumen_total',
            'condicion_valor': 100000,
            'es_temporal': False,
            'puntos_bonus': 2000
        },
        {
            'nombre': 'Rey de la Constancia',
            'descripcion': 'Líder en entrenamientos del mes',
            'icono': '👑',
            'color_hex': '#FFD700',
            'condicion_tipo': 'ranking_entrenamientos',
            'condicion_valor': 1,
            'es_temporal': True,
            'puntos_bonus': 1500
        },
        {
            'nombre': 'Leyenda Viviente',
            'descripcion': 'Ha alcanzado la Liga de Leyendas',
            'icono': '⭐',
            'color_hex': '#FF0000',
            'condicion_tipo': 'liga',
            'condicion_valor': 500000,
            'es_temporal': False,
            'puntos_bonus': 5000
        },
        {
            'nombre': 'Cazador de Récords',
            'descripcion': 'Ha superado 10 récords personales',
            'icono': '🎯',
            'color_hex': '#00FF00',
            'condicion_tipo': 'records_totales',
            'condicion_valor': 10,
            'es_temporal': False,
            'puntos_bonus': 800
        },
        {
            'nombre': 'El Invencible',
            'descripcion': '#1 en puntos totales por 7 días consecutivos',
            'icono': '🛡️',
            'color_hex': '#4169E1',
            'condicion_tipo': 'ranking_top_dias',
            'condicion_valor': 7,
            'es_temporal': True,
            'puntos_bonus': 3000
        }
    ]
    
    for titulo_data in titulos_default:
        TituloEspecial.objects.get_or_create(
            nombre=titulo_data['nombre'],
            defaults=titulo_data
        )
    
    print("✅ Títulos especiales creados")

# =============================================================================
# SCRIPT PRINCIPAL DE INICIALIZACIÓN
# =============================================================================

def inicializar_sistema_rankings():
    """
    Inicializa todo el sistema de rankings y leaderboards
    """
    print("🏆 Inicializando Sistema de Rankings y Leaderboard...")
    print("=" * 60)
    
    # 1. Crear ligas
    print("1. Creando ligas...")
    RankingService.inicializar_ligas()
    
    # 2. Crear temporada actual
    print("2. Creando temporada actual...")
    RankingService.crear_temporada_actual()
    
    # 3. Crear títulos especiales
    print("3. Creando títulos especiales...")
    crear_titulos_especiales()
    
    # 4. Actualizar rankings iniciales
    print("4. Actualizando rankings...")
    RankingService.actualizar_rankings()
    
    print()
    print("✅ Sistema de Rankings y Leaderboard inicializado correctamente!")
    print()
    print("🎯 CARACTERÍSTICAS IMPLEMENTADAS:")
    print("   • 7 Ligas competitivas (Bronce → Leyenda)")
    print("   • 6 Tipos de rankings diferentes")
    print("   • Temporadas mensuales automáticas")
    print("   • 6 Títulos especiales épicos")
    print("   • Sistema de posiciones dinámico")
    print()
    print("🚀 PRÓXIMOS PASOS:")
    print("   1. Ejecutar: python manage.py shell < sistema_rankings_leaderboard.py")
    print("   2. Crear vista de leaderboard")
    print("   3. Integrar en templates")
    print("   4. Configurar actualización automática")

if __name__ == "__main__":
    inicializar_sistema_rankings()

# =============================================================================
# COMANDOS DE GESTIÓN ÚTILES
# =============================================================================

"""
COMANDOS ÚTILES PARA EL SISTEMA:

# Actualizar rankings manualmente
RankingService.actualizar_rankings()

# Obtener top 10 por puntos
top_puntos = RankingService.obtener_top_rankings('puntos_totales', 10)

# Obtener liga de un usuario
liga = RankingService.obtener_liga_usuario(perfil)

# Obtener posición de un usuario
posicion = RankingService.obtener_posicion_usuario(perfil, 'puntos_totales')

# Ver todos los rankings disponibles
for entry in RankingEntry.objects.all():
    print(f"{entry.perfil.cliente.nombre}: {entry.tipo_ranking} - Pos #{entry.posicion}")
"""

