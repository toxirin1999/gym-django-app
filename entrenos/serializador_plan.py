# ========== SERIALIZADOR DE PLAN CON CONTENIDO EDUCATIVO ==========

import json
from datetime import date, datetime
from decimal import Decimal

def serializar_plan_para_sesion(plan):
    """
    Convierte un plan con objetos ContenidoEducativo a un diccionario serializable.
    
    Args:
        plan: El plan generado con agregar_educacion_a_plan()
    
    Returns:
        dict: Plan serializable que puede guardarse en sesión
    """
    
    def serializar_valor(valor):
        """Serializa valores complejos a tipos JSON-compatibles"""
        
        # Si es un objeto ContenidoEducativo (dataclass)
        if hasattr(valor, '__dataclass_fields__'):
            return {
                'titulo': valor.titulo,
                'explicacion_simple': valor.explicacion_simple,
                'explicacion_detallada': valor.explicacion_detallada,
                'ejemplos': valor.ejemplos if isinstance(valor.ejemplos, list) else list(valor.ejemplos)
            }
        
        # Si es un Decimal
        elif isinstance(valor, Decimal):
            return float(valor)
        
        # Si es una fecha
        elif isinstance(valor, (date, datetime)):
            return valor.isoformat()
        
        # Si es un diccionario
        elif isinstance(valor, dict):
            return {k: serializar_valor(v) for k, v in valor.items()}
        
        # Si es una lista
        elif isinstance(valor, (list, tuple)):
            return [serializar_valor(item) for item in valor]
        
        # Si es un objeto con __dict__ (otros objetos personalizados)
        elif hasattr(valor, '__dict__'):
            return serializar_valor(valor.__dict__)
        
        # Tipos básicos (str, int, float, bool, None)
        else:
            return valor
    
    # Serializar el plan completo
    return serializar_valor(plan)


def deserializar_plan_desde_sesion(plan_serializado):
    """
    Convierte un plan serializado de sesión de vuelta a su estructura original.
    
    Args:
        plan_serializado: Plan guardado en sesión
    
    Returns:
        dict: Plan con estructura original (ContenidoEducativo como dicts)
    """
    # En realidad, para nuestro caso, no necesitamos deserializar
    # porque trabajamos con dicts en el template
    return plan_serializado


# ========== ACTUALIZAR LA VISTA vista_plan_anual ==========

# Reemplaza esta línea en tu vista:
# request.session[f'plan_anual_{cliente_id}'] = plan

# Con esta:
# plan_serializado = serializar_plan_para_sesion(plan)
# request.session[f'plan_anual_{cliente_id}'] = plan_serializado

# ========== EJEMPLO DE USO ==========

"""
En tu vista vista_plan_anual:

    # ... código anterior ...
    
    plan = agregar_educacion_a_plan(plan_original)
    
    # ✅ NUEVO: Serializar antes de guardar en sesión
    plan_serializado = serializar_plan_para_sesion(plan)
    request.session[f'plan_anual_{cliente_id}'] = plan_serializado
    request.session.modified = True
    
    # ... resto del código ...
"""
