# logros/management/commands/crear_pruebas_epicas.py

import sys
from django.core.management.base import BaseCommand
from logros.models import Arquetipo, PruebaLegendaria

# Soluciona el problema de los emojis y caracteres especiales en la terminal
sys.stdout.reconfigure(encoding='utf-8')


class Command(BaseCommand):
    help = 'Crea un conjunto épico de Pruebas Legendarias para los 100 arquetipos existentes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("🧹 Limpiando Pruebas Legendarias existentes..."))
        count, _ = PruebaLegendaria.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"✅ {count} pruebas antiguas han sido eliminadas."))

        self.stdout.write(self.style.SUCCESS("\n⚔️ Creando Pruebas Legendarias para los 100 Arquetipos..."))

        # Aquí pegamos toda la lógica de tu script, pero dentro del método 'handle'

        # =============================================================================
        # NIVELES 1-10: LOS ASPIRANTES - Fundamentos y Constancia
        # =============================================================================
        self.stdout.write(self.style.HTTP_INFO("\n🥊 === LOS ASPIRANTES (Niveles 1-10) ==="))
        pruebas_nivel_1 = [
            {'nombre': 'El Primer Puñetazo',
             'descripcion': 'Completa tu primer entrenamiento. Todo héroe comienza aquí.',
             'clave_calculo': 'primer_entrenamiento', 'meta_valor': 1, 'puntos_recompensa': 50, 'es_secreta': False},
            {'nombre': '100 Flexiones', 'descripcion': 'Realiza 100 flexiones acumuladas en total.',
             'clave_calculo': 'flexiones_totales_meta_100', 'meta_valor': 100, 'puntos_recompensa': 100,
             'es_secreta': False},
            {'nombre': 'La Rutina Diaria', 'descripcion': 'Entrena 3 días consecutivos.',
             'clave_calculo': 'racha_dias_meta_3', 'meta_valor': 3, 'puntos_recompensa': 150, 'es_secreta': False},
            {'nombre': 'Limitador Roto', 'descripcion': 'Supera tu primer récord personal.',
             'clave_calculo': 'record_personal_superado_1', 'meta_valor': 1, 'puntos_recompensa': 200,
             'es_secreta': True},
        ]

        # Nivel 2: Rock Lee
        pruebas_nivel_2 = [
            {'nombre': 'Las Puertas del Esfuerzo', 'descripcion': 'Mantén una racha de 7 días entrenando.',
             'clave_calculo': 'racha_dias_meta_7', 'meta_valor': 7, 'puntos_recompensa': 200, 'es_secreta': False},
            {'nombre': 'La Llama de la Juventud', 'descripcion': 'Completa 15 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_15', 'meta_valor': 15, 'puntos_recompensa': 250,
             'es_secreta': False},
            {'nombre': 'Entrenamiento de Pesas', 'descripcion': 'Levanta un total de 5,000 kg acumulados.',
             'clave_calculo': 'volumen_total_meta_5000kg', 'meta_valor': 5000, 'puntos_recompensa': 300,
             'es_secreta': False},
        ]

        # Nivel 3: Krillin
        pruebas_nivel_3 = [
            {'nombre': 'El Guerrero Humano', 'descripcion': 'Alcanza 40kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_40kg', 'meta_valor': 40, 'puntos_recompensa': 300, 'es_secreta': False},
            {'nombre': 'Destructo Disc', 'descripcion': 'Completa 20 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_20', 'meta_valor': 20, 'puntos_recompensa': 350,
             'es_secreta': False},
            {'nombre': 'Corazón Valiente', 'descripcion': 'Mantén una racha de 10 días.',
             'clave_calculo': 'racha_dias_meta_10', 'meta_valor': 10, 'puntos_recompensa': 400, 'es_secreta': False},
        ]

        # Nivel 4: Yamcha
        pruebas_nivel_4 = [
            {'nombre': 'Puño del Lobo', 'descripcion': 'Alcanza 45kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_45kg', 'meta_valor': 45, 'puntos_recompensa': 350, 'es_secreta': False},
            {'nombre': 'Redención del Guerrero', 'descripcion': 'Levanta 8,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_8000kg', 'meta_valor': 8000, 'puntos_recompensa': 400,
             'es_secreta': False},
            {'nombre': 'Espíritu Indomable', 'descripcion': 'Completa 25 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_25', 'meta_valor': 25, 'puntos_recompensa': 450,
             'es_secreta': False},
        ]

        # Nivel 5: Tien Shinhan
        pruebas_nivel_5 = [
            {'nombre': 'El Tercer Ojo', 'descripcion': 'Domina 3 ejercicios diferentes.',
             'clave_calculo': 'ejercicios_dominados_meta_3', 'meta_valor': 3, 'puntos_recompensa': 400,
             'es_secreta': False},
            {'nombre': 'Kikoho', 'descripcion': 'Alcanza 50kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_50kg', 'meta_valor': 50, 'puntos_recompensa': 500, 'es_secreta': False},
            {'nombre': 'Técnica Mortal', 'descripcion': 'Levanta 12,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_12000kg', 'meta_valor': 12000, 'puntos_recompensa': 550,
             'es_secreta': False},
        ]

        # Nivel 6: Roronoa Zoro
        pruebas_nivel_6 = [
            {'nombre': 'Las Tres Espadas', 'descripcion': 'Domina 3 ejercicios diferentes.',
             'clave_calculo': 'ejercicios_dominados_meta_3', 'meta_valor': 3, 'puntos_recompensa': 450,
             'es_secreta': False},
            {'nombre': 'El Camino del Espadachín', 'descripcion': 'Alcanza 55kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_55kg', 'meta_valor': 55, 'puntos_recompensa': 550, 'es_secreta': False},
            {'nombre': 'Perdido pero Determinado', 'descripcion': 'Mantén una racha de 14 días.',
             'clave_calculo': 'racha_dias_meta_14', 'meta_valor': 14, 'puntos_recompensa': 600, 'es_secreta': False},
        ]

        # Nivel 7: Sanji
        pruebas_nivel_7 = [
            {'nombre': 'Pierna del Diablo', 'descripcion': 'Alcanza 80kg en Sentadilla.',
             'clave_calculo': 'rm_sentadilla_meta_80kg', 'meta_valor': 80, 'puntos_recompensa': 500,
             'es_secreta': False},
            {'nombre': 'Cocinero Guerrero', 'descripcion': 'Completa 35 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_35', 'meta_valor': 35, 'puntos_recompensa': 600,
             'es_secreta': False},
            {'nombre': 'Caballero de los Mares', 'descripcion': 'Levanta 15,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_15000kg', 'meta_valor': 15000, 'puntos_recompensa': 650,
             'es_secreta': False},
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
             'clave_calculo': 'entrenos_completados_meta_40', 'meta_valor': 40, 'puntos_recompensa': 750,
             'es_secreta': False},
            {'nombre': 'El Alquimista de Acero', 'descripcion': 'Levanta 20,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_20000kg', 'meta_valor': 20000, 'puntos_recompensa': 800,
             'es_secreta': False},
        ]

        # Nivel 10: Alphonse Elric
        pruebas_nivel_10 = [
            {'nombre': 'Armadura Viviente', 'descripcion': 'Alcanza 70kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_70kg', 'meta_valor': 70, 'puntos_recompensa': 700, 'es_secreta': False},
            {'nombre': 'Hermanos de Acero', 'descripcion': 'Mantén una racha de 20 días.',
             'clave_calculo': 'racha_dias_meta_20', 'meta_valor': 20, 'puntos_recompensa': 850, 'es_secreta': False},
            {'nombre': 'Alma Inquebrantable', 'descripcion': 'Completa 45 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_45', 'meta_valor': 45, 'puntos_recompensa': 900,
             'es_secreta': False},
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
             'clave_calculo': 'volumen_total_meta_25000kg', 'meta_valor': 25000, 'puntos_recompensa': 900,
             'es_secreta': False},
            {'nombre': 'Medio Demonio', 'descripcion': 'Supera 3 récords personales.',
             'clave_calculo': 'records_totales_meta_3', 'meta_valor': 3, 'puntos_recompensa': 1000,
             'es_secreta': False},
        ]

        # Nivel 12: Sesshomaru
        pruebas_nivel_12 = [
            {'nombre': 'Señor de las Tierras del Oeste', 'descripcion': 'Alcanza 80kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_80kg', 'meta_valor': 80, 'puntos_recompensa': 850, 'es_secreta': False},
            {'nombre': 'Látigo de Luz', 'descripcion': 'Mantén una racha de 25 días.',
             'clave_calculo': 'racha_dias_meta_25', 'meta_valor': 25, 'puntos_recompensa': 1000, 'es_secreta': False},
            {'nombre': 'Perfección Demoniaca', 'descripcion': 'Completa 50 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_50', 'meta_valor': 50, 'puntos_recompensa': 1100,
             'es_secreta': False},
        ]

        # Nivel 13: Yusuke Urameshi
        pruebas_nivel_13 = [
            {'nombre': 'Pistola Espiritual', 'descripcion': 'Alcanza 85kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_85kg', 'meta_valor': 85, 'puntos_recompensa': 900, 'es_secreta': False},
            {'nombre': 'Detective Espiritual', 'descripcion': 'Levanta 30,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_30000kg', 'meta_valor': 30000, 'puntos_recompensa': 1000,
             'es_secreta': False},
            {'nombre': 'Mazoku Awakening', 'descripcion': 'Supera 4 récords personales.',
             'clave_calculo': 'records_totales_meta_4', 'meta_valor': 4, 'puntos_recompensa': 1200,
             'es_secreta': False},
        ]

        # Nivel 14: Hiei
        pruebas_nivel_14 = [
            {'nombre': 'Espada del Fuego Infernal', 'descripcion': 'Alcanza 90kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_90kg', 'meta_valor': 90, 'puntos_recompensa': 950, 'es_secreta': False},
            {'nombre': 'Dragón de las Llamas Oscuras', 'descripcion': 'Mantén una racha de 30 días.',
             'clave_calculo': 'racha_dias_meta_30', 'meta_valor': 30, 'puntos_recompensa': 1200, 'es_secreta': False},
            {'nombre': 'Velocidad Demoniaca', 'descripcion': 'Completa 60 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_60', 'meta_valor': 60, 'puntos_recompensa': 1300,
             'es_secreta': False},
        ]

        # Nivel 15: Kurama
        pruebas_nivel_15 = [
            {'nombre': 'Rosa Látigo', 'descripcion': 'Alcanza 95kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_95kg', 'meta_valor': 95, 'puntos_recompensa': 1000, 'es_secreta': False},
            {'nombre': 'Zorro de Nueve Colas', 'descripcion': 'Levanta 35,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_35000kg', 'meta_valor': 35000, 'puntos_recompensa': 1200,
             'es_secreta': False},
            {'nombre': 'Sabiduría Milenaria', 'descripcion': 'Domina 5 ejercicios diferentes.',
             'clave_calculo': 'ejercicios_dominados_meta_5', 'meta_valor': 5, 'puntos_recompensa': 1400,
             'es_secreta': False},
        ]

        # Nivel 16: Ichigo Kurosaki
        pruebas_nivel_16 = [
            {'nombre': 'Zangetsu Despierta', 'descripcion': 'Alcanza 100kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_100kg', 'meta_valor': 100, 'puntos_recompensa': 1200, 'es_secreta': False},
            {'nombre': 'Getsuga Tensho', 'descripcion': 'Supera 5 récords personales.',
             'clave_calculo': 'records_totales_meta_5', 'meta_valor': 5, 'puntos_recompensa': 1500,
             'es_secreta': False},
            {'nombre': 'Shinigami Sustituto', 'descripcion': 'Completa 70 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_70', 'meta_valor': 70, 'puntos_recompensa': 1600,
             'es_secreta': False},
        ]

        # Nivel 17: Rukia Kuchiki
        pruebas_nivel_17 = [
            {'nombre': 'Sode no Shirayuki', 'descripcion': 'Alcanza 105kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_105kg', 'meta_valor': 105, 'puntos_recompensa': 1250, 'es_secreta': False},
            {'nombre': 'Danza de la Luna Blanca', 'descripcion': 'Mantén una racha de 35 días.',
             'clave_calculo': 'racha_dias_meta_35', 'meta_valor': 35, 'puntos_recompensa': 1500, 'es_secreta': False},
            {'nombre': 'Nobleza Shinigami', 'descripcion': 'Levanta 40,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_40000kg', 'meta_valor': 40000, 'puntos_recompensa': 1700,
             'es_secreta': False},
        ]

        # Nivel 18: Byakuya Kuchiki
        pruebas_nivel_18 = [
            {'nombre': 'Senbonzakura Kageyoshi', 'descripcion': 'Alcanza 110kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_110kg', 'meta_valor': 110, 'puntos_recompensa': 1300, 'es_secreta': False},
            {'nombre': 'Capitán del Escuadrón 6', 'descripcion': 'Completa 80 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_80', 'meta_valor': 80, 'puntos_recompensa': 1700,
             'es_secreta': False},
            {'nombre': 'Orgullo de la Nobleza', 'descripcion': 'Supera 6 récords personales.',
             'clave_calculo': 'records_totales_meta_6', 'meta_valor': 6, 'puntos_recompensa': 1800,
             'es_secreta': False},
        ]

        # Nivel 19: Jotaro Kujo
        pruebas_nivel_19 = [
            {'nombre': 'Star Platinum', 'descripcion': 'Alcanza 115kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_115kg', 'meta_valor': 115, 'puntos_recompensa': 1400, 'es_secreta': False},
            {'nombre': 'Ora Ora Ora!', 'descripcion': 'Levanta 45,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_45000kg', 'meta_valor': 45000, 'puntos_recompensa': 1800,
             'es_secreta': False},
            {'nombre': 'Yare Yare Daze', 'descripcion': 'Mantén una racha de 40 días.',
             'clave_calculo': 'racha_dias_meta_40', 'meta_valor': 40, 'puntos_recompensa': 2000, 'es_secreta': True},
        ]

        # Nivel 20: Dio Brando
        pruebas_nivel_20 = [
            {'nombre': 'The World', 'descripcion': 'Alcanza 120kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_120kg', 'meta_valor': 120, 'puntos_recompensa': 1500, 'es_secreta': False},
            {'nombre': 'Muda Muda Muda!', 'descripcion': 'Completa 90 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_90', 'meta_valor': 90, 'puntos_recompensa': 1900,
             'es_secreta': False},
            {'nombre': 'Vampiro Supremo', 'descripcion': 'Supera 7 récords personales.',
             'clave_calculo': 'records_totales_meta_7', 'meta_valor': 7, 'puntos_recompensa': 2100,
             'es_secreta': False},
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
             'clave_calculo': 'volumen_total_meta_50000kg', 'meta_valor': 50000, 'puntos_recompensa': 2000,
             'es_secreta': False},
            {'nombre': 'Llamas de la Emoción', 'descripcion': 'Mantén una racha de 45 días.',
             'clave_calculo': 'racha_dias_meta_45', 'meta_valor': 45, 'puntos_recompensa': 2200, 'es_secreta': False},
        ]

        # Nivel 22: Erza Scarlet
        pruebas_nivel_22 = [
            {'nombre': 'Reina de las Hadas', 'descripcion': 'Alcanza 130kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_130kg', 'meta_valor': 130, 'puntos_recompensa': 1700, 'es_secreta': False},
            {'nombre': 'Armadura del Cielo', 'descripcion': 'Completa 100 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_100', 'meta_valor': 100, 'puntos_recompensa': 2100,
             'es_secreta': False},
            {'nombre': 'Disciplina Férrea', 'descripcion': 'Supera 8 récords personales.',
             'clave_calculo': 'records_totales_meta_8', 'meta_valor': 8, 'puntos_recompensa': 2300,
             'es_secreta': False},
        ]

        # Nivel 23: Gray Fullbuster
        pruebas_nivel_23 = [
            {'nombre': 'Ice Make', 'descripcion': 'Alcanza 135kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_135kg', 'meta_valor': 135, 'puntos_recompensa': 1800, 'es_secreta': False},
            {'nombre': 'Demonio Slayer', 'descripcion': 'Levanta 55,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_55000kg', 'meta_valor': 55000, 'puntos_recompensa': 2200,
             'es_secreta': False},
            {'nombre': 'Corazón de Hielo', 'descripcion': 'Mantén una racha de 50 días.',
             'clave_calculo': 'racha_dias_meta_50', 'meta_valor': 50, 'puntos_recompensa': 2500, 'es_secreta': False},
        ]

        # Nivel 24: Laxus Dreyar
        pruebas_nivel_24 = [
            {'nombre': 'Rugido del Dragón del Rayo', 'descripcion': 'Alcanza 140kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_140kg', 'meta_valor': 140, 'puntos_recompensa': 1900, 'es_secreta': False},
            {'nombre': 'Modo Dragón del Rayo', 'descripcion': 'Completa 110 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_110', 'meta_valor': 110, 'puntos_recompensa': 2300,
             'es_secreta': False},
            {'nombre': 'Orgullo de Fairy Tail', 'descripcion': 'Supera 9 récords personales.',
             'clave_calculo': 'records_totales_meta_9', 'meta_valor': 9, 'puntos_recompensa': 2600,
             'es_secreta': False},
        ]

        # Nivel 25: Gaara
        pruebas_nivel_25 = [
            {'nombre': 'Defensa Absoluta', 'descripcion': 'Alcanza 145kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_145kg', 'meta_valor': 145, 'puntos_recompensa': 2000, 'es_secreta': False},
            {'nombre': 'Funeral de Arena', 'descripcion': 'Levanta 60,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_60000kg', 'meta_valor': 60000, 'puntos_recompensa': 2400,
             'es_secreta': False},
            {'nombre': 'Kazekage', 'descripcion': 'Mantén una racha de 55 días.',
             'clave_calculo': 'racha_dias_meta_55', 'meta_valor': 55, 'puntos_recompensa': 2700, 'es_secreta': False},
        ]

        # Nivel 26: Kakashi Hatake
        pruebas_nivel_26 = [
            {'nombre': 'Sharingan Copy', 'descripcion': 'Domina 7 ejercicios diferentes.',
             'clave_calculo': 'ejercicios_dominados_meta_7', 'meta_valor': 7, 'puntos_recompensa': 2200,
             'es_secreta': False},
            {'nombre': 'Chidori', 'descripcion': 'Alcanza 150kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_150kg', 'meta_valor': 150, 'puntos_recompensa': 2500, 'es_secreta': False},
            {'nombre': 'Ninja Copy', 'descripcion': 'Completa 120 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_120', 'meta_valor': 120, 'puntos_recompensa': 2800,
             'es_secreta': False},
        ]

        # Nivel 27: Might Guy
        pruebas_nivel_27 = [
            {'nombre': 'Las Ocho Puertas', 'descripcion': 'Alcanza 155kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_155kg', 'meta_valor': 155, 'puntos_recompensa': 2300, 'es_secreta': False},
            {'nombre': 'Bestia Verde de Konoha', 'descripcion': 'Mantén una racha de 60 días.',
             'clave_calculo': 'racha_dias_meta_60', 'meta_valor': 60, 'puntos_recompensa': 2900, 'es_secreta': False},
            {'nombre': 'Puerta de la Muerte', 'descripcion': 'Levanta 70,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_70000kg', 'meta_valor': 70000, 'puntos_recompensa': 3200,
             'es_secreta': True},
        ]

        # Nivel 28: Jiraiya
        pruebas_nivel_28 = [
            {'nombre': 'Modo Sabio', 'descripcion': 'Alcanza 160kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_160kg', 'meta_valor': 160, 'puntos_recompensa': 2400, 'es_secreta': False},
            {'nombre': 'Rasengan Gigante', 'descripcion': 'Supera 10 récords personales.',
             'clave_calculo': 'records_totales_meta_10', 'meta_valor': 10, 'puntos_recompensa': 3000,
             'es_secreta': False},
            {'nombre': 'Sannin Legendario', 'descripcion': 'Completa 130 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_130', 'meta_valor': 130, 'puntos_recompensa': 3100,
             'es_secreta': False},
        ]

        # Nivel 29: Orochimaru
        pruebas_nivel_29 = [
            {'nombre': 'Serpiente Inmortal', 'descripcion': 'Alcanza 165kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_165kg', 'meta_valor': 165, 'puntos_recompensa': 2500, 'es_secreta': False},
            {'nombre': 'Técnicas Prohibidas', 'descripcion': 'Levanta 75,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_75000kg', 'meta_valor': 75000, 'puntos_recompensa': 3200,
             'es_secreta': False},
            {'nombre': 'Búsqueda de la Inmortalidad', 'descripcion': 'Mantén una racha de 65 días.',
             'clave_calculo': 'racha_dias_meta_65', 'meta_valor': 65, 'puntos_recompensa': 3400, 'es_secreta': False},
        ]

        # Nivel 30: Tsunade
        pruebas_nivel_30 = [
            {'nombre': 'Fuerza de los Cien Sellos', 'descripcion': 'Alcanza 170kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_170kg', 'meta_valor': 170, 'puntos_recompensa': 2600, 'es_secreta': False},
            {'nombre': 'Hokage Médico', 'descripcion': 'Completa 140 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_140', 'meta_valor': 140, 'puntos_recompensa': 3300,
             'es_secreta': False},
            {'nombre': 'Sannin de la Fuerza', 'descripcion': 'Supera 12 récords personales.',
             'clave_calculo': 'records_totales_meta_12', 'meta_valor': 12, 'puntos_recompensa': 3500,
             'es_secreta': False},
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
             'clave_calculo': 'volumen_total_meta_80000kg', 'meta_valor': 80000, 'puntos_recompensa': 3600,
             'es_secreta': False},
            {'nombre': 'Símbolo de la Paz', 'descripcion': 'Mantén una racha de 70 días.',
             'clave_calculo': 'racha_dias_meta_70', 'meta_valor': 70, 'puntos_recompensa': 4000, 'es_secreta': False},
        ]

        # Nivel 32: Endeavor
        pruebas_nivel_32 = [
            {'nombre': 'Llamas del Infierno', 'descripcion': 'Alcanza 180kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_180kg', 'meta_valor': 180, 'puntos_recompensa': 3200, 'es_secreta': False},
            {'nombre': 'Héroe Número 2', 'descripcion': 'Completa 150 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_150', 'meta_valor': 150, 'puntos_recompensa': 3700,
             'es_secreta': False},
            {'nombre': 'Prominencia Burn', 'descripcion': 'Supera 15 récords personales.',
             'clave_calculo': 'records_totales_meta_15', 'meta_valor': 15, 'puntos_recompensa': 4200,
             'es_secreta': False},
        ]

        # Nivel 33: Shoto Todoroki
        pruebas_nivel_33 = [
            {'nombre': 'Hielo y Fuego', 'descripcion': 'Alcanza 185kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_185kg', 'meta_valor': 185, 'puntos_recompensa': 3400, 'es_secreta': False},
            {'nombre': 'Poder Equilibrado', 'descripcion': 'Levanta 90,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_90000kg', 'meta_valor': 90000, 'puntos_recompensa': 3900,
             'es_secreta': False},
            {'nombre': 'Héroe de Nueva Generación', 'descripcion': 'Mantén una racha de 75 días.',
             'clave_calculo': 'racha_dias_meta_75', 'meta_valor': 75, 'puntos_recompensa': 4400, 'es_secreta': False},
        ]

        # Nivel 34: Yujiro Hanma
        pruebas_nivel_34 = [
            {'nombre': 'El Ogre Más Fuerte', 'descripcion': 'Alcanza 200kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_200kg', 'meta_valor': 200, 'puntos_recompensa': 4000, 'es_secreta': False},
            {'nombre': 'Técnica del Demonio', 'descripcion': 'Supera 18 récords personales.',
             'clave_calculo': 'records_totales_meta_18', 'meta_valor': 18, 'puntos_recompensa': 5000,
             'es_secreta': False},
            {'nombre': 'La Criatura Más Fuerte', 'descripcion': 'Levanta 100,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_100000kg', 'meta_valor': 100000, 'puntos_recompensa': 5500,
             'es_secreta': False},
        ]

        # Nivel 35: Baki Hanma
        pruebas_nivel_35 = [
            {'nombre': 'Hijo del Ogre', 'descripcion': 'Alcanza 190kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_190kg', 'meta_valor': 190, 'puntos_recompensa': 3800, 'es_secreta': False},
            {'nombre': 'Técnicas de Combate', 'descripcion': 'Completa 160 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_160', 'meta_valor': 160, 'puntos_recompensa': 4300,
             'es_secreta': False},
            {'nombre': 'Espíritu Indomable', 'descripcion': 'Mantén una racha de 80 días.',
             'clave_calculo': 'racha_dias_meta_80', 'meta_valor': 80, 'puntos_recompensa': 4800, 'es_secreta': False},
        ]

        # Nivel 36: Saber (Artoria)
        pruebas_nivel_36 = [
            {'nombre': 'Excalibur', 'descripcion': 'Alcanza 195kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_195kg', 'meta_valor': 195, 'puntos_recompensa': 3900, 'es_secreta': False},
            {'nombre': 'Rey de los Caballeros', 'descripcion': 'Levanta 110,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_110000kg', 'meta_valor': 110000, 'puntos_recompensa': 4600,
             'es_secreta': False},
            {'nombre': 'Noble Phantasm', 'descripcion': 'Supera 20 récords personales.',
             'clave_calculo': 'records_totales_meta_20', 'meta_valor': 20, 'puntos_recompensa': 5200,
             'es_secreta': False},
        ]

        # Nivel 37: Gilgamesh
        pruebas_nivel_37 = [
            {'nombre': 'Gate of Babylon', 'descripcion': 'Alcanza 205kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_205kg', 'meta_valor': 205, 'puntos_recompensa': 4200, 'es_secreta': False},
            {'nombre': 'Rey de los Héroes', 'descripcion': 'Completa 170 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_170', 'meta_valor': 170, 'puntos_recompensa': 4800,
             'es_secreta': False},
            {'nombre': 'Ea - Espada de Ruptura', 'descripcion': 'Mantén una racha de 85 días.',
             'clave_calculo': 'racha_dias_meta_85', 'meta_valor': 85, 'puntos_recompensa': 5400, 'es_secreta': True},
        ]

        # Nivel 38: Escanor
        pruebas_nivel_38 = [
            {'nombre': 'Sunshine', 'descripcion': 'Alcanza 210kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_210kg', 'meta_valor': 210, 'puntos_recompensa': 4400, 'es_secreta': False},
            {'nombre': 'The One', 'descripcion': 'Levanta 120,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_120000kg', 'meta_valor': 120000, 'puntos_recompensa': 5000,
             'es_secreta': False},
            {'nombre': 'Orgullo del León', 'descripcion': 'Supera 22 récords personales.',
             'clave_calculo': 'records_totales_meta_22', 'meta_valor': 22, 'puntos_recompensa': 5600,
             'es_secreta': False},
        ]

        # Nivel 39: Meliodas
        pruebas_nivel_39 = [
            {'nombre': 'Full Counter', 'descripcion': 'Alcanza 215kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_215kg', 'meta_valor': 215, 'puntos_recompensa': 4600, 'es_secreta': False},
            {'nombre': 'Modo Demonio', 'descripcion': 'Completa 180 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_180', 'meta_valor': 180, 'puntos_recompensa': 5200,
             'es_secreta': False},
            {'nombre': 'Capitán de los Pecados', 'descripcion': 'Mantén una racha de 90 días.',
             'clave_calculo': 'racha_dias_meta_90', 'meta_valor': 90, 'puntos_recompensa': 5800, 'es_secreta': False},
        ]

        # Nivel 40: Ban
        pruebas_nivel_40 = [
            {'nombre': 'Snatch', 'descripcion': 'Alcanza 220kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_220kg', 'meta_valor': 220, 'puntos_recompensa': 4800, 'es_secreta': False},
            {'nombre': 'Inmortalidad', 'descripcion': 'Levanta 130,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_130000kg', 'meta_valor': 130000, 'puntos_recompensa': 5400,
             'es_secreta': False},
            {'nombre': 'Zorro del Pecado de la Avaricia', 'descripcion': 'Supera 25 récords personales.',
             'clave_calculo': 'records_totales_meta_25', 'meta_valor': 25, 'puntos_recompensa': 6000,
             'es_secreta': False},
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
             'clave_calculo': 'entrenos_completados_meta_200', 'meta_valor': 200, 'puntos_recompensa': 6500,
             'es_secreta': False},
            {'nombre': 'Trascendencia Mortal', 'descripcion': 'Levanta 150,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_150000kg', 'meta_valor': 150000, 'puntos_recompensa': 7000,
             'es_secreta': False},
        ]

        # Nivel 42: Vegeta (SSJ Blue)
        pruebas_nivel_42 = [
            {'nombre': 'Orgullo del Príncipe', 'descripcion': 'Alcanza 240kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_240kg', 'meta_valor': 240, 'puntos_recompensa': 6200, 'es_secreta': False},
            {'nombre': 'Final Flash Divino', 'descripcion': 'Mantén una racha de 100 días.',
             'clave_calculo': 'racha_dias_meta_100', 'meta_valor': 100, 'puntos_recompensa': 7500, 'es_secreta': False},
            {'nombre': 'Príncipe de los Saiyans', 'descripcion': 'Supera 30 récords personales.',
             'clave_calculo': 'records_totales_meta_30', 'meta_valor': 30, 'puntos_recompensa': 8000,
             'es_secreta': False},
        ]

        # Nivel 43: Beerus
        pruebas_nivel_43 = [
            {'nombre': 'Hakai', 'descripcion': 'Alcanza 250kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_250kg', 'meta_valor': 250, 'puntos_recompensa': 7000, 'es_secreta': False},
            {'nombre': 'El Despertar del Destructor', 'descripcion': 'Levanta 200,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_200000kg', 'meta_valor': 200000, 'puntos_recompensa': 8000,
             'es_secreta': False},
            {'nombre': 'Equilibrio Universal', 'descripcion': 'Completa 250 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_250', 'meta_valor': 250, 'puntos_recompensa': 8500,
             'es_secreta': False},
        ]

        # Nivel 44: Whis
        pruebas_nivel_44 = [
            {'nombre': 'Ultra Instinto', 'descripcion': 'Alcanza 260kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_260kg', 'meta_valor': 260, 'puntos_recompensa': 7500, 'es_secreta': False},
            {'nombre': 'Maestro de los Ángeles', 'descripcion': 'Mantén una racha de 120 días.',
             'clave_calculo': 'racha_dias_meta_120', 'meta_valor': 120, 'puntos_recompensa': 9000, 'es_secreta': False},
            {'nombre': 'Reversión Temporal', 'descripcion': 'Supera 35 récords personales.',
             'clave_calculo': 'records_totales_meta_35', 'meta_valor': 35, 'puntos_recompensa': 9500,
             'es_secreta': False},
        ]

        # Nivel 45: Gogeta Blue
        pruebas_nivel_45 = [
            {'nombre': 'Fusión Perfecta', 'descripcion': 'Alcanza 270kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_270kg', 'meta_valor': 270, 'puntos_recompensa': 8000, 'es_secreta': False},
            {'nombre': 'Soul Punisher', 'descripcion': 'Levanta 250,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_250000kg', 'meta_valor': 250000, 'puntos_recompensa': 9000,
             'es_secreta': False},
            {'nombre': 'Poder Combinado', 'descripcion': 'Completa 300 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_300', 'meta_valor': 300, 'puntos_recompensa': 10000,
             'es_secreta': False},
        ]

        # Nivel 46: Vegito Blue
        pruebas_nivel_46 = [
            {'nombre': 'Potara Fusion', 'descripcion': 'Alcanza 280kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_280kg', 'meta_valor': 280, 'puntos_recompensa': 8500, 'es_secreta': False},
            {'nombre': 'Final Kamehameha', 'descripcion': 'Mantén una racha de 150 días.',
             'clave_calculo': 'racha_dias_meta_150', 'meta_valor': 150, 'puntos_recompensa': 10000,
             'es_secreta': False},
            {'nombre': 'Fusión Eterna', 'descripcion': 'Supera 40 récords personales.',
             'clave_calculo': 'records_totales_meta_40', 'meta_valor': 40, 'puntos_recompensa': 11000,
             'es_secreta': False},
        ]

        # Nivel 47: Broly (Legendario)
        pruebas_nivel_47 = [
            {'nombre': 'Super Saiyan Legendario', 'descripcion': 'Alcanza 290kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_290kg', 'meta_valor': 290, 'puntos_recompensa': 9000, 'es_secreta': False},
            {'nombre': 'Poder Descontrolado', 'descripcion': 'Levanta 300,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_300000kg', 'meta_valor': 300000, 'puntos_recompensa': 10500,
             'es_secreta': False},
            {'nombre': 'Ira Infinita', 'descripcion': 'Completa 350 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_350', 'meta_valor': 350, 'puntos_recompensa': 12000,
             'es_secreta': False},
        ]

        # Nivel 48: Jiren
        pruebas_nivel_48 = [
            {'nombre': 'Poder Absoluto', 'descripcion': 'Alcanza 300kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_300kg', 'meta_valor': 300, 'puntos_recompensa': 10000,
             'es_secreta': False},
            {'nombre': 'Orgullo del Universo 11', 'descripcion': 'Mantén una racha de 180 días.',
             'clave_calculo': 'racha_dias_meta_180', 'meta_valor': 180, 'puntos_recompensa': 12000,
             'es_secreta': False},
            {'nombre': 'Más Allá de los Límites', 'descripcion': 'Supera 45 récords personales.',
             'clave_calculo': 'records_totales_meta_45', 'meta_valor': 45, 'puntos_recompensa': 13000,
             'es_secreta': False},
        ]

        # Nivel 49: Moro
        pruebas_nivel_49 = [
            {'nombre': 'Devorador de Planetas', 'descripcion': 'Alcanza 320kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_320kg', 'meta_valor': 320, 'puntos_recompensa': 11000,
             'es_secreta': False},
            {'nombre': 'Absorción de Energía', 'descripcion': 'Levanta 400,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_400000kg', 'meta_valor': 400000, 'puntos_recompensa': 13000,
             'es_secreta': False},
            {'nombre': 'Hechicero Galáctico', 'descripcion': 'Completa 400 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_400', 'meta_valor': 400, 'puntos_recompensa': 14000,
             'es_secreta': False},
        ]

        # Nivel 50: Gas
        pruebas_nivel_50 = [
            {'nombre': 'El Más Fuerte del Universo', 'descripcion': 'Alcanza 350kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_350kg', 'meta_valor': 350, 'puntos_recompensa': 12000,
             'es_secreta': False},
            {'nombre': 'Evolución Constante', 'descripcion': 'Mantén una racha de 200 días.',
             'clave_calculo': 'racha_dias_meta_200', 'meta_valor': 200, 'puntos_recompensa': 15000,
             'es_secreta': False},
            {'nombre': 'Heeter Force', 'descripcion': 'Supera 50 récords personales.',
             'clave_calculo': 'records_totales_meta_50', 'meta_valor': 50, 'puntos_recompensa': 16000,
             'es_secreta': True},
        ]

        # =============================================================================
        # NIVELES 51-60: LOS NINJAS LEGENDARIOS
        # =============================================================================

        print("\n🥷 === LOS NINJAS LEGENDARIOS (Niveles 51-60) ===")

        # Nivel 51: Itachi Uchiha
        pruebas_nivel_51 = [
            {'nombre': 'Tsukuyomi', 'descripcion': 'Alcanza 360kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_360kg', 'meta_valor': 360, 'puntos_recompensa': 13000,
             'es_secreta': False},
            {'nombre': 'Amaterasu', 'descripcion': 'Levanta 500,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_500000kg', 'meta_valor': 500000, 'puntos_recompensa': 16000,
             'es_secreta': False},
            {'nombre': 'Susanoo', 'descripcion': 'Completa 450 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_450', 'meta_valor': 450, 'puntos_recompensa': 17000,
             'es_secreta': False},
        ]

        # Nivel 52: Minato Namikaze
        pruebas_nivel_52 = [
            {'nombre': 'Hiraishin no Jutsu', 'descripcion': 'Alcanza 370kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_370kg', 'meta_valor': 370, 'puntos_recompensa': 14000,
             'es_secreta': False},
            {'nombre': 'Rasengan', 'descripcion': 'Mantén una racha de 250 días.',
             'clave_calculo': 'racha_dias_meta_250', 'meta_valor': 250, 'puntos_recompensa': 18000,
             'es_secreta': False},
            {'nombre': 'Cuarto Hokage', 'descripcion': 'Supera 60 récords personales.',
             'clave_calculo': 'records_totales_meta_60', 'meta_valor': 60, 'puntos_recompensa': 19000,
             'es_secreta': False},
        ]

        # Nivel 53: Hashirama Senju
        pruebas_nivel_53 = [
            {'nombre': 'Mokuton: Nacimiento del Mundo de Árboles', 'descripcion': 'Alcanza 380kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_380kg', 'meta_valor': 380, 'puntos_recompensa': 15000,
             'es_secreta': False},
            {'nombre': 'El Dios de los Shinobi', 'descripcion': 'Levanta 600,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_600000kg', 'meta_valor': 600000, 'puntos_recompensa': 19000,
             'es_secreta': False},
            {'nombre': 'Primer Hokage', 'descripcion': 'Completa 500 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_500', 'meta_valor': 500, 'puntos_recompensa': 20000,
             'es_secreta': False},
        ]

        # Nivel 54: Madara Uchiha
        pruebas_nivel_54 = [
            {'nombre': 'Susanoo Perfecto', 'descripcion': 'Alcanza 400kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_400kg', 'meta_valor': 400, 'puntos_recompensa': 16000,
             'es_secreta': False},
            {'nombre': 'Infinite Tsukuyomi', 'descripcion': 'Mantén una racha de 300 días.',
             'clave_calculo': 'racha_dias_meta_300', 'meta_valor': 300, 'puntos_recompensa': 22000,
             'es_secreta': False},
            {'nombre': 'Uchiha Legendario', 'descripcion': 'Supera 70 récords personales.',
             'clave_calculo': 'records_totales_meta_70', 'meta_valor': 70, 'puntos_recompensa': 24000,
             'es_secreta': False},
        ]

        # Nivel 55: Naruto (Modo Sabio)
        pruebas_nivel_55 = [
            {'nombre': 'Modo Sabio Perfecto', 'descripcion': 'Alcanza 420kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_420kg', 'meta_valor': 420, 'puntos_recompensa': 17000,
             'es_secreta': False},
            {'nombre': 'Rasengan Gigante', 'descripcion': 'Levanta 700,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_700000kg', 'meta_valor': 700000, 'puntos_recompensa': 23000,
             'es_secreta': False},
            {'nombre': 'Hokage de la Nueva Era', 'descripcion': 'Completa 600 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_600', 'meta_valor': 600, 'puntos_recompensa': 25000,
             'es_secreta': False},
        ]

        # Nivel 56: Sasuke (Rinnegan)
        pruebas_nivel_56 = [
            {'nombre': 'Rinnegan Awakening', 'descripcion': 'Alcanza 440kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_440kg', 'meta_valor': 440, 'puntos_recompensa': 18000,
             'es_secreta': False},
            {'nombre': 'Amenotejikara', 'descripcion': 'Mantén una racha de 350 días.',
             'clave_calculo': 'racha_dias_meta_350', 'meta_valor': 350, 'puntos_recompensa': 26000,
             'es_secreta': False},
            {'nombre': 'Último Uchiha', 'descripcion': 'Supera 80 récords personales.',
             'clave_calculo': 'records_totales_meta_80', 'meta_valor': 80, 'puntos_recompensa': 28000,
             'es_secreta': False},
        ]

        # Nivel 57: Obito (Juubi)
        pruebas_nivel_57 = [
            {'nombre': 'Jinchuriki del Juubi', 'descripcion': 'Alcanza 460kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_460kg', 'meta_valor': 460, 'puntos_recompensa': 19000,
             'es_secreta': False},
            {'nombre': 'Kamui Dimension', 'descripcion': 'Levanta 800,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_800000kg', 'meta_valor': 800000, 'puntos_recompensa': 27000,
             'es_secreta': False},
            {'nombre': 'Máscara de Tobi', 'descripcion': 'Completa 700 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_700', 'meta_valor': 700, 'puntos_recompensa': 30000,
             'es_secreta': False},
        ]

        # Nivel 58: Kaguya Otsutsuki
        pruebas_nivel_58 = [
            {'nombre': 'Diosa Conejo', 'descripcion': 'Alcanza 480kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_480kg', 'meta_valor': 480, 'puntos_recompensa': 20000,
             'es_secreta': False},
            {'nombre': 'All-Killing Ash Bones', 'descripcion': 'Mantén una racha de 400 días.',
             'clave_calculo': 'racha_dias_meta_400', 'meta_valor': 400, 'puntos_recompensa': 30000,
             'es_secreta': False},
            {'nombre': 'Madre del Chakra', 'descripcion': 'Supera 90 récords personales.',
             'clave_calculo': 'records_totales_meta_90', 'meta_valor': 90, 'puntos_recompensa': 32000,
             'es_secreta': False},
        ]

        # Nivel 59: Ichigo (Final)
        pruebas_nivel_59 = [
            {'nombre': 'True Bankai', 'descripcion': 'Alcanza 500kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_500kg', 'meta_valor': 500, 'puntos_recompensa': 25000,
             'es_secreta': False},
            {'nombre': 'Quincy-Shinigami-Hollow', 'descripcion': 'Levanta 1,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_1M', 'meta_valor': 1000000, 'puntos_recompensa': 35000,
             'es_secreta': False},
            {'nombre': 'Protector de Karakura', 'descripcion': 'Completa 800 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_800', 'meta_valor': 800, 'puntos_recompensa': 38000,
             'es_secreta': False},
        ]

        # Nivel 60: Aizen Sosuke
        pruebas_nivel_60 = [
            {'nombre': 'Kyoka Suigetsu', 'descripcion': 'Alcanza 520kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_520kg', 'meta_valor': 520, 'puntos_recompensa': 30000,
             'es_secreta': False},
            {'nombre': 'Hogyoku Fusion', 'descripcion': 'Mantén una racha de 500 días.',
             'clave_calculo': 'racha_dias_meta_500', 'meta_valor': 500, 'puntos_recompensa': 40000,
             'es_secreta': False},
            {'nombre': 'Trascendencia Shinigami', 'descripcion': 'Supera 100 récords personales.',
             'clave_calculo': 'records_totales_meta_100', 'meta_valor': 100, 'puntos_recompensa': 45000,
             'es_secreta': True},
        ]
        pruebas_nivel_61 = [
            {'nombre': 'Dominio del Ultra Instinto', 'descripcion': 'Alcanza 550kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_550kg', 'meta_valor': 550, 'puntos_recompensa': 50000},
            {'nombre': 'Esquiva Divina', 'descripcion': 'Levanta 1,200,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_1200000', 'meta_valor': 1200000, 'puntos_recompensa': 60000},
            {'nombre': 'Maestría del Vacío', 'descripcion': 'Completa 900 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_900', 'meta_valor': 900, 'puntos_recompensa': 65000},
        ]

        # Nivel 62: Vegeta (Ultra Ego)
        pruebas_nivel_62 = [
            {'nombre': 'Poder del Ultra Ego', 'descripcion': 'Alcanza 580kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_580kg', 'meta_valor': 580, 'puntos_recompensa': 55000},
            {'nombre': 'Voluntad de Destrucción', 'descripcion': 'Mantén una racha de 600 días.',
             'clave_calculo': 'racha_dias_meta_600', 'meta_valor': 600, 'puntos_recompensa': 68000},
            {'nombre': 'Príncipe de la Destrucción', 'descripcion': 'Supera 120 récords personales.',
             'clave_calculo': 'records_totales_meta_120', 'meta_valor': 120, 'puntos_recompensa': 72000},
        ]

        # Nivel 63: Gogeta (Ultra)
        pruebas_nivel_63 = [
            {'nombre': 'Fusión Trascendental', 'descripcion': 'Alcanza 600kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_600kg', 'meta_valor': 600, 'puntos_recompensa': 60000},
            {'nombre': 'Stardust Breaker Cósmico', 'descripcion': 'Levanta 1,600,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_1600000', 'meta_valor': 1600000, 'puntos_recompensa': 75000},
            {'nombre': 'Guerrero Definitivo', 'descripcion': 'Completa 1100 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_1100', 'meta_valor': 1100, 'puntos_recompensa': 80000},
        ]

        # Nivel 64: Vegito (Ultra)
        pruebas_nivel_64 = [
            {'nombre': 'Potara Divina', 'descripcion': 'Alcanza 620kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_620kg', 'meta_valor': 620, 'puntos_recompensa': 65000},
            {'nombre': 'Espada de Espíritu Final', 'descripcion': 'Mantén una racha de 650 días.',
             'clave_calculo': 'racha_dias_meta_650', 'meta_valor': 650, 'puntos_recompensa': 82000},
            {'nombre': 'El Guerrero Invencible', 'descripcion': 'Supera 140 récords personales.',
             'clave_calculo': 'records_totales_meta_140', 'meta_valor': 140, 'puntos_recompensa': 88000},
        ]

        # Nivel 65: Broly (Berserker)
        pruebas_nivel_65 = [
            {'nombre': 'Furia Berserker', 'descripcion': 'Alcanza 650kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_650kg', 'meta_valor': 650, 'puntos_recompensa': 70000},
            {'nombre': 'Explosión Gigante', 'descripcion': 'Levanta 2,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_2000000', 'meta_valor': 2000000, 'puntos_recompensa': 90000},
            {'nombre': 'Poder Incontenible', 'descripcion': 'Completa 1300 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_1300', 'meta_valor': 1300, 'puntos_recompensa': 95000},
        ]

        # Nivel 66: Jiren (Límite Roto)
        pruebas_nivel_66 = [
            {'nombre': 'Más Allá de la Fuerza', 'descripcion': 'Alcanza 680kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_680kg', 'meta_valor': 680, 'puntos_recompensa': 75000},
            {'nombre': 'Meditación de Poder', 'descripcion': 'Mantén una racha de 700 días.',
             'clave_calculo': 'racha_dias_meta_700', 'meta_valor': 700, 'puntos_recompensa': 98000},
            {'nombre': 'El Mortal más Fuerte', 'descripcion': 'Supera 160 récords personales.',
             'clave_calculo': 'records_totales_meta_160', 'meta_valor': 160, 'puntos_recompensa': 105000},
        ]

        # Nivel 67: Moro (Planeta)
        pruebas_nivel_67 = [
            {'nombre': 'Devorador de Mundos', 'descripcion': 'Alcanza 700kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_700kg', 'meta_valor': 700, 'puntos_recompensa': 80000},
            {'nombre': 'Magia Ancestral', 'descripcion': 'Levanta 2,500,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_2500000', 'meta_valor': 2500000, 'puntos_recompensa': 110000},
            {'nombre': 'Prisionero Galáctico', 'descripcion': 'Completa 1500 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_1500', 'meta_valor': 1500, 'puntos_recompensa': 115000},
        ]

        # Nivel 68: Gas (Evolución)
        pruebas_nivel_68 = [
            {'nombre': 'Deseo Cumplido', 'descripcion': 'Alcanza 750kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_750kg', 'meta_valor': 750, 'puntos_recompensa': 85000},
            {'nombre': 'Armamento Heeter', 'descripcion': 'Mantén una racha de 750 días.',
             'clave_calculo': 'racha_dias_meta_750', 'meta_valor': 750, 'puntos_recompensa': 120000},
            {'nombre': 'El Más Fuerte (Temporalmente)', 'descripcion': 'Supera 180 récords personales.',
             'clave_calculo': 'records_totales_meta_180', 'meta_valor': 180, 'puntos_recompensa': 125000},
        ]

        # Nivel 69: Black Frieza
        pruebas_nivel_69 = [
            {'nombre': 'Forma Definitiva', 'descripcion': 'Alcanza 800kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_800kg', 'meta_valor': 800, 'puntos_recompensa': 90000},
            {'nombre': 'Emperador del Universo', 'descripcion': 'Levanta 3,500,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_3500000', 'meta_valor': 3500000, 'puntos_recompensa': 130000},
            {'nombre': 'Venganza Dorada', 'descripcion': 'Completa 1700 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_1700', 'meta_valor': 1700, 'puntos_recompensa': 135000},
        ]

        # Nivel 70: Granolah
        pruebas_nivel_70 = [
            {'nombre': 'El Ojo Certero', 'descripcion': 'Alcanza 850kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_850kg', 'meta_valor': 850, 'puntos_recompensa': 95000},
            {'nombre': 'El Último Cerealiano', 'descripcion': 'Mantén una racha de 800 días.',
             'clave_calculo': 'racha_dias_meta_800', 'meta_valor': 800, 'puntos_recompensa': 140000},
            {'nombre': 'Punto Vital', 'descripcion': 'Supera 200 récords personales.',
             'clave_calculo': 'records_totales_meta_200', 'meta_valor': 200, 'puntos_recompensa': 150000},
        ]

        # =============================================================================
        # NIVELES 71-75: LOS CÓSMICOS
        # =============================================================================

        self.stdout.write(self.style.HTTP_INFO("\n🌌 === LOS CÓSMICOS (Niveles 71-75) ==="))

        # Nivel 71: Sailor Moon
        pruebas_nivel_71 = [
            {'nombre': 'Cristal de Plata', 'descripcion': 'Alcanza 900kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_900kg', 'meta_valor': 900, 'puntos_recompensa': 100000},
            {'nombre': 'Por el Amor y la Justicia', 'descripcion': 'Levanta 5,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_5000000', 'meta_valor': 5000000, 'puntos_recompensa': 155000},
            {'nombre': 'Guerrera de la Luna', 'descripcion': 'Completa 2000 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_2000', 'meta_valor': 2000, 'puntos_recompensa': 160000},
        ]

        # Nivel 72: Seiya de Pegaso
        pruebas_nivel_72 = [
            {'nombre': 'Meteoro de Pegaso', 'descripcion': 'Alcanza 950kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_950kg', 'meta_valor': 950, 'puntos_recompensa': 110000},
            {'nombre': 'Armadura Divina', 'descripcion': 'Mantén una racha de 850 días.',
             'clave_calculo': 'racha_dias_meta_850', 'meta_valor': 850, 'puntos_recompensa': 165000},
            {'nombre': 'Arde, Cosmos', 'descripcion': 'Supera 220 récords personales.',
             'clave_calculo': 'records_totales_meta_220', 'meta_valor': 220, 'puntos_recompensa': 170000},
        ]

        # Nivel 73: Saga de Géminis
        pruebas_nivel_73 = [
            {'nombre': 'Explosión de Galaxias', 'descripcion': 'Alcanza 1000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1000kg', 'meta_valor': 1000, 'puntos_recompensa': 120000},
            {'nombre': 'Otra Dimensión', 'descripcion': 'Levanta 7,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_7000000', 'meta_valor': 7000000, 'puntos_recompensa': 175000},
            {'nombre': 'El Patriarca', 'descripcion': 'Completa 2400 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_2400', 'meta_valor': 2400, 'puntos_recompensa': 180000},
        ]

        # Nivel 74: Shaka de Virgo
        pruebas_nivel_74 = [
            {'nombre': 'El Tesoro del Cielo', 'descripcion': 'Alcanza 1100kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1100kg', 'meta_valor': 1100, 'puntos_recompensa': 130000},
            {'nombre': 'El Hombre más Cercano a Dios', 'descripcion': 'Mantén una racha de 900 días.',
             'clave_calculo': 'racha_dias_meta_900', 'meta_valor': 900, 'puntos_recompensa': 185000},
            {'nombre': 'Sexto Sentido', 'descripcion': 'Supera 250 récords personales.',
             'clave_calculo': 'records_totales_meta_250', 'meta_valor': 250, 'puntos_recompensa': 190000},
        ]

        # Nivel 75: Athena
        pruebas_nivel_75 = [
            {'nombre': 'El Sello de Athena', 'descripcion': 'Alcanza 1200kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1200kg', 'meta_valor': 1200, 'puntos_recompensa': 140000},
            {'nombre': 'Diosa de la Sabiduría', 'descripcion': 'Levanta 9,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_9000000', 'meta_valor': 9000000, 'puntos_recompensa': 200000},
            {'nombre': 'Protectora de la Tierra', 'descripcion': 'Completa 2800 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_2800', 'meta_valor': 2800, 'puntos_recompensa': 210000},
        ]
        self.stdout.write(self.style.HTTP_INFO("\n🌌 === LOS CÓSMICOS (Continuación) (Niveles 76-80) ==="))

        # Nivel 76: Hades
        pruebas_nivel_76 = [
            {'nombre': 'Inframundo', 'descripcion': 'Alcanza 1300kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1300kg', 'meta_valor': 1300, 'puntos_recompensa': 150000},
            {'nombre': 'El Gran Eclipse', 'descripcion': 'Levanta 10,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_10000000', 'meta_valor': 10000000, 'puntos_recompensa': 220000},
            {'nombre': 'Rey del Inframundo', 'descripcion': 'Completa 3000 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_3000', 'meta_valor': 3000, 'puntos_recompensa': 230000},
        ]

        # Nivel 77: Simon (Gurren Lagann)
        pruebas_nivel_77 = [
            {'nombre': 'Taladro Giga', 'descripcion': 'Alcanza 1400kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1400kg', 'meta_valor': 1400, 'puntos_recompensa': 160000},
            {'nombre': '¡Atraviesa los Cielos!', 'descripcion': 'Mantén una racha de 950 días.',
             'clave_calculo': 'racha_dias_meta_950', 'meta_valor': 950, 'puntos_recompensa': 240000},
            {'nombre': 'Poder Espiral', 'descripcion': 'Supera 280 récords personales.',
             'clave_calculo': 'records_totales_meta_280', 'meta_valor': 280, 'puntos_recompensa': 250000},
        ]

        # Nivel 78: Anti-Spiral
        pruebas_nivel_78 = [
            {'nombre': 'Universo Alterno', 'descripcion': 'Alcanza 1500kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1500kg', 'meta_valor': 1500, 'puntos_recompensa': 170000},
            {'nombre': 'Desesperación Infinita', 'descripcion': 'Levanta 15,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_15000000', 'meta_valor': 15000000, 'puntos_recompensa': 260000},
            {'nombre': 'Némesis Espiral', 'descripcion': 'Completa 3400 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_3400', 'meta_valor': 3400, 'puntos_recompensa': 270000},
        ]

        # Nivel 79: Tengen Toppa Gurren Lagann
        pruebas_nivel_79 = [
            {'nombre': 'Giga Drill Break', 'descripcion': 'Alcanza 1600kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1600kg', 'meta_valor': 1600, 'puntos_recompensa': 180000},
            {'nombre': 'Probabilidad Cósmica', 'descripcion': 'Mantén una racha de 1000 días (¡Casi 3 años!).',
             'clave_calculo': 'racha_dias_meta_1000', 'meta_valor': 1000, 'puntos_recompensa': 280000},
            {'nombre': 'El Poder de la Humanidad', 'descripcion': 'Supera 300 récords personales.',
             'clave_calculo': 'records_totales_meta_300', 'meta_valor': 300, 'puntos_recompensa': 290000},
        ]

        # Nivel 80: Super Tengen Toppa Gurren Lagann
        pruebas_nivel_80 = [
            {'nombre': 'Super Giga Drill Break', 'descripcion': 'Alcanza 1700kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1700kg', 'meta_valor': 1700, 'puntos_recompensa': 190000},
            {'nombre': 'Más Grande que el Universo', 'descripcion': 'Levanta 20,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_20000000', 'meta_valor': 20000000, 'puntos_recompensa': 300000},
            {'nombre': 'La Voluntad Encarnada', 'descripcion': 'Completa 3800 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_3800', 'meta_valor': 3800, 'puntos_recompensa': 310000},
        ]

        # =============================================================================
        # NIVELES 81-90: LOS OMNIPOTENTES
        # =============================================================================

        self.stdout.write(self.style.HTTP_INFO("\n♾️ === LOS OMNIPOTENTES (Niveles 81-90) ==="))

        # Nivel 81: Madoka Kaname (Diosa)
        pruebas_nivel_81 = [
            {'nombre': 'Ley del Ciclo', 'descripcion': 'Alcanza 1800kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1800kg', 'meta_valor': 1800, 'puntos_recompensa': 200000},
            {'nombre': 'Flecha de la Esperanza', 'descripcion': 'Levanta 25,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_25000000', 'meta_valor': 25000000, 'puntos_recompensa': 320000},
            {'nombre': 'Concepto Universal', 'descripcion': 'Completa 4000 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_4000', 'meta_valor': 4000, 'puntos_recompensa': 330000},
        ]

        # Nivel 82: Homura Akemi (Demonio)
        pruebas_nivel_82 = [
            {'nombre': 'Manipulación del Tiempo', 'descripcion': 'Alcanza 1900kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_1900kg', 'meta_valor': 1900, 'puntos_recompensa': 220000},
            {'nombre': 'Reescritura del Universo', 'descripcion': 'Mantén una racha de 1100 días.',
             'clave_calculo': 'racha_dias_meta_1100', 'meta_valor': 1100, 'puntos_recompensa': 340000},
            {'nombre': 'Amor Absoluto', 'descripcion': 'Supera 350 récords personales.',
             'clave_calculo': 'records_totales_meta_350', 'meta_valor': 350, 'puntos_recompensa': 350000},
        ]

        # Nivel 83: Haruhi Suzumiya
        pruebas_nivel_83 = [
            {'nombre': 'Creación de Realidad', 'descripcion': 'Alcanza 2000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_2000kg', 'meta_valor': 2000, 'puntos_recompensa': 240000},
            {'nombre': 'Brigada SOS', 'descripcion': 'Levanta 35,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_35000000', 'meta_valor': 35000000, 'puntos_recompensa': 360000},
            {'nombre': 'Diosa Inconsciente', 'descripcion': 'Completa 4400 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_4400', 'meta_valor': 4400, 'puntos_recompensa': 370000},
        ]

        # Nivel 84: The Truth (FMA)
        pruebas_nivel_84 = [
            {'nombre': 'La Puerta de la Verdad', 'descripcion': 'Alcanza 2200kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_2200kg', 'meta_valor': 2200, 'puntos_recompensa': 260000},
            {'nombre': 'Todo es Uno, Uno es Todo', 'descripcion': 'Mantén una racha de 1200 días.',
             'clave_calculo': 'racha_dias_meta_1200', 'meta_valor': 1200, 'puntos_recompensa': 380000},
            {'nombre': 'Conocimiento Absoluto', 'descripcion': 'Supera 400 récords personales.',
             'clave_calculo': 'records_totales_meta_400', 'meta_valor': 400, 'puntos_recompensa': 390000},
        ]

        # Nivel 85: Giorno Giovanna (GER)
        pruebas_nivel_85 = [
            {'nombre': 'Gold Experience Requiem', 'descripcion': 'Alcanza 2400kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_2400kg', 'meta_valor': 2400, 'puntos_recompensa': 280000},
            {'nombre': 'Retorno a Cero', 'descripcion': 'Levanta 45,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_45000000', 'meta_valor': 45000000, 'puntos_recompensa': 400000},
            {'nombre': 'El Sueño Dorado', 'descripcion': 'Completa 4800 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_4800', 'meta_valor': 4800, 'puntos_recompensa': 410000},
        ]

        # Nivel 86: Rimuru Tempest
        pruebas_nivel_86 = [
            {'nombre': 'Gran Sabio', 'descripcion': 'Alcanza 2600kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_2600kg', 'meta_valor': 2600, 'puntos_recompensa': 300000},
            {'nombre': 'Depredador', 'descripcion': 'Mantén una racha de 1300 días.',
             'clave_calculo': 'racha_dias_meta_1300', 'meta_valor': 1300, 'puntos_recompensa': 420000},
            {'nombre': 'Señor Demonio', 'descripcion': 'Supera 450 récords personales.',
             'clave_calculo': 'records_totales_meta_450', 'meta_valor': 450, 'puntos_recompensa': 430000},
        ]

        # Nivel 87: Ainz Ooal Gown
        pruebas_nivel_87 = [
            {'nombre': 'El Objetivo de Toda Vida es la Muerte', 'descripcion': 'Alcanza 2800kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_2800kg', 'meta_valor': 2800, 'puntos_recompensa': 320000},
            {'nombre': 'Rey Hechicero', 'descripcion': 'Levanta 60,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_60000000', 'meta_valor': 60000000, 'puntos_recompensa': 440000},
            {'nombre': 'Gobernante de Nazarick', 'descripcion': 'Completa 5200 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_5200', 'meta_valor': 5200, 'puntos_recompensa': 450000},
        ]

        # Nivel 88: Saitama (Completo)
        pruebas_nivel_88 = [
            {'nombre': 'Puñetazo Serio', 'descripcion': 'Alcanza 3000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_3000kg', 'meta_valor': 3000, 'puntos_recompensa': 340000},
            {'nombre': 'Héroe por Hobby', 'descripcion': 'Mantén una racha de 1400 días.',
             'clave_calculo': 'racha_dias_meta_1400', 'meta_valor': 1400, 'puntos_recompensa': 460000},
            {'nombre': 'Limitador Roto (Real)', 'descripcion': 'Supera 500 récords personales.',
             'clave_calculo': 'records_totales_meta_500', 'meta_valor': 500, 'puntos_recompensa': 470000},
        ]

        # Nivel 89: Zeno Sama
        pruebas_nivel_89 = [
            {'nombre': 'Borrado Universal', 'descripcion': 'Alcanza 3500kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_3500kg', 'meta_valor': 3500, 'puntos_recompensa': 360000},
            {'nombre': 'Rey de Todo', 'descripcion': 'Levanta 80,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_80000000', 'meta_valor': 80000000, 'puntos_recompensa': 480000},
            {'nombre': 'Juego Cósmico', 'descripcion': 'Completa 5600 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_5600', 'meta_valor': 5600, 'puntos_recompensa': 490000},
        ]

        # Nivel 90: Daishinkan
        pruebas_nivel_90 = [
            {'nombre': 'Gran Sacerdote', 'descripcion': 'Alcanza 4000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_4000kg', 'meta_valor': 4000, 'puntos_recompensa': 380000},
            {'nombre': 'Orden Angelical', 'descripcion': 'Mantén una racha de 1500 días.',
             'clave_calculo': 'racha_dias_meta_1500', 'meta_valor': 1500, 'puntos_recompensa': 500000},
            {'nombre': 'El Ser más Poderoso', 'descripcion': 'Supera 550 récords personales.',
             'clave_calculo': 'records_totales_meta_550', 'meta_valor': 550, 'puntos_recompensa': 510000},
        ]

        # =============================================================================
        # NIVELES 91-99: LOS ABSOLUTOS
        # =============================================================================

        self.stdout.write(self.style.HTTP_INFO("\n🌟 === LOS ABSOLUTOS (Niveles 91-99) ==="))

        # Nivel 91: Yogiri Takatou
        pruebas_nivel_91 = [
            {'nombre': 'Muerte Instantánea', 'descripcion': 'Alcanza 4200kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_4200kg', 'meta_valor': 4200, 'puntos_recompensa': 400000},
            {'nombre': 'Fin de la Línea', 'descripcion': 'Levanta 95,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_95000000', 'meta_valor': 95000000, 'puntos_recompensa': 520000},
            {'nombre': 'El Fin', 'descripcion': 'Completa 6000 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_6000', 'meta_valor': 6000, 'puntos_recompensa': 530000},
        ]

        # Nivel 92: Arceus
        pruebas_nivel_92 = [
            {'nombre': 'Juicio', 'descripcion': 'Alcanza 4400kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_4400kg', 'meta_valor': 4400, 'puntos_recompensa': 420000},
            {'nombre': 'Las Mil Manos', 'descripcion': 'Mantén una racha de 1600 días.',
             'clave_calculo': 'racha_dias_meta_1600', 'meta_valor': 1600, 'puntos_recompensa': 540000},
            {'nombre': 'El Pokémon Alfa', 'descripcion': 'Supera 600 récords personales.',
             'clave_calculo': 'records_totales_meta_600', 'meta_valor': 600, 'puntos_recompensa': 550000},
        ]

        # Nivel 93: Akuto Sai
        pruebas_nivel_93 = [
            {'nombre': 'Rey Demonio', 'descripcion': 'Alcanza 4600kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_4600kg', 'meta_valor': 4600, 'puntos_recompensa': 440000},
            {'nombre': 'Control de Historias', 'descripcion': 'Levanta 110,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_110000000', 'meta_valor': 110000000, 'puntos_recompensa': 560000},
            {'nombre': 'El Futuro Rey Demonio', 'descripcion': 'Completa 6400 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_6400', 'meta_valor': 6400, 'puntos_recompensa': 570000},
        ]

        # Nivel 94: Featherine Augustus Aurora
        pruebas_nivel_94 = [
            {'nombre': 'La Bruja del Teatro', 'descripcion': 'Alcanza 4800kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_4800kg', 'meta_valor': 4800, 'puntos_recompensa': 460000},
            {'nombre': 'Reescritura de la Trama', 'descripcion': 'Mantén una racha de 1700 días.',
             'clave_calculo': 'racha_dias_meta_1700', 'meta_valor': 1700, 'puntos_recompensa': 580000},
            {'nombre': 'La Creadora', 'descripcion': 'Supera 650 récords personales.',
             'clave_calculo': 'records_totales_meta_650', 'meta_valor': 650, 'puntos_recompensa': 590000},
        ]

        # Nivel 95: Lambdadelta
        pruebas_nivel_95 = [
            {'nombre': 'La Bruja de la Certeza', 'descripcion': 'Alcanza 5000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5000kg', 'meta_valor': 5000, 'puntos_recompensa': 480000},
            {'nombre': 'Certeza Absoluta', 'descripcion': 'Levanta 130,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_130000000', 'meta_valor': 130000000, 'puntos_recompensa': 600000},
            {'nombre': 'El Juego Eterno', 'descripcion': 'Completa 6800 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_6800', 'meta_valor': 6800, 'puntos_recompensa': 610000},
        ]

        # Nivel 96: Bernkastel
        pruebas_nivel_96 = [
            {'nombre': 'La Bruja de los Milagros', 'descripcion': 'Alcanza 5200kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5200kg', 'meta_valor': 5200, 'puntos_recompensa': 500000},
            {'nombre': 'Milagro Infinito', 'descripcion': 'Mantén una racha de 1800 días.',
             'clave_calculo': 'racha_dias_meta_1800', 'meta_valor': 1800, 'puntos_recompensa': 620000},
            {'nombre': 'El Gato en la Caja', 'descripcion': 'Supera 700 récords personales.',
             'clave_calculo': 'records_totales_meta_700', 'meta_valor': 700, 'puntos_recompensa': 630000},
        ]

        # Nivel 97: Kami Tenchi
        pruebas_nivel_97 = [
            {'nombre': 'El Dios de Tenchi', 'descripcion': 'Alcanza 5400kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5400kg', 'meta_valor': 5400, 'puntos_recompensa': 520000},
            {'nombre': 'Las Alas del Light Hawk', 'descripcion': 'Levanta 150,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_150000000', 'meta_valor': 150000000, 'puntos_recompensa': 640000},
            {'nombre': 'Omnipresencia', 'descripcion': 'Completa 7200 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_7200', 'meta_valor': 7200, 'puntos_recompensa': 650000},
        ]

        # Nivel 98: Hajun
        pruebas_nivel_98 = [
            {'nombre': 'El Dios Hadou', 'descripcion': 'Alcanza 5600kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5600kg', 'meta_valor': 5600, 'puntos_recompensa': 540000},
            {'nombre': 'La Ley del Trono', 'descripcion': 'Mantén una racha de 1900 días.',
             'clave_calculo': 'racha_dias_meta_1900', 'meta_valor': 1900, 'puntos_recompensa': 660000},
            {'nombre': 'El Único en el Cielo', 'descripcion': 'Supera 750 récords personales.',
             'clave_calculo': 'records_totales_meta_750', 'meta_valor': 750, 'puntos_recompensa': 670000},
        ]

        # Nivel 99: Azathoth
        pruebas_nivel_99 = [
            {'nombre': 'El Sultán Demonio Ciego e Idiota', 'descripcion': 'Alcanza 5800kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5800kg', 'meta_valor': 5800, 'puntos_recompensa': 560000},
            {'nombre': 'El Caos Reptante', 'descripcion': 'Levanta 170,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_170000000', 'meta_valor': 170000000, 'puntos_recompensa': 680000},
            {'nombre': 'El Centro del Infinito', 'descripcion': 'Completa 7600 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_7600', 'meta_valor': 7600, 'puntos_recompensa': 690000},
        ]
        # Nivel 100: The One Above All - El nivel máximo
        pruebas_nivel_100 = [
            {'nombre': 'Omnipotencia Absoluta', 'descripcion': 'Alcanza 5000kg en Press de Banca.',
             'clave_calculo': 'rm_banca_meta_5000kg', 'meta_valor': 5000, 'puntos_recompensa': 500000,
             'es_secreta': False},
            {'nombre': 'Más Allá de la Comprensión', 'descripcion': 'Completa 10000 entrenamientos.',
             'clave_calculo': 'entrenos_completados_meta_10000', 'meta_valor': 10000, 'puntos_recompensa': 750000,
             'es_secreta': False},
            {'nombre': 'El Uno Sobre Todo', 'descripcion': 'Mantén el puesto #1 en el ranking durante 365 días.',
             'clave_calculo': 'ranking_top_1_por_365_dias', 'meta_valor': 365, 'puntos_recompensa': 1000000,
             'es_secreta': False},
            {'nombre': 'Trascendencia Absoluta', 'descripcion': 'Levanta 100,000,000kg de volumen total.',
             'clave_calculo': 'volumen_total_meta_100M', 'meta_valor': 100000000, 'puntos_recompensa': 2000000,
             'es_secreta': True},
        ]

        # =============================================================================
        # CREAR TODAS LAS PRUEBAS
        # =============================================================================

        # Definimos todas las pruebas dentro de una lista, igual que en tu script
        # NOTA: Asegúrate de que todas las variables (ej. pruebas_nivel_44) estén definidas correctamente.

        # Lista de todas las pruebas a crear
        # REEMPLAZA TU LISTA 'todas_las_pruebas' CON ESTA VERSIÓN COMPLETA

        todas_las_pruebas = [
            # Niveles 1-10: Los Aspirantes
            (1, pruebas_nivel_1), (2, pruebas_nivel_2), (3, pruebas_nivel_3), (4, pruebas_nivel_4),
            (5, pruebas_nivel_5),
            (6, pruebas_nivel_6), (7, pruebas_nivel_7), (8, pruebas_nivel_8), (9, pruebas_nivel_9),
            (10, pruebas_nivel_10),

            # Niveles 11-20: Los Guerreros Emergentes
            (11, pruebas_nivel_11), (12, pruebas_nivel_12), (13, pruebas_nivel_13), (14, pruebas_nivel_14),
            (15, pruebas_nivel_15),
            (16, pruebas_nivel_16), (17, pruebas_nivel_17), (18, pruebas_nivel_18), (19, pruebas_nivel_19),
            (20, pruebas_nivel_20),

            # Niveles 21-30: Los Guerreros Élite
            (21, pruebas_nivel_21), (22, pruebas_nivel_22), (23, pruebas_nivel_23), (24, pruebas_nivel_24),
            (25, pruebas_nivel_25),
            (26, pruebas_nivel_26), (27, pruebas_nivel_27), (28, pruebas_nivel_28), (29, pruebas_nivel_29),
            (30, pruebas_nivel_30),

            # Niveles 31-40: Los Legendarios
            (31, pruebas_nivel_31), (32, pruebas_nivel_32), (33, pruebas_nivel_33), (34, pruebas_nivel_34),
            (35, pruebas_nivel_35),
            (36, pruebas_nivel_36), (37, pruebas_nivel_37), (38, pruebas_nivel_38), (39, pruebas_nivel_39),
            (40, pruebas_nivel_40),

            # Niveles 41-50: Los Saiyans Divinos
            (41, pruebas_nivel_41), (42, pruebas_nivel_42), (43, pruebas_nivel_43), (44, pruebas_nivel_44),
            (45, pruebas_nivel_45),
            (46, pruebas_nivel_46), (47, pruebas_nivel_47), (48, pruebas_nivel_48), (49, pruebas_nivel_49),
            (50, pruebas_nivel_50),

            # Niveles 51-60: Los Ninjas Legendarios
            (51, pruebas_nivel_51), (52, pruebas_nivel_52), (53, pruebas_nivel_53), (54, pruebas_nivel_54),
            (55, pruebas_nivel_55),
            (56, pruebas_nivel_56), (57, pruebas_nivel_57), (58, pruebas_nivel_58), (59, pruebas_nivel_59),
            (60, pruebas_nivel_60),

            # Niveles 61-70: Los Divinos Cósmicos
            (61, pruebas_nivel_61), (62, pruebas_nivel_62), (63, pruebas_nivel_63), (64, pruebas_nivel_64),
            (65, pruebas_nivel_65),
            (66, pruebas_nivel_66), (67, pruebas_nivel_67), (68, pruebas_nivel_68), (69, pruebas_nivel_69),
            (70, pruebas_nivel_70),

            # Niveles 71-80: Los Cósmicos
            (71, pruebas_nivel_71), (72, pruebas_nivel_72), (73, pruebas_nivel_73), (74, pruebas_nivel_74),
            (75, pruebas_nivel_75),
            (76, pruebas_nivel_76), (77, pruebas_nivel_77), (78, pruebas_nivel_78), (79, pruebas_nivel_79),
            (80, pruebas_nivel_80),

            # Niveles 81-90: Los Omnipotentes
            (81, pruebas_nivel_81), (82, pruebas_nivel_82), (83, pruebas_nivel_83), (84, pruebas_nivel_84),
            (85, pruebas_nivel_85),
            (86, pruebas_nivel_86), (87, pruebas_nivel_87), (88, pruebas_nivel_88), (89, pruebas_nivel_89),
            (90, pruebas_nivel_90),

            # Niveles 91-99: Los Absolutos
            (91, pruebas_nivel_91), (92, pruebas_nivel_92), (93, pruebas_nivel_93), (94, pruebas_nivel_94),
            (95, pruebas_nivel_95),
            (96, pruebas_nivel_96), (97, pruebas_nivel_97), (98, pruebas_nivel_98), (99, pruebas_nivel_99),

            # Nivel 100: The One Above All
            (100, pruebas_nivel_100),
        ]

        total_pruebas_creadas = 0
        for nivel, pruebas_data in todas_las_pruebas:
            total_pruebas_creadas += self.crear_pruebas_para_arquetipo(nivel, pruebas_data)

        self.stdout.write(self.style.SUCCESS(f"\n🎉 ¡CREACIÓN COMPLETADA!"))
        self.stdout.write(f"⚔️ Total de Pruebas Legendarias creadas: {total_pruebas_creadas}")
        self.stdout.write(f"🏆 Total de Arquetipos con pruebas: {len(todas_las_pruebas)}")
        self.stdout.write(f"📊 Pruebas en la base de datos: {PruebaLegendaria.objects.count()}")
        self.stdout.write(self.style.SUCCESS("\n🚀 ¡El Códice de las Leyendas está 100% COMPLETO!"))

    def crear_pruebas_para_arquetipo(self, nivel, pruebas_data):
        """
        Crea pruebas para un arquetipo específico.
        Ahora es un método de la clase Command.
        """
        try:
            arquetipo = Arquetipo.objects.get(nivel=nivel)
            self.stdout.write(
                self.style.HTTP_INFO(f"\n⚔️ Creando pruebas para Nivel {nivel}: {arquetipo.titulo_arquetipo}..."))

            pruebas_creadas = 0
            for prueba_data in pruebas_data:
                try:
                    PruebaLegendaria.objects.create(arquetipo=arquetipo, **prueba_data)
                    self.stdout.write(f"   ✅ {prueba_data['nombre']}")
                    pruebas_creadas += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ ERROR al crear '{prueba_data['nombre']}': {e}"))

            return pruebas_creadas
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


        except Arquetipo.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Arquetipo nivel {nivel} no encontrado"))
            return 0
