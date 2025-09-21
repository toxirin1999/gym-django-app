# entrenos/management/commands/migrar_ejercicios.py

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Solución definitiva para corregir relaciones rotas.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- SOLUCIÓN DEFINITIVA PARA RELACIONES ROTAS ---'))

        try:
            with connection.cursor() as cursor:
                # Paso 1: Deshabilitar foreign key constraints temporalmente
                self.stdout.write('Paso 1: Deshabilitando foreign key constraints...')
                cursor.execute("PRAGMA foreign_keys = OFF")

                # Paso 2: Identificar y mostrar relaciones rotas
                self.stdout.write('Paso 2: Identificando relaciones rotas...')
                cursor.execute("""
                    SELECT re.id, re.ejercicio_id 
                    FROM rutinas_rutinaejercicio re
                    LEFT JOIN rutinas_ejerciciobase eb ON re.ejercicio_id = eb.id
                    WHERE eb.id IS NULL
                """)
                relaciones_rotas = cursor.fetchall()
                self.stdout.write(f'Encontradas {len(relaciones_rotas)} relaciones rotas')

                # Paso 3: Crear mapas de corrección
                self.stdout.write('Paso 3: Creando mapas de corrección...')

                # Obtener todos los ejercicios de rutinas
                cursor.execute("SELECT id, nombre FROM rutinas_ejerciciobase")
                ejercicios_rutinas = {nombre.lower().strip(): id_ej for id_ej, nombre in cursor.fetchall()}

                # Obtener todos los ejercicios de entrenos
                cursor.execute("SELECT id, nombre FROM entrenos_ejerciciobase")
                ejercicios_entrenos = {id_ej: nombre for id_ej, nombre in cursor.fetchall()}

                # Paso 4: Corregir relaciones una por una
                self.stdout.write('Paso 4: Corrigiendo relaciones...')
                corregidas = 0
                eliminadas = 0

                for relacion_id, id_roto in relaciones_rotas:
                    nombre_ejercicio = ejercicios_entrenos.get(id_roto)

                    if nombre_ejercicio:
                        # Buscar el ID correcto en rutinas (case insensitive)
                        nombre_normalizado = nombre_ejercicio.lower().strip()
                        id_correcto = ejercicios_rutinas.get(nombre_normalizado)

                        if id_correcto:
                            # Corregir la relación usando formateo de string directo
                            sql = f"UPDATE rutinas_rutinaejercicio SET ejercicio_id = {id_correcto} WHERE id = {relacion_id}"
                            cursor.execute(sql)
                            corregidas += 1
                            self.stdout.write(f"  ✅ Corregida: '{nombre_ejercicio}' (ID {id_roto} -> {id_correcto})")
                        else:
                            # Si no encontramos el ejercicio, eliminar la relación rota
                            sql = f"DELETE FROM rutinas_rutinaejercicio WHERE id = {relacion_id}"
                            cursor.execute(sql)
                            eliminadas += 1
                            self.stdout.write(f"  🗑️ Eliminada relación rota: '{nombre_ejercicio}' (ID {id_roto})")
                    else:
                        # Si no encontramos el nombre, eliminar la relación rota
                        sql = f"DELETE FROM rutinas_rutinaejercicio WHERE id = {relacion_id}"
                        cursor.execute(sql)
                        eliminadas += 1
                        self.stdout.write(f"  🗑️ Eliminada relación rota: ID desconocido {id_roto}")

                # Paso 5: Verificación intermedia
                self.stdout.write('Paso 5: Verificación intermedia...')
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM rutinas_rutinaejercicio re
                    LEFT JOIN rutinas_ejerciciobase eb ON re.ejercicio_id = eb.id
                    WHERE eb.id IS NULL
                """)
                relaciones_rotas_restantes = cursor.fetchone()[0]

                if relaciones_rotas_restantes == 0:
                    self.stdout.write(self.style.SUCCESS('✅ TODAS LAS RELACIONES ESTÁN CORRECTAS'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Aún quedan {relaciones_rotas_restantes} relaciones rotas'))

                # Paso 6: Rehabilitar foreign key constraints
                self.stdout.write('Paso 6: Rehabilitando foreign key constraints...')
                cursor.execute("PRAGMA foreign_keys = ON")

                # Paso 7: Verificación final con constraints activas
                self.stdout.write('Paso 7: Verificación final con constraints activas...')
                cursor.execute("PRAGMA foreign_key_check")
                errores_fk = cursor.fetchall()

                if not errores_fk:
                    self.stdout.write(self.style.SUCCESS('✅ VERIFICACIÓN FINAL EXITOSA - NO HAY ERRORES DE FK'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Errores de FK encontrados: {len(errores_fk)}'))
                    for error in errores_fk:
                        self.stdout.write(f"  Error: {error}")

                self.stdout.write(self.style.SUCCESS(f'Resumen: {corregidas} corregidas, {eliminadas} eliminadas'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

        self.stdout.write(self.style.SUCCESS('--- PROCESO COMPLETADO ---'))
