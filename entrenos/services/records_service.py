"""
Servicio de Detección de Récords Personales
Detecta automáticamente cuando se establecen nuevos récords
"""

from django.db.models import Max
from decimal import Decimal
import logging
from analytics.planificador_helms.database.ejercicios import obtener_grupo_muscular

logger = logging.getLogger(__name__)


class RecordsService:
    """
    Servicio para detectar y gestionar récords personales
    """
    
    # Palabras clave para ignorar en récords de peso/volumen
    KEYWORDS_EXCLUIDAS_RECORDS = [
        'plancha', 'plank', 'elevación de piernas', 'elevacion de piernas', 
        'abdominal', 'crunch', 'mountain climbers', 'cardio', 'burpee', 
        'estiramiento', 'yoga', 'asistencia', 'zancadas'
    ]
    
    @staticmethod
    def detectar_records_sesion(entreno):
        """
        Analiza los ejercicios de un entrenamiento y detecta récords personales.
        Soporta múltiples modelos de ejercicio (Manual, Liftin Detallado, Liftin Simple).
        """
        from entrenos.models import RecordPersonal
        
        cliente = entreno.cliente
        records_nuevos = []
        
        # 1. Recopilar todos los ejercicios de todas las fuentes posibles
        ejercicios_fuentes = []
        
        # A. Ejercicios Realizados (Manuales / Genéricos)
        ejercicios_fuentes.extend(list(entreno.ejercicios_realizados.filter(completado=True)))
        
        # B. Ejercicios Liftin Detallados
        if hasattr(entreno, 'ejercicios_liftin_detallados'):
            ejercicios_fuentes.extend(list(entreno.ejercicios_liftin_detallados.filter(completado=True)))
            
        # C. Ejercicios Liftin Simples
        if hasattr(entreno, 'ejercicios_liftin'):
            ejercicios_fuentes.extend(list(entreno.ejercicios_liftin.filter(estado='completado')))

        for ejercicio in ejercicios_fuentes:
            # Obtener nombre de forma segura (algunos modelos usan 'nombre', otros 'nombre_ejercicio')
            nombre = getattr(ejercicio, 'nombre_ejercicio', getattr(ejercicio, 'nombre', ''))
            if not nombre:
                continue
                
            ej_nombre_lower = nombre.lower()
            
            # Obtener peso de forma segura (manejar peso_kg vs weight_kg)
            peso = 0
            for attr in ['peso_kg', 'weight_kg', 'peso']:
                if hasattr(ejercicio, attr):
                    val = getattr(ejercicio, attr)
                    if val is not None:
                        try:
                            peso = float(val)
                            break
                        except (ValueError, TypeError):
                            continue

            # Obtener grupo muscular (con fallback al archivo ejercicios.py)
            grupo = getattr(ejercicio, 'grupo_muscular', None)
            if not grupo or grupo == 'otros':
                grupo_db = obtener_grupo_muscular(nombre)
                if grupo_db and grupo_db != 'otros':
                    grupo = grupo_db.capitalize()
            
            # FILTRO: Ignorar si pertenece a grupos que no son de fuerza pura o si tiene peso 0
            if (grupo in ['Core', 'Cardio', 'Otros'] or 
                any(kw in ej_nombre_lower for kw in RecordsService.KEYWORDS_EXCLUIDAS_RECORDS) or
                peso <= 0):
                continue

            # Verificar récord de peso máximo
            record_peso = RecordsService._verificar_record_peso(
                cliente, nombre, peso, entreno
            )
            if record_peso:
                records_nuevos.append(record_peso)
            
            # Verificar récord de volumen total
            # Calcular volumen de forma robusta
            vol_val = 0
            if hasattr(ejercicio, 'volumen') and callable(ejercicio.volumen):
                vol_val = ejercicio.volumen()
            elif hasattr(ejercicio, 'volumen_ejercicio'): # Para EjercicioLiftinDetallado
                 vol_val = ejercicio.volumen_ejercicio
            else:
                # Cálculo manual si no tiene método
                series = getattr(ejercicio, 'series', getattr(ejercicio, 'series_realizadas', 1))
                reps = getattr(ejercicio, 'repeticiones', getattr(ejercicio, 'repeticiones_min', 1))
                vol_val = peso * (series or 1) * (reps or 1)

            record_volumen = RecordsService._verificar_record_volumen(
                cliente, nombre, vol_val, entreno
            )
            if record_volumen:
                records_nuevos.append(record_volumen)
        
        if records_nuevos:
            logger.info(f"📊 Detectados {len(records_nuevos)} récords nuevos para {cliente.nombre}")
        return records_nuevos
    
    @staticmethod
    def _verificar_record_peso(cliente, ejercicio_nombre, peso_actual, entreno):
        """
        Verifica si el peso levantado es un récord personal
        """
        from entrenos.models import RecordPersonal
        peso_actual = Decimal(str(peso_actual))
        
        # Buscar récord actual para este ejercicio
        record_actual = RecordPersonal.objects.filter(
            cliente=cliente,
            ejercicio_nombre__iexact=ejercicio_nombre,
            tipo_record='peso_maximo',
            superado=False
        ).first()
        
        # Si no hay récord previo, este es el primero
        if not record_actual:
            nuevo_record = RecordPersonal.objects.create(
                cliente=cliente,
                ejercicio_nombre=ejercicio_nombre,
                tipo_record='peso_maximo',
                valor=peso_actual,
                entreno=entreno
            )
            logger.info(f"🏆 Primer récord: {ejercicio_nombre} - {peso_actual} kg")
            return nuevo_record
        
        # Si el peso actual es mayor, es un nuevo récord
        if peso_actual > record_actual.valor:
            # Marcar el récord anterior como superado
            record_actual.superado = True
            record_actual.fecha_superado = entreno.fecha
            record_actual.save()
            
            # Crear el nuevo récord
            nuevo_record = RecordPersonal.objects.create(
                cliente=cliente,
                ejercicio_nombre=ejercicio_nombre,
                tipo_record='peso_maximo',
                valor=peso_actual,
                entreno=entreno
            )
            logger.info(f"🏆 Nuevo récord de peso: {ejercicio_nombre} - {peso_actual} kg (anterior: {record_actual.valor} kg)")
            return nuevo_record
        
        return None
    
    @staticmethod
    def _verificar_record_volumen(cliente, ejercicio_nombre, volumen_actual, entreno):
        """
        Verifica si el volumen total es un récord personal
        """
        from entrenos.models import RecordPersonal
        volumen_actual = Decimal(str(volumen_actual))
        
        # Buscar récord actual para este ejercicio
        record_actual = RecordPersonal.objects.filter(
            cliente=cliente,
            ejercicio_nombre__iexact=ejercicio_nombre,
            tipo_record='volumen_total',
            superado=False
        ).first()
        
        # Si no hay récord previo, este es el primero
        if not record_actual:
            nuevo_record = RecordPersonal.objects.create(
                cliente=cliente,
                ejercicio_nombre=ejercicio_nombre,
                tipo_record='volumen_total',
                valor=volumen_actual,
                entreno=entreno
            )
            logger.info(f"🏆 Primer récord de volumen: {ejercicio_nombre} - {volumen_actual} kg")
            return nuevo_record
        
        # Si el volumen actual es mayor, es un nuevo récord
        if volumen_actual > record_actual.valor:
            # Marcar el récord anterior como superado
            record_actual.superado = True
            record_actual.fecha_superado = entreno.fecha
            record_actual.save()
            
            # Crear el nuevo récord
            nuevo_record = RecordPersonal.objects.create(
                cliente=cliente,
                ejercicio_nombre=ejercicio_nombre,
                tipo_record='volumen_total',
                valor=volumen_actual,
                entreno=entreno
            )
            logger.info(f"🏆 Nuevo récord de volumen: {ejercicio_nombre} - {volumen_actual} kg (anterior: {record_actual.valor} kg)")
            return nuevo_record
        
        return None
    
    @staticmethod
    def obtener_records_vigentes(cliente):
        """
        Obtiene todos los récords vigentes (no superados) de un cliente
        """
        from entrenos.models import RecordPersonal
        
        return RecordPersonal.objects.filter(
            cliente=cliente,
            superado=False
        ).order_by('ejercicio_nombre', 'tipo_record')
    
    @staticmethod
    def obtener_records_recientes(cliente, limite=10):
        """
        Obtiene los récords más recientes de un cliente
        """
        from entrenos.models import RecordPersonal
        
        return RecordPersonal.objects.filter(
            cliente=cliente
        ).order_by('-fecha_logrado')[:limite]
