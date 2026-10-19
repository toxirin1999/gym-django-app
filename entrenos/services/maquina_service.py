"""Lo que la app sabe de cada máquina de un cliente (13-oct-2026).

Dos cosas que antes adivinaba con reglas genéricas:

- **Tope**: el peso máximo que permite la máquina (``TopeMaquinaGym``). Se
  guarda al cerrar una sesión con "Tope kg" marcado y nunca se propone por
  encima. Si un día se levanta más sin marcarlo, el tope desaparece.
- **Salto real**: el incremento de peso que de verdad usa en esa máquina,
  aprendido de los pesos registrados (60 → 62,5 es 2,5; 20 → 21 es 1). Antes
  todas las poleas iban de 5 en 5 y el fly saltaba de 20 a 25 kg.
"""

from decimal import Decimal

SESIONES_PARA_INCREMENTO = 8
INCREMENTO_MINIMO = 1.0     # diferencias menores suelen ser ruido del selector


def _clave(nombre):
    from entrenos.services.decision_log_service import normalizar_ejercicio
    return normalizar_ejercicio(nombre)


# ─────────────────────────────────────────────────────────────
# Tope
# ─────────────────────────────────────────────────────────────

def tope_de(cliente, nombre):
    """Peso máximo guardado para esa máquina (float) o None."""
    from entrenos.models import TopeMaquinaGym

    tope = TopeMaquinaGym.objects.filter(
        cliente=cliente, ejercicio_normalizado=_clave(nombre),
    ).values_list('peso_max_kg', flat=True).first()
    return float(tope) if tope is not None else None


def registrar_topes_de_entreno(entreno):
    """Al cerrar una sesión: guarda, corrige o retira los topes de sus máquinas."""
    from entrenos.models import EjercicioRealizado, TopeMaquinaGym
    from entrenos.services.ultima_sesion_service import series_de_trabajo

    for ej in EjercicioRealizado.objects.filter(entreno=entreno, completado=True):
        clave = _clave(ej.nombre_ejercicio)
        if not clave:
            continue
        pesos = [s['peso'] for s in series_de_trabajo(entreno, ej.nombre_ejercicio) if s['peso'] > 0]
        if not pesos:
            continue
        maximo = max(pesos)
        if ej.es_tope_maquina:
            TopeMaquinaGym.objects.update_or_create(
                cliente=entreno.cliente, ejercicio_normalizado=clave,
                defaults={'ejercicio': ej.nombre_ejercicio, 'peso_max_kg': Decimal(str(maximo))},
            )
        else:
            TopeMaquinaGym.objects.filter(
                cliente=entreno.cliente, ejercicio_normalizado=clave,
                peso_max_kg__lt=Decimal(str(maximo)) - Decimal('0.01'),
            ).delete()


def aplicar_tope(cliente, ej):
    """Nunca proponer por encima del tope de la máquina. Devuelve un cambio o None."""
    nombre = ej.get('nombre') or ''
    tope = tope_de(cliente, nombre)
    if tope is None:
        return None
    ej['tope_maquina_kg'] = tope
    ej['sugerencia_tope'] = True
    try:
        propuesto = float(ej.get('peso_kg') or 0)
    except (TypeError, ValueError):
        return None
    if propuesto <= tope + 1e-6:
        return None
    from entrenos.services.ultima_sesion_service import kg
    ej['peso_kg_anterior'] = propuesto
    ej['peso_kg'] = tope
    if 'peso_recomendado_kg' in ej:
        ej['peso_recomendado_kg'] = tope
    ej['progresion_pospuesta'] = True
    ej['progresion_aplicada'] = False
    ej['progresion_accion'] = 'subir_peso'
    ej['progresion_motivo'] = f'{kg(tope)} kg es el máximo de esta máquina: progreso por repeticiones.'
    ej['progresion_motivo_local'] = 'tope_maquina'
    ej.pop('motivo_peso', None)
    return {
        'tipo': 'progresion_pospuesta',
        'ejercicio_original': nombre,
        'ejercicio_nuevo': None,
        'accion': 'subir_peso',
        'peso_sugerido': tope,
        'razon': ej['progresion_motivo'],
    }


# ─────────────────────────────────────────────────────────────
# Salto real de peso
# ─────────────────────────────────────────────────────────────

def incremento_real(cliente, nombre, por_defecto=2.5):
    """El salto de peso más pequeño que usa en esa máquina, o ``por_defecto``."""
    from entrenos.models import SerieRealizada

    entrenos = list(
        SerieRealizada.objects.filter(
            entreno__cliente=cliente, ejercicio__nombre__iexact=nombre,
            completado=True, es_aproximacion=False, peso_kg__gt=0,
        ).order_by('-entreno__fecha').values_list('entreno_id', flat=True).distinct()[:200]
    )
    ids = list(dict.fromkeys(entrenos))[:SESIONES_PARA_INCREMENTO]
    if not ids:
        return float(por_defecto)
    pesos = sorted({
        round(float(p), 2) for p in SerieRealizada.objects.filter(
            entreno_id__in=ids, ejercicio__nombre__iexact=nombre,
            completado=True, es_aproximacion=False, peso_kg__gt=0,
        ).values_list('peso_kg', flat=True)
    })
    saltos = [
        round(b - a, 2) for a, b in zip(pesos, pesos[1:]) if b - a >= INCREMENTO_MINIMO - 1e-9
    ]
    return float(min(saltos)) if saltos else float(por_defecto)


# ─────────────────────────────────────────────────────────────
# Escala real de carga (17-oct-2026)
# ─────────────────────────────────────────────────────────────
# David: "todas las máquinas van de 5 en 5; los discos de 2,5 en 2,5". El
# salto aprendido del historial heredaba los pesos raros que dejaba el
# selector (50,5 → 55,5 → 59,5 daba saltos de 4 kg) y proponía 37,5 kg en
# total para dos mancuernas. Cuando el tipo de equipo se reconoce, manda su
# escala física; el historial solo decide si no se reconoce.

SALTO_MAQUINA = 5.0
SALTO_DISCOS = 2.5
SALTO_MANCUERNA = 2.5      # por mancuerna; en "peso total" de dos, el doble
SALTO_KETTLEBELL = 4.0
# 19-oct-2026: barra Z con discos de 2,5 → se cargan de dos en dos (uno por lado).
SALTO_BARRA_Z = 5.0

_TOKENS_KETTLEBELL = ('kettlebell', 'pesa rusa')
_TOKENS_BARRA_Z = ('barra z', 'barra ez', 'ez bar', 'z-bar')
_TOKENS_MANCUERNA = ('mancuerna', 'dumbbell', 'arnold')
_TOKENS_UNA_MANO = ('una mano', 'un brazo', 'unilateral', 'por lado', 'alterno')
_TOKENS_DISCOS = (
    'barra', 'barbell', 'disco', 'press banca', 'sentadilla', 'peso muerto',
    'deadlift', 'squat', 'bench press', 'multipower', 'smith', 'prensa',
    'leg press', 'hack', 'hip thrust', 'zancada',
)
_TOKENS_MAQUINA = (
    'máquina', 'maquina', 'machine', 'polea', 'cable', 'pec deck', 'peck',
    'jalón', 'jalon', 'pulldown', 'pallof', 'femoral', 'leg curl',
    'extensión de cuádriceps', 'extension de cuadriceps', 'extensión de pierna',
    'leg extension', 'aductor', 'abductor', 'contractora', 'gemelo',
)


def tipo_equipo_carga(nombre, equipo=None):
    """'kettlebell' | 'barra_z' | 'mancuerna_una' | 'mancuerna_dos' | 'discos' | 'maquina' | None."""
    descriptor = f'{nombre or ""} {equipo or ""}'.casefold()
    # 18-oct-2026: una sola kettlebell, de 4 en 4 (8, 12, 16, 20…).
    if any(t in descriptor for t in _TOKENS_KETTLEBELL):
        return 'kettlebell'
    if any(t in descriptor for t in _TOKENS_BARRA_Z):
        return 'barra_z'
    if any(t in descriptor for t in _TOKENS_MANCUERNA):
        return 'mancuerna_una' if any(t in descriptor for t in _TOKENS_UNA_MANO) else 'mancuerna_dos'
    if any(t in descriptor for t in _TOKENS_DISCOS):
        return 'discos'
    if any(t in descriptor for t in _TOKENS_MAQUINA):
        return 'maquina'
    return None


def salto_fisico(nombre, equipo=None):
    """Salto de la escala física del equipo, o None si no se reconoce."""
    return {
        'maquina': SALTO_MAQUINA,
        'discos': SALTO_DISCOS,
        'mancuerna_una': SALTO_MANCUERNA,
        'mancuerna_dos': SALTO_MANCUERNA * 2,
        'kettlebell': SALTO_KETTLEBELL,
        'barra_z': SALTO_BARRA_Z,
    }.get(tipo_equipo_carga(nombre, equipo))


def salto_carga(cliente, nombre):
    """El salto con el que se proponen y ajustan pesos de ese ejercicio."""
    from rutinas.models import EjercicioBase

    base = EjercicioBase.objects.filter(nombre__iexact=nombre or '').first()
    fisico = salto_fisico(nombre, base.equipo if base else None)
    if fisico:
        return fisico
    por_defecto = float(base.incremento_kg) if base and base.incremento_kg else 2.5
    # Sin tipo reconocido: lo aprendido solo si es un salto que existe en un
    # gimnasio (1; 1,25; 2; 2,5; 5). Un 4,75 sale de pesos mal apuntados
    # (18-oct-2026: el Curl Araña proponía 19 kg tras hacer 20 × 15).
    aprendido = incremento_real(cliente, nombre, por_defecto)
    validos = (1.0, 1.25, 2.0, 2.5, 4.0, 5.0)
    return next((v for v in validos if abs(aprendido - v) < 0.01), 2.5)


def a_escala(peso, salto, hacia='cerca'):
    """Lleva un peso a la escala real: 37,5 con salto 5 → 35 ('abajo') o 40 ('arriba').

    'cerca' redondea al más próximo y, en empate, hacia abajo (más prudente).
    """
    import math
    try:
        peso, salto = float(peso), float(salto)
    except (TypeError, ValueError):
        return peso
    if peso <= 0 or salto <= 0:
        return peso
    k = peso / salto
    if hacia == 'abajo':
        n = math.floor(k + 1e-9)
    elif hacia == 'arriba':
        n = math.ceil(k - 1e-9)
    else:
        n = math.floor(k) if k - math.floor(k) <= 0.5 + 1e-9 else math.ceil(k)
    return round(max(n, 1) * salto, 2)
