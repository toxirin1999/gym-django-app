# planificador_helms/utils/validacion.py
"""
Funciones de validación de entrada para el sistema Helms.
"""

from typing import Tuple


def validar_rpe(rpe: int) -> int:
    """
    Valida que el RPE esté en el rango correcto (1-10).
    
    Args:
        rpe: Valor de RPE a validar
        
    Returns:
        int: RPE validado
        
    Raises:
        ValueError: Si el RPE está fuera del rango 1-10
    """
    if not isinstance(rpe, (int, float)):
        raise ValueError(f"RPE debe ser un número, recibido: {type(rpe).__name__}")
    
    rpe = int(rpe)
    if not 1 <= rpe <= 10:
        raise ValueError(f"RPE debe estar entre 1-10, recibido: {rpe}")
    
    return rpe


def validar_rep_range(rep_range: str) -> Tuple[int, int]:
    """
    Valida y parsea un rango de repeticiones.
    
    Args:
        rep_range: String con formato "min-max" (ej: "8-12")
        
    Returns:
        Tuple[int, int]: (min_reps, max_reps)
        
    Raises:
        ValueError: Si el formato es inválido
    """
    if not isinstance(rep_range, str):
        raise ValueError(f"rep_range debe ser string, recibido: {type(rep_range).__name__}")
    
    try:
        parts = rep_range.split('-')
        if len(parts) != 2:
            raise ValueError
        
        min_r, max_r = map(int, parts)
        
        if min_r < 1:
            raise ValueError("Las repeticiones mínimas deben ser >= 1")
        
        if min_r > max_r:
            raise ValueError(f"Rango inválido: {min_r} > {max_r}")
        
        return (min_r, max_r)
    
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Formato de rango de reps inválido: '{rep_range}'. Use formato 'min-max' (ej: '8-12')")


def validar_peso(peso: float, nombre_ejercicio: str = "") -> float:
    """
    Valida que el peso sea un valor positivo razonable.
    
    Args:
        peso: Peso en kg
        nombre_ejercicio: Nombre del ejercicio (opcional, para mensajes de error)
        
    Returns:
        float: Peso validado
        
    Raises:
        ValueError: Si el peso es inválido
    """
    try:
        peso = float(peso)
    except (ValueError, TypeError):
        raise ValueError(f"Peso inválido para '{nombre_ejercicio}': debe ser un número")
    
    if peso < 0:
        raise ValueError(f"Peso no puede ser negativo: {peso} kg")
    
    if peso > 500:  # Límite razonable para seguridad
        raise ValueError(f"Peso excesivo para '{nombre_ejercicio}': {peso} kg (máximo 500 kg)")
    
    return peso


def validar_series(series: int, nombre_ejercicio: str = "") -> int:
    """
    Valida que el número de series sea razonable.
    
    Args:
        series: Número de series
        nombre_ejercicio: Nombre del ejercicio (opcional)
        
    Returns:
        int: Series validadas
        
    Raises:
        ValueError: Si el número de series es inválido
    """
    try:
        series = int(series)
    except (ValueError, TypeError):
        raise ValueError(f"Series inválidas para '{nombre_ejercicio}': debe ser un número entero")
    
    if series < 0:
        raise ValueError(f"Series no pueden ser negativas: {series}")
    
    if series > 10:  # Límite razonable
        raise ValueError(f"Número de series excesivo para '{nombre_ejercicio}': {series} (máximo 10)")
    
    return series


def validar_dias_disponibles(dias: int) -> int:
    """
    Valida que los días disponibles sean 3, 4 o 5.
    
    Args:
        dias: Número de días disponibles
        
    Returns:
        int: Días validados
        
    Raises:
        ValueError: Si los días no son 3, 4 o 5
    """
    if dias not in [3, 4, 5]:
        raise ValueError(f"Días disponibles debe ser 3, 4 o 5, recibido: {dias}")
    
    return dias


def validar_experiencia_años(años: float) -> float:
    """
    Valida los años de experiencia.
    
    Args:
        años: Años de experiencia en entrenamiento
        
    Returns:
        float: Años validados
        
    Raises:
        ValueError: Si los años son inválidos
    """
    try:
        años = float(años)
    except (ValueError, TypeError):
        raise ValueError(f"Años de experiencia inválidos: debe ser un número")
    
    if años < 0:
        raise ValueError(f"Años de experiencia no pueden ser negativos: {años}")
    
    if años > 100:
        raise ValueError(f"Años de experiencia excesivos: {años}")
    
    return años
