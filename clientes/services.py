# clientes/services.py

from datetime import date, timedelta
from django.db.models import Avg, Sum, Count
from decimal import Decimal

# Importamos todos los modelos necesarios
from clientes.models import Cliente, BitacoraDiaria, RevisionProgreso, ObjetivoCliente
from entrenos.models import EntrenoRealizado, EjercicioLiftinDetallado, EjercicioBase
from logros.models import PruebaLegendaria, PruebaUsuario
from joi.models import RecuerdoEmocional


def generar_ficha_contexto_dinamica(cliente_id, dias_a_revisar=30):
    """
    Recopila y formatea un informe detallado de 360° sobre un cliente para el chatbot Joi.
    Esta versión está optimizada para cargar correctamente los ejercicios detallados.
    """
    # --- MODO DEPURACIÓN: Descomenta la línea de abajo para forzar un ID ---
    # cliente_id = 1

    try:
        cliente = Cliente.objects.get(id=cliente_id)
        user = cliente.user
    except (Cliente.DoesNotExist, AttributeError):
        return "Error: No se pudo encontrar el cliente o el usuario asociado."

    # --- 1. CONFIGURACIÓN INICIAL Y CONSULTA ÚNICA DE ENTRENAMIENTOS ---
    fecha_fin = date.today()
    fecha_inicio = fecha_fin - timedelta(days=dias_a_revisar)
    periodo_analisis = f"{fecha_inicio.strftime('%d de %B de %Y')} - {fecha_fin.strftime('%d de %B de %Y')}"

    # ¡CONSULTA ÚNICA Y OPTIMIZADA!
    # Traemos todos los entrenos y sus ejercicios relacionados de una sola vez.
    entrenos_del_periodo = EntrenoRealizado.objects.filter(
        cliente=cliente, fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('-fecha').prefetch_related('ejercicios_liftin_detallados')

    # --- 2. DATOS BÁSICOS ---
    info_basica = f"**Nombre del Atleta:** {cliente.nombre}\n**Objetivo Principal Declarado:** {cliente.get_objetivo_principal_display()}"

    # --- 3. RESUMEN DE GAMIFICACIÓN ---
    # (Esta sección ya funcionaba bien, la dejamos como estaba)
    resumen_gamificacion = "\n**Resumen de Motivación y Logros:**\n..."  # (Pega aquí tu código de gamificación)

    # --- 4. ANÁLISIS DE ENTRENAMIENTOS (Usando nuestra consulta única) ---

    # 4.1 Resumen General
    resumen_entrenamiento = "\n**Resumen General de Rendimiento:**\n"
    if entrenos_del_periodo.exists():
        # Django es lo suficientemente inteligente para no volver a la base de datos aquí
        stats = entrenos_del_periodo.aggregate(
            num_sesiones=Count('id'),
            volumen_total=Sum('volumen_total_kg'),
            duracion_promedio=Avg('duracion_minutos')
        )
        resumen_entrenamiento += f"- Sesiones realizadas: {stats['num_sesiones'] or 0}\n"
        resumen_entrenamiento += f"- Volumen total levantado: {stats['volumen_total'] or 0:.0f} kg\n"
        resumen_entrenamiento += f"- Duración promedio: {stats['duracion_promedio'] or 0:.0f} min\n"
    else:
        resumen_entrenamiento += "- No se han registrado entrenamientos en este periodo.\n"

    # 4.2 Análisis Detallado de Últimos Entrenamientos
    detalle_ultimos_entrenos = "\n**Análisis Detallado de los Últimos Entrenamientos:**\n"

    if entrenos_del_periodo.exists():
        # Iteramos sobre los 3 entrenamientos más recientes que ya tenemos en memoria
        for entreno in entrenos_del_periodo[:3]:
            detalle_ultimos_entrenos += (
                f"\n*   **Entrenamiento del {entreno.fecha.strftime('%d de %B')}** "
                f"(Rutina: {entreno.resumen_rutina}, Volumen: {entreno.volumen_formateado}):\n"
            )

            # --- ¡ESTE ES EL CAMBIO CLAVE! ---
            # Buscamos en el modelo correcto: 'EjercicioRealizado'
            # Y usamos el 'related_name' que es 'ejercicios_realizados'
            ejercicios = entreno.ejercicios_realizados.all()
            # ---------------------------------

            if ejercicios:  # Si la relación devuelve ejercicios
                for ejercicio in ejercicios:
                    # Formateamos los datos usando los campos de EjercicioRealizado
                    detalle_ultimos_entrenos += (
                        f"    - {ejercicio.nombre_ejercicio}: "
                        f"{ejercicio.peso_kg} kg / "
                        f"{ejercicio.series} series de {ejercicio.repeticiones} reps\n"
                    )
            else:
                detalle_ultimos_entrenos += "    - (No se encontraron ejercicios detallados para este entrenamiento).\n"
    else:
        detalle_ultimos_entrenos += "- No hay entrenamientos detallados para analizar en este periodo.\n"
    # --- 5. OTRAS SECCIONES (Bitácora, Progreso Físico, etc.) ---
    # (Aquí iría el resto del código para las otras secciones, que ya funcionaban)
    resumen_bitacora = "\n**Resumen de Bienestar (Bitácora):**\n..."  # (Pega aquí tu código de bitácora)
    notas_relevantes = "\n**Entradas Relevantes de la Bitácora del Usuario:**\n..."  # (Pega aquí tu código de notas)
    resumen_progreso = "\n**Progreso Físico Medido:**\n..."  # (Pega aquí tu código de progreso)
    ejercicios_clave_analisis = "\n**Análisis de Progresión de Fuerza:**\n..."  # (Pega aquí tu código de análisis de progresión)

    # --- 6. CONSTRUCCIÓN DE LA FICHA DE CONTEXTO FINAL ---
    ficha_contexto = f"""
{info_basica.strip()}
{resumen_gamificacion.strip()}
{resumen_entrenamiento.strip()}
{detalle_ultimos_entrenos.strip()}
{ejercicios_clave_analisis.strip()}
{resumen_progreso.strip()}
{resumen_bitacora.strip()}
{notas_relevantes.strip()}
    """

    return ficha_contexto.strip()
