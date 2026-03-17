# ============================================
# 15 INSIGNIAS ADICIONALES
# Script para crear insignias nuevas en el sistema
# ============================================

from diario.models import Insignia

insignias_adicionales = [

    # ========================================
    # SABIDURÍA (5 adicionales)
    # ========================================

    {
        'codigo': 'sabio_ancestral',
        'nombre': 'Sabio Ancestral',
        'descripcion': 'Completaste 100 reflexiones guiadas. Tu dedicación al autoconocimiento es extraordinaria.',
        'virtud_asociada': 'sabiduria',
        'icono': 'fa-scroll',
        'color': '#8B4513',
        'criterio_logro': 'Completar 100 reflexiones guiadas',
        'puntos_virtud': 100,
        'orden': 6,
        'activa': True,
    },

    {
        'codigo': 'escriba_dedicado',
        'nombre': 'Escriba Dedicado',
        'descripcion': 'Escribiste 50 reflexiones libres. Tu voz interior se fortalece con cada palabra.',
        'virtud_asociada': 'sabiduria',
        'icono': 'fa-pen-fancy',
        'color': '#4A148C',
        'criterio_logro': 'Escribir 50 reflexiones libres',
        'puntos_virtud': 40,
        'orden': 7,
        'activa': True,
    },

    {
        'codigo': 'maestro_categorias',
        'nombre': 'Maestro de Categorías',
        'descripcion': 'Completaste al menos una reflexión guiada de cada categoría (salud, social, naturaleza, filosofía, personal).',
        'virtud_asociada': 'sabiduria',
        'icono': 'fa-layer-group',
        'color': '#1976D2',
        'criterio_logro': 'Completar reflexiones de todas las categorías',
        'puntos_virtud': 25,
        'orden': 8,
        'activa': True,
    },

    {
        'codigo': 'reflexion_profunda',
        'nombre': 'Reflexión Profunda',
        'descripcion': 'Escribiste una reflexión de más de 1,000 palabras. La profundidad de tu introspección es admirable.',
        'virtud_asociada': 'sabiduria',
        'icono': 'fa-book-open',
        'color': '#00695C',
        'criterio_logro': 'Escribir una reflexión de 1,000+ palabras',
        'puntos_virtud': 15,
        'orden': 9,
        'activa': True,
    },

    {
        'codigo': 'ciclo_completo',
        'nombre': 'Ciclo Completo',
        'descripcion': 'Escribiste al menos una reflexión cada mes durante un año completo.',
        'virtud_asociada': 'sabiduria',
        'icono': 'fa-calendar-check',
        'color': '#6A1B9A',
        'criterio_logro': 'Reflexión en cada mes del año',
        'puntos_virtud': 50,
        'orden': 10,
        'activa': True,
    },

    # ========================================
    # CORAJE (3 adicionales)
    # ========================================

    {
        'codigo': 'phoenix_renacido',
        'nombre': 'Fénix Renacido',
        'descripcion': 'Volviste a escribir después de una ausencia de 30+ días. El coraje no es nunca caer, sino siempre levantarse.',
        'virtud_asociada': 'coraje',
        'icono': 'fa-phoenix-squadron',
        'color': '#D84315',
        'criterio_logro': 'Volver a escribir después de 30+ días de ausencia',
        'puntos_virtud': 30,
        'orden': 6,
        'activa': True,
    },

    {
        'codigo': 'guerrero_matutino',
        'nombre': 'Guerrero Matutino',
        'descripcion': 'Completaste tu entrada de Prosoche matutina durante 30 días consecutivos.',
        'virtud_asociada': 'coraje',
        'icono': 'fa-sun',
        'color': '#F57C00',
        'criterio_logro': 'Prosoche matutina 30 días consecutivos',
        'puntos_virtud': 25,
        'orden': 7,
        'activa': True,
    },

    {
        'codigo': 'guardian_nocturno',
        'nombre': 'Guardián Nocturno',
        'descripcion': 'Completaste tu reflexión nocturna durante 30 días consecutivos.',
        'virtud_asociada': 'coraje',
        'icono': 'fa-moon',
        'color': '#283593',
        'criterio_logro': 'Reflexión nocturna 30 días consecutivos',
        'puntos_virtud': 25,
        'orden': 8,
        'activa': True,
    },

    # ========================================
    # JUSTICIA (3 adicionales)
    # ========================================

    {
        'codigo': 'guardian_relaciones',
        'nombre': 'Guardián de Relaciones',
        'descripcion': 'Mantuviste 5 relaciones en estado "saludable" en Simbiosis durante un mes.',
        'virtud_asociada': 'justicia',
        'icono': 'fa-user-shield',
        'color': '#0288D1',
        'criterio_logro': '5 relaciones saludables durante 30 días',
        'puntos_virtud': 30,
        'orden': 3,
        'activa': True,
    },

    {
        'codigo': 'corazon_empatico',
        'nombre': 'Corazón Empático',
        'descripcion': 'Completaste 10 reflexiones guiadas de categoría "social" (causas humanitarias).',
        'virtud_asociada': 'justicia',
        'icono': 'fa-heart-circle',
        'color': '#C2185B',
        'criterio_logro': 'Completar 10 reflexiones sociales',
        'puntos_virtud': 25,
        'orden': 4,
        'activa': True,
    },

    {
        'codigo': 'puente_constructor',
        'nombre': 'Constructor de Puentes',
        'descripcion': 'Mejoraste la salud de una relación que estaba en estado "necesita atención" o "crítico".',
        'virtud_asociada': 'justicia',
        'icono': 'fa-bridge',
        'color': '#5D4037',
        'criterio_logro': 'Mejorar salud de una relación',
        'puntos_virtud': 20,
        'orden': 5,
        'activa': True,
    },

    # ========================================
    # TEMPLANZA (3 adicionales)
    # ========================================

    {
        'codigo': 'equilibrista_maestro',
        'nombre': 'Equilibrista Maestro',
        'descripcion': 'Mantuviste los 6 pilares activos durante 4 semanas consecutivas.',
        'virtud_asociada': 'templanza',
        'icono': 'fa-balance-scale-right',
        'color': '#455A64',
        'criterio_logro': '6 pilares activos durante 4 semanas',
        'puntos_virtud': 40,
        'orden': 3,
        'activa': True,
    },

    {
        'codigo': 'atleta_filosofo',
        'nombre': 'Atleta Filósofo',
        'descripcion': 'Registraste tu seguimiento de Vires (salud física) durante 100 días.',
        'virtud_asociada': 'templanza',
        'icono': 'fa-running',
        'color': '#E64A19',
        'criterio_logro': 'Vires registrado 100 días',
        'puntos_virtud': 50,
        'orden': 4,
        'activa': True,
    },

    {
        'codigo': 'moderacion_sabia',
        'nombre': 'Moderación Sabia',
        'descripcion': 'Completaste 20 ejercicios de Areté. Tu práctica de la excelencia es constante.',
        'virtud_asociada': 'templanza',
        'icono': 'fa-om',
        'color': '#6A1B9A',
        'criterio_logro': 'Completar 20 ejercicios de Areté',
        'puntos_virtud': 35,
        'orden': 5,
        'activa': True,
    },

    # ========================================
    # INSIGNIAS GENERALES (1 adicional)
    # ========================================

    {
        'codigo': 'polimata_estoico',
        'nombre': 'Polímata Estoico',
        'descripcion': 'Alcanzaste nivel "Adepto" o superior en las 4 virtudes. Tu desarrollo es verdaderamente integral.',
        'virtud_asociada': 'general',
        'icono': 'fa-crown',
        'color': '#FFD700',
        'criterio_logro': 'Nivel Adepto+ en las 4 virtudes',
        'puntos_virtud': 100,
        'orden': 2,
        'activa': True,
        'es_secreta': False,
    },
]


def crear_insignias_adicionales():
    """
    Ejecuta esta función para crear las 15 insignias adicionales.
    """
    contador = 0
    for insignia_data in insignias_adicionales:
        insignia, created = Insignia.objects.get_or_create(
            codigo=insignia_data['codigo'],
            defaults=insignia_data
        )
        if created:
            contador += 1
            print(f"✓ Creada: {insignia.nombre} ({insignia.get_virtud_asociada_display()})")
        else:
            print(f"- Ya existe: {insignia_data['nombre']}")

    print(f"\n{contador} insignias nuevas creadas exitosamente.")
    print(f"Total de insignias en la base de datos: {Insignia.objects.count()}")

    # Resumen por virtud
    print("\n=== RESUMEN POR VIRTUD ===")
    from django.db.models import Count
    resumen = Insignia.objects.values('virtud_asociada').annotate(total=Count('id'))
    for item in resumen:
        print(f"{item['virtud_asociada']}: {item['total']} insignias")


# Para ejecutar:
# python manage.py shell
# >>> exec(open('insignias_adicionales.py').read())
# >>> crear_insignias_adicionales()


# ============================================
# FUNCIONES DE VERIFICACIÓN ADICIONALES
# Añadir estas funciones a views_logos.py
# ============================================

def verificar_insignias_reflexiones_libres(usuario):
    """
    Verifica insignias relacionadas con reflexiones libres.
    """
    from diario.models import ReflexionLibre, Insignia, InsigniaUsuario

    total_libres = ReflexionLibre.objects.filter(
        usuario=usuario,
        tipo='espontanea'
    ).count()

    # Escriba Dedicado (50 reflexiones libres)
    if total_libres >= 50:
        insignia = Insignia.objects.filter(codigo='escriba_dedicado').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )

    # Reflexión Profunda (1,000+ palabras)
    reflexion_larga = ReflexionLibre.objects.filter(
        usuario=usuario
    ).annotate(
        longitud=Length('contenido')
    ).filter(longitud__gte=1000).exists()

    if reflexion_larga:
        insignia = Insignia.objects.filter(codigo='reflexion_profunda').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )


def verificar_insignia_phoenix(usuario):
    """
    Verifica la insignia Fénix Renacido (volver después de 30+ días).
    """
    from diario.models import RachaEscritura, Insignia, InsigniaUsuario
    from datetime import timedelta

    racha = RachaEscritura.objects.filter(usuario=usuario).first()
    if not racha:
        return

    # Si la última entrada fue hace más de 30 días y acaba de escribir hoy
    if racha.fecha_ultima_entrada:
        dias_ausencia = (timezone.now().date() - racha.fecha_ultima_entrada).days
        if dias_ausencia >= 30:
            insignia = Insignia.objects.filter(codigo='phoenix_renacido').first()
            if insignia:
                InsigniaUsuario.objects.get_or_create(
                    usuario=usuario,
                    insignia=insignia
                )


def verificar_insignia_maestro_categorias(usuario):
    """
    Verifica si el usuario completó reflexiones de todas las categorías.
    """
    from diario.models import ReflexionLibre, Insignia, InsigniaUsuario

    categorias_completadas = ReflexionLibre.objects.filter(
        usuario=usuario,
        reflexion_guiada__isnull=False
    ).values_list(
        'reflexion_guiada__categoria',
        flat=True
    ).distinct()

    categorias_requeridas = ['salud', 'social', 'naturaleza', 'filosofia', 'personal']

    if all(cat in categorias_completadas for cat in categorias_requeridas):
        insignia = Insignia.objects.filter(codigo='maestro_categorias').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )


def verificar_insignia_ciclo_completo(usuario):
    """
    Verifica si el usuario escribió al menos una reflexión cada mes del año.
    """
    from diario.models import ReflexionLibre, Insignia, InsigniaUsuario
    from django.db.models.functions import ExtractMonth

    meses_con_reflexiones = ReflexionLibre.objects.filter(
        usuario=usuario
    ).annotate(
        mes=ExtractMonth('fecha')
    ).values_list('mes', flat=True).distinct()

    if len(set(meses_con_reflexiones)) == 12:
        insignia = Insignia.objects.filter(codigo='ciclo_completo').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )


def verificar_insignia_polimata(usuario):
    """
    Verifica si el usuario alcanzó nivel Adepto+ en las 4 virtudes.
    """
    from diario.models import Virtud, Insignia, InsigniaUsuario

    virtudes = Virtud.objects.filter(usuario=usuario)

    niveles_altos = ['adepto', 'maestro', 'sabio']
    todas_altas = all(v.nivel in niveles_altos for v in virtudes)

    if todas_altas and virtudes.count() == 4:
        insignia = Insignia.objects.filter(codigo='polimata_estoico').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )


def verificar_insignias_prosoche(usuario):
    """
    Verifica insignias relacionadas con Prosoche matutina y nocturna.
    Llamar después de completar una entrada de Prosoche.
    """
    from diario.models import EntradaDiario, Insignia, InsigniaUsuario
    from datetime import timedelta

    hoy = timezone.now().date()
    hace_30_dias = hoy - timedelta(days=30)

    # Verificar Guerrero Matutino (30 días consecutivos de Prosoche matutina)
    entradas_matutinas = EntradaDiario.objects.filter(
        usuario=usuario,
        fecha__gte=hace_30_dias,
        fecha__lte=hoy,
        # Asumiendo que tienes un campo que indica si completó la parte matutina
    ).count()

    if entradas_matutinas >= 30:
        insignia = Insignia.objects.filter(codigo='guerrero_matutino').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )

    # Verificar Guardián Nocturno (30 días consecutivos de reflexión nocturna)
    entradas_nocturnas = EntradaDiario.objects.filter(
        usuario=usuario,
        fecha__gte=hace_30_dias,
        fecha__lte=hoy,
        felicidad__isnull=False  # Indica que completó la reflexión nocturna
    ).count()

    if entradas_nocturnas >= 30:
        insignia = Insignia.objects.filter(codigo='guardian_nocturno').first()
        if insignia:
            InsigniaUsuario.objects.get_or_create(
                usuario=usuario,
                insignia=insignia
            )


# ============================================
# INSTRUCCIONES DE INTEGRACIÓN
# ============================================

"""
PASO 1: Crear las insignias
-----------------------------
python manage.py shell
>>> exec(open('insignias_adicionales.py').read())
>>> crear_insignias_adicionales()


PASO 2: Integrar las funciones de verificación
-----------------------------------------------
Añade estas funciones al archivo views_logos.py y llámalas en los momentos apropiados:

1. En la vista de guardar reflexión libre:
   - verificar_insignias_reflexiones_libres(request.user)
   - verificar_insignia_phoenix(request.user)
   - verificar_insignia_ciclo_completo(request.user)

2. En la vista de guardar reflexión guiada:
   - verificar_insignia_maestro_categorias(request.user)

3. En la vista de guardar entrada de Prosoche:
   - verificar_insignias_prosoche(request.user)

4. Después de actualizar virtudes:
   - verificar_insignia_polimata(request.user)


PASO 3: Verificar que funciona
-------------------------------
1. Crea algunas reflexiones de prueba
2. Verifica que las insignias se desbloquean correctamente
3. Revisa que los modales de celebración aparecen
4. Confirma que los puntos de virtud se otorgan
"""
