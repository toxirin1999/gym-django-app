# diario/services/insignias_service.py

from django.utils import timezone
from ..models import Insignia, InsigniaUsuario, ProsocheHabito


class InsigniasService:
    """Servicio para gestión automática de insignias"""
    
    # Definición de insignias de hábitos
    INSIGNIAS_HABITOS = {
        # Hábitos positivos
        'habito_positivo_1dia': {
            'nombre': 'Primer Paso',
            'descripcion': 'Completaste tu primer día de un hábito positivo',
            'icono': '🎯'
        },
        'habito_positivo_7dias': {
            'nombre': 'Una Semana de Constancia',
            'descripcion': 'Mantuviste un hábito positivo durante 7 días',
            'icono': '🥈'
        },
        'habito_positivo_21dias': {
            'nombre': 'Formando el Hábito',
            'descripcion': '21 días de un hábito positivo - ¡Se está consolidando!',
            'icono': '🥇'
        },
        'habito_positivo_30dias': {
            'nombre': 'Un Mes de Éxito',
            'descripcion': 'Completaste 30 días de un hábito positivo',
            'icono': '💎'
        },
        'habito_positivo_66dias': {
            'nombre': 'Hábito Automático',
            'descripcion': '66 días - El hábito es ahora parte de ti',
            'icono': '👑'
        },
        
        # Hábitos negativos (a eliminar)
        'habito_negativo_1dia': {
            'nombre': 'Primer Día Limpio',
            'descripcion': 'Un día sin tu hábito negativo - ¡Excelente inicio!',
            'icono': '🎯'
        },
        'habito_negativo_3dias': {
            'nombre': '72 Horas de Libertad',
            'descripcion': '3 días sin el hábito - Las primeras 72 horas son críticas',
            'icono': '🥉'
        },
        'habito_negativo_7dias': {
            'nombre': 'Una Semana de Victoria',
            'descripcion': '7 días sin el hábito negativo - ¡La semana más difícil!',
            'icono': '🥈'
        },
        'habito_negativo_21dias': {
            'nombre': 'Rompiendo el Patrón',
            'descripcion': '21 días limpio - El hábito está perdiendo fuerza',
            'icono': '🥇'
        },
        'habito_negativo_30dias': {
            'nombre': 'Un Mes de Libertad',
            'descripcion': '30 días sin el hábito - ¡Logro monumental!',
            'icono': '💎'
        },
        'habito_negativo_90dias': {
            'nombre': 'Hábito Roto',
            'descripcion': '90 días - Has superado el período crítico',
            'icono': '👑'
        },
    }
    
    @staticmethod
    def crear_insignias_sistema():
        """Crea las insignias del sistema si no existen"""
        for codigo, datos in InsigniasService.INSIGNIAS_HABITOS.items():
            Insignia.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': datos['nombre'],
                    'descripcion': datos['descripcion'],
                    'icono': datos['icono'],
                    'virtud_asociada': 'general',
                    'criterio_logro': datos['descripcion']
                }
            )
    
    @staticmethod
    def verificar_insignias_habito(habito, usuario):
        """
        Verifica y otorga insignias basadas en el progreso del hábito
        Retorna lista de insignias nuevas otorgadas
        """
        insignias_otorgadas = []
        
        if habito.tipo_habito == 'positivo':
            # Verificar insignias de hábitos positivos
            dias_completados = habito.get_dias_completados()
            
            insignias_a_verificar = [
                (1, 'habito_positivo_1dia'),
                (7, 'habito_positivo_7dias'),
                (21, 'habito_positivo_21dias'),
                (30, 'habito_positivo_30dias'),
                (66, 'habito_positivo_66dias'),
            ]
            
            for dias_requeridos, codigo_insignia in insignias_a_verificar:
                if dias_completados >= dias_requeridos:
                    insignia_otorgada = InsigniasService._otorgar_insignia(
                        usuario, 
                        codigo_insignia
                    )
                    if insignia_otorgada:
                        insignias_otorgadas.append(insignia_otorgada)
        
        else:  # habito negativo
            # Verificar insignias de hábitos a eliminar
            dias_sin_habito = habito.get_dias_sin_habito()
            
            insignias_a_verificar = [
                (1, 'habito_negativo_1dia'),
                (3, 'habito_negativo_3dias'),
                (7, 'habito_negativo_7dias'),
                (21, 'habito_negativo_21dias'),
                (30, 'habito_negativo_30dias'),
                (90, 'habito_negativo_90dias'),
            ]
            
            for dias_requeridos, codigo_insignia in insignias_a_verificar:
                if dias_sin_habito >= dias_requeridos:
                    insignia_otorgada = InsigniasService._otorgar_insignia(
                        usuario,
                        codigo_insignia
                    )
                    if insignia_otorgada:
                        insignias_otorgadas.append(insignia_otorgada)
        
        return insignias_otorgadas
    
    @staticmethod
    def _otorgar_insignia(usuario, codigo_insignia):
        """
        Otorga una insignia a un usuario si no la tiene ya
        Retorna la insignia otorgada o None si ya la tenía
        """
        try:
            insignia = Insignia.objects.get(codigo=codigo_insignia)
            
            # Verificar si el usuario ya tiene esta insignia
            insignia_usuario, created = InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia,
                defaults={'vista': False}
            )
            
            if created:
                return insignia
            
        except Insignia.DoesNotExist:
            # La insignia no existe en el sistema, crearla
            InsigniasService.crear_insignias_sistema()
            # Intentar de nuevo
            return InsigniasService._otorgar_insignia(usuario, codigo_insignia)
        
        return None
    
    @staticmethod
    def obtener_insignias_nuevas(usuario):
        """Obtiene las insignias no vistas del usuario"""
        return InsigniaUsuario.objects.filter(
            usuario=usuario,
            vista=False
        ).select_related('insignia')
    
    @staticmethod
    def marcar_insignias_vistas(usuario):
        """Marca todas las insignias del usuario como vistas"""
        InsigniaUsuario.objects.filter(
            usuario=usuario,
            vista=False
        ).update(vista=True)
