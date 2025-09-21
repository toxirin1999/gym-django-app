#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Perfil de Usuario
Permite configurar y editar los datos básicos del usuario
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

class PerfilUsuario:
    def __init__(self, parent, db, callback_actualizado=None):
        """
        Inicializa la ventana de perfil de usuario
        
        Args:
            parent: Ventana padre
            db: Instancia de BaseDatosNutricion
            callback_actualizado: Función a llamar cuando se actualice el perfil
        """
        self.parent = parent
        self.db = db
        self.callback_actualizado = callback_actualizado
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Configuración de Perfil")
        self.ventana.geometry("500x600")
        self.ventana.configure(bg='#f0f0f0')
        self.ventana.resizable(False, False)
        
        # Hacer modal
        self.ventana.transient(parent)
        self.ventana.grab_set()
        
        # Variables de formulario
        self.vars = {}
        self.crear_variables()
        
        # Verificar si hay usuario existente
        self.usuario_existente = self.db.obtener_usuario_actual()
        
        # Crear interfaz
        self.crear_interfaz()
        
        # Cargar datos si hay usuario existente
        if self.usuario_existente:
            self.cargar_datos_existentes()
        
        # Centrar ventana
        self.centrar_ventana()
    
    def crear_variables(self):
        """Crea las variables del formulario"""
        self.vars['nombre'] = tk.StringVar()
        self.vars['edad'] = tk.IntVar()
        self.vars['sexo'] = tk.StringVar()
        self.vars['peso'] = tk.DoubleVar()
        self.vars['altura'] = tk.IntVar()
        self.vars['nivel_actividad'] = tk.StringVar()
        self.vars['objetivo'] = tk.StringVar()
        self.vars['experiencia'] = tk.StringVar()
        
        # Valores por defecto
        self.vars['sexo'].set("Masculino")
        self.vars['nivel_actividad'].set("Activo")
        self.vars['objetivo'].set("Ganancia muscular")
        self.vars['experiencia'].set("Intermedio")
    
    def crear_interfaz(self):
        """Crea la interfaz de usuario"""
        # Frame principal con scroll
        main_frame = ttk.Frame(self.ventana)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título
        titulo = ttk.Label(
            main_frame,
            text="CONFIGURACIÓN DE PERFIL",
            font=('Arial', 16, 'bold')
        )
        titulo.pack(pady=(0, 20))
        
        # Subtítulo
        if self.usuario_existente:
            subtitulo_text = "Editar información personal"
        else:
            subtitulo_text = "Configura tu información personal para obtener cálculos precisos"
        
        subtitulo = ttk.Label(
            main_frame,
            text=subtitulo_text,
            font=('Arial', 10),
            foreground='#666666'
        )
        subtitulo.pack(pady=(0, 30))
        
        # Frame del formulario
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Crear campos del formulario
        self.crear_campos_formulario(form_frame)
        
        # Frame de botones
        botones_frame = ttk.Frame(main_frame)
        botones_frame.pack(fill=tk.X, pady=(30, 0))
        
        self.crear_botones(botones_frame)
    
    def crear_campos_formulario(self, parent):
        """Crea los campos del formulario"""
        
        # Nombre
        self.crear_campo_texto(parent, "Nombre completo:", self.vars['nombre'], 0)
        
        # Edad
        self.crear_campo_numero(parent, "Edad (años):", self.vars['edad'], 1, 15, 80)
        
        # Sexo
        self.crear_campo_combobox(parent, "Sexo:", self.vars['sexo'], 2, 
                                 ["Masculino", "Femenino"])
        
        # Peso
        self.crear_campo_numero(parent, "Peso actual (kg):", self.vars['peso'], 3, 30.0, 200.0)
        
        # Altura
        self.crear_campo_numero(parent, "Altura (cm):", self.vars['altura'], 4, 120, 220)
        
        # Nivel de actividad
        niveles_actividad = [
            "Sedentario",
            "Ligeramente activo", 
            "Activo",
            "Muy activo"
        ]
        self.crear_campo_combobox(parent, "Nivel de actividad:", self.vars['nivel_actividad'], 5,
                                 niveles_actividad)
        
        # Descripción del nivel de actividad
        desc_actividad = ttk.Label(
            parent,
            text="• Sedentario: Trabajo de oficina, poco movimiento\n"
                 "• Ligeramente activo: Caminar ocasionalmente\n"
                 "• Activo: Ejercicio regular, trabajo físico\n"
                 "• Muy activo: Ejercicio intenso diario, trabajo físico pesado",
            font=('Arial', 8),
            foreground='#666666',
            justify=tk.LEFT
        )
        desc_actividad.grid(row=6, column=0, columnspan=2, sticky="w", pady=(5, 15))
        
        # Objetivo
        objetivos = [
            "Pérdida de grasa",
            "Mantenimiento",
            "Ganancia muscular"
        ]
        self.crear_campo_combobox(parent, "Objetivo principal:", self.vars['objetivo'], 7,
                                 objetivos)
        
        # Experiencia
        experiencias = [
            "Novato",
            "Intermedio", 
            "Avanzado"
        ]
        self.crear_campo_combobox(parent, "Experiencia en entrenamiento:", self.vars['experiencia'], 8,
                                 experiencias)
    
    def crear_campo_texto(self, parent, label_text, variable, row):
        """Crea un campo de texto"""
        label = ttk.Label(parent, text=label_text, font=('Arial', 10, 'bold'))
        label.grid(row=row, column=0, sticky="w", pady=(10, 5))
        
        entry = ttk.Entry(parent, textvariable=variable, font=('Arial', 10), width=30)
        entry.grid(row=row, column=1, sticky="w", pady=(10, 5), padx=(10, 0))
        
        return entry
    
    def crear_campo_numero(self, parent, label_text, variable, row, min_val, max_val):
        """Crea un campo numérico con validación"""
        label = ttk.Label(parent, text=label_text, font=('Arial', 10, 'bold'))
        label.grid(row=row, column=0, sticky="w", pady=(10, 5))
        
        # Frame para el entry y la validación
        entry_frame = ttk.Frame(parent)
        entry_frame.grid(row=row, column=1, sticky="w", pady=(10, 5), padx=(10, 0))
        
        entry = ttk.Entry(entry_frame, textvariable=variable, font=('Arial', 10), width=15)
        entry.pack(side=tk.LEFT)
        
        # Label de rango válido
        rango_label = ttk.Label(
            entry_frame,
            text=f"({min_val}-{max_val})",
            font=('Arial', 8),
            foreground='#666666'
        )
        rango_label.pack(side=tk.LEFT, padx=(5, 0))
        
        return entry
    
    def crear_campo_combobox(self, parent, label_text, variable, row, valores):
        """Crea un campo combobox"""
        label = ttk.Label(parent, text=label_text, font=('Arial', 10, 'bold'))
        label.grid(row=row, column=0, sticky="w", pady=(10, 5))
        
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=valores,
            state="readonly",
            font=('Arial', 10),
            width=27
        )
        combo.grid(row=row, column=1, sticky="w", pady=(10, 5), padx=(10, 0))
        
        return combo
    
    def crear_botones(self, parent):
        """Crea los botones de acción"""
        # Botón cancelar
        btn_cancelar = ttk.Button(
            parent,
            text="Cancelar",
            command=self.cancelar
        )
        btn_cancelar.pack(side=tk.LEFT)
        
        # Botón guardar
        texto_boton = "Actualizar" if self.usuario_existente else "Crear Perfil"
        btn_guardar = ttk.Button(
            parent,
            text=texto_boton,
            command=self.guardar_perfil
        )
        btn_guardar.pack(side=tk.RIGHT)
        
        # Hacer que Enter guarde el perfil
        self.ventana.bind('<Return>', lambda e: self.guardar_perfil())
    
    def cargar_datos_existentes(self):
        """Carga los datos del usuario existente en el formulario"""
        if self.usuario_existente:
            self.vars['nombre'].set(self.usuario_existente['nombre'])
            self.vars['edad'].set(self.usuario_existente['edad'])
            self.vars['sexo'].set(self.usuario_existente['sexo'])
            self.vars['peso'].set(self.usuario_existente['peso'])
            self.vars['altura'].set(self.usuario_existente['altura'])
            self.vars['nivel_actividad'].set(self.usuario_existente['nivel_actividad'])
            self.vars['objetivo'].set(self.usuario_existente['objetivo'])
            self.vars['experiencia'].set(self.usuario_existente['experiencia'])
    
    def validar_datos(self):
        """Valida los datos del formulario"""
        errores = []
        
        # Validar nombre
        if not self.vars['nombre'].get().strip():
            errores.append("El nombre es obligatorio")
        
        # Validar edad
        edad = self.vars['edad'].get()
        if edad < 15 or edad > 80:
            errores.append("La edad debe estar entre 15 y 80 años")
        
        # Validar peso
        peso = self.vars['peso'].get()
        if peso < 30 or peso > 200:
            errores.append("El peso debe estar entre 30 y 200 kg")
        
        # Validar altura
        altura = self.vars['altura'].get()
        if altura < 120 or altura > 220:
            errores.append("La altura debe estar entre 120 y 220 cm")
        
        # Validar campos obligatorios
        campos_obligatorios = ['sexo', 'nivel_actividad', 'objetivo', 'experiencia']
        for campo in campos_obligatorios:
            if not self.vars[campo].get():
                errores.append(f"El campo {campo.replace('_', ' ')} es obligatorio")
        
        return errores
    
    def guardar_perfil(self):
        """Guarda o actualiza el perfil del usuario"""
        # Validar datos
        errores = self.validar_datos()
        if errores:
            messagebox.showerror(
                "Errores de validación",
                "\n".join(errores)
            )
            return
        
        # Preparar datos
        datos_usuario = {
            'nombre': self.vars['nombre'].get().strip(),
            'edad': self.vars['edad'].get(),
            'sexo': self.vars['sexo'].get(),
            'peso': self.vars['peso'].get(),
            'altura': self.vars['altura'].get(),
            'nivel_actividad': self.vars['nivel_actividad'].get(),
            'objetivo': self.vars['objetivo'].get(),
            'experiencia': self.vars['experiencia'].get()
        }
        
        try:
            if self.usuario_existente:
                # Actualizar usuario existente
                self.db.actualizar_usuario(self.usuario_existente['id'], datos_usuario)
                usuario_id = self.usuario_existente['id']
                mensaje = "Perfil actualizado correctamente"
            else:
                # Crear nuevo usuario
                usuario_id = self.db.crear_usuario(datos_usuario)
                mensaje = "Perfil creado correctamente"
            
            messagebox.showinfo("Éxito", mensaje)
            
            # Llamar callback si existe
            if self.callback_actualizado:
                self.callback_actualizado(usuario_id)
            
            # Cerrar ventana
            self.ventana.destroy()
            
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error al guardar el perfil: {str(e)}"
            )
    
    def cancelar(self):
        """Cancela la edición y cierra la ventana"""
        if self.datos_modificados():
            respuesta = messagebox.askyesno(
                "Confirmar",
                "¿Estás seguro de que quieres cancelar? Se perderán los cambios."
            )
            if not respuesta:
                return
        
        self.ventana.destroy()
    
    def datos_modificados(self):
        """Verifica si los datos han sido modificados"""
        if not self.usuario_existente:
            # Si es un usuario nuevo, verificar si hay datos ingresados
            return any([
                self.vars['nombre'].get().strip(),
                self.vars['edad'].get() != 0,
                self.vars['peso'].get() != 0.0,
                self.vars['altura'].get() != 0
            ])
        
        # Si es usuario existente, comparar con datos originales
        return any([
            self.vars['nombre'].get() != self.usuario_existente['nombre'],
            self.vars['edad'].get() != self.usuario_existente['edad'],
            self.vars['sexo'].get() != self.usuario_existente['sexo'],
            self.vars['peso'].get() != self.usuario_existente['peso'],
            self.vars['altura'].get() != self.usuario_existente['altura'],
            self.vars['nivel_actividad'].get() != self.usuario_existente['nivel_actividad'],
            self.vars['objetivo'].get() != self.usuario_existente['objetivo'],
            self.vars['experiencia'].get() != self.usuario_existente['experiencia']
        ])
    
    def centrar_ventana(self):
        """Centra la ventana en la pantalla"""
        self.ventana.update_idletasks()
        
        # Obtener dimensiones
        width = self.ventana.winfo_width()
        height = self.ventana.winfo_height()
        
        # Calcular posición
        pos_x = (self.ventana.winfo_screenwidth() // 2) - (width // 2)
        pos_y = (self.ventana.winfo_screenheight() // 2) - (height // 2)
        
        # Establecer posición
        self.ventana.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

# Función de prueba
if __name__ == "__main__":
    from base_datos_nutricion import BaseDatosNutricion
    
    root = tk.Tk()
    root.withdraw()  # Ocultar ventana principal
    
    db = BaseDatosNutricion()
    
    def callback_test(usuario_id):
        print(f"Usuario creado/actualizado con ID: {usuario_id}")
        root.quit()
    
    perfil = PerfilUsuario(root, db, callback_test)
    root.mainloop()

