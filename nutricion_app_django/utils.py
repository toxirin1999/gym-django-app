"""
Utilidades para los cálculos de nutrición
Adaptadas de la aplicación original de tkinter a Django
"""
import math


class CalculadoraNutricion:
    """Clase para realizar cálculos nutricionales basados en el libro The Muscle & Strength Pyramid"""

    @staticmethod
    def calcular_calorias_mantenimiento(peso, factor_actividad):
        """
        Calcula las calorías de mantenimiento usando la fórmula del libro

        Args:
            peso (float): Peso en kg
            factor_actividad (float): Factor de actividad (1.3 - 2.2)

        Returns:
            float: Calorías de mantenimiento
        """
        # Fórmula base: peso en kg × 22
        calorias_base = peso * 22

        # Aplicar factor de actividad
        calorias_mantenimiento = calorias_base * factor_actividad

        return round(calorias_mantenimiento, 0)

    @staticmethod
    def calcular_calorias_objetivo(calorias_mantenimiento, objetivo):
        """
        Calcula las calorías objetivo según el objetivo del usuario
        
        Args:
            calorias_mantenimiento (float): Calorías de mantenimiento
            objetivo (str): Objetivo del usuario
            
        Returns:
            tuple: (calorias_objetivo, deficit_superavit_porcentaje)
        """
        if objetivo == "Pérdida de grasa":
            # Déficit del 15-25% (usamos 20% como promedio)
            deficit_porcentaje = 20
            calorias_objetivo = calorias_mantenimiento * (1 - deficit_porcentaje / 100)
            return round(calorias_objetivo, 0), -deficit_porcentaje

        elif objetivo == "Ganancia muscular":
            # Superávit del 10-20% (usamos 15% como promedio)
            superavit_porcentaje = 15
            calorias_objetivo = calorias_mantenimiento * (1 + superavit_porcentaje / 100)
            return round(calorias_objetivo, 0), superavit_porcentaje

        else:  # Mantenimiento
            return calorias_mantenimiento, 0

    @staticmethod
    def calcular_peso_objetivo_semanal(peso, objetivo):
        """
        Calcula el cambio de peso objetivo semanal
        
        Args:
            peso (float): Peso actual en kg
            objetivo (str): Objetivo del usuario
            
        Returns:
            float: Cambio de peso semanal esperado
        """
        if objetivo == "Pérdida de grasa":
            # Pérdida de peso recomendada: 0.5-1% del peso corporal por semana
            return round(-(peso * 0.007), 2)  # 0.7% promedio

        elif objetivo == "Ganancia muscular":
            # Ganancia de peso recomendada: 0.25-0.5% del peso corporal por semana
            return round(peso * 0.004, 2)  # 0.4% promedio

        else:  # Mantenimiento
            return 0

    @staticmethod
    def obtener_factor_actividad_por_nivel(nivel_actividad):
        """
        Obtiene el factor de actividad recomendado según el nivel
        
        Args:
            nivel_actividad (str): Nivel de actividad del usuario
            
        Returns:
            float: Factor de actividad recomendado
        """
        factores = {
            "Sedentario": 1.5,
            "Ligeramente activo": 1.7,
            "Activo": 1.9,
            "Muy activo": 2.1
        }
        return factores.get(nivel_actividad, 1.7)

    @staticmethod
    def calcular_proteina_gramos(peso, altura, objetivo, metodo="peso_corporal", gramos_por_kg=None):
        """
        Calcula los gramos de proteína necesarios
        
        Args:
            peso (float): Peso en kg
            altura (int): Altura en cm
            objetivo (str): Objetivo del usuario
            metodo (str): Método de cálculo ("peso_corporal" o "altura_cm")
            gramos_por_kg (float): Gramos por kg si se especifica
            
        Returns:
            float: Gramos de proteína
        """
        if metodo == "altura_cm":
            return float(altura)

        # Método por peso corporal
        if gramos_por_kg is None:
            # Valores por defecto según objetivo
            if objetivo == "Pérdida de grasa":
                gramos_por_kg = 2.4  # Promedio del rango 2.2-2.6
            elif objetivo == "Ganancia muscular":
                gramos_por_kg = 1.9  # Promedio del rango 1.6-2.2
            else:  # Mantenimiento
                gramos_por_kg = 2.0

        return round(peso * gramos_por_kg, 1)

    @staticmethod
    def calcular_macronutrientes(calorias_objetivo, proteina_gramos, grasa_porcentaje, peso):
        """
        Calcula la distribución completa de macronutrientes
        
        Args:
            calorias_objetivo (float): Calorías objetivo
            proteina_gramos (float): Gramos de proteína
            grasa_porcentaje (float): Porcentaje de calorías de grasa
            peso (float): Peso en kg para verificar mínimos
            
        Returns:
            dict: Distribución completa de macronutrientes
        """
        # Calcular proteína
        proteina_calorias = proteina_gramos * 4

        # Calcular grasa
        grasa_calorias = calorias_objetivo * (grasa_porcentaje / 100)
        grasa_gramos = grasa_calorias / 9

        # Verificar mínimo de grasa (0.5 g/kg)
        grasa_minima = 0.5 * peso
        if grasa_gramos < grasa_minima:
            grasa_gramos = grasa_minima
            grasa_calorias = grasa_gramos * 9
            grasa_porcentaje = (grasa_calorias / calorias_objetivo) * 100

        # Calcular carbohidratos (resto de calorías)
        carbohidratos_calorias = calorias_objetivo - proteina_calorias - grasa_calorias
        carbohidratos_gramos = carbohidratos_calorias / 4

        # Calcular porcentajes
        proteina_porcentaje = (proteina_calorias / calorias_objetivo) * 100
        grasa_porcentaje_calc = (grasa_calorias / calorias_objetivo) * 100
        carbohidratos_porcentaje = (carbohidratos_calorias / calorias_objetivo) * 100

        return {
            'proteina_gramos': round(proteina_gramos, 1),
            'proteina_calorias': round(proteina_calorias, 0),
            'proteina_porcentaje': round(proteina_porcentaje, 1),
            'grasa_gramos': round(grasa_gramos, 1),
            'grasa_calorias': round(grasa_calorias, 0),
            'grasa_porcentaje': round(grasa_porcentaje_calc, 1),
            'carbohidratos_gramos': round(carbohidratos_gramos, 1),
            'carbohidratos_calorias': round(carbohidratos_calorias, 0),
            'carbohidratos_porcentaje': round(carbohidratos_porcentaje, 1)
        }

    @staticmethod
    def obtener_recomendaciones_nivel1(objetivo, deficit_superavit):
        """
        Obtiene recomendaciones específicas para el Nivel 1
        
        Args:
            objetivo (str): Objetivo del usuario
            deficit_superavit (float): Porcentaje de déficit/superávit
            
        Returns:
            list: Lista de recomendaciones
        """
        recomendaciones = []

        if objetivo == "Pérdida de grasa":
            recomendaciones.extend([
                "• Mantén un déficit calórico moderado y sostenible",
                "• Pésate diariamente y toma el promedio semanal",
                "• Ajusta las calorías si la pérdida es muy rápida o lenta",
                "• Prioriza alimentos saciantes y ricos en nutrientes",
                "• Mantén la actividad física regular"
            ])
        elif objetivo == "Ganancia muscular":
            recomendaciones.extend([
                "• Mantén un superávit calórico moderado",
                "• Controla el peso semanalmente para evitar exceso de grasa",
                "• Combina con entrenamiento de resistencia progresivo",
                "• Distribuye las calorías a lo largo del día",
                "• Sé paciente: la ganancia muscular es un proceso lento"
            ])
        else:  # Mantenimiento
            recomendaciones.extend([
                "• Mantén las calorías estables día a día",
                "• Usa el peso como indicador de mantenimiento",
                "• Enfócate en la calidad de los alimentos",
                "• Mantén rutinas de ejercicio regulares",
                "• Ajusta según cambios en actividad o composición corporal"
            ])

        return recomendaciones

    @staticmethod
    def obtener_recomendaciones_nivel2(objetivo, proteina_gramos, peso):
        """
        Obtiene recomendaciones específicas para el Nivel 2
        
        Args:
            objetivo (str): Objetivo del usuario
            proteina_gramos (float): Gramos de proteína calculados
            peso (float): Peso del usuario
            
        Returns:
            list: Lista de recomendaciones
        """
        recomendaciones = []

        # Recomendaciones generales
        recomendaciones.extend([
            f"• Consume {proteina_gramos}g de proteína distribuidos en 3-4 comidas",
            "• Incluye una fuente de proteína en cada comida principal",
            "• Las grasas son esenciales: no las elimines completamente",
            "• Los carbohidratos proporcionan energía para el entrenamiento"
        ])

        # Recomendaciones específicas por objetivo
        if objetivo == "Pérdida de grasa":
            recomendaciones.extend([
                "• Prioriza proteínas magras para maximizar la saciedad",
                "• Incluye grasas saludables en cantidades moderadas",
                "• Consume carbohidratos principalmente alrededor del entrenamiento"
            ])
        elif objetivo == "Ganancia muscular":
            recomendaciones.extend([
                "• Incluye fuentes variadas de proteína de alta calidad",
                "• No temas a las grasas: ayudan con las hormonas",
                "• Consume carbohidratos suficientes para el rendimiento"
            ])

        return recomendaciones


class ValidadorNutricion:
    """Clase para validar datos nutricionales"""

    @staticmethod
    def validar_perfil_usuario(datos):
        """
        Valida los datos del perfil de usuario
        
        Args:
            datos (dict): Datos del usuario
            
        Returns:
            list: Lista de errores de validación
        """
        errores = []

        # Validar edad
        if datos.get('edad', 0) < 15 or datos.get('edad', 0) > 80:
            errores.append("La edad debe estar entre 15 y 80 años")

        # Validar peso
        if datos.get('peso', 0) < 30 or datos.get('peso', 0) > 200:
            errores.append("El peso debe estar entre 30 y 200 kg")

        # Validar altura
        if datos.get('altura', 0) < 120 or datos.get('altura', 0) > 220:
            errores.append("La altura debe estar entre 120 y 220 cm")

        return errores

    @staticmethod
    def validar_factor_actividad(factor):
        """
        Valida el factor de actividad
        
        Args:
            factor (float): Factor de actividad
            
        Returns:
            bool: True si es válido
        """
        return 1.3 <= factor <= 2.2

    @staticmethod
    def validar_macronutrientes(proteina_gramos, grasa_porcentaje, peso):
        """
        Valida los valores de macronutrientes
        
        Args:
            proteina_gramos (float): Gramos de proteína
            grasa_porcentaje (float): Porcentaje de grasa
            peso (float): Peso del usuario
            
        Returns:
            list: Lista de advertencias
        """
        advertencias = []

        # Verificar proteína mínima
        proteina_minima = peso * 1.6
        if proteina_gramos < proteina_minima:
            advertencias.append(f"La proteína está por debajo del mínimo recomendado ({proteina_minima:.1f}g)")

        # Verificar grasa mínima
        if grasa_porcentaje < 15:
            advertencias.append("El porcentaje de grasa está por debajo del mínimo recomendado (15%)")

        # Verificar grasa máxima
        if grasa_porcentaje > 40:
            advertencias.append("El porcentaje de grasa está por encima del máximo recomendado (40%)")

        return advertencias
