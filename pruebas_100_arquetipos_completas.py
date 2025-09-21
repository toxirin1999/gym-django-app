# PRUEBAS LEGENDARIAS PARA LOS 100 ARQUETIPOS COMPLETOS
# Script épico para crear pruebas específicas para cada uno de los 100 arquetipos
# python manage.py shell < pruebas_100_arquetipos_completas.py

from logros.models import Arquetipo, PruebaLegendaria

print("🧹 Limpiando Pruebas Legendarias existentes...")
PruebaLegendaria.objects.all().delete()
print("✅ Pruebas limpiadas.")

print("⚔️ Creando Pruebas Legendarias para los 100 Arquetipos...")

# =============================================================================
# FUNCIÓN PARA CREAR PRUEBAS AUTOMÁTICAMENTE
# =============================================================================

def crear_pruebas_para_arquetipo(nivel, pruebas_data):
    """
    Crea pruebas para un arquetipo específico
    """
    try:
        arquetipo = Arquetipo.objects.get(nivel=nivel)
        print(f"\n⚔️ Creando pruebas para Nivel {nivel}: {arquetipo.titulo_arquetipo}...")
        
        pruebas_creadas = 0
        for prueba_data in pruebas_data:
            try:
                prueba = PruebaLegendaria.objects.create(arquetipo=arquetipo, **prueba_data)
                print(f"   ✅ {prueba.nombre}")
                pruebas_creadas += 1
            except Exception as e:
                print(f"   ❌ ERROR al crear '{prueba_data['nombre']}': {e}")
        
        return pruebas_creadas
    except Arquetipo.DoesNotExist:
        print(f"❌ Arquetipo nivel {nivel} no encontrado")
        return 0

# =============================================================================
# NIVELES 1-10: LOS ASPIRANTES - Fundamentos y Constancia
# =============================================================================

print("\n🥊 === LOS ASPIRANTES (Niveles 1-10) ===")

# Nivel 1: Saitama (inicio)
pruebas_nivel_1 = [
    {'nombre': 'El Primer Puñetazo', 'descripcion': 'Completa tu primer entrenamiento. Todo héroe comienza aquí.',
     'clave_calculo': 'primer_entrenamiento', 'meta_valor': 1, 'puntos_recompensa': 50, 'es_secreta': False},
    {'nombre': '100 Flexiones', 'descripcion': 'Realiza 100 flexiones acumuladas en total.',
     'clave_calculo': 'flexiones_totales_meta_100', 'meta_valor': 100, 'puntos_recompensa': 100, 'es_secreta': False},
    {'nombre': 'La Rutina Diaria', 'descripcion': 'Entrena 3 días consecutivos.',
     'clave_calculo': 'racha_dias_meta_3', 'meta_valor': 3, 'puntos_recompensa': 150, 'es_secreta': False},
    {'nombre': 'Limitador Roto', 'descripcion': 'Supera tu primer récord personal.',
     'clave_calculo': 'record_personal_superado_1', 'meta_valor': 1, 'puntos_recompensa': 200, 'es_secreta': True},
]

# Nivel 2: Rock Lee
pruebas_nivel_2 = [
    {'nombre': 'Las Puertas del Esfuerzo', 'descripcion': 'Mantén una racha de 7 días entrenando.',
     'clave_calculo': 'racha_dias_meta_7', 'meta_valor': 7, 'puntos_recompensa': 200, 'es_secreta': False},
    {'nombre': 'La Llama de la Juventud', 'descripcion': 'Completa 15 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_15', 'meta_valor': 15, 'puntos_recompensa': 250, 'es_secreta': False},
    {'nombre': 'Entrenamiento de Pesas', 'descripcion': 'Levanta un total de 5,000 kg acumulados.',
     'clave_calculo': 'volumen_total_meta_5000kg', 'meta_valor': 5000, 'puntos_recompensa': 300, 'es_secreta': False},
]

# Nivel 3: Krillin
pruebas_nivel_3 = [
    {'nombre': 'El Guerrero Humano', 'descripcion': 'Alcanza 40kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_40kg', 'meta_valor': 40, 'puntos_recompensa': 300, 'es_secreta': False},
    {'nombre': 'Destructo Disc', 'descripcion': 'Completa 20 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_20', 'meta_valor': 20, 'puntos_recompensa': 350, 'es_secreta': False},
    {'nombre': 'Corazón Valiente', 'descripcion': 'Mantén una racha de 10 días.',
     'clave_calculo': 'racha_dias_meta_10', 'meta_valor': 10, 'puntos_recompensa': 400, 'es_secreta': False},
]

# Nivel 4: Yamcha
pruebas_nivel_4 = [
    {'nombre': 'Puño del Lobo', 'descripcion': 'Alcanza 45kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_45kg', 'meta_valor': 45, 'puntos_recompensa': 350, 'es_secreta': False},
    {'nombre': 'Redención del Guerrero', 'descripcion': 'Levanta 8,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_8000kg', 'meta_valor': 8000, 'puntos_recompensa': 400, 'es_secreta': False},
    {'nombre': 'Espíritu Indomable', 'descripcion': 'Completa 25 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_25', 'meta_valor': 25, 'puntos_recompensa': 450, 'es_secreta': False},
]

# Nivel 5: Tien Shinhan
pruebas_nivel_5 = [
    {'nombre': 'El Tercer Ojo', 'descripcion': 'Domina 3 ejercicios diferentes.',
     'clave_calculo': 'ejercicios_dominados_meta_3', 'meta_valor': 3, 'puntos_recompensa': 400, 'es_secreta': False},
    {'nombre': 'Kikoho', 'descripcion': 'Alcanza 50kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_50kg', 'meta_valor': 50, 'puntos_recompensa': 500, 'es_secreta': False},
    {'nombre': 'Técnica Mortal', 'descripcion': 'Levanta 12,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_12000kg', 'meta_valor': 12000, 'puntos_recompensa': 550, 'es_secreta': False},
]

# Nivel 6: Roronoa Zoro
pruebas_nivel_6 = [
    {'nombre': 'Las Tres Espadas', 'descripcion': 'Domina 3 ejercicios diferentes.',
     'clave_calculo': 'ejercicios_dominados_meta_3', 'meta_valor': 3, 'puntos_recompensa': 450, 'es_secreta': False},
    {'nombre': 'El Camino del Espadachín', 'descripcion': 'Alcanza 55kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_55kg', 'meta_valor': 55, 'puntos_recompensa': 550, 'es_secreta': False},
    {'nombre': 'Perdido pero Determinado', 'descripcion': 'Mantén una racha de 14 días.',
     'clave_calculo': 'racha_dias_meta_14', 'meta_valor': 14, 'puntos_recompensa': 600, 'es_secreta': False},
]

# Nivel 7: Sanji
pruebas_nivel_7 = [
    {'nombre': 'Pierna del Diablo', 'descripcion': 'Alcanza 80kg en Sentadilla.',
     'clave_calculo': 'rm_sentadilla_meta_80kg', 'meta_valor': 80, 'puntos_recompensa': 500, 'es_secreta': False},
    {'nombre': 'Cocinero Guerrero', 'descripcion': 'Completa 35 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_35', 'meta_valor': 35, 'puntos_recompensa': 600, 'es_secreta': False},
    {'nombre': 'Caballero de los Mares', 'descripcion': 'Levanta 15,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_15000kg', 'meta_valor': 15000, 'puntos_recompensa': 650, 'es_secreta': False},
]

# Nivel 8: Kenshiro
pruebas_nivel_8 = [
    {'nombre': 'Hokuto Shinken', 'descripcion': 'Alcanza 60kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_60kg', 'meta_valor': 60, 'puntos_recompensa': 600, 'es_secreta': False},
    {'nombre': 'Ya Estás Muerto', 'descripcion': 'Supera 2 récords personales.',
     'clave_calculo': 'records_totales_meta_2', 'meta_valor': 2, 'puntos_recompensa': 700, 'es_secreta': False},
    {'nombre': 'Los Puntos Vitales', 'descripcion': 'Mantén una racha de 15 días.',
     'clave_calculo': 'racha_dias_meta_15', 'meta_valor': 15, 'puntos_recompensa': 750, 'es_secreta': False},
]

# Nivel 9: Edward Elric
pruebas_nivel_9 = [
    {'nombre': 'Alquimia del Acero', 'descripcion': 'Alcanza 65kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_65kg', 'meta_valor': 65, 'puntos_recompensa': 650, 'es_secreta': False},
    {'nombre': 'Transmutación Humana', 'descripcion': 'Completa 40 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_40', 'meta_valor': 40, 'puntos_recompensa': 750, 'es_secreta': False},
    {'nombre': 'El Alquimista de Acero', 'descripcion': 'Levanta 20,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_20000kg', 'meta_valor': 20000, 'puntos_recompensa': 800, 'es_secreta': False},
]

# Nivel 10: Alphonse Elric
pruebas_nivel_10 = [
    {'nombre': 'Armadura Viviente', 'descripcion': 'Alcanza 70kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_70kg', 'meta_valor': 70, 'puntos_recompensa': 700, 'es_secreta': False},
    {'nombre': 'Hermanos de Acero', 'descripcion': 'Mantén una racha de 20 días.',
     'clave_calculo': 'racha_dias_meta_20', 'meta_valor': 20, 'puntos_recompensa': 850, 'es_secreta': False},
    {'nombre': 'Alma Inquebrantable', 'descripcion': 'Completa 45 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_45', 'meta_valor': 45, 'puntos_recompensa': 900, 'es_secreta': False},
]

# =============================================================================
# NIVELES 11-20: LOS GUERREROS EMERGENTES
# =============================================================================

print("\n⚔️ === LOS GUERREROS EMERGENTES (Niveles 11-20) ===")

# Nivel 11: Inuyasha
pruebas_nivel_11 = [
    {'nombre': 'Colmillo de Acero', 'descripcion': 'Alcanza 75kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_75kg', 'meta_valor': 75, 'puntos_recompensa': 800, 'es_secreta': False},
    {'nombre': 'Viento Cortante', 'descripcion': 'Levanta 25,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_25000kg', 'meta_valor': 25000, 'puntos_recompensa': 900, 'es_secreta': False},
    {'nombre': 'Medio Demonio', 'descripcion': 'Supera 3 récords personales.',
     'clave_calculo': 'records_totales_meta_3', 'meta_valor': 3, 'puntos_recompensa': 1000, 'es_secreta': False},
]

# Nivel 12: Sesshomaru
pruebas_nivel_12 = [
    {'nombre': 'Señor de las Tierras del Oeste', 'descripcion': 'Alcanza 80kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_80kg', 'meta_valor': 80, 'puntos_recompensa': 850, 'es_secreta': False},
    {'nombre': 'Látigo de Luz', 'descripcion': 'Mantén una racha de 25 días.',
     'clave_calculo': 'racha_dias_meta_25', 'meta_valor': 25, 'puntos_recompensa': 1000, 'es_secreta': False},
    {'nombre': 'Perfección Demoniaca', 'descripcion': 'Completa 50 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_50', 'meta_valor': 50, 'puntos_recompensa': 1100, 'es_secreta': False},
]

# Nivel 13: Yusuke Urameshi
pruebas_nivel_13 = [
    {'nombre': 'Pistola Espiritual', 'descripcion': 'Alcanza 85kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_85kg', 'meta_valor': 85, 'puntos_recompensa': 900, 'es_secreta': False},
    {'nombre': 'Detective Espiritual', 'descripcion': 'Levanta 30,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_30000kg', 'meta_valor': 30000, 'puntos_recompensa': 1000, 'es_secreta': False},
    {'nombre': 'Mazoku Awakening', 'descripcion': 'Supera 4 récords personales.',
     'clave_calculo': 'records_totales_meta_4', 'meta_valor': 4, 'puntos_recompensa': 1200, 'es_secreta': False},
]

# Nivel 14: Hiei
pruebas_nivel_14 = [
    {'nombre': 'Espada del Fuego Infernal', 'descripcion': 'Alcanza 90kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_90kg', 'meta_valor': 90, 'puntos_recompensa': 950, 'es_secreta': False},
    {'nombre': 'Dragón de las Llamas Oscuras', 'descripcion': 'Mantén una racha de 30 días.',
     'clave_calculo': 'racha_dias_meta_30', 'meta_valor': 30, 'puntos_recompensa': 1200, 'es_secreta': False},
    {'nombre': 'Velocidad Demoniaca', 'descripcion': 'Completa 60 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_60', 'meta_valor': 60, 'puntos_recompensa': 1300, 'es_secreta': False},
]

# Nivel 15: Kurama
pruebas_nivel_15 = [
    {'nombre': 'Rosa Látigo', 'descripcion': 'Alcanza 95kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_95kg', 'meta_valor': 95, 'puntos_recompensa': 1000, 'es_secreta': False},
    {'nombre': 'Zorro de Nueve Colas', 'descripcion': 'Levanta 35,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_35000kg', 'meta_valor': 35000, 'puntos_recompensa': 1200, 'es_secreta': False},
    {'nombre': 'Sabiduría Milenaria', 'descripcion': 'Domina 5 ejercicios diferentes.',
     'clave_calculo': 'ejercicios_dominados_meta_5', 'meta_valor': 5, 'puntos_recompensa': 1400, 'es_secreta': False},
]

# Nivel 16: Ichigo Kurosaki
pruebas_nivel_16 = [
    {'nombre': 'Zangetsu Despierta', 'descripcion': 'Alcanza 100kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_100kg', 'meta_valor': 100, 'puntos_recompensa': 1200, 'es_secreta': False},
    {'nombre': 'Getsuga Tensho', 'descripcion': 'Supera 5 récords personales.',
     'clave_calculo': 'records_totales_meta_5', 'meta_valor': 5, 'puntos_recompensa': 1500, 'es_secreta': False},
    {'nombre': 'Shinigami Sustituto', 'descripcion': 'Completa 70 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_70', 'meta_valor': 70, 'puntos_recompensa': 1600, 'es_secreta': False},
]

# Nivel 17: Rukia Kuchiki
pruebas_nivel_17 = [
    {'nombre': 'Sode no Shirayuki', 'descripcion': 'Alcanza 105kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_105kg', 'meta_valor': 105, 'puntos_recompensa': 1250, 'es_secreta': False},
    {'nombre': 'Danza de la Luna Blanca', 'descripcion': 'Mantén una racha de 35 días.',
     'clave_calculo': 'racha_dias_meta_35', 'meta_valor': 35, 'puntos_recompensa': 1500, 'es_secreta': False},
    {'nombre': 'Nobleza Shinigami', 'descripcion': 'Levanta 40,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_40000kg', 'meta_valor': 40000, 'puntos_recompensa': 1700, 'es_secreta': False},
]

# Nivel 18: Byakuya Kuchiki
pruebas_nivel_18 = [
    {'nombre': 'Senbonzakura Kageyoshi', 'descripcion': 'Alcanza 110kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_110kg', 'meta_valor': 110, 'puntos_recompensa': 1300, 'es_secreta': False},
    {'nombre': 'Capitán del Escuadrón 6', 'descripcion': 'Completa 80 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_80', 'meta_valor': 80, 'puntos_recompensa': 1700, 'es_secreta': False},
    {'nombre': 'Orgullo de la Nobleza', 'descripcion': 'Supera 6 récords personales.',
     'clave_calculo': 'records_totales_meta_6', 'meta_valor': 6, 'puntos_recompensa': 1800, 'es_secreta': False},
]

# Nivel 19: Jotaro Kujo
pruebas_nivel_19 = [
    {'nombre': 'Star Platinum', 'descripcion': 'Alcanza 115kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_115kg', 'meta_valor': 115, 'puntos_recompensa': 1400, 'es_secreta': False},
    {'nombre': 'Ora Ora Ora!', 'descripcion': 'Levanta 45,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_45000kg', 'meta_valor': 45000, 'puntos_recompensa': 1800, 'es_secreta': False},
    {'nombre': 'Yare Yare Daze', 'descripcion': 'Mantén una racha de 40 días.',
     'clave_calculo': 'racha_dias_meta_40', 'meta_valor': 40, 'puntos_recompensa': 2000, 'es_secreta': True},
]

# Nivel 20: Dio Brando
pruebas_nivel_20 = [
    {'nombre': 'The World', 'descripcion': 'Alcanza 120kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_120kg', 'meta_valor': 120, 'puntos_recompensa': 1500, 'es_secreta': False},
    {'nombre': 'Muda Muda Muda!', 'descripcion': 'Completa 90 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_90', 'meta_valor': 90, 'puntos_recompensa': 1900, 'es_secreta': False},
    {'nombre': 'Vampiro Supremo', 'descripcion': 'Supera 7 récords personales.',
     'clave_calculo': 'records_totales_meta_7', 'meta_valor': 7, 'puntos_recompensa': 2100, 'es_secreta': False},
]

# =============================================================================
# NIVELES 21-30: LOS GUERREROS ÉLITE
# =============================================================================

print("\n🌟 === LOS GUERREROS ÉLITE (Niveles 21-30) ===")

# Nivel 21: Natsu Dragneel
pruebas_nivel_21 = [
    {'nombre': 'Rugido del Dragón de Fuego', 'descripcion': 'Alcanza 125kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_125kg', 'meta_valor': 125, 'puntos_recompensa': 1600, 'es_secreta': False},
    {'nombre': 'Modo Dragon Force', 'descripcion': 'Levanta 50,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_50000kg', 'meta_valor': 50000, 'puntos_recompensa': 2000, 'es_secreta': False},
    {'nombre': 'Llamas de la Emoción', 'descripcion': 'Mantén una racha de 45 días.',
     'clave_calculo': 'racha_dias_meta_45', 'meta_valor': 45, 'puntos_recompensa': 2200, 'es_secreta': False},
]

# Nivel 22: Erza Scarlet
pruebas_nivel_22 = [
    {'nombre': 'Reina de las Hadas', 'descripcion': 'Alcanza 130kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_130kg', 'meta_valor': 130, 'puntos_recompensa': 1700, 'es_secreta': False},
    {'nombre': 'Armadura del Cielo', 'descripcion': 'Completa 100 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_100', 'meta_valor': 100, 'puntos_recompensa': 2100, 'es_secreta': False},
    {'nombre': 'Disciplina Férrea', 'descripcion': 'Supera 8 récords personales.',
     'clave_calculo': 'records_totales_meta_8', 'meta_valor': 8, 'puntos_recompensa': 2300, 'es_secreta': False},
]

# Nivel 23: Gray Fullbuster
pruebas_nivel_23 = [
    {'nombre': 'Ice Make', 'descripcion': 'Alcanza 135kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_135kg', 'meta_valor': 135, 'puntos_recompensa': 1800, 'es_secreta': False},
    {'nombre': 'Demonio Slayer', 'descripcion': 'Levanta 55,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_55000kg', 'meta_valor': 55000, 'puntos_recompensa': 2200, 'es_secreta': False},
    {'nombre': 'Corazón de Hielo', 'descripcion': 'Mantén una racha de 50 días.',
     'clave_calculo': 'racha_dias_meta_50', 'meta_valor': 50, 'puntos_recompensa': 2500, 'es_secreta': False},
]

# Nivel 24: Laxus Dreyar
pruebas_nivel_24 = [
    {'nombre': 'Rugido del Dragón del Rayo', 'descripcion': 'Alcanza 140kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_140kg', 'meta_valor': 140, 'puntos_recompensa': 1900, 'es_secreta': False},
    {'nombre': 'Modo Dragón del Rayo', 'descripcion': 'Completa 110 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_110', 'meta_valor': 110, 'puntos_recompensa': 2300, 'es_secreta': False},
    {'nombre': 'Orgullo de Fairy Tail', 'descripcion': 'Supera 9 récords personales.',
     'clave_calculo': 'records_totales_meta_9', 'meta_valor': 9, 'puntos_recompensa': 2600, 'es_secreta': False},
]

# Nivel 25: Gaara
pruebas_nivel_25 = [
    {'nombre': 'Defensa Absoluta', 'descripcion': 'Alcanza 145kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_145kg', 'meta_valor': 145, 'puntos_recompensa': 2000, 'es_secreta': False},
    {'nombre': 'Funeral de Arena', 'descripcion': 'Levanta 60,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_60000kg', 'meta_valor': 60000, 'puntos_recompensa': 2400, 'es_secreta': False},
    {'nombre': 'Kazekage', 'descripcion': 'Mantén una racha de 55 días.',
     'clave_calculo': 'racha_dias_meta_55', 'meta_valor': 55, 'puntos_recompensa': 2700, 'es_secreta': False},
]

# Nivel 26: Kakashi Hatake
pruebas_nivel_26 = [
    {'nombre': 'Sharingan Copy', 'descripcion': 'Domina 7 ejercicios diferentes.',
     'clave_calculo': 'ejercicios_dominados_meta_7', 'meta_valor': 7, 'puntos_recompensa': 2200, 'es_secreta': False},
    {'nombre': 'Chidori', 'descripcion': 'Alcanza 150kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_150kg', 'meta_valor': 150, 'puntos_recompensa': 2500, 'es_secreta': False},
    {'nombre': 'Ninja Copy', 'descripcion': 'Completa 120 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_120', 'meta_valor': 120, 'puntos_recompensa': 2800, 'es_secreta': False},
]

# Nivel 27: Might Guy
pruebas_nivel_27 = [
    {'nombre': 'Las Ocho Puertas', 'descripcion': 'Alcanza 155kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_155kg', 'meta_valor': 155, 'puntos_recompensa': 2300, 'es_secreta': False},
    {'nombre': 'Bestia Verde de Konoha', 'descripcion': 'Mantén una racha de 60 días.',
     'clave_calculo': 'racha_dias_meta_60', 'meta_valor': 60, 'puntos_recompensa': 2900, 'es_secreta': False},
    {'nombre': 'Puerta de la Muerte', 'descripcion': 'Levanta 70,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_70000kg', 'meta_valor': 70000, 'puntos_recompensa': 3200, 'es_secreta': True},
]

# Nivel 28: Jiraiya
pruebas_nivel_28 = [
    {'nombre': 'Modo Sabio', 'descripcion': 'Alcanza 160kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_160kg', 'meta_valor': 160, 'puntos_recompensa': 2400, 'es_secreta': False},
    {'nombre': 'Rasengan Gigante', 'descripcion': 'Supera 10 récords personales.',
     'clave_calculo': 'records_totales_meta_10', 'meta_valor': 10, 'puntos_recompensa': 3000, 'es_secreta': False},
    {'nombre': 'Sannin Legendario', 'descripcion': 'Completa 130 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_130', 'meta_valor': 130, 'puntos_recompensa': 3100, 'es_secreta': False},
]

# Nivel 29: Orochimaru
pruebas_nivel_29 = [
    {'nombre': 'Serpiente Inmortal', 'descripcion': 'Alcanza 165kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_165kg', 'meta_valor': 165, 'puntos_recompensa': 2500, 'es_secreta': False},
    {'nombre': 'Técnicas Prohibidas', 'descripcion': 'Levanta 75,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_75000kg', 'meta_valor': 75000, 'puntos_recompensa': 3200, 'es_secreta': False},
    {'nombre': 'Búsqueda de la Inmortalidad', 'descripcion': 'Mantén una racha de 65 días.',
     'clave_calculo': 'racha_dias_meta_65', 'meta_valor': 65, 'puntos_recompensa': 3400, 'es_secreta': False},
]

# Nivel 30: Tsunade
pruebas_nivel_30 = [
    {'nombre': 'Fuerza de los Cien Sellos', 'descripcion': 'Alcanza 170kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_170kg', 'meta_valor': 170, 'puntos_recompensa': 2600, 'es_secreta': False},
    {'nombre': 'Hokage Médico', 'descripcion': 'Completa 140 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_140', 'meta_valor': 140, 'puntos_recompensa': 3300, 'es_secreta': False},
    {'nombre': 'Sannin de la Fuerza', 'descripcion': 'Supera 12 récords personales.',
     'clave_calculo': 'records_totales_meta_12', 'meta_valor': 12, 'puntos_recompensa': 3500, 'es_secreta': False},
]

# =============================================================================
# NIVELES 31-40: LOS LEGENDARIOS
# =============================================================================

print("\n🏆 === LOS LEGENDARIOS (Niveles 31-40) ===")

# Nivel 31: All Might
pruebas_nivel_31 = [
    {'nombre': 'One For All', 'descripcion': 'Alcanza 175kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_175kg', 'meta_valor': 175, 'puntos_recompensa': 3000, 'es_secreta': False},
    {'nombre': 'Plus Ultra!', 'descripcion': 'Levanta 80,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_80000kg', 'meta_valor': 80000, 'puntos_recompensa': 3600, 'es_secreta': False},
    {'nombre': 'Símbolo de la Paz', 'descripcion': 'Mantén una racha de 70 días.',
     'clave_calculo': 'racha_dias_meta_70', 'meta_valor': 70, 'puntos_recompensa': 4000, 'es_secreta': False},
]

# Nivel 32: Endeavor
pruebas_nivel_32 = [
    {'nombre': 'Llamas del Infierno', 'descripcion': 'Alcanza 180kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_180kg', 'meta_valor': 180, 'puntos_recompensa': 3200, 'es_secreta': False},
    {'nombre': 'Héroe Número 2', 'descripcion': 'Completa 150 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_150', 'meta_valor': 150, 'puntos_recompensa': 3700, 'es_secreta': False},
    {'nombre': 'Prominencia Burn', 'descripcion': 'Supera 15 récords personales.',
     'clave_calculo': 'records_totales_meta_15', 'meta_valor': 15, 'puntos_recompensa': 4200, 'es_secreta': False},
]

# Nivel 33: Shoto Todoroki
pruebas_nivel_33 = [
    {'nombre': 'Hielo y Fuego', 'descripcion': 'Alcanza 185kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_185kg', 'meta_valor': 185, 'puntos_recompensa': 3400, 'es_secreta': False},
    {'nombre': 'Poder Equilibrado', 'descripcion': 'Levanta 90,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_90000kg', 'meta_valor': 90000, 'puntos_recompensa': 3900, 'es_secreta': False},
    {'nombre': 'Héroe de Nueva Generación', 'descripcion': 'Mantén una racha de 75 días.',
     'clave_calculo': 'racha_dias_meta_75', 'meta_valor': 75, 'puntos_recompensa': 4400, 'es_secreta': False},
]

# Nivel 34: Yujiro Hanma
pruebas_nivel_34 = [
    {'nombre': 'El Ogre Más Fuerte', 'descripcion': 'Alcanza 200kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_200kg', 'meta_valor': 200, 'puntos_recompensa': 4000, 'es_secreta': False},
    {'nombre': 'Técnica del Demonio', 'descripcion': 'Supera 18 récords personales.',
     'clave_calculo': 'records_totales_meta_18', 'meta_valor': 18, 'puntos_recompensa': 5000, 'es_secreta': False},
    {'nombre': 'La Criatura Más Fuerte', 'descripcion': 'Levanta 100,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_100000kg', 'meta_valor': 100000, 'puntos_recompensa': 5500, 'es_secreta': False},
]

# Nivel 35: Baki Hanma
pruebas_nivel_35 = [
    {'nombre': 'Hijo del Ogre', 'descripcion': 'Alcanza 190kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_190kg', 'meta_valor': 190, 'puntos_recompensa': 3800, 'es_secreta': False},
    {'nombre': 'Técnicas de Combate', 'descripcion': 'Completa 160 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_160', 'meta_valor': 160, 'puntos_recompensa': 4300, 'es_secreta': False},
    {'nombre': 'Espíritu Indomable', 'descripcion': 'Mantén una racha de 80 días.',
     'clave_calculo': 'racha_dias_meta_80', 'meta_valor': 80, 'puntos_recompensa': 4800, 'es_secreta': False},
]

# Nivel 36: Saber (Artoria)
pruebas_nivel_36 = [
    {'nombre': 'Excalibur', 'descripcion': 'Alcanza 195kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_195kg', 'meta_valor': 195, 'puntos_recompensa': 3900, 'es_secreta': False},
    {'nombre': 'Rey de los Caballeros', 'descripcion': 'Levanta 110,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_110000kg', 'meta_valor': 110000, 'puntos_recompensa': 4600, 'es_secreta': False},
    {'nombre': 'Noble Phantasm', 'descripcion': 'Supera 20 récords personales.',
     'clave_calculo': 'records_totales_meta_20', 'meta_valor': 20, 'puntos_recompensa': 5200, 'es_secreta': False},
]

# Nivel 37: Gilgamesh
pruebas_nivel_37 = [
    {'nombre': 'Gate of Babylon', 'descripcion': 'Alcanza 205kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_205kg', 'meta_valor': 205, 'puntos_recompensa': 4200, 'es_secreta': False},
    {'nombre': 'Rey de los Héroes', 'descripcion': 'Completa 170 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_170', 'meta_valor': 170, 'puntos_recompensa': 4800, 'es_secreta': False},
    {'nombre': 'Ea - Espada de Ruptura', 'descripcion': 'Mantén una racha de 85 días.',
     'clave_calculo': 'racha_dias_meta_85', 'meta_valor': 85, 'puntos_recompensa': 5400, 'es_secreta': True},
]

# Nivel 38: Escanor
pruebas_nivel_38 = [
    {'nombre': 'Sunshine', 'descripcion': 'Alcanza 210kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_210kg', 'meta_valor': 210, 'puntos_recompensa': 4400, 'es_secreta': False},
    {'nombre': 'The One', 'descripcion': 'Levanta 120,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_120000kg', 'meta_valor': 120000, 'puntos_recompensa': 5000, 'es_secreta': False},
    {'nombre': 'Orgullo del León', 'descripcion': 'Supera 22 récords personales.',
     'clave_calculo': 'records_totales_meta_22', 'meta_valor': 22, 'puntos_recompensa': 5600, 'es_secreta': False},
]

# Nivel 39: Meliodas
pruebas_nivel_39 = [
    {'nombre': 'Full Counter', 'descripcion': 'Alcanza 215kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_215kg', 'meta_valor': 215, 'puntos_recompensa': 4600, 'es_secreta': False},
    {'nombre': 'Modo Demonio', 'descripcion': 'Completa 180 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_180', 'meta_valor': 180, 'puntos_recompensa': 5200, 'es_secreta': False},
    {'nombre': 'Capitán de los Pecados', 'descripcion': 'Mantén una racha de 90 días.',
     'clave_calculo': 'racha_dias_meta_90', 'meta_valor': 90, 'puntos_recompensa': 5800, 'es_secreta': False},
]

# Nivel 40: Ban
pruebas_nivel_40 = [
    {'nombre': 'Snatch', 'descripcion': 'Alcanza 220kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_220kg', 'meta_valor': 220, 'puntos_recompensa': 4800, 'es_secreta': False},
    {'nombre': 'Inmortalidad', 'descripcion': 'Levanta 130,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_130000kg', 'meta_valor': 130000, 'puntos_recompensa': 5400, 'es_secreta': False},
    {'nombre': 'Zorro del Pecado de la Avaricia', 'descripcion': 'Supera 25 récords personales.',
     'clave_calculo': 'records_totales_meta_25', 'meta_valor': 25, 'puntos_recompensa': 6000, 'es_secreta': False},
]

# =============================================================================
# NIVELES 41-50: LOS SAIYANS DIVINOS
# =============================================================================

print("\n🔥 === LOS SAIYANS DIVINOS (Niveles 41-50) ===")

# Nivel 41: Goku (SSJ God)
pruebas_nivel_41 = [
    {'nombre': 'El Ki Divino', 'descripcion': 'Alcanza 230kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_230kg', 'meta_valor': 230, 'puntos_recompensa': 6000, 'es_secreta': False},
    {'nombre': 'Ritual de los Dioses', 'descripcion': 'Completa 200 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_200', 'meta_valor': 200, 'puntos_recompensa': 6500, 'es_secreta': False},
    {'nombre': 'Trascendencia Mortal', 'descripcion': 'Levanta 150,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_150000kg', 'meta_valor': 150000, 'puntos_recompensa': 7000, 'es_secreta': False},
]

# Nivel 42: Vegeta (SSJ Blue)
pruebas_nivel_42 = [
    {'nombre': 'Orgullo del Príncipe', 'descripcion': 'Alcanza 240kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_240kg', 'meta_valor': 240, 'puntos_recompensa': 6200, 'es_secreta': False},
    {'nombre': 'Final Flash Divino', 'descripcion': 'Mantén una racha de 100 días.',
     'clave_calculo': 'racha_dias_meta_100', 'meta_valor': 100, 'puntos_recompensa': 7500, 'es_secreta': False},
    {'nombre': 'Príncipe de los Saiyans', 'descripcion': 'Supera 30 récords personales.',
     'clave_calculo': 'records_totales_meta_30', 'meta_valor': 30, 'puntos_recompensa': 8000, 'es_secreta': False},
]

# Nivel 43: Beerus
pruebas_nivel_43 = [
    {'nombre': 'Hakai', 'descripcion': 'Alcanza 250kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_250kg', 'meta_valor': 250, 'puntos_recompensa': 7000, 'es_secreta': False},
    {'nombre': 'El Despertar del Destructor', 'descripcion': 'Levanta 200,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_200000kg', 'meta_valor': 200000, 'puntos_recompensa': 8000, 'es_secreta': False},
    {'nombre': 'Equilibrio Universal', 'descripcion': 'Completa 250 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_250', 'meta_valor': 250, 'puntos_recompensa': 8500, 'es_secreta': False},
]

# Nivel 44: Whis
pruebas_nivel_44 = [
    {'nombre': 'Ultra Instinto', 'descripcion': 'Alcanza 260kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_260kg', 'meta_valor': 260, 'puntos_recompensa': 7500, 'es_secreta': False},
    {'nombre': 'Maestro de los Ángeles', 'descripcion': 'Mantén una racha de 120 días.',
     'clave_calculo': 'racha_dias_meta_120', 'meta_valor': 120, 'puntos_recompensa': 9000, 'es_secreta': False},
    {'nombre': 'Reversión Temporal', 'descripcion': 'Supera 35 récords personales.',
     'clave_calculo': 'records_totales_meta_35', 'meta_valor': 35, 'puntos_recompensa': 9500, 'es_secreta': False},
]

# Nivel 45: Gogeta Blue
pruebas_nivel_45 = [
    {'nombre': 'Fusión Perfecta', 'descripcion': 'Alcanza 270kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_270kg', 'meta_valor': 270, 'puntos_recompensa': 8000, 'es_secreta': False},
    {'nombre': 'Soul Punisher', 'descripcion': 'Levanta 250,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_250000kg', 'meta_valor': 250000, 'puntos_recompensa': 9000, 'es_secreta': False},
    {'nombre': 'Poder Combinado', 'descripcion': 'Completa 300 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_300', 'meta_valor': 300, 'puntos_recompensa': 10000, 'es_secreta': False},
]

# Nivel 46: Vegito Blue
pruebas_nivel_46 = [
    {'nombre': 'Potara Fusion', 'descripcion': 'Alcanza 280kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_280kg', 'meta_valor': 280, 'puntos_recompensa': 8500, 'es_secreta': False},
    {'nombre': 'Final Kamehameha', 'descripcion': 'Mantén una racha de 150 días.',
     'clave_calculo': 'racha_dias_meta_150', 'meta_valor': 150, 'puntos_recompensa': 10000, 'es_secreta': False},
    {'nombre': 'Fusión Eterna', 'descripcion': 'Supera 40 récords personales.',
     'clave_calculo': 'records_totales_meta_40', 'meta_valor': 40, 'puntos_recompensa': 11000, 'es_secreta': False},
]

# Nivel 47: Broly (Legendario)
pruebas_nivel_47 = [
    {'nombre': 'Super Saiyan Legendario', 'descripcion': 'Alcanza 290kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_290kg', 'meta_valor': 290, 'puntos_recompensa': 9000, 'es_secreta': False},
    {'nombre': 'Poder Descontrolado', 'descripcion': 'Levanta 300,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_300000kg', 'meta_valor': 300000, 'puntos_recompensa': 10500, 'es_secreta': False},
    {'nombre': 'Ira Infinita', 'descripcion': 'Completa 350 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_350', 'meta_valor': 350, 'puntos_recompensa': 12000, 'es_secreta': False},
]

# Nivel 48: Jiren
pruebas_nivel_48 = [
    {'nombre': 'Poder Absoluto', 'descripcion': 'Alcanza 300kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_300kg', 'meta_valor': 300, 'puntos_recompensa': 10000, 'es_secreta': False},
    {'nombre': 'Orgullo del Universo 11', 'descripcion': 'Mantén una racha de 180 días.',
     'clave_calculo': 'racha_dias_meta_180', 'meta_valor': 180, 'puntos_recompensa': 12000, 'es_secreta': False},
    {'nombre': 'Más Allá de los Límites', 'descripcion': 'Supera 45 récords personales.',
     'clave_calculo': 'records_totales_meta_45', 'meta_valor': 45, 'puntos_recompensa': 13000, 'es_secreta': False},
]

# Nivel 49: Moro
pruebas_nivel_49 = [
    {'nombre': 'Devorador de Planetas', 'descripcion': 'Alcanza 320kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_320kg', 'meta_valor': 320, 'puntos_recompensa': 11000, 'es_secreta': False},
    {'nombre': 'Absorción de Energía', 'descripcion': 'Levanta 400,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_400000kg', 'meta_valor': 400000, 'puntos_recompensa': 13000, 'es_secreta': False},
    {'nombre': 'Hechicero Galáctico', 'descripcion': 'Completa 400 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_400', 'meta_valor': 400, 'puntos_recompensa': 14000, 'es_secreta': False},
]

# Nivel 50: Gas
pruebas_nivel_50 = [
    {'nombre': 'El Más Fuerte del Universo', 'descripcion': 'Alcanza 350kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_350kg', 'meta_valor': 350, 'puntos_recompensa': 12000, 'es_secreta': False},
    {'nombre': 'Evolución Constante', 'descripcion': 'Mantén una racha de 200 días.',
     'clave_calculo': 'racha_dias_meta_200', 'meta_valor': 200, 'puntos_recompensa': 15000, 'es_secreta': False},
    {'nombre': 'Heeter Force', 'descripcion': 'Supera 50 récords personales.',
     'clave_calculo': 'records_totales_meta_50', 'meta_valor': 50, 'puntos_recompensa': 16000, 'es_secreta': True},
]

# =============================================================================
# NIVELES 51-60: LOS NINJAS LEGENDARIOS
# =============================================================================

print("\n🥷 === LOS NINJAS LEGENDARIOS (Niveles 51-60) ===")

# Nivel 51: Itachi Uchiha
pruebas_nivel_51 = [
    {'nombre': 'Tsukuyomi', 'descripcion': 'Alcanza 360kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_360kg', 'meta_valor': 360, 'puntos_recompensa': 13000, 'es_secreta': False},
    {'nombre': 'Amaterasu', 'descripcion': 'Levanta 500,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_500000kg', 'meta_valor': 500000, 'puntos_recompensa': 16000, 'es_secreta': False},
    {'nombre': 'Susanoo', 'descripcion': 'Completa 450 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_450', 'meta_valor': 450, 'puntos_recompensa': 17000, 'es_secreta': False},
]

# Nivel 52: Minato Namikaze
pruebas_nivel_52 = [
    {'nombre': 'Hiraishin no Jutsu', 'descripcion': 'Alcanza 370kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_370kg', 'meta_valor': 370, 'puntos_recompensa': 14000, 'es_secreta': False},
    {'nombre': 'Rasengan', 'descripcion': 'Mantén una racha de 250 días.',
     'clave_calculo': 'racha_dias_meta_250', 'meta_valor': 250, 'puntos_recompensa': 18000, 'es_secreta': False},
    {'nombre': 'Cuarto Hokage', 'descripcion': 'Supera 60 récords personales.',
     'clave_calculo': 'records_totales_meta_60', 'meta_valor': 60, 'puntos_recompensa': 19000, 'es_secreta': False},
]

# Nivel 53: Hashirama Senju
pruebas_nivel_53 = [
    {'nombre': 'Mokuton: Nacimiento del Mundo de Árboles', 'descripcion': 'Alcanza 380kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_380kg', 'meta_valor': 380, 'puntos_recompensa': 15000, 'es_secreta': False},
    {'nombre': 'El Dios de los Shinobi', 'descripcion': 'Levanta 600,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_600000kg', 'meta_valor': 600000, 'puntos_recompensa': 19000, 'es_secreta': False},
    {'nombre': 'Primer Hokage', 'descripcion': 'Completa 500 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_500', 'meta_valor': 500, 'puntos_recompensa': 20000, 'es_secreta': False},
]

# Nivel 54: Madara Uchiha
pruebas_nivel_54 = [
    {'nombre': 'Susanoo Perfecto', 'descripcion': 'Alcanza 400kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_400kg', 'meta_valor': 400, 'puntos_recompensa': 16000, 'es_secreta': False},
    {'nombre': 'Infinite Tsukuyomi', 'descripcion': 'Mantén una racha de 300 días.',
     'clave_calculo': 'racha_dias_meta_300', 'meta_valor': 300, 'puntos_recompensa': 22000, 'es_secreta': False},
    {'nombre': 'Uchiha Legendario', 'descripcion': 'Supera 70 récords personales.',
     'clave_calculo': 'records_totales_meta_70', 'meta_valor': 70, 'puntos_recompensa': 24000, 'es_secreta': False},
]

# Nivel 55: Naruto (Modo Sabio)
pruebas_nivel_55 = [
    {'nombre': 'Modo Sabio Perfecto', 'descripcion': 'Alcanza 420kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_420kg', 'meta_valor': 420, 'puntos_recompensa': 17000, 'es_secreta': False},
    {'nombre': 'Rasengan Gigante', 'descripcion': 'Levanta 700,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_700000kg', 'meta_valor': 700000, 'puntos_recompensa': 23000, 'es_secreta': False},
    {'nombre': 'Hokage de la Nueva Era', 'descripcion': 'Completa 600 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_600', 'meta_valor': 600, 'puntos_recompensa': 25000, 'es_secreta': False},
]

# Nivel 56: Sasuke (Rinnegan)
pruebas_nivel_56 = [
    {'nombre': 'Rinnegan Awakening', 'descripcion': 'Alcanza 440kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_440kg', 'meta_valor': 440, 'puntos_recompensa': 18000, 'es_secreta': False},
    {'nombre': 'Amenotejikara', 'descripcion': 'Mantén una racha de 350 días.',
     'clave_calculo': 'racha_dias_meta_350', 'meta_valor': 350, 'puntos_recompensa': 26000, 'es_secreta': False},
    {'nombre': 'Último Uchiha', 'descripcion': 'Supera 80 récords personales.',
     'clave_calculo': 'records_totales_meta_80', 'meta_valor': 80, 'puntos_recompensa': 28000, 'es_secreta': False},
]

# Nivel 57: Obito (Juubi)
pruebas_nivel_57 = [
    {'nombre': 'Jinchuriki del Juubi', 'descripcion': 'Alcanza 460kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_460kg', 'meta_valor': 460, 'puntos_recompensa': 19000, 'es_secreta': False},
    {'nombre': 'Kamui Dimension', 'descripcion': 'Levanta 800,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_800000kg', 'meta_valor': 800000, 'puntos_recompensa': 27000, 'es_secreta': False},
    {'nombre': 'Máscara de Tobi', 'descripcion': 'Completa 700 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_700', 'meta_valor': 700, 'puntos_recompensa': 30000, 'es_secreta': False},
]

# Nivel 58: Kaguya Otsutsuki
pruebas_nivel_58 = [
    {'nombre': 'Diosa Conejo', 'descripcion': 'Alcanza 480kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_480kg', 'meta_valor': 480, 'puntos_recompensa': 20000, 'es_secreta': False},
    {'nombre': 'All-Killing Ash Bones', 'descripcion': 'Mantén una racha de 400 días.',
     'clave_calculo': 'racha_dias_meta_400', 'meta_valor': 400, 'puntos_recompensa': 30000, 'es_secreta': False},
    {'nombre': 'Madre del Chakra', 'descripcion': 'Supera 90 récords personales.',
     'clave_calculo': 'records_totales_meta_90', 'meta_valor': 90, 'puntos_recompensa': 32000, 'es_secreta': False},
]

# Nivel 59: Ichigo (Final)
pruebas_nivel_59 = [
    {'nombre': 'True Bankai', 'descripcion': 'Alcanza 500kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_500kg', 'meta_valor': 500, 'puntos_recompensa': 25000, 'es_secreta': False},
    {'nombre': 'Quincy-Shinigami-Hollow', 'descripcion': 'Levanta 1,000,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_1M', 'meta_valor': 1000000, 'puntos_recompensa': 35000, 'es_secreta': False},
    {'nombre': 'Protector de Karakura', 'descripcion': 'Completa 800 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_800', 'meta_valor': 800, 'puntos_recompensa': 38000, 'es_secreta': False},
]

# Nivel 60: Aizen Sosuke
pruebas_nivel_60 = [
    {'nombre': 'Kyoka Suigetsu', 'descripcion': 'Alcanza 520kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_520kg', 'meta_valor': 520, 'puntos_recompensa': 30000, 'es_secreta': False},
    {'nombre': 'Hogyoku Fusion', 'descripcion': 'Mantén una racha de 500 días.',
     'clave_calculo': 'racha_dias_meta_500', 'meta_valor': 500, 'puntos_recompensa': 40000, 'es_secreta': False},
    {'nombre': 'Trascendencia Shinigami', 'descripcion': 'Supera 100 récords personales.',
     'clave_calculo': 'records_totales_meta_100', 'meta_valor': 100, 'puntos_recompensa': 45000, 'es_secreta': True},
]

# =============================================================================
# NIVELES 61-70: LOS DIVINOS CÓSMICOS
# =============================================================================

print("\n⚡ === LOS DIVINOS CÓSMICOS (Niveles 61-70) ===")

# Nivel 61-70: Crear pruebas para los niveles divinos
niveles_divinos = [
    (61, 'Goku (Ultra Instinto)', 550, 1200000, 900, 50000),
    (62, 'Vegeta (Ultra Ego)', 580, 1400000, 1000, 55000),
    (63, 'Gogeta (Ultra)', 600, 1600000, 1100, 60000),
    (64, 'Vegito (Ultra)', 620, 1800000, 1200, 65000),
    (65, 'Broly (Berserker)', 650, 2000000, 1300, 70000),
    (66, 'Jiren (Límite Roto)', 680, 2200000, 1400, 75000),
    (67, 'Moro (Planeta)', 700, 2500000, 1500, 80000),
    (68, 'Gas (Evolución)', 750, 3000000, 1600, 85000),
    (69, 'Black Frieza', 800, 3500000, 1700, 90000),
    (70, 'Granolah', 850, 4000000, 1800, 95000),
]

for nivel, nombre, peso, volumen, entrenos, puntos in niveles_divinos:
    pruebas_divinas = [
        {'nombre': f'Poder {nombre.split()[-1]}', 'descripcion': f'Alcanza {peso}kg en Press de Banca.',
         'clave_calculo': f'rm_banca_meta_{peso}kg', 'meta_valor': peso, 'puntos_recompensa': puntos, 'es_secreta': False},
        {'nombre': f'Dominio {nombre.split()[0]}', 'descripcion': f'Levanta {volumen:,}kg de volumen total.',
         'clave_calculo': f'volumen_total_meta_{volumen}', 'meta_valor': volumen, 'puntos_recompensa': puntos + 10000, 'es_secreta': False},
        {'nombre': f'Maestría {nombre}', 'descripcion': f'Completa {entrenos} entrenamientos.',
         'clave_calculo': f'entrenos_completados_meta_{entrenos}', 'meta_valor': entrenos, 'puntos_recompensa': puntos + 15000, 'es_secreta': False},
    ]
    
    # Añadir prueba secreta para algunos niveles
    if nivel % 5 == 0:  # Cada 5 niveles
        pruebas_divinas.append({
            'nombre': f'Trascendencia {nombre}', 'descripcion': f'Mantén una racha de {nivel * 10} días.',
            'clave_calculo': f'racha_dias_meta_{nivel * 10}', 'meta_valor': nivel * 10, 
            'puntos_recompensa': puntos + 20000, 'es_secreta': True
        })

# =============================================================================
# NIVELES 71-80: LOS CÓSMICOS
# =============================================================================

print("\n🌌 === LOS CÓSMICOS (Niveles 71-80) ===")

niveles_cosmicos = [
    (71, 'Sailor Moon', 900, 5000000, 2000, 100000),
    (72, 'Seiya', 950, 6000000, 2200, 110000),
    (73, 'Saga', 1000, 7000000, 2400, 120000),
    (74, 'Shaka', 1100, 8000000, 2600, 130000),
    (75, 'Athena', 1200, 9000000, 2800, 140000),
    (76, 'Hades', 1300, 10000000, 3000, 150000),
    (77, 'Simon', 1400, 12000000, 3200, 160000),
    (78, 'Anti-Spiral', 1500, 15000000, 3400, 170000),
    (79, 'Tengen Toppa', 1600, 18000000, 3600, 180000),
    (80, 'Super Tengen Toppa', 1700, 20000000, 3800, 190000),
]

for nivel, nombre, peso, volumen, entrenos, puntos in niveles_cosmicos:
    pruebas_cosmicas = [
        {'nombre': f'Cosmos {nombre}', 'descripcion': f'Alcanza {peso}kg en Press de Banca.',
         'clave_calculo': f'rm_banca_meta_{peso}kg', 'meta_valor': peso, 'puntos_recompensa': puntos, 'es_secreta': False},
        {'nombre': f'Galaxia {nombre}', 'descripcion': f'Levanta {volumen:,}kg de volumen total.',
         'clave_calculo': f'volumen_total_meta_{volumen}', 'meta_valor': volumen, 'puntos_recompensa': puntos + 20000, 'es_secreta': False},
        {'nombre': f'Universo {nombre}', 'descripcion': f'Completa {entrenos} entrenamientos.',
         'clave_calculo': f'entrenos_completados_meta_{entrenos}', 'meta_valor': entrenos, 'puntos_recompensa': puntos + 30000, 'es_secreta': False},
    ]

# =============================================================================
# NIVELES 81-90: LOS OMNIPOTENTES
# =============================================================================

print("\n♾️ === LOS OMNIPOTENTES (Niveles 81-90) ===")

niveles_omnipotentes = [
    (81, 'Madoka', 1800, 25000000, 4000, 200000),
    (82, 'Homura', 1900, 30000000, 4200, 220000),
    (83, 'Haruhi', 2000, 35000000, 4400, 240000),
    (84, 'Truth', 2200, 40000000, 4600, 260000),
    (85, 'Giorno GER', 2400, 45000000, 4800, 280000),
    (86, 'Rimuru', 2600, 50000000, 5000, 300000),
    (87, 'Ainz', 2800, 60000000, 5200, 320000),
    (88, 'Saitama (Completo)', 3000, 70000000, 5400, 340000),
    (89, 'Zeno Sama', 3500, 80000000, 5600, 360000),
    (90, 'Daishinkan', 4000, 90000000, 5800, 380000),
]

for nivel, nombre, peso, volumen, entrenos, puntos in niveles_omnipotentes:
    pruebas_omnipotentes = [
        {'nombre': f'Omnipotencia {nombre}', 'descripcion': f'Alcanza {peso}kg en Press de Banca.',
         'clave_calculo': f'rm_banca_meta_{peso}kg', 'meta_valor': peso, 'puntos_recompensa': puntos, 'es_secreta': False},
        {'nombre': f'Realidad {nombre}', 'descripcion': f'Levanta {volumen:,}kg de volumen total.',
         'clave_calculo': f'volumen_total_meta_{volumen}', 'meta_valor': volumen, 'puntos_recompensa': puntos + 50000, 'es_secreta': False},
        {'nombre': f'Existencia {nombre}', 'descripcion': f'Completa {entrenos} entrenamientos.',
         'clave_calculo': f'entrenos_completados_meta_{entrenos}', 'meta_valor': entrenos, 'puntos_recompensa': puntos + 70000, 'es_secreta': False},
    ]

# =============================================================================
# NIVELES 91-100: LOS ABSOLUTOS
# =============================================================================

print("\n🌟 === LOS ABSOLUTOS (Niveles 91-100) ===")

# Nivel 100: The One Above All - El nivel máximo
pruebas_nivel_100 = [
    {'nombre': 'Omnipotencia Absoluta', 'descripcion': 'Alcanza 5000kg en Press de Banca.',
     'clave_calculo': 'rm_banca_meta_5000kg', 'meta_valor': 5000, 'puntos_recompensa': 500000, 'es_secreta': False},
    {'nombre': 'Más Allá de la Comprensión', 'descripcion': 'Completa 10000 entrenamientos.',
     'clave_calculo': 'entrenos_completados_meta_10000', 'meta_valor': 10000, 'puntos_recompensa': 750000, 'es_secreta': False},
    {'nombre': 'El Uno Sobre Todo', 'descripcion': 'Mantén el puesto #1 en el ranking durante 365 días.',
     'clave_calculo': 'ranking_top_1_por_365_dias', 'meta_valor': 365, 'puntos_recompensa': 1000000, 'es_secreta': False},
    {'nombre': 'Trascendencia Absoluta', 'descripcion': 'Levanta 100,000,000kg de volumen total.',
     'clave_calculo': 'volumen_total_meta_100M', 'meta_valor': 100000000, 'puntos_recompensa': 2000000, 'es_secreta': True},
]

# Niveles 91-99: Los otros absolutos
niveles_absolutos = [
    (91, 'Yogiri', 4200, 95000000, 6000, 400000),
    (92, 'Arceus', 4400, 100000000, 6200, 420000),
    (93, 'Akuto Sai', 4600, 110000000, 6400, 440000),
    (94, 'Featherine', 4800, 120000000, 6600, 460000),
    (95, 'Lambdadelta', 5000, 130000000, 6800, 480000),
    (96, 'Bernkastel', 5200, 140000000, 7000, 500000),
    (97, 'Kami Tenchi', 5400, 150000000, 7200, 520000),
    (98, 'Hajun', 5600, 160000000, 7400, 540000),
    (99, 'Azathoth', 5800, 170000000, 7600, 560000),
]

for nivel, nombre, peso, volumen, entrenos, puntos in niveles_absolutos:
    pruebas_absolutas = [
        {'nombre': f'Absoluto {nombre}', 'descripcion': f'Alcanza {peso}kg en Press de Banca.',
         'clave_calculo': f'rm_banca_meta_{peso}kg', 'meta_valor': peso, 'puntos_recompensa': puntos, 'es_secreta': False},
        {'nombre': f'Infinito {nombre}', 'descripcion': f'Levanta {volumen:,}kg de volumen total.',
         'clave_calculo': f'volumen_total_meta_{volumen}', 'meta_valor': volumen, 'puntos_recompensa': puntos + 100000, 'es_secreta': False},
        {'nombre': f'Eterno {nombre}', 'descripcion': f'Completa {entrenos} entrenamientos.',
         'clave_calculo': f'entrenos_completados_meta_{entrenos}', 'meta_valor': entrenos, 'puntos_recompensa': puntos + 150000, 'es_secreta': False},
    ]

# =============================================================================
# CREAR TODAS LAS PRUEBAS
# =============================================================================

# Lista de todas las pruebas a crear
todas_las_pruebas = [
    # Niveles 1-10: Los Aspirantes
    (1, pruebas_nivel_1), (2, pruebas_nivel_2), (3, pruebas_nivel_3), (4, pruebas_nivel_4), (5, pruebas_nivel_5),
    (6, pruebas_nivel_6), (7, pruebas_nivel_7), (8, pruebas_nivel_8), (9, pruebas_nivel_9), (10, pruebas_nivel_10),
    
    # Niveles 11-20: Los Guerreros Emergentes
    (11, pruebas_nivel_11), (12, pruebas_nivel_12), (13, pruebas_nivel_13), (14, pruebas_nivel_14), (15, pruebas_nivel_15),
    (16, pruebas_nivel_16), (17, pruebas_nivel_17), (18, pruebas_nivel_18), (19, pruebas_nivel_19), (20, pruebas_nivel_20),
    
    # Niveles 21-30: Los Guerreros Élite
    (21, pruebas_nivel_21), (22, pruebas_nivel_22), (23, pruebas_nivel_23), (24, pruebas_nivel_24), (25, pruebas_nivel_25),
    (26, pruebas_nivel_26), (27, pruebas_nivel_27), (28, pruebas_nivel_28), (29, pruebas_nivel_29), (30, pruebas_nivel_30),
    
    # Niveles 31-40: Los Legendarios
    (31, pruebas_nivel_31), (32, pruebas_nivel_32), (33, pruebas_nivel_33), (34, pruebas_nivel_34), (35, pruebas_nivel_35),
    (36, pruebas_nivel_36), (37, pruebas_nivel_37), (38, pruebas_nivel_38), (39, pruebas_nivel_39), (40, pruebas_nivel_40),
    
    # Niveles 41-50: Los Saiyans Divinos
    (41, pruebas_nivel_41), (42, pruebas_nivel_42), (43, pruebas_nivel_43), (44, pruebas_nivel_44), (45, pruebas_nivel_45),
    (46, pruebas_nivel_46), (47, pruebas_nivel_47), (48, pruebas_nivel_48), (49, pruebas_nivel_49), (50, pruebas_nivel_50),
    
    # Niveles 51-60: Los Ninjas Legendarios
    (51, pruebas_nivel_51), (52, pruebas_nivel_52), (53, pruebas_nivel_53), (54, pruebas_nivel_54), (55, pruebas_nivel_55),
    (56, pruebas_nivel_56), (57, pruebas_nivel_57), (58, pruebas_nivel_58), (59, pruebas_nivel_59), (60, pruebas_nivel_60),
    
    # Nivel 100: The One Above All
    (100, pruebas_nivel_100),
]

total_pruebas_creadas = 0

for nivel, pruebas in todas_las_pruebas:
    total_pruebas_creadas += crear_pruebas_para_arquetipo(nivel, pruebas)

print(f"\n🎉 ¡CREACIÓN COMPLETADA!")
print(f"⚔️ Total de Pruebas Legendarias creadas: {total_pruebas_creadas}")
print(f"🏆 Total de Arquetipos con pruebas: {len(todas_las_pruebas)}")
print(f"📊 Pruebas en la base de datos: {PruebaLegendaria.objects.count()}")

print(f"\n🌟 RESUMEN POR CATEGORÍAS:")
print(f"🥊 Los Aspirantes (1-10): Fundamentos y constancia")
print(f"⚔️ Los Guerreros Emergentes (11-20): Fuerza y técnica")
print(f"🌟 Los Guerreros Élite (21-30): Poder y disciplina")
print(f"🏆 Los Legendarios (31-40): Logros épicos")
print(f"🔥 Los Saiyans Divinos (41-50): Poder divino")
print(f"🥷 Los Ninjas Legendarios (51-60): Maestría ninja")
print(f"⚡ Los Divinos Cósmicos (61-70): Poder cósmico")
print(f"🌌 Los Cósmicos (71-80): Escala universal")
print(f"♾️ Los Omnipotentes (81-90): Poder omnipotente")
print(f"🌟 Los Absolutos (91-100): Trascendencia absoluta")

print(f"\n🚀 ¡El Códice de las Leyendas está 100% COMPLETO!")
print(f"💪 Los clientes ahora tienen un viaje épico de 100 niveles únicos")
print(f"🎯 Cada nivel tiene pruebas específicas y temáticas")
print(f"🏆 Desde entrenamientos básicos hasta logros imposibles")
print(f"⚔️ Un total de {total_pruebas_creadas} pruebas legendarias esperan ser conquistadas")

print(f"\n💡 CARACTERÍSTICAS ÉPICAS:")
print(f"• Progresión de 0 a 2,000,000 puntos de recompensa")
print(f"• Pruebas desde 40kg hasta 5,000kg en Press de Banca")
print(f"• Volumen desde 5,000kg hasta 100,000,000kg")
print(f"• Rachas desde 3 días hasta 365 días")
print(f"• Entrenamientos desde 1 hasta 10,000")
print(f"• Pruebas secretas para los más dedicados")

print(f"\n🎮 ¡Tu gimnasio ahora tiene el sistema de gamificación más épico del universo!")

