# SISTEMA AVANZADO DE PRUEBAS LEGENDARIAS ESPECÍFICAS
# Expansión del Códice de las Leyendas con desafíos épicos por arquetipos

"""
OBJETIVO: Crear pruebas legendarias específicas y temáticas para cada arquetipo,
con diferentes tipos de desafíos que reflejen las habilidades únicas de cada personaje.

TIPOS DE PRUEBAS:
1. Pruebas de Fuerza - Basadas en peso máximo
2. Pruebas de Resistencia - Basadas en volumen y constancia  
3. Pruebas de Técnica - Basadas en variedad de ejercicios
4. Pruebas de Velocidad - Basadas en tiempo de entrenamiento
5. Pruebas Secretas - Desafíos ocultos especiales
6. Pruebas de Maestría - Combinaciones complejas
"""

from logros.models import Arquetipo, PruebaLegendaria


# =============================================================================
# SCRIPT PARA CREAR PRUEBAS LEGENDARIAS AVANZADAS
# =============================================================================

def crear_pruebas_legendarias_avanzadas():
    """
    Crea un sistema completo de pruebas legendarias específicas
    para cada arquetipo del Códice de las Leyendas.
    """

    print("🎮 Iniciando creación de Pruebas Legendarias Avanzadas...")

    # =============================================================================
    # ARQUETIPOS NIVEL 1-10: LOS PRINCIPIANTES
    # =============================================================================

    # SAITAMA - EL ASPIRANTE CALVO (Nivel 1)
    saitama = Arquetipo.objects.filter(titulo_arquetipo__icontains="Saitama").first()
    if saitama:
        pruebas_saitama = [
            {
                'nombre': 'El Primer Puñetazo',
                'descripcion': 'Completa tu primer entrenamiento en el Códice',
                'tipo': 'entrenos_completados',
                'meta': 1,
                'puntos_recompensa': 50,
                'es_secreta': False
            },
            {
                'nombre': '100 Flexiones',
                'descripcion': 'Realiza 100 flexiones acumuladas (como Saitama)',
                'tipo': 'ejercicio_especifico',
                'meta': 100,
                'puntos_recompensa': 100,
                'es_secreta': False
            },
            {
                'nombre': 'La Rutina Diaria',
                'descripcion': 'Entrena 3 días consecutivos sin fallar',
                'tipo': 'racha_dias',
                'meta': 3,
                'puntos_recompensa': 75,
                'es_secreta': False
            },
            {
                'nombre': 'Limitador Roto (Secreto)',
                'descripcion': 'Supera tu récord personal en cualquier ejercicio',
                'tipo': 'record_personal_superado',
                'meta': 1,
                'puntos_recompensa': 200,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(saitama, pruebas_saitama)

    # ROCK LEE - EL GENIO DEL ESFUERZO (Nivel 2)
    rock_lee = Arquetipo.objects.filter(titulo_arquetipo__icontains="Rock Lee").first()
    if rock_lee:
        pruebas_rock_lee = [
            {
                'nombre': 'Las Puertas del Esfuerzo',
                'descripcion': 'Mantén una racha de 7 días consecutivos',
                'tipo': 'racha_dias',
                'meta': 7,
                'puntos_recompensa': 150,
                'es_secreta': False
            },
            {
                'nombre': 'La Llama de la Juventud',
                'descripcion': 'Completa 10 entrenamientos totales',
                'tipo': 'entrenos_completados',
                'meta': 10,
                'puntos_recompensa': 200,
                'es_secreta': False
            },
            {
                'nombre': 'Entrenamiento de Peso',
                'descripcion': 'Alcanza 40kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 40,
                'puntos_recompensa': 250,
                'es_secreta': False
            },
            {
                'nombre': 'Juventud Eterna (Secreto)',
                'descripcion': 'Entrena más de 60 minutos en una sesión',
                'tipo': 'duracion_sesion',
                'meta': 60,
                'puntos_recompensa': 300,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(rock_lee, pruebas_rock_lee)

    # KRILLIN - EL GUERRERO HUMANO (Nivel 3)
    krillin = Arquetipo.objects.filter(titulo_arquetipo__icontains="Krillin").first()
    if krillin:
        pruebas_krillin = [
            {
                'nombre': 'El Guerrero Humano',
                'descripcion': 'Alcanza 50kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 50,
                'puntos_recompensa': 300,
                'es_secreta': False
            },
            {
                'nombre': 'Destructo Disc',
                'descripcion': 'Domina 3 ejercicios diferentes',
                'tipo': 'ejercicios_dominados',
                'meta': 3,
                'puntos_recompensa': 200,
                'es_secreta': False
            },
            {
                'nombre': 'Entrenamiento Z',
                'descripcion': 'Levanta 5,000kg de volumen total acumulado',
                'tipo': 'volumen_total',
                'meta': 5000,
                'puntos_recompensa': 250,
                'es_secreta': False
            },
            {
                'nombre': 'Poder Oculto (Secreto)',
                'descripcion': 'Completa 15 entrenamientos en 30 días',
                'tipo': 'entrenos_en_periodo',
                'meta': 15,
                'puntos_recompensa': 400,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(krillin, pruebas_krillin)

    # =============================================================================
    # ARQUETIPOS NIVEL 11-20: LOS GUERREROS
    # =============================================================================

    # ICHIGO - EL SHINIGAMI SUSTITUTO (Nivel 17)
    ichigo = Arquetipo.objects.filter(titulo_arquetipo__icontains="Ichigo").first()
    if ichigo:
        pruebas_ichigo = [
            {
                'nombre': 'Zangetsu Despierta',
                'descripcion': 'Alcanza 75kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 75,
                'puntos_recompensa': 500,
                'es_secreta': False
            },
            {
                'nombre': 'Getsuga Tensho',
                'descripcion': 'Levanta 15,000kg de volumen total',
                'tipo': 'volumen_total',
                'meta': 15000,
                'puntos_recompensa': 400,
                'es_secreta': False
            },
            {
                'nombre': 'Entrenamiento Shinigami',
                'descripcion': 'Mantén 14 días de racha consecutiva',
                'tipo': 'racha_dias',
                'meta': 14,
                'puntos_recompensa': 600,
                'es_secreta': False
            },
            {
                'nombre': 'Bankai Final (Secreto)',
                'descripcion': 'Supera 3 récords personales en una semana',
                'tipo': 'records_en_semana',
                'meta': 3,
                'puntos_recompensa': 800,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(ichigo, pruebas_ichigo)

    # =============================================================================
    # ARQUETIPOS NIVEL 31-40: LOS LEGENDARIOS
    # =============================================================================

    # ALL MIGHT - EL SÍMBOLO DE LA PAZ (Nivel 31)
    all_might = Arquetipo.objects.filter(titulo_arquetipo__icontains="All Might").first()
    if all_might:
        pruebas_all_might = [
            {
                'nombre': 'One For All',
                'descripcion': 'Alcanza 100kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 100,
                'puntos_recompensa': 1000,
                'es_secreta': False
            },
            {
                'nombre': 'Plus Ultra!',
                'descripcion': 'Levanta 25,000kg de volumen total',
                'tipo': 'volumen_total',
                'meta': 25000,
                'puntos_recompensa': 800,
                'es_secreta': False
            },
            {
                'nombre': 'Símbolo de la Paz',
                'descripcion': 'Mantén 21 días de racha consecutiva',
                'tipo': 'racha_dias',
                'meta': 21,
                'puntos_recompensa': 1200,
                'es_secreta': False
            },
            {
                'nombre': 'Detroit Smash (Secreto)',
                'descripcion': 'Levanta más de 2,000kg en una sola sesión',
                'tipo': 'volumen_sesion',
                'meta': 2000,
                'puntos_recompensa': 1500,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(all_might, pruebas_all_might)

    # =============================================================================
    # ARQUETIPOS NIVEL 41-50: LOS SAIYANS
    # =============================================================================

    # GOKU SSJ - EL SUPER SAIYAN LEGENDARIO (Nivel 45)
    goku_ssj = Arquetipo.objects.filter(titulo_arquetipo__icontains="Goku SSJ").first()
    if goku_ssj:
        pruebas_goku_ssj = [
            {
                'nombre': 'La Transformación Dorada',
                'descripcion': 'Alcanza 150kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 150,
                'puntos_recompensa': 2000,
                'es_secreta': False
            },
            {
                'nombre': 'Kamehameha Legendario',
                'descripcion': 'Levanta 50,000kg de volumen total',
                'tipo': 'volumen_total',
                'meta': 50000,
                'puntos_recompensa': 1500,
                'es_secreta': False
            },
            {
                'nombre': 'Entrenamiento Saiyan',
                'descripcion': 'Completa 50 entrenamientos totales',
                'tipo': 'entrenos_completados',
                'meta': 50,
                'puntos_recompensa': 1800,
                'es_secreta': False
            },
            {
                'nombre': 'La Ira del Saiyan (Secreto)',
                'descripcion': 'Levanta más de 3,000kg en una sola sesión',
                'tipo': 'volumen_sesion',
                'meta': 3000,
                'puntos_recompensa': 2500,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(goku_ssj, pruebas_goku_ssj)

    # =============================================================================
    # ARQUETIPOS NIVEL 61-70: LOS DIVINOS
    # =============================================================================

    # BEERUS - EL DIOS DE LA DESTRUCCIÓN (Nivel 65)
    beerus = Arquetipo.objects.filter(titulo_arquetipo__icontains="Beerus").first()
    if beerus:
        pruebas_beerus = [
            {
                'nombre': 'Hakai',
                'descripcion': 'Alcanza 200kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 200,
                'puntos_recompensa': 5000,
                'es_secreta': False
            },
            {
                'nombre': 'El Despertar del Destructor',
                'descripcion': 'Levanta 100,000kg de volumen total',
                'tipo': 'volumen_total',
                'meta': 100000,
                'puntos_recompensa': 4000,
                'es_secreta': False
            },
            {
                'nombre': 'Poder Divino',
                'descripcion': 'Mantén 30 días de racha consecutiva',
                'tipo': 'racha_dias',
                'meta': 30,
                'puntos_recompensa': 6000,
                'es_secreta': False
            },
            {
                'nombre': 'Destrucción Universal (Secreto)',
                'descripcion': 'Supera 10 récords personales',
                'tipo': 'records_totales',
                'meta': 10,
                'puntos_recompensa': 8000,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(beerus, pruebas_beerus)

    # =============================================================================
    # ARQUETIPOS NIVEL 91-100: LOS ABSOLUTOS
    # =============================================================================

    # THE ONE ABOVE ALL - EL UNO SOBRE TODO (Nivel 100)
    one_above_all = Arquetipo.objects.filter(titulo_arquetipo__icontains="The One Above All").first()
    if one_above_all:
        pruebas_one_above_all = [
            {
                'nombre': 'Omnipotencia Absoluta',
                'descripcion': 'Alcanza 500kg en Press de Banca',
                'tipo': 'rm_banca',
                'meta': 500,
                'puntos_recompensa': 50000,
                'es_secreta': False
            },
            {
                'nombre': 'El Uno Sobre Todo',
                'descripcion': 'Mantén el #1 del ranking por 30 días',
                'tipo': 'ranking_top',
                'meta': 30,
                'puntos_recompensa': 100000,
                'es_secreta': False
            },
            {
                'nombre': 'Creación Universal',
                'descripcion': 'Levanta 1,000,000kg de volumen total',
                'tipo': 'volumen_total',
                'meta': 1000000,
                'puntos_recompensa': 75000,
                'es_secreta': False
            },
            {
                'nombre': 'Trascendencia Absoluta (Secreto)',
                'descripcion': 'Completa 365 entrenamientos (un año completo)',
                'tipo': 'entrenos_completados',
                'meta': 365,
                'puntos_recompensa': 200000,
                'es_secreta': True
            }
        ]
        crear_pruebas_para_arquetipo(one_above_all, pruebas_one_above_all)

    print("✅ Sistema de Pruebas Legendarias Avanzadas creado exitosamente!")
    print("🎮 Total de arquetipos con pruebas específicas: 8+")
    print("⚔️ Tipos de pruebas implementadas: 12 diferentes")
    print("🏆 Pruebas secretas incluidas para máxima motivación")


def crear_pruebas_para_arquetipo(arquetipo, lista_pruebas):
    """
    Crea las pruebas legendarias para un arquetipo específico.
    """
    print(f"⚔️ Creando pruebas para {arquetipo.titulo}...")

    for prueba_data in lista_pruebas:
        prueba, created = PruebaLegendaria.objects.get_or_create(
            arquetipo=arquetipo,
            nombre=prueba_data['nombre'],
            defaults={
                'descripcion': prueba_data['descripcion'],
                'tipo': prueba_data['tipo'],
                'meta': prueba_data['meta'],
                'puntos_recompensa': prueba_data['puntos_recompensa'],
                'es_secreta': prueba_data['es_secreta']
            }
        )

        if created:
            print(f"  ✅ {prueba_data['nombre']} - {prueba_data['puntos_recompensa']} pts")
        else:
            print(f"  ⚠️ {prueba_data['nombre']} - Ya existe")


# =============================================================================
# TIPOS DE PRUEBAS IMPLEMENTADAS
# =============================================================================

TIPOS_PRUEBAS_EXPLICACION = """
TIPOS DE PRUEBAS LEGENDARIAS:

1. 'entrenos_completados' - Número total de entrenamientos
2. 'racha_dias' - Días consecutivos entrenando
3. 'rm_banca' - Peso máximo en Press de Banca
4. 'volumen_total' - Kilogramos totales levantados
5. 'volumen_sesion' - Kilogramos en una sola sesión
6. 'ejercicios_dominados' - Variedad de ejercicios realizados
7. 'duracion_sesion' - Minutos de entrenamiento en una sesión
8. 'record_personal_superado' - Récords personales superados
9. 'records_en_semana' - Récords superados en 7 días
10. 'records_totales' - Total de récords personales
11. 'entrenos_en_periodo' - Entrenamientos en X días
12. 'ranking_top' - Días manteniendo posición #1

CARACTERÍSTICAS:
- Pruebas normales: Visibles desde el inicio
- Pruebas secretas: Se revelan al cumplir condiciones
- Recompensas escaladas: Más puntos para niveles altos
- Temáticas específicas: Reflejan habilidades del personaje
"""

# =============================================================================
# EJECUTAR SCRIPT
# =============================================================================

if __name__ == "__main__":
    print("🎮 SISTEMA DE PRUEBAS LEGENDARIAS AVANZADAS")
    print("=" * 50)
    print()

    # Ejecutar creación de pruebas
    crear_pruebas_legendarias_avanzadas()

    print()
    print("🎯 PRÓXIMOS PASOS:")
    print("1. Ejecutar este script: python manage.py shell < pruebas_legendarias_avanzadas.py")
    print("2. Verificar que las pruebas se crearon correctamente")
    print("3. Probar el sistema con entrenamientos reales")
    print("4. Ajustar metas y recompensas según feedback")
    print()
    print("⚔️ ¡El Códice de las Leyendas ahora tiene desafíos épicos específicos!")
