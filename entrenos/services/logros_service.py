"""
Servicio de Detección de Logros Automáticos
Detecta y desbloquea logros basados en las sesiones de entrenamiento
"""

from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)


class LogrosService:
    """
    Servicio para detectar y desbloquear logros automáticamente
    """
    
    @staticmethod
    def verificar_logros_sesion(sesion):
        """
        Verifica todos los logros posibles después de una sesión
        Retorna lista de logros desbloqueados
        """
        from entrenos.models import LogroAutomatico, ClienteLogroAutomatico
        
        cliente = sesion.entreno.cliente
        logros_nuevos = []
        
        # Obtener todos los logros activos
        logros_activos = LogroAutomatico.objects.filter(activo=True)
        
        for logro in logros_activos:
            # Verificar si ya fue desbloqueado
            ya_desbloqueado = ClienteLogroAutomatico.objects.filter(
                cliente=cliente,
                logro=logro
            ).exists()
            
            if ya_desbloqueado:
                continue
            
            # Verificar si cumple la condición
            cumple = LogrosService._verificar_condicion_logro(logro, cliente, sesion)
            
            if cumple:
                # Desbloquear logro
                cliente_logro = ClienteLogroAutomatico.objects.create(
                    cliente=cliente,
                    logro=logro,
                    sesion=sesion
                )
                logros_nuevos.append(logro)
                logger.info(f"🏆 Logro desbloqueado: {logro.nombre} para {cliente.nombre}")
        
        return logros_nuevos
    
    @staticmethod
    def _verificar_condicion_logro(logro, cliente, sesion):
        """
        Verifica si se cumple la condición de un logro específico
        """
        condicion_tipo = logro.condicion_tipo
        condicion_valor = logro.condicion_valor
        
        try:
            # LOGROS DE RACHA
            if condicion_tipo == 'racha_dias':
                dias_requeridos = condicion_valor.get('dias', 7)
                racha_actual = LogrosService._calcular_racha_actual(cliente)
                return racha_actual >= dias_requeridos
            
            # LOGROS DE VOLUMEN
            elif condicion_tipo == 'volumen_sesion':
                volumen_requerido = condicion_valor.get('kg', 5000)
                return sesion.volumen_sesion >= volumen_requerido
            
            elif condicion_tipo == 'volumen_total_historico':
                from entrenos.models import EntrenoRealizado
                volumen_requerido = condicion_valor.get('kg', 10000)
                volumen_total = EntrenoRealizado.objects.filter(
                    cliente=cliente
                ).aggregate(total=Sum('volumen_total_kg'))['total'] or 0
                return volumen_total >= volumen_requerido
            
            # LOGROS DE TIEMPO
            elif condicion_tipo == 'primera_sesion':
                return True  # Si llegó aquí, es su primera sesión con logros
            
            elif condicion_tipo == 'total_sesiones':
                from entrenos.models import SesionEntrenamiento
                sesiones_requeridas = condicion_valor.get('cantidad', 10)
                total_sesiones = SesionEntrenamiento.objects.filter(
                    entreno__cliente=cliente
                ).count()
                return total_sesiones >= sesiones_requeridas
            
            elif condicion_tipo == 'duracion_sesion':
                duracion_requerida = condicion_valor.get('minutos', 60)
                return sesion.duracion_minutos >= duracion_requerida
            
            # LOGROS DE PERFECCIÓN
            elif condicion_tipo == 'sesion_perfecta':
                return sesion.es_sesion_perfecta
            
            elif condicion_tipo == 'sesiones_perfectas_consecutivas':
                cantidad_requerida = condicion_valor.get('cantidad', 5)
                return LogrosService._verificar_sesiones_perfectas_consecutivas(
                    cliente, cantidad_requerida
                )
            
            # LOGROS DE RÉCORDS
            elif condicion_tipo == 'total_records':
                from entrenos.models import RecordPersonal
                records_requeridos = condicion_valor.get('cantidad', 5)
                total_records = RecordPersonal.objects.filter(
                    cliente=cliente,
                    superado=False
                ).count()
                return total_records >= records_requeridos
            
            elif condicion_tipo == 'records_en_sesion':
                records_requeridos = condicion_valor.get('cantidad', 3)
                return sesion.nuevos_records >= records_requeridos
            
            # LOGROS ESPECIALES
            elif condicion_tipo == 'hora_entrenamiento':
                hora_tipo = condicion_valor.get('tipo', 'madrugada')  # madrugada, noche
                if hora_tipo == 'madrugada' and sesion.hora_inicio:
                    return sesion.hora_inicio.hour < 7
                elif hora_tipo == 'noche' and sesion.hora_inicio:
                    return sesion.hora_inicio.hour >= 21
            
            elif condicion_tipo == 'rpe_controlado':
                rpe_min = condicion_valor.get('min', 6)
                rpe_max = condicion_valor.get('max', 8)
                if sesion.rpe_medio:
                    return rpe_min <= sesion.rpe_medio <= rpe_max
            
            # Si no coincide con ningún tipo conocido
            logger.warning(f"Tipo de condición desconocido: {condicion_tipo}")
            return False
            
        except Exception as e:
            logger.error(f"Error verificando condición {condicion_tipo}: {e}")
            return False
    
    @staticmethod
    def _calcular_racha_actual(cliente):
        """
        Calcula la racha actual de días consecutivos entrenando
        """
        from entrenos.models import EntrenoRealizado
        
        entrenamientos = EntrenoRealizado.objects.filter(
            cliente=cliente
        ).order_by('-fecha').values_list('fecha', flat=True)
        
        if not entrenamientos:
            return 0
        
        # Obtener fechas únicas
        fechas_unicas = sorted(set(entrenamientos), reverse=True)
        
        if not fechas_unicas:
            return 0
        
        racha = 1
        fecha_anterior = fechas_unicas[0]
        
        for fecha in fechas_unicas[1:]:
            diferencia = (fecha_anterior - fecha).days
            if diferencia == 1:
                racha += 1
                fecha_anterior = fecha
            else:
                break
        
        return racha
    
    @staticmethod
    def _verificar_sesiones_perfectas_consecutivas(cliente, cantidad_requerida):
        """
        Verifica si el cliente tiene N sesiones perfectas consecutivas
        """
        from entrenos.models import SesionEntrenamiento
        
        sesiones = SesionEntrenamiento.objects.filter(
            entreno__cliente=cliente
        ).order_by('-fecha_creacion')[:cantidad_requerida]
        
        if sesiones.count() < cantidad_requerida:
            return False
        
        # Verificar que todas sean perfectas
        return all(sesion.es_sesion_perfecta for sesion in sesiones)
    
    @staticmethod
    def inicializar_logros_predefinidos():
        """
        Crea los logros predefinidos en la base de datos
        Ejecutar una sola vez o cuando se quieran agregar nuevos logros
        """
        from entrenos.models import LogroAutomatico
        
        logros = [
            # LOGROS DE RACHA
            {
                'codigo': 'racha_3_dias',
                'nombre': 'Inicio Constante 🔥',
                'descripcion': 'Entrena 3 días consecutivos',
                'icono': '🔥',
                'categoria': 'racha',
                'rareza': 'comun',
                'condicion_tipo': 'racha_dias',
                'condicion_valor': {'dias': 3},
                'puntos_recompensa': 10
            },
            {
                'codigo': 'racha_7_dias',
                'nombre': 'Racha de Fuego 🔥',
                'descripcion': 'Entrena 7 días consecutivos',
                'icono': '🔥',
                'categoria': 'racha',
                'rareza': 'raro',
                'condicion_tipo': 'racha_dias',
                'condicion_valor': {'dias': 7},
                'puntos_recompensa': 25
            },
            {
                'codigo': 'racha_14_dias',
                'nombre': 'Imparable 🔥',
                'descripcion': 'Entrena 14 días consecutivos',
                'icono': '🔥',
                'categoria': 'racha',
                'rareza': 'epico',
                'condicion_tipo': 'racha_dias',
                'condicion_valor': {'dias': 14},
                'puntos_recompensa': 50
            },
            {
                'codigo': 'racha_30_dias',
                'nombre': 'Leyenda Viviente 🔥',
                'descripcion': 'Entrena 30 días consecutivos',
                'icono': '🔥',
                'categoria': 'racha',
                'rareza': 'legendario',
                'condicion_tipo': 'racha_dias',
                'condicion_valor': {'dias': 30},
                'puntos_recompensa': 100
            },
            
            # LOGROS DE VOLUMEN
            {
                'codigo': 'volumen_5k',
                'nombre': 'Levantador Fuerte 💪',
                'descripcion': 'Levanta 5,000 kg en una sesión',
                'icono': '💪',
                'categoria': 'volumen',
                'rareza': 'comun',
                'condicion_tipo': 'volumen_sesion',
                'condicion_valor': {'kg': 5000},
                'puntos_recompensa': 15
            },
            {
                'codigo': 'volumen_10k',
                'nombre': 'Bestia de Hierro 💪',
                'descripcion': 'Levanta 10,000 kg en una sesión',
                'icono': '💪',
                'categoria': 'volumen',
                'rareza': 'raro',
                'condicion_tipo': 'volumen_sesion',
                'condicion_valor': {'kg': 10000},
                'puntos_recompensa': 30
            },
            {
                'codigo': 'volumen_20k',
                'nombre': 'Titán del Gimnasio 💪',
                'descripcion': 'Levanta 20,000 kg en una sesión',
                'icono': '💪',
                'categoria': 'volumen',
                'rareza': 'epico',
                'condicion_tipo': 'volumen_sesion',
                'condicion_valor': {'kg': 20000},
                'puntos_recompensa': 60
            },
            
            # LOGROS DE TIEMPO
            {
                'codigo': 'primera_sesion',
                'nombre': 'Primer Paso 🎯',
                'descripcion': 'Completa tu primera sesión',
                'icono': '🎯',
                'categoria': 'tiempo',
                'rareza': 'comun',
                'condicion_tipo': 'primera_sesion',
                'condicion_valor': {},
                'puntos_recompensa': 5
            },
            {
                'codigo': 'sesiones_10',
                'nombre': 'Comprometido ⏱️',
                'descripcion': 'Completa 10 sesiones',
                'icono': '⏱️',
                'categoria': 'tiempo',
                'rareza': 'comun',
                'condicion_tipo': 'total_sesiones',
                'condicion_valor': {'cantidad': 10},
                'puntos_recompensa': 20
            },
            {
                'codigo': 'sesiones_50',
                'nombre': 'Veterano ⏱️',
                'descripcion': 'Completa 50 sesiones',
                'icono': '⏱️',
                'categoria': 'tiempo',
                'rareza': 'raro',
                'condicion_tipo': 'total_sesiones',
                'condicion_valor': {'cantidad': 50},
                'puntos_recompensa': 50
            },
            {
                'codigo': 'sesiones_100',
                'nombre': 'Centurión ⏱️',
                'descripcion': 'Completa 100 sesiones',
                'icono': '⏱️',
                'categoria': 'tiempo',
                'rareza': 'epico',
                'condicion_tipo': 'total_sesiones',
                'condicion_valor': {'cantidad': 100},
                'puntos_recompensa': 100
            },
            
            # LOGROS DE PERFECCIÓN
            {
                'codigo': 'sesion_perfecta',
                'nombre': 'Perfección ⭐',
                'descripcion': 'Completa el 100% de las series en una sesión',
                'icono': '⭐',
                'categoria': 'perfeccion',
                'rareza': 'comun',
                'condicion_tipo': 'sesion_perfecta',
                'condicion_valor': {},
                'puntos_recompensa': 10
            },
            {
                'codigo': 'perfectas_5',
                'nombre': 'Racha Perfecta ⭐',
                'descripcion': '5 sesiones perfectas consecutivas',
                'icono': '⭐',
                'categoria': 'perfeccion',
                'rareza': 'raro',
                'condicion_tipo': 'sesiones_perfectas_consecutivas',
                'condicion_valor': {'cantidad': 5},
                'puntos_recompensa': 35
            },
            
            # LOGROS DE RÉCORDS
            {
                'codigo': 'records_5',
                'nombre': 'Rompedor de Récords 🏆',
                'descripcion': 'Establece 5 récords personales',
                'icono': '🏆',
                'categoria': 'records',
                'rareza': 'raro',
                'condicion_tipo': 'total_records',
                'condicion_valor': {'cantidad': 5},
                'puntos_recompensa': 25
            },
            {
                'codigo': 'records_10',
                'nombre': 'Maestro de Récords 🏆',
                'descripcion': 'Establece 10 récords personales',
                'icono': '🏆',
                'categoria': 'records',
                'rareza': 'epico',
                'condicion_tipo': 'total_records',
                'condicion_valor': {'cantidad': 10},
                'puntos_recompensa': 50
            },
            {
                'codigo': 'records_sesion_3',
                'nombre': 'Día de Récords 🏆',
                'descripcion': 'Rompe 3 récords en una sola sesión',
                'icono': '🏆',
                'categoria': 'records',
                'rareza': 'epico',
                'condicion_tipo': 'records_en_sesion',
                'condicion_valor': {'cantidad': 3},
                'puntos_recompensa': 40
            },
            
            # LOGROS ESPECIALES
            {
                'codigo': 'madrugador',
                'nombre': 'Madrugador 🌅',
                'descripcion': 'Entrena antes de las 7 AM',
                'icono': '🌅',
                'categoria': 'especial',
                'rareza': 'raro',
                'condicion_tipo': 'hora_entrenamiento',
                'condicion_valor': {'tipo': 'madrugada'},
                'puntos_recompensa': 15
            },
            {
                'codigo': 'guerrero_nocturno',
                'nombre': 'Guerrero Nocturno 🌙',
                'descripcion': 'Entrena después de las 9 PM',
                'icono': '🌙',
                'categoria': 'especial',
                'rareza': 'raro',
                'condicion_tipo': 'hora_entrenamiento',
                'condicion_valor': {'tipo': 'noche'},
                'puntos_recompensa': 15
            },
            {
                'codigo': 'maratonista',
                'nombre': 'Maratonista 🏃',
                'descripcion': 'Sesión de más de 2 horas',
                'icono': '🏃',
                'categoria': 'especial',
                'rareza': 'raro',
                'condicion_tipo': 'duracion_sesion',
                'condicion_valor': {'minutos': 120},
                'puntos_recompensa': 20
            },
            {
                'codigo': 'velocista',
                'nombre': 'Velocista ⚡',
                'descripcion': 'Completa una sesión en menos de 30 minutos',
                'icono': '⚡',
                'categoria': 'especial',
                'rareza': 'raro',
                'condicion_tipo': 'duracion_sesion',
                'condicion_valor': {'minutos': 30, 'operador': 'menor'},
                'puntos_recompensa': 15
            },
        ]
        
        creados = 0
        actualizados = 0
        
        for logro_data in logros:
            logro, created = LogroAutomatico.objects.update_or_create(
                codigo=logro_data['codigo'],
                defaults=logro_data
            )
            if created:
                creados += 1
                logger.info(f"✅ Logro creado: {logro.nombre}")
            else:
                actualizados += 1
                logger.info(f"🔄 Logro actualizado: {logro.nombre}")
        
        logger.info(f"📊 Total: {creados} creados, {actualizados} actualizados")
        return creados, actualizados
