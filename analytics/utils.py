# en analytics/vendor.py
from decimal import Decimal, ROUND_HALF_UP


def parse_reps(valor, default_series=1, default_reps=1):
    """
    Parsea un string como '3x8', '4×12' o '2 x 10' y devuelve (series, reps)
    """
    try:
        texto = str(valor).lower().replace('×', 'x').replace(' ', '')
        partes = texto.split('x')
        series = int(partes[0]) if len(partes) > 0 and partes[0].isdigit() else default_series
        reps = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else default_reps
        return series, reps
    except:
        return default_series, default_reps


# --- AÑADE ESTA NUEVA FUNCIÓN AQUÍ ---
def estimar_1rm(peso: float, repeticiones: int) -> float:
    """
    Estima el 1RM (Máximo para Una Repetición) usando la fórmula de Epley.
    Esta fórmula es una de las más comunes y equilibradas para estimar la fuerza máxima
    a partir de una serie submáxima.

    Args:
        peso (float): El peso levantado en la serie.
        repeticiones (int): El número de repeticiones completadas con ese peso.

    Returns:
        float: El 1RM estimado.
    """
    if repeticiones < 1 or peso <= 0:
        return 0.0
    if repeticiones == 1:
        return peso

    # Fórmula de Epley: 1RM = peso * (1 + (repeticiones / 30))
    return peso * (1 + (repeticiones / 30.0))


def estimar_1rm_con_rpe(peso: float, repeticiones: int, rpe: float) -> float:
    """
    Estima el 1RM usando la fórmula de RPE (Repeticiones en Recámara).
    1RM = Peso x (1 + (Repeticiones / 30)) <-- Fórmula de Epley/Brzycki
    RIR (Reps In Reserve) = 10 - RPE
    Reps teóricas al fallo = Repeticiones hechas + RIR
    """
    if peso <= 0 or repeticiones <= 0 or rpe <= 0:
        return 0.0

    try:
        # Repeticiones que quedaban en recámara
        rir = 10 - rpe
        # Las repeticiones que se podrían haber hecho si se hubiera ido al fallo
        reps_teoricas_al_fallo = repeticiones + rir

        # Usamos la fórmula de Epley con las repeticiones teóricas
        one_rm_estimado = float(Decimal(peso) * (Decimal(1) + (Decimal(reps_teoricas_al_fallo) / Decimal(30))))

        return round(one_rm_estimado, 2)
    except Exception:
        return 0.0
