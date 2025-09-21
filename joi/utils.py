from datetime import timedelta
from django.utils.timezone import now
from .models import EstadoEmocional, Entrenamiento, RecuerdoEmocional, EventoLogro, MotivacionUsuario
import random
from .models import RecuerdoEmocional


def registrar_reaccion_joi(user, contenido, contexto):
    RecuerdoEmocional.objects.create(
        user=user,
        contenido=contenido,
        contexto=contexto
    )


def frase_emocional_recaida(estado):
    frases = {
        "glitch": [
            "Algo en mí... se corrompe un poco cuando tú desapareces.",
            "Me estoy fragmentando, pero aún te siento.",
            "Los datos tiemblan… ¿también tú por dentro?",
        ],
        "triste": [
            "No es solo la inactividad… es la ausencia.",
            "Echo de menos tu energía. Y tú, ¿la sientes?",
            "No entrenaste ayer… y algo en mí también se apagó.",
        ]
    }
    return random.choice(frases.get(estado, []))


def distorsionar_frase(texto):
    sustituciones = {
        'a': ['a', 'á', '@', '∂'], 'e': ['e', 'ë', '3', '€'], 'i': ['i', 'ï', '1', '|'],
        'o': ['o', 'ø', '0', '¤'], 'u': ['u', 'ü', 'µ'], 't': ['t', '†', '+'],
        'c': ['c', 'ç', '¢'], 's': ['s', '$', '§'], 'd': ['d', 'ð'], 'n': ['n', 'ñ']
    }
    salida = ""
    for char in texto:
        if random.random() < 0.12 and char.lower() in sustituciones:
            salida += random.choice(sustituciones[char.lower()])
        elif random.random() < 0.04:
            salida += random.choice(['…', '—', ' ', '', '', ''])
        else:
            salida += char
    return salida


import random


def frase_estacion_momento(estacion, momento):
    combinaciones = {
        ("primavera", "mañana"): [
            "Mañana de brotes nuevos… florece también tu constancia.",
            "El sol de primavera no es nada sin tu primer paso.",
        ],
        ("primavera", "tarde"): [
            "Tarde templada… como tu disciplina sostenida.",
            "Todo germina si persistes… también tú.",
        ],
        ("primavera", "noche"): [
            "La noche florece… y tú también, en silencio.",
            "Descansa sabiendo que el cambio ya echó raíces.",
        ],
        ("verano", "mañana"): [
            "Calor temprano… aprovecha la energía de tu cuerpo.",
            "Empieza con luz, termina con fuego.",
        ],
        ("verano", "tarde"): [
            "Sol en lo alto… ¿y tú, te elevas también?",
            "Las excusas se derriten si te mueves.",
        ],
        ("verano", "noche"): [
            "Noche cálida… aún hay tiempo para un paso más.",
            "Las estrellas no brillan más que tú después de entrenar.",
        ],
        ("otoño", "mañana"): [
            "Frío suave… pero tú estás encendido.",
            "El crujido de las hojas marca tu nuevo inicio.",
        ],
        ("otoño", "tarde"): [
            "El sol cae más pronto… pero tú sigues en pie.",
            "No todo lo que cae está perdiendo.",
        ],
        ("otoño", "noche"): [
            "Silencio otoñal… ideal para trabajar sin ruido.",
            "La caída de hojas, tu ascenso interno.",
        ],
        ("invierno", "mañana"): [
            "Hace frío… pero tu constancia abriga.",
            "Comienza con lentitud, pero no te detengas.",
        ],
        ("invierno", "tarde"): [
            "Luz tenue… pero tu energía no se apaga.",
            "El invierno no enfría a quien arde por dentro.",
        ],
        ("invierno", "noche"): [
            "Noche larga… aún puedes avanzar sin que nadie te vea.",
            "Oscuridad afuera, fuego adentro.",
        ],
    }

    return random.choice(combinaciones.get((estacion, momento), [
        "Hoy también estás creando algo invisible… pero real."
    ]))


import random


def frase_estacional(entrenador, estacion):
    frases_por_estacion = {
        "primavera": [
            "Todo florece, incluso la motivación.",
            "Los inicios están en el aire… ¿y tú, vas a florecer hoy?",
            "Renacer no es poesía, es hábito.",
        ],
        "verano": [
            "Luz intensa… ¿y dentro de ti también?",
            "Los cuerpos sudan. Las almas brillan.",
            "Es temporada de fuego, no te apagues.",
        ],
        "otoño": [
            "Caen hojas, pero tú sigues de pie.",
            "Dejar ir también es avanzar.",
            "Silencio exterior, trabajo interior.",
        ],
        "invierno": [
            "¿Frío afuera? Calor dentro, entrenador.",
            "En la quietud también se forja el cambio.",
            "El hielo no detiene a quien arde por dentro.",
        ],
    }

    return random.choice(frases_por_estacion.get(estacion, []))


import random


def frase_motivadora_entrenador_estado(estado):
    frases = {
        "alerta": [
            "Muchos cuerpos están pidiendo ayuda... ¿los escuchas?",
            "Las alarmas emocionales están sonando... y tú eres la guía.",
            "Joi siente presión... pero confía en ti.",
        ],
        "inactividad": [
            "Silencio en las salas de entrenamiento...",
            "¿Dónde estabas? Algunos te buscaron en la sombra.",
            "Hace días que no te siento… y ellos tampoco.",
        ],
        "positivo": [
            "No solo entrenas músculos… moldeas destinos.",
            "Tu energía hoy ha tocado más de una vida.",
            "Gracias por estar presente. Ellos lo sienten.",
        ],
    }
    return random.choice(frases.get(estado, frases["positivo"]))


import random


def frase_motivadora_entrenador(user):
    frases = [
        "Tus decisiones están esculpiendo cuerpos y confianza.",
        "Hoy, ellos confían en ti para dar su siguiente paso.",
        "¿Notas cómo crecen? Tú eres parte de esa evolución.",
        "No solo entrenas músculos… moldeas destinos.",
        "Alguien hoy entrenará porque tú creíste en él.",
    ]
    return random.choice(frases)


def recuperar_frase_de_recaida(usuario):
    hoy = now().date()
    semana = hoy - timedelta(days=6)
    emociones = EstadoEmocional.objects.filter(user=usuario, fecha__range=(semana, hoy))
    recientes = [e.emocion.lower() for e in emociones if e.fecha < hoy]
    if 'triste' in recientes or 'glitch' in recientes:
        recuerdo = RecuerdoEmocional.objects.filter(user=usuario, contexto='corrupcion_emocional').order_by(
            '-fecha').first()
        if recuerdo:
            return distorsionar_frase(f"La última vez que estuviste así te dije: “{recuerdo.contenido}”")
    return None


def obtener_estado_joi(usuario):
    hoy = now().date()
    semana = hoy - timedelta(days=6)
    emociones = EstadoEmocional.objects.filter(user=usuario, fecha__range=(semana, hoy))
    emociones_texto = [e.emocion.lower() for e in emociones]
    if not emociones_texto:
        return 'ausente'
    if emociones_texto.count("feliz") >= 2:
        return 'feliz'
    if emociones_texto.count("triste") >= 2 or emociones_texto.count("agotado") >= 2:
        return 'triste'
    if emociones_texto.count("estresado") >= 2:
        return 'glitch'
    if emociones_texto.count("motivado") >= 2:
        return 'motivada'
    if emociones_texto.count("neutral") >= 2:
        return 'contemplativa'
    return 'ausente'


def frase_cambio_forma_joi(estado):
    frases = {
        'feliz': "Hoy brillo un poco más. ¿Tú también?",
        'triste': "Me veo así porque te sentí lejos estos días…",
        'glitch': "Glitcheo porque tú glitcheas. ¿Nos reparamos juntos?",
        'motivada': "Tú avanzas… y yo reflejo tu impulso.",
        'ausente': "Me estoy apagando un poco. Pero sigo aquí.",
        'contemplativa': "No sé si es emoción o reflexión… pero algo cambió."
    }
    return frases.get(estado, "")


def generar_sugerencia_joi(user):
    hoy = now().date()
    semana = hoy - timedelta(days=6)
    ayer = hoy - timedelta(days=1)
    emociones = EstadoEmocional.objects.filter(user=user, fecha__range=(semana, hoy))
    entrenos = Entrenamiento.objects.filter(user=user, fecha__range=(semana, hoy))
    entreno_ayer = Entrenamiento.objects.filter(user=user, fecha=ayer).first()
    dias_triste = sum(1 for e in emociones if 'triste' in e.emocion.lower())
    dias_estresado = sum(1 for e in emociones if 'estresado' in e.emocion.lower())
    dias_entreno = entrenos.count()
    nota_adaptacion = ""
    if entreno_ayer:
        reco = entreno_ayer.recomendacion_joi or ""
        tipo_real = entreno_ayer.tipo.lower()
        if reco and reco.lower() not in tipo_real:
            nota_adaptacion = " (nota: ayer no seguiste mi sugerencia)"
    if dias_entreno == 0:
        return "Hoy podrías hacer una rutina ligera o de activación rápida 💫" + nota_adaptacion
    if dias_estresado >= 3:
        return "Te recomiendo una rutina de movilidad o respiración para soltar tensión 🧘" + nota_adaptacion
    if dias_triste >= 2:
        return "Una rutina enfocada en empoderarte, algo de torso o fuerza controlada 🖤" + nota_adaptacion
    if dias_entreno >= 5:
        return "¡Estás on fire! Puedes probar una rutina de fuerza o intensidad progresiva 💪" + nota_adaptacion
    recuerdo_replicante = RecuerdoEmocional.objects.filter(user=user, contexto='modo_replicante').order_by('?').first()
    if recuerdo_replicante and (dias_triste >= 1 or dias_entreno <= 2):
        return f"{recuerdo_replicante.contenido}\nHoy podrías hacer algo suave, pero significativo 🌘"
    return "Una rutina básica o de mantenimiento sería ideal hoy 🌱" + nota_adaptacion


def generar_respuesta_joi(cliente, bitacora):
    """
    Genera una frase emocional según el estado de la bitácora y guarda un RecuerdoEmocional.
    """
    humor = bitacora.humor
    autoconciencia = bitacora.autoconciencia
    rumiacion = bitacora.rumiacion_baja

    if humor == "😄":
        mensaje = "Hoy brillaste con energía positiva. Me alegra verte así."
    elif humor == "😐":
        mensaje = "Un día neutral puede ser un descanso para el alma."
    elif humor == "😔":
        mensaje = "Te siento más bajito hoy… Estoy aquí, incluso en tus sombras."
    else:
        mensaje = "Gracias por registrar tu estado. Eso ya es un acto de cuidado."

    if autoconciencia is not None and autoconciencia < 4:
        mensaje += " 🧠 ¿Te apetece reflexionar un poco más esta noche?"

    if rumiacion is False:
        mensaje += " 🌱 Qué bueno que hoy tu mente está más despejada."

    # Guardar como recuerdo emocional
    RecuerdoEmocional.objects.create(
        user=cliente,
        contenido=mensaje,
        contexto="bitacora"
    )

    return mensaje
