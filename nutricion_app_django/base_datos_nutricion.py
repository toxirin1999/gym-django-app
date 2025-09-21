#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base de Datos para la Aplicación de Nutrición
Gestiona toda la información de usuarios, cálculos y progreso
"""

import sqlite3
import os
from datetime import datetime
import json

class BaseDatosNutricion:
    def __init__(self, db_path="nutricion.db"):
        """Inicializa la base de datos"""
        self.db_path = db_path
        self.crear_tablas()
    
    def crear_tablas(self):
        """Crea las tablas necesarias en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                edad INTEGER NOT NULL,
                sexo TEXT NOT NULL,
                peso REAL NOT NULL,
                altura REAL NOT NULL,
                nivel_actividad TEXT NOT NULL,
                objetivo TEXT NOT NULL,
                experiencia TEXT DEFAULT 'intermedio',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT 1
            )
        ''')
        
        # Tabla de cálculos del Nivel 1 (Balance Energético)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculos_nivel1 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                calorias_mantenimiento REAL NOT NULL,
                calorias_objetivo REAL NOT NULL,
                factor_actividad REAL NOT NULL,
                deficit_superavit_porcentaje REAL NOT NULL,
                metodo_calculo TEXT NOT NULL,
                fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de cálculos del Nivel 2 (Macronutrientes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculos_nivel2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                proteina_gramos REAL NOT NULL,
                grasa_gramos REAL NOT NULL,
                carbohidratos_gramos REAL NOT NULL,
                proteina_calorias REAL NOT NULL,
                grasa_calorias REAL NOT NULL,
                carbohidratos_calorias REAL NOT NULL,
                proteina_porcentaje REAL NOT NULL,
                grasa_porcentaje REAL NOT NULL,
                carbohidratos_porcentaje REAL NOT NULL,
                fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de progreso por niveles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progreso_niveles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                nivel INTEGER NOT NULL,
                completado BOOLEAN DEFAULT 0,
                fecha_completado TIMESTAMP,
                datos_json TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                UNIQUE(usuario_id, nivel)
            )
        ''')
        
        # Tabla de seguimiento de peso
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seguimiento_peso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                peso REAL NOT NULL,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notas TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de configuraciones de micronutrientes (Nivel 3)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion_nivel3 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                agua_litros REAL,
                frutas_porciones INTEGER,
                verduras_porciones INTEGER,
                suplementos_recomendados TEXT,
                fecha_configuracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de configuraciones de timing (Nivel 4)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion_nivel4 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                comidas_por_dia INTEGER,
                timing_pre_entreno TEXT,
                timing_post_entreno TEXT,
                distribucion_macros TEXT,
                refeeds_configurados BOOLEAN DEFAULT 0,
                fecha_configuracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabla de suplementos (Nivel 5)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion_nivel5 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                creatina BOOLEAN DEFAULT 0,
                proteina_polvo BOOLEAN DEFAULT 0,
                multivitaminico BOOLEAN DEFAULT 0,
                omega3 BOOLEAN DEFAULT 0,
                vitamina_d BOOLEAN DEFAULT 0,
                otros_suplementos TEXT,
                fecha_configuracion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def crear_usuario(self, datos_usuario):
        """Crea un nuevo usuario en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Desactivar usuario anterior si existe
        cursor.execute("UPDATE usuarios SET activo = 0")
        
        # Insertar nuevo usuario
        cursor.execute('''
            INSERT INTO usuarios (nombre, edad, sexo, peso, altura, nivel_actividad, objetivo, experiencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datos_usuario['nombre'],
            datos_usuario['edad'],
            datos_usuario['sexo'],
            datos_usuario['peso'],
            datos_usuario['altura'],
            datos_usuario['nivel_actividad'],
            datos_usuario['objetivo'],
            datos_usuario.get('experiencia', 'intermedio')
        ))
        
        usuario_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return usuario_id
    
    def obtener_usuario_actual(self):
        """Obtiene el usuario activo actual"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, nombre, edad, sexo, peso, altura, nivel_actividad, objetivo, experiencia
            FROM usuarios 
            WHERE activo = 1 
            ORDER BY fecha_creacion DESC 
            LIMIT 1
        ''')
        
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return {
                'id': resultado[0],
                'nombre': resultado[1],
                'edad': resultado[2],
                'sexo': resultado[3],
                'peso': resultado[4],
                'altura': resultado[5],
                'nivel_actividad': resultado[6],
                'objetivo': resultado[7],
                'experiencia': resultado[8]
            }
        return None
    
    def obtener_usuario_por_id(self, usuario_id):
        """Obtiene un usuario específico por ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, nombre, edad, sexo, peso, altura, nivel_actividad, objetivo, experiencia
            FROM usuarios 
            WHERE id = ?
        ''', (usuario_id,))
        
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return {
                'id': resultado[0],
                'nombre': resultado[1],
                'edad': resultado[2],
                'sexo': resultado[3],
                'peso': resultado[4],
                'altura': resultado[5],
                'nivel_actividad': resultado[6],
                'objetivo': resultado[7],
                'experiencia': resultado[8]
            }
        return None
    
    def guardar_calculo_nivel1(self, usuario_id, datos_calculo):
        """Guarda los cálculos del Nivel 1 (Balance Energético)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO calculos_nivel1 
                (usuario_id, calorias_mantenimiento, calorias_objetivo, factor_actividad, 
                 deficit_superavit_porcentaje, metodo_calculo)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                usuario_id,
                datos_calculo['calorias_mantenimiento'],
                datos_calculo['calorias_objetivo'],
                datos_calculo['factor_actividad'],
                datos_calculo['deficit_superavit_porcentaje'],
                datos_calculo['metodo_calculo']
            ))
            
            conn.commit()
            
            # Marcar nivel 1 como completado
            self.marcar_nivel_completado(usuario_id, 1, datos_calculo)
            
        finally:
            conn.close()
    
    def guardar_calculo_nivel2(self, usuario_id, datos_macros):
        """Guarda los cálculos del Nivel 2 (Macronutrientes)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO calculos_nivel2 
                (usuario_id, proteina_gramos, grasa_gramos, carbohidratos_gramos,
                 proteina_calorias, grasa_calorias, carbohidratos_calorias,
                 proteina_porcentaje, grasa_porcentaje, carbohidratos_porcentaje)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                usuario_id,
                datos_macros['proteina_gramos'],
                datos_macros['grasa_gramos'],
                datos_macros['carbohidratos_gramos'],
                datos_macros['proteina_calorias'],
                datos_macros['grasa_calorias'],
                datos_macros['carbohidratos_calorias'],
                datos_macros['proteina_porcentaje'],
                datos_macros['grasa_porcentaje'],
                datos_macros['carbohidratos_porcentaje']
            ))
            
            conn.commit()
            
            # Marcar nivel 2 como completado
            self.marcar_nivel_completado(usuario_id, 2, datos_macros)
            
        finally:
            conn.close()
    
    def marcar_nivel_completado(self, usuario_id, nivel, datos=None):
        """Marca un nivel como completado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        datos_json = json.dumps(datos) if datos else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO progreso_niveles 
            (usuario_id, nivel, completado, fecha_completado, datos_json)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP, ?)
        ''', (usuario_id, nivel, datos_json))
        
        conn.commit()
        conn.close()
    
    def obtener_progreso_usuario(self, usuario_id):
        """Obtiene el progreso del usuario en todos los niveles"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT nivel, completado, fecha_completado, datos_json
            FROM progreso_niveles 
            WHERE usuario_id = ?
        ''', (usuario_id,))
        
        resultados = cursor.fetchall()
        conn.close()
        
        progreso = {}
        for resultado in resultados:
            nivel = resultado[0]
            progreso[f'nivel_{nivel}_completado'] = bool(resultado[1])
            progreso[f'nivel_{nivel}_fecha'] = resultado[2]
            if resultado[3]:
                progreso[f'nivel_{nivel}_datos'] = json.loads(resultado[3])
        
        return progreso
    
    def obtener_ultimo_calculo_nivel1(self, usuario_id):
        """Obtiene el último cálculo del Nivel 1 para un usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT calorias_mantenimiento, calorias_objetivo, factor_actividad,
                   deficit_superavit_porcentaje, metodo_calculo, fecha_calculo
            FROM calculos_nivel1 
            WHERE usuario_id = ? 
            ORDER BY fecha_calculo DESC 
            LIMIT 1
        ''', (usuario_id,))
        
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return {
                'calorias_mantenimiento': resultado[0],
                'calorias_objetivo': resultado[1],
                'factor_actividad': resultado[2],
                'deficit_superavit_porcentaje': resultado[3],
                'metodo_calculo': resultado[4],
                'fecha_calculo': resultado[5]
            }
        return None
    
    def obtener_ultimo_calculo_nivel2(self, usuario_id):
        """Obtiene el último cálculo del Nivel 2 para un usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT proteina_gramos, grasa_gramos, carbohidratos_gramos,
                   proteina_calorias, grasa_calorias, carbohidratos_calorias,
                   proteina_porcentaje, grasa_porcentaje, carbohidratos_porcentaje,
                   fecha_calculo
            FROM calculos_nivel2 
            WHERE usuario_id = ? 
            ORDER BY fecha_calculo DESC 
            LIMIT 1
        ''', (usuario_id,))
        
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return {
                'proteina_gramos': resultado[0],
                'grasa_gramos': resultado[1],
                'carbohidratos_gramos': resultado[2],
                'proteina_calorias': resultado[3],
                'grasa_calorias': resultado[4],
                'carbohidratos_calorias': resultado[5],
                'proteina_porcentaje': resultado[6],
                'grasa_porcentaje': resultado[7],
                'carbohidratos_porcentaje': resultado[8],
                'fecha_calculo': resultado[9]
            }
        return None
    
    def registrar_peso(self, usuario_id, peso, notas=""):
        """Registra un nuevo peso para el seguimiento"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO seguimiento_peso (usuario_id, peso, notas)
            VALUES (?, ?, ?)
        ''', (usuario_id, peso, notas))
        
        conn.commit()
        conn.close()
    
    def obtener_historial_peso(self, usuario_id, limite=30):
        """Obtiene el historial de peso del usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT peso, fecha_registro, notas
            FROM seguimiento_peso 
            WHERE usuario_id = ? 
            ORDER BY fecha_registro DESC 
            LIMIT ?
        ''', (usuario_id, limite))
        
        resultados = cursor.fetchall()
        conn.close()
        
        return [{'peso': r[0], 'fecha': r[1], 'notas': r[2]} for r in resultados]
    
    def obtener_datos_completos_usuario(self, usuario_id):
        """Obtiene todos los datos de un usuario para el dashboard"""
        datos = {}
        
        # Datos básicos del usuario
        datos['usuario'] = self.obtener_usuario_por_id(usuario_id)
        
        # Progreso en niveles
        datos['progreso'] = self.obtener_progreso_usuario(usuario_id)
        
        # Cálculos de niveles
        datos['nivel1'] = self.obtener_ultimo_calculo_nivel1(usuario_id)
        datos['nivel2'] = self.obtener_ultimo_calculo_nivel2(usuario_id)
        
        # Historial de peso
        datos['historial_peso'] = self.obtener_historial_peso(usuario_id)
        
        return datos
    
    def actualizar_usuario(self, usuario_id, datos_usuario):
        """Actualiza los datos de un usuario existente"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE usuarios 
            SET nombre=?, edad=?, sexo=?, peso=?, altura=?, 
                nivel_actividad=?, objetivo=?, experiencia=?
            WHERE id=?
        ''', (
            datos_usuario['nombre'],
            datos_usuario['edad'],
            datos_usuario['sexo'],
            datos_usuario['peso'],
            datos_usuario['altura'],
            datos_usuario['nivel_actividad'],
            datos_usuario['objetivo'],
            datos_usuario.get('experiencia', 'intermedio'),
            usuario_id
        ))
        
        conn.commit()
        conn.close()
    
    def eliminar_usuario(self, usuario_id):
        """Elimina un usuario y todos sus datos asociados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Eliminar en orden para respetar las claves foráneas
        tablas = [
            'seguimiento_peso',
            'configuracion_nivel5',
            'configuracion_nivel4',
            'configuracion_nivel3',
            'progreso_niveles',
            'calculos_nivel2',
            'calculos_nivel1',
            'usuarios'
        ]
        
        for tabla in tablas:
            cursor.execute(f'DELETE FROM {tabla} WHERE usuario_id = ?', (usuario_id,))
        
        conn.commit()
        conn.close()
    
    def cerrar_conexion(self):
        """Cierra la conexión a la base de datos"""
        # En SQLite no es necesario mantener conexiones abiertas
        pass

