from django.utils import timezone
from django.db import models
from decimal import Decimal
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EntrenamientoGamificacionService:
    """
    Servicio de gamificación - VERSIÓN FINAL CON MANEJO SEGURO DE TIPOS
    """

    @staticmethod
    def procesar_entrenamiento_completado(entreno_realizado):
        """
        Procesa un entrenamiento completado y actualiza la gamificación
        VERSIÓN FINAL - Con manejo robusto de tipos de datos
        """
        try:
            from logros.models import PerfilGamificacion, PruebaUsuario, Arquetipo
            from logros.services import CodiceService

            cliente = entreno_realizado.cliente

            # Obtener o crear perfil de gamificación
            perfil, created = PerfilGamificacion.objects.get_or_create(cliente=cliente)

            if created:
                logger.info(f"Nuevo perfil de gamificación creado para {cliente.nombre}")

            # 1. CALCULAR PUNTOS BASE (con manejo seguro de tipos)
            puntos_base = EntrenamientoGamificacionService._calcular_puntos_base_seguro(entreno_realizado)

            # 2. VERIFICAR PRUEBAS COMPLETADAS
            pruebas_completadas = EntrenamientoGamificacionService._verificar_pruebas_completadas_final(
                entreno_realizado, perfil
            )

            # 3. CALCULAR PUNTOS BONUS
            puntos_bonus = EntrenamientoGamificacionService._calcular_puntos_bonus_seguro(
                cliente, entreno_realizado
            )

            # 4. SUMAR PUNTOS DE PRUEBAS
            puntos_pruebas = sum(prueba.puntos_recompensa for prueba in pruebas_completadas)

            # 5. CALCULAR TOTAL
            puntos_totales = puntos_base + puntos_bonus + puntos_pruebas

            # 6. ACTUALIZAR PERFIL
            perfil.puntos_totales += puntos_totales
            perfil.save()

            # 7. VERIFICAR ASCENSIÓN
            nivel_anterior, nivel_nuevo, ascension = EntrenamientoGamificacionService._verificar_ascension_final(perfil)

            # 8. GUARDAR PUNTOS EN ENTRENAMIENTO (si el campo existe)
            if hasattr(entreno_realizado, 'puntos_ganados'):
                entreno_realizado.puntos_ganados = puntos_totales
                entreno_realizado.save(update_fields=['puntos_ganados'])

            logger.info(f"Gamificación procesada para {cliente.nombre}: +{puntos_totales} puntos")

            # --- PREPARAMOS EL DICCIONARIO DE RESPUESTA CON EFECTOS ---
            respuesta = {
                'puntos_base': puntos_base,
                'puntos_bonus': puntos_bonus,
                'puntos_pruebas': puntos_pruebas,
                'puntos_totales': puntos_totales,
                'ascension': ascension,
                'nivel_anterior': nivel_anterior,
                'nivel_nuevo': nivel_nuevo,
                'perfil': perfil,
                # Convertimos las pruebas a un formato serializable con efectos
                'pruebas_completadas': [
                    {
                        'nombre': prueba.nombre,
                        'puntos': prueba.puntos_recompensa,
                        'efecto': 'nueva_prueba'  # Añadimos la clave del efecto
                    }
                    for prueba in pruebas_completadas
                ]
            }

            # Añadimos el efecto de ascensión si ocurrió
            if ascension:
                respuesta['efecto_principal'] = 'ascension'

            return respuesta

        except Exception as e:
            logger.error(f"Error procesando gamificación para entrenamiento {entreno_realizado.id}: {e}")
            return {
                'puntos_totales': 0,
                'pruebas_completadas': [],
                'ascension': False,
                'error': str(e)
            }

    @staticmethod
    def _calcular_puntos_base_seguro(entreno_realizado):
        """
        Calcula puntos base por el entrenamiento
        VERSIÓN SEGURA - Maneja conversiones de tipos correctamente
        """
        puntos = 15  # Puntos base por entrenar

        try:
            # Usar el volumen ya calculado - CONVERSIÓN SEGURA
            volumen_total = entreno_realizado.volumen_total_kg
            if volumen_total is not None:
                # Convertir a float de manera segura
                if isinstance(volumen_total, str):
                    volumen_total = float(volumen_total.replace(',', '.'))
                else:
                    volumen_total = float(volumen_total)
            else:
                volumen_total = 0.0

            puntos_volumen = min(20, int(volumen_total / 200)) if volumen_total > 0 else 0

            # Puntos por duración - CONVERSIÓN SEGURA
            duracion = entreno_realizado.duracion_minutos
            if duracion is not None:
                if isinstance(duracion, str):
                    duracion = int(float(duracion))  # Convertir via float por si tiene decimales
                else:
                    duracion = int(duracion)
            else:
                duracion = 60

            puntos_duracion = min(10, int(duracion / 5)) if duracion > 0 else 0

            # Puntos por número de ejercicios - CONVERSIÓN SEGURA
            num_ejercicios = entreno_realizado.numero_ejercicios
            if num_ejercicios is not None:
                if isinstance(num_ejercicios, str):
                    num_ejercicios = int(float(num_ejercicios))
                else:
                    num_ejercicios = int(num_ejercicios)
            else:
                num_ejercicios = 0

            puntos_ejercicios = min(5, num_ejercicios)

            total = puntos + puntos_volumen + puntos_duracion + puntos_ejercicios

            logger.debug(
                f"Puntos base calculados: {puntos} + {puntos_volumen} volumen + {puntos_duracion} duración + {puntos_ejercicios} ejercicios = {total}")

            return total

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculando puntos base: {e}. Retornando puntos mínimos.")
            return 15  # Retornar puntos base mínimos en caso de error

    @staticmethod
    def _calcular_puntos_bonus_seguro(cliente, entreno_realizado):
        """
        Calcula puntos bonus - VERSIÓN SEGURA
        """
        bonus = 0

        try:
            # Bonus por racha
            racha_actual = EntrenamientoGamificacionService._calcular_racha_actual(cliente)
            bonus += min(15, racha_actual)

            # Bonus por fin de semana
            if hasattr(entreno_realizado, 'fecha') and entreno_realizado.fecha:
                if entreno_realizado.fecha.weekday() >= 5:
                    bonus += 3

            logger.debug(f"Puntos bonus calculados: {bonus}")

        except Exception as e:
            logger.error(f"Error calculando bonus: {e}")

        return bonus

    @staticmethod
    def _verificar_ascension_final(perfil):
        """Verifica ascensión usando tu sistema actual"""
        try:
            # Obtener nivel anterior
            nivel_anterior = "Ninguno"
            if hasattr(perfil, 'nivel_actual') and perfil.nivel_actual:
                nivel_anterior = perfil.nivel_actual.titulo_arquetipo

            # Tu sistema ya maneja la ascensión automáticamente via signals
            perfil.refresh_from_db()

            # Obtener nivel nuevo
            nivel_nuevo = "Ninguno"
            if hasattr(perfil, 'nivel_actual') and perfil.nivel_actual:
                nivel_nuevo = perfil.nivel_actual.titulo_arquetipo

            ascension = nivel_anterior != nivel_nuevo

            return nivel_anterior, nivel_nuevo, ascension

        except Exception as e:
            logger.error(f"Error verificando ascensión: {e}")
            return "Error", "Error", False

    @staticmethod
    def _verificar_pruebas_completadas_final(entreno_realizado, perfil):
        """Verifica pruebas usando la estructura correcta"""
        try:
            from logros.models import PruebaUsuario

            pruebas_completadas = []

            # Obtener nivel actual
            nivel_actual = None
            if hasattr(perfil, 'nivel_actual'):
                nivel_actual = perfil.nivel_actual

            if not nivel_actual:
                return pruebas_completadas

            # Usar perfil en lugar de cliente
            pruebas_activas = PruebaUsuario.objects.filter(
                perfil=perfil,
                prueba__arquetipo=nivel_actual,
                completada=False
            )

            for prueba_usuario in pruebas_activas:
                prueba = prueba_usuario.prueba

                if EntrenamientoGamificacionService._evaluar_prueba_individual(
                        prueba, entreno_realizado.cliente, entreno_realizado
                ):
                    prueba_usuario.completada = True
                    prueba_usuario.fecha_completada = timezone.now()
                    prueba_usuario.save()

                    pruebas_completadas.append(prueba)
                    logger.info(f"Prueba completada: {prueba.nombre} por {entreno_realizado.cliente.nombre}")

        except Exception as e:
            logger.error(f"Error verificando pruebas: {e}")

        return pruebas_completadas

    @staticmethod
    def _evaluar_prueba_individual(prueba, cliente, entreno_realizado):
        """Evalúa si una prueba específica se completó"""
        clave = prueba.clave_calculo
        meta = prueba.meta_valor

        try:
            if clave == 'primer_entrenamiento':
                return True

            elif clave.startswith('press_banca_') and clave.endswith('kg'):
                peso_objetivo = int(clave.replace('press_banca_', '').replace('kg', ''))
                return EntrenamientoGamificacionService._verificar_peso_ejercicio(
                    entreno_realizado, 'press', peso_objetivo
                )

            elif clave == 'volumen_total':
                return EntrenamientoGamificacionService._verificar_volumen_total_historico(cliente, meta)

            elif clave.startswith('racha_') and clave.endswith('_dias'):
                dias_objetivo = int(clave.replace('racha_', '').replace('_dias', ''))
                return EntrenamientoGamificacionService._verificar_racha_dias(cliente, dias_objetivo)

            elif clave == 'entrenos_totales':
                from entrenos.models import EntrenoRealizado
                total_entrenos = EntrenoRealizado.objects.filter(cliente=cliente).count()
                return total_entrenos >= meta

            return False

        except Exception as e:
            logger.error(f"Error evaluando prueba {prueba.nombre}: {e}")
            return False

    @staticmethod
    def _verificar_peso_ejercicio(entreno_realizado, nombre_ejercicio_buscar, peso_objetivo):
        """Verifica si se levantó un peso específico"""
        try:
            ejercicios = entreno_realizado.ejercicios_realizados.filter(
                nombre_ejercicio__icontains=nombre_ejercicio_buscar,
                completado=True
            )

            for ejercicio in ejercicios:
                peso_kg = ejercicio.peso_kg
                # Conversión segura del peso
                if isinstance(peso_kg, str):
                    peso_kg = float(peso_kg.replace(',', '.'))
                else:
                    peso_kg = float(peso_kg)

                if peso_kg >= peso_objetivo:
                    return True

            return False
        except Exception as e:
            logger.error(f"Error verificando peso: {e}")
            return False

    @staticmethod
    def _verificar_volumen_total_historico(cliente, volumen_objetivo):
        """Verifica volumen total histórico"""
        try:
            from entrenos.models import EntrenoRealizado

            total_volumen = EntrenoRealizado.objects.filter(
                cliente=cliente
            ).aggregate(total=models.Sum('volumen_total_kg'))['total'] or 0

            # Conversión segura del volumen
            if isinstance(total_volumen, str):
                total_volumen = float(total_volumen.replace(',', '.'))
            else:
                total_volumen = float(total_volumen)

            return total_volumen >= volumen_objetivo

        except Exception as e:
            logger.error(f"Error verificando volumen histórico: {e}")
            return False

    @staticmethod
    def _verificar_racha_dias(cliente, dias_objetivo):
        """Verifica racha de días consecutivos"""
        try:
            from entrenos.models import EntrenoRealizado

            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=cliente
            ).order_by('-fecha')

            if not entrenamientos.exists():
                return False

            fechas_unicas = []
            for entreno in entrenamientos:
                if entreno.fecha not in fechas_unicas:
                    fechas_unicas.append(entreno.fecha)

            if not fechas_unicas:
                return False

            racha_actual = 1
            fecha_anterior = fechas_unicas[0]

            for fecha in fechas_unicas[1:]:
                diferencia = (fecha_anterior - fecha).days
                if diferencia == 1:
                    racha_actual += 1
                    fecha_anterior = fecha
                else:
                    break

            return racha_actual >= dias_objetivo

        except Exception as e:
            logger.error(f"Error verificando racha: {e}")
            return False

    @staticmethod
    def _calcular_racha_actual(cliente):
        """Calcula racha actual de días"""
        try:
            from entrenos.models import EntrenoRealizado

            entrenamientos = EntrenoRealizado.objects.filter(
                cliente=cliente
            ).order_by('-fecha')

            if not entrenamientos.exists():
                return 0

            fechas = []
            for entreno in entrenamientos:
                if entreno.fecha not in fechas:
                    fechas.append(entreno.fecha)

            if not fechas:
                return 0

            racha = 1
            fecha_anterior = fechas[0]

            for fecha in fechas[1:]:
                diferencia = (fecha_anterior - fecha).days
                if diferencia == 1:
                    racha += 1
                    fecha_anterior = fecha
                else:
                    break

            return racha

        except Exception as e:
            logger.error(f"Error calculando racha: {e}")
            return 0

    @staticmethod
    def obtener_resumen_gamificacion(cliente):
        """
        Obtiene resumen de gamificación - VERSIÓN MEJORADA CON MANEJO DE ERRORES
        """
        try:
            from logros.models import PerfilGamificacion, PruebaUsuario, Arquetipo

            perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()
            if not perfil:
                logger.info(f"No se encontró perfil de gamificación para {cliente.nombre}")
                return {
                    'tiene_perfil': False,
                    'nivel_actual': 'El Aspirante Calvo',
                    'puntos_actuales': 0,
                    'puntos_siguiente': 500,
                    'porcentaje_progreso': 0,
                    'pruebas_activas': [],
                    'racha_actual': 0,
                    'siguiente_nivel': 'Rock Lee - El Genio del Esfuerzo'
                }

            # Obtener nivel actual de manera segura
            nivel_actual = None
            nivel_actual_nombre = 'El Aspirante Calvo'

            try:
                if hasattr(perfil, 'nivel_actual') and perfil.nivel_actual:
                    nivel_actual = perfil.nivel_actual
                    nivel_actual_nombre = nivel_actual.titulo_arquetipo
            except Exception as e:
                logger.warning(f"Error obteniendo nivel actual: {e}")

            # Calcular siguiente nivel de manera segura
            siguiente_arquetipo = None
            siguiente_nivel_nombre = 'Próximo Nivel'

            try:
                if nivel_actual:
                    siguiente_arquetipo = Arquetipo.objects.filter(
                        nivel=nivel_actual.nivel + 1
                    ).first()
                else:
                    siguiente_arquetipo = Arquetipo.objects.filter(nivel=1).first()

                if siguiente_arquetipo:
                    siguiente_nivel_nombre = siguiente_arquetipo.titulo_arquetipo
            except Exception as e:
                logger.warning(f"Error obteniendo siguiente nivel: {e}")

            # Calcular progreso de manera segura
            puntos_actuales = getattr(perfil, 'puntos_totales', 0)
            puntos_siguiente = getattr(siguiente_arquetipo, 'puntos_requeridos', 500) if siguiente_arquetipo else 500
            puntos_nivel_actual = getattr(nivel_actual, 'puntos_requeridos', 0) if nivel_actual else 0

            try:
                progreso = puntos_actuales - puntos_nivel_actual
                total_necesario = puntos_siguiente - puntos_nivel_actual
                porcentaje = min(100, (progreso / total_necesario * 100)) if total_necesario > 0 else 0
            except (ZeroDivisionError, TypeError):
                porcentaje = 0

            # Obtener pruebas activas de manera segura
            pruebas_activas = []
            try:
                if nivel_actual:
                    pruebas_activas = PruebaUsuario.objects.filter(
                        perfil=perfil,
                        prueba__arquetipo=nivel_actual,
                        completada=False
                    ).select_related('prueba')[:3]
            except Exception as e:
                logger.warning(f"Error obteniendo pruebas activas: {e}")

            # Calcular racha de manera segura
            racha_actual = 0
            try:
                racha_actual = EntrenamientoGamificacionService._calcular_racha_actual(cliente)
            except Exception as e:
                logger.warning(f"Error calculando racha: {e}")

            return {
                'tiene_perfil': True,
                'perfil': perfil,
                'nivel_actual': nivel_actual_nombre,
                'puntos_actuales': puntos_actuales,
                'puntos_siguiente': puntos_siguiente,
                'porcentaje_progreso': int(porcentaje),
                'pruebas_activas': pruebas_activas,
                'siguiente_nivel': siguiente_nivel_nombre,
                'racha_actual': racha_actual
            }

        except Exception as e:
            logger.error(f"Error crítico obteniendo resumen de gamificación: {e}")
            return {
                'tiene_perfil': False,
                'error': str(e),
                'nivel_actual': 'Error',
                'puntos_actuales': 0,
                'puntos_siguiente': 500,
                'porcentaje_progreso': 0,
                'pruebas_activas': [],
                'racha_actual': 0,
                'siguiente_nivel': 'Error'
            }
