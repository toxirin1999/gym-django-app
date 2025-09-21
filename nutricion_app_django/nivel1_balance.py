#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nivel 1 - Balance Energético
Implementa los cálculos de calorías de mantenimiento y objetivos según el libro
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math

class Nivel1Balance:
    def __init__(self, parent, usuario_id, db, callback_actualizado=None):
        """
        Inicializa la ventana del Nivel 1 - Balance Energético
        
        Args:
            parent: Ventana padre
            usuario_id: ID del usuario actual
            db: Instancia de BaseDatosNutricion
            callback_actualizado: Función a llamar cuando se actualicen los datos
        """
        self.parent = parent
        self.usuario_id = usuario_id
        self.db = db
        self.callback_actualizado = callback_actualizado
        
        # Obtener datos del usuario
        self.usuario = self.db.obtener_usuario_por_id(usuario_id)
        if not self.usuario:
            messagebox.showerror("Error", "No se encontraron datos del usuario")
            return
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Nivel 1 - Balance Energético")
        self.ventana.geometry("800x700")
        self.ventana.configure(bg='#f0f0f0')
        
        # Variables de cálculo
        self.vars = {}
        self.crear_variables()
        
        # Crear interfaz
        self.crear_interfaz()
        
        # Cargar datos existentes si los hay
        self.cargar_datos_existentes()
        
        # Centrar ventana
        self.centrar_ventana()
    
    def crear_variables(self):
        """Crea las variables para los cálculos"""
        self.vars['metodo'] = tk.StringVar(value="calculo_rapido")
        self.vars['factor_actividad'] = tk.DoubleVar(value=1.7)
        self.vars['calorias_mantenimiento'] = tk.DoubleVar()
        self.vars['calorias_objetivo'] = tk.DoubleVar()
        self.vars['deficit_superavit'] = tk.DoubleVar()
        self.vars['peso_objetivo_semanal'] = tk.DoubleVar()
    
    def crear_interfaz(self):
        """Crea la interfaz del Nivel 1"""
        # Frame principal con scroll
        main_frame = ttk.Frame(self.ventana)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título
        titulo = ttk.Label(
            main_frame,
            text="NIVEL 1 - BALANCE ENERGÉTICO",
            font=('Arial', 18, 'bold'),
            foreground='#2E8B57'
        )
        titulo.pack(pady=(0, 10))
        
        # Subtítulo
        subtitulo = ttk.Label(
            main_frame,
            text="La base de la pirámide nutricional - Lo más importante",
            font=('Arial', 12),
            foreground='#666666'
        )
        subtitulo.pack(pady=(0, 20))
        
        # Información del usuario
        self.crear_info_usuario(main_frame)
        
        # Métodos de cálculo
        self.crear_seccion_metodos(main_frame)
        
        # Resultados
        self.crear_seccion_resultados(main_frame)
        
        # Botones
        self.crear_botones(main_frame)
    
    def crear_info_usuario(self, parent):
        """Crea la sección de información del usuario"""
        info_frame = ttk.LabelFrame(parent, text="Información del Usuario", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Crear grid de información
        info_data = [
            ("Nombre:", self.usuario['nombre']),
            ("Edad:", f"{self.usuario['edad']} años"),
            ("Sexo:", self.usuario['sexo']),
            ("Peso:", f"{self.usuario['peso']} kg"),
            ("Altura:", f"{self.usuario['altura']} cm"),
            ("Nivel de actividad:", self.usuario['nivel_actividad']),
            ("Objetivo:", self.usuario['objetivo'])
        ]
        
        for i, (label, valor) in enumerate(info_data):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(info_frame, text=label, font=('Arial', 10, 'bold')).grid(
                row=row, column=col, sticky="w", padx=(0, 10), pady=2
            )
            ttk.Label(info_frame, text=valor).grid(
                row=row, column=col+1, sticky="w", padx=(0, 30), pady=2
            )
    
    def crear_seccion_metodos(self, parent):
        """Crea la sección de métodos de cálculo"""
        metodos_frame = ttk.LabelFrame(parent, text="Método de Cálculo", padding=15)
        metodos_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Explicación
        explicacion = ttk.Label(
            metodos_frame,
            text="Elige el método para calcular tus calorías de mantenimiento:",
            font=('Arial', 11, 'bold')
        )
        explicacion.pack(anchor=tk.W, pady=(0, 15))
        
        # Método 1: Cálculo rápido (recomendado para empezar)
        metodo1_frame = ttk.Frame(metodos_frame)
        metodo1_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Radiobutton(
            metodo1_frame,
            text="Cálculo Rápido (Recomendado para empezar)",
            variable=self.vars['metodo'],
            value="calculo_rapido",
            command=self.cambiar_metodo
        ).pack(anchor=tk.W)
        
        ttk.Label(
            metodo1_frame,
            text="Usa fórmulas estándar basadas en peso corporal y factor de actividad",
            font=('Arial', 9),
            foreground='#666666'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        # Frame para factor de actividad
        self.factor_frame = ttk.Frame(metodos_frame)
        self.factor_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(
            self.factor_frame,
            text="Factor de actividad:",
            font=('Arial', 10, 'bold')
        ).pack(anchor=tk.W)
        
        # Crear escala para factor de actividad
        factor_scale_frame = ttk.Frame(self.factor_frame)
        factor_scale_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.factor_scale = tk.Scale(
            factor_scale_frame,
            from_=1.3,
            to=2.2,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=self.vars['factor_actividad'],
            command=self.actualizar_factor_descripcion
        )
        self.factor_scale.pack(fill=tk.X)
        
        # Descripción del factor
        self.factor_descripcion = ttk.Label(
            self.factor_frame,
            text="",
            font=('Arial', 9),
            foreground='#666666'
        )
        self.factor_descripcion.pack(anchor=tk.W, pady=(5, 0))
        
        # Actualizar descripción inicial
        self.actualizar_factor_descripcion()
        
        # Método 2: Tracking de 2 semanas (más preciso)
        metodo2_frame = ttk.Frame(metodos_frame)
        metodo2_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Radiobutton(
            metodo2_frame,
            text="Tracking de 2 semanas (Más preciso)",
            variable=self.vars['metodo'],
            value="tracking_2_semanas",
            command=self.cambiar_metodo
        ).pack(anchor=tk.W)
        
        ttk.Label(
            metodo2_frame,
            text="Requiere trackear peso y calorías durante 2 semanas (implementación futura)",
            font=('Arial', 9),
            foreground='#666666'
        ).pack(anchor=tk.W, padx=(20, 0))
        
        # Botón calcular
        btn_calcular = ttk.Button(
            metodos_frame,
            text="Calcular Calorías de Mantenimiento",
            command=self.calcular_mantenimiento
        )
        btn_calcular.pack(pady=(20, 0))
    
    def crear_seccion_resultados(self, parent):
        """Crea la sección de resultados"""
        self.resultados_frame = ttk.LabelFrame(parent, text="Resultados", padding=15)
        self.resultados_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Inicialmente oculto
        self.resultados_visibles = False
    
    def crear_botones(self, parent):
        """Crea los botones de acción"""
        botones_frame = ttk.Frame(parent)
        botones_frame.pack(fill=tk.X)
        
        ttk.Button(
            botones_frame,
            text="Cerrar",
            command=self.ventana.destroy
        ).pack(side=tk.LEFT)
        
        self.btn_guardar = ttk.Button(
            botones_frame,
            text="Guardar y Continuar al Nivel 2",
            command=self.guardar_resultados,
            state=tk.DISABLED
        )
        self.btn_guardar.pack(side=tk.RIGHT)
    
    def cambiar_metodo(self):
        """Maneja el cambio de método de cálculo"""
        metodo = self.vars['metodo'].get()
        
        if metodo == "calculo_rapido":
            self.factor_frame.pack(fill=tk.X, pady=(10, 0))
        else:
            self.factor_frame.pack_forget()
            messagebox.showinfo(
                "Método no disponible",
                "El método de tracking de 2 semanas estará disponible en una futura versión.\\n"
                "Por ahora, usa el cálculo rápido."
            )
            self.vars['metodo'].set("calculo_rapido")
    
    def actualizar_factor_descripcion(self, valor=None):
        """Actualiza la descripción del factor de actividad"""
        factor = self.vars['factor_actividad'].get()
        
        if factor <= 1.6:
            descripcion = "Sedentario + 3-6 días de entrenamiento con pesas"
        elif factor <= 1.8:
            descripcion = "Ligeramente activo + 3-6 días de entrenamiento con pesas"
        elif factor <= 2.0:
            descripcion = "Activo + 3-6 días de entrenamiento con pesas"
        else:
            descripcion = "Muy activo + 3-6 días de entrenamiento con pesas"
        
        self.factor_descripcion.config(text=f"Factor {factor}: {descripcion}")
    
    def calcular_mantenimiento(self):
        """Calcula las calorías de mantenimiento"""
        try:
            # Método de cálculo rápido
            peso_kg = self.usuario['peso']
            factor_actividad = self.vars['factor_actividad'].get()
            
            # Fórmula base: peso en kg × 22
            calorias_base = peso_kg * 22
            
            # Aplicar factor de actividad
            calorias_mantenimiento = calorias_base * factor_actividad
            
            # Guardar resultado
            self.vars['calorias_mantenimiento'].set(calorias_mantenimiento)
            
            # Calcular calorías objetivo según el objetivo del usuario
            self.calcular_objetivo()
            
            # Mostrar resultados
            self.mostrar_resultados()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en el cálculo: {str(e)}")
    
    def calcular_objetivo(self):
        """Calcula las calorías objetivo según el objetivo del usuario"""
        calorias_mantenimiento = self.vars['calorias_mantenimiento'].get()
        objetivo = self.usuario['objetivo']
        
        if objetivo == "Pérdida de grasa":
            # Déficit del 15-25% (usamos 20% como promedio)
            deficit_porcentaje = 20
            calorias_objetivo = calorias_mantenimiento * (1 - deficit_porcentaje / 100)
            self.vars['deficit_superavit'].set(-deficit_porcentaje)
            
            # Pérdida de peso recomendada: 0.5-1% del peso corporal por semana
            peso_objetivo_semanal = -(self.usuario['peso'] * 0.007)  # 0.7% promedio
            
        elif objetivo == "Ganancia muscular":
            # Superávit del 10-20% (usamos 15% como promedio)
            superavit_porcentaje = 15
            calorias_objetivo = calorias_mantenimiento * (1 + superavit_porcentaje / 100)
            self.vars['deficit_superavit'].set(superavit_porcentaje)
            
            # Ganancia de peso recomendada: 0.25-0.5% del peso corporal por semana
            peso_objetivo_semanal = self.usuario['peso'] * 0.004  # 0.4% promedio
            
        else:  # Mantenimiento
            calorias_objetivo = calorias_mantenimiento
            self.vars['deficit_superavit'].set(0)
            peso_objetivo_semanal = 0
        
        self.vars['calorias_objetivo'].set(calorias_objetivo)
        self.vars['peso_objetivo_semanal'].set(peso_objetivo_semanal)
    
    def mostrar_resultados(self):
        """Muestra los resultados del cálculo"""
        # Limpiar frame de resultados
        for widget in self.resultados_frame.winfo_children():
            widget.destroy()
        
        calorias_mantenimiento = self.vars['calorias_mantenimiento'].get()
        calorias_objetivo = self.vars['calorias_objetivo'].get()
        deficit_superavit = self.vars['deficit_superavit'].get()
        peso_objetivo_semanal = self.vars['peso_objetivo_semanal'].get()
        
        # Título de resultados
        ttk.Label(
            self.resultados_frame,
            text="Resultados del Cálculo",
            font=('Arial', 14, 'bold')
        ).pack(pady=(0, 15))
        
        # Calorías de mantenimiento
        mantenimiento_frame = ttk.Frame(self.resultados_frame)
        mantenimiento_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            mantenimiento_frame,
            text="Calorías de mantenimiento:",
            font=('Arial', 12, 'bold')
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            mantenimiento_frame,
            text=f"{int(calorias_mantenimiento)} kcal/día",
            font=('Arial', 12),
            foreground='#2E8B57'
        ).pack(side=tk.RIGHT)
        
        # Calorías objetivo
        objetivo_frame = ttk.Frame(self.resultados_frame)
        objetivo_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            objetivo_frame,
            text="Calorías objetivo:",
            font=('Arial', 12, 'bold')
        ).pack(side=tk.LEFT)
        
        color_objetivo = '#e74c3c' if deficit_superavit < 0 else '#27ae60' if deficit_superavit > 0 else '#3498db'
        ttk.Label(
            objetivo_frame,
            text=f"{int(calorias_objetivo)} kcal/día",
            font=('Arial', 12, 'bold'),
            foreground=color_objetivo
        ).pack(side=tk.RIGHT)
        
        # Diferencia
        diferencia = calorias_objetivo - calorias_mantenimiento
        diferencia_frame = ttk.Frame(self.resultados_frame)
        diferencia_frame.pack(fill=tk.X, pady=(0, 15))
        
        if diferencia != 0:
            signo = "+" if diferencia > 0 else ""
            tipo = "Superávit" if diferencia > 0 else "Déficit"
            ttk.Label(
                diferencia_frame,
                text=f"{tipo}:",
                font=('Arial', 11)
            ).pack(side=tk.LEFT)
            
            ttk.Label(
                diferencia_frame,
                text=f"{signo}{int(diferencia)} kcal/día ({signo}{deficit_superavit:.1f}%)",
                font=('Arial', 11),
                foreground=color_objetivo
            ).pack(side=tk.RIGHT)
        
        # Separador
        ttk.Separator(self.resultados_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Cambio de peso esperado
        ttk.Label(
            self.resultados_frame,
            text="Cambio de peso esperado:",
            font=('Arial', 12, 'bold')
        ).pack(pady=(0, 10))
        
        if peso_objetivo_semanal != 0:
            signo = "+" if peso_objetivo_semanal > 0 else ""
            peso_mensual = peso_objetivo_semanal * 4.33  # Promedio de semanas por mes
            
            ttk.Label(
                self.resultados_frame,
                text=f"Semanal: {signo}{peso_objetivo_semanal:.2f} kg",
                font=('Arial', 11)
            ).pack()
            
            ttk.Label(
                self.resultados_frame,
                text=f"Mensual: {signo}{peso_mensual:.2f} kg",
                font=('Arial', 11)
            ).pack()
        else:
            ttk.Label(
                self.resultados_frame,
                text="Mantener peso actual",
                font=('Arial', 11)
            ).pack()
        
        # Separador
        ttk.Separator(self.resultados_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Recomendaciones
        self.mostrar_recomendaciones()
        
        # Habilitar botón guardar
        self.btn_guardar.config(state=tk.NORMAL)
        self.resultados_visibles = True
    
    def mostrar_recomendaciones(self):
        """Muestra recomendaciones específicas"""
        ttk.Label(
            self.resultados_frame,
            text="Recomendaciones:",
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W, pady=(0, 10))
        
        objetivo = self.usuario['objetivo']
        
        if objetivo == "Pérdida de grasa":
            recomendaciones = [
                "• Mantén un déficit moderado para preservar masa muscular",
                "• Prioriza el entrenamiento de fuerza",
                "• Ajusta las calorías si pierdes peso muy rápido o muy lento",
                "• Considera refeeds semanales si el déficit es prolongado"
            ]
        elif objetivo == "Ganancia muscular":
            recomendaciones = [
                "• Mantén un superávit moderado para minimizar ganancia de grasa",
                "• Enfócate en entrenamientos de hipertrofia",
                "• Ajusta las calorías según la ganancia de peso semanal",
                "• Sé paciente: la ganancia muscular es un proceso lento"
            ]
        else:
            recomendaciones = [
                "• Monitorea tu peso semanalmente",
                "• Ajusta las calorías si hay cambios no deseados",
                "• Mantén un entrenamiento consistente",
                "• Considera cambiar de objetivo según tus prioridades"
            ]
        
        for recomendacion in recomendaciones:
            ttk.Label(
                self.resultados_frame,
                text=recomendacion,
                font=('Arial', 10),
                foreground='#666666'
            ).pack(anchor=tk.W, pady=1)
    
    def cargar_datos_existentes(self):
        """Carga datos existentes si los hay"""
        datos_existentes = self.db.obtener_ultimo_calculo_nivel1(self.usuario_id)
        if datos_existentes:
            self.vars['calorias_mantenimiento'].set(datos_existentes['calorias_mantenimiento'])
            self.vars['calorias_objetivo'].set(datos_existentes['calorias_objetivo'])
            self.vars['factor_actividad'].set(datos_existentes['factor_actividad'])
            self.vars['deficit_superavit'].set(datos_existentes['deficit_superavit_porcentaje'])
            
            # Mostrar resultados
            self.mostrar_resultados()
    
    def guardar_resultados(self):
        """Guarda los resultados en la base de datos"""
        if not self.resultados_visibles:
            messagebox.showwarning("Sin resultados", "Primero debes calcular las calorías")
            return
        
        try:
            datos_calculo = {
                'calorias_mantenimiento': self.vars['calorias_mantenimiento'].get(),
                'calorias_objetivo': self.vars['calorias_objetivo'].get(),
                'factor_actividad': self.vars['factor_actividad'].get(),
                'deficit_superavit_porcentaje': self.vars['deficit_superavit'].get(),
                'metodo_calculo': self.vars['metodo'].get()
            }
            
            self.db.guardar_calculo_nivel1(self.usuario_id, datos_calculo)
            
            messagebox.showinfo(
                "Guardado exitoso",
                "Los cálculos del Nivel 1 han sido guardados correctamente.\\n"
                "Ahora puedes continuar al Nivel 2 - Macronutrientes."
            )
            
            # Llamar callback si existe
            if self.callback_actualizado:
                self.callback_actualizado()
            
            # Preguntar si quiere continuar al Nivel 2
            respuesta = messagebox.askyesno(
                "Continuar",
                "¿Quieres continuar al Nivel 2 - Macronutrientes?"
            )
            
            if respuesta:
                self.ventana.destroy()
                from nivel2_macros import Nivel2Macros
                Nivel2Macros(self.parent, self.usuario_id, self.db, self.callback_actualizado)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")
    
    def centrar_ventana(self):
        """Centra la ventana en la pantalla"""
        self.ventana.update_idletasks()
        width = self.ventana.winfo_width()
        height = self.ventana.winfo_height()
        pos_x = (self.ventana.winfo_screenwidth() // 2) - (width // 2)
        pos_y = (self.ventana.winfo_screenheight() // 2) - (height // 2)
        self.ventana.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

# Función de prueba
if __name__ == "__main__":
    from base_datos_nutricion import BaseDatosNutricion
    
    root = tk.Tk()
    root.withdraw()
    
    db = BaseDatosNutricion()
    
    # Crear usuario de prueba
    datos_usuario = {
        'nombre': 'Usuario Prueba',
        'edad': 30,
        'sexo': 'Masculino',
        'peso': 80.0,
        'altura': 180,
        'nivel_actividad': 'Activo',
        'objetivo': 'Ganancia muscular',
        'experiencia': 'Intermedio'
    }
    
    usuario_id = db.crear_usuario(datos_usuario)
    
    nivel1 = Nivel1Balance(root, usuario_id, db)
    root.mainloop()

