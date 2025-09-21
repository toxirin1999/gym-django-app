#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nivel 2 - Macronutrientes
Implementa los cálculos de proteína, grasas y carbohidratos según el libro
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches

class Nivel2Macros:
    def __init__(self, parent, usuario_id, db, callback_actualizado=None):
        """
        Inicializa la ventana del Nivel 2 - Macronutrientes
        
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
        
        # Obtener datos del usuario y nivel 1
        self.usuario = self.db.obtener_usuario_por_id(usuario_id)
        self.datos_nivel1 = self.db.obtener_ultimo_calculo_nivel1(usuario_id)
        
        if not self.usuario or not self.datos_nivel1:
            messagebox.showerror(
                "Error", 
                "Necesitas completar el Nivel 1 (Balance Energético) antes de continuar"
            )
            return
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Nivel 2 - Macronutrientes")
        self.ventana.geometry("900x800")
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
        # Variables de entrada
        self.vars['proteina_metodo'] = tk.StringVar(value="peso_corporal")
        self.vars['proteina_gramos_kg'] = tk.DoubleVar()
        self.vars['grasa_porcentaje'] = tk.DoubleVar()
        
        # Variables de resultados
        self.vars['proteina_gramos'] = tk.DoubleVar()
        self.vars['proteina_calorias'] = tk.DoubleVar()
        self.vars['grasa_gramos'] = tk.DoubleVar()
        self.vars['grasa_calorias'] = tk.DoubleVar()
        self.vars['carbohidratos_gramos'] = tk.DoubleVar()
        self.vars['carbohidratos_calorias'] = tk.DoubleVar()
        
        # Porcentajes
        self.vars['proteina_porcentaje'] = tk.DoubleVar()
        self.vars['grasa_porcentaje_calc'] = tk.DoubleVar()
        self.vars['carbohidratos_porcentaje'] = tk.DoubleVar()
        
        # Establecer valores por defecto según objetivo
        self.establecer_valores_defecto()
    
    def establecer_valores_defecto(self):
        """Establece valores por defecto según el objetivo del usuario"""
        objetivo = self.usuario['objetivo']
        
        if objetivo == "Pérdida de grasa":
            # Proteína alta para preservar masa muscular
            self.vars['proteina_gramos_kg'].set(2.4)  # Promedio del rango 2.2-2.6
            self.vars['grasa_porcentaje'].set(20)     # Promedio del rango 15-25%
        elif objetivo == "Ganancia muscular":
            # Proteína moderada, más calorías para grasas y carbohidratos
            self.vars['proteina_gramos_kg'].set(1.9)  # Promedio del rango 1.6-2.2
            self.vars['grasa_porcentaje'].set(25)     # Promedio del rango 20-30%
        else:  # Mantenimiento
            self.vars['proteina_gramos_kg'].set(2.0)
            self.vars['grasa_porcentaje'].set(25)
    
    def crear_interfaz(self):
        """Crea la interfaz del Nivel 2"""
        # Frame principal con scroll
        main_frame = ttk.Frame(self.ventana)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título
        titulo = ttk.Label(
            main_frame,
            text="NIVEL 2 - MACRONUTRIENTES",
            font=('Arial', 18, 'bold'),
            foreground='#4682B4'
        )
        titulo.pack(pady=(0, 10))
        
        # Subtítulo
        subtitulo = ttk.Label(
            main_frame,
            text="Distribución de proteínas, grasas y carbohidratos",
            font=('Arial', 12),
            foreground='#666666'
        )
        subtitulo.pack(pady=(0, 20))
        
        # Información del nivel 1
        self.crear_info_nivel1(main_frame)
        
        # Configuración de macronutrientes
        self.crear_seccion_configuracion(main_frame)
        
        # Resultados
        self.crear_seccion_resultados(main_frame)
        
        # Botones
        self.crear_botones(main_frame)
    
    def crear_info_nivel1(self, parent):
        """Crea la sección con información del Nivel 1"""
        info_frame = ttk.LabelFrame(parent, text="Datos del Nivel 1 - Balance Energético", padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        calorias_objetivo = int(self.datos_nivel1['calorias_objetivo'])
        objetivo = self.usuario['objetivo']
        
        ttk.Label(
            info_frame,
            text=f"Calorías objetivo: {calorias_objetivo} kcal/día",
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        ttk.Label(
            info_frame,
            text=f"Objetivo: {objetivo}",
            font=('Arial', 11)
        ).pack(anchor=tk.W, pady=(5, 0))
    
    def crear_seccion_configuracion(self, parent):
        """Crea la sección de configuración de macronutrientes"""
        config_frame = ttk.LabelFrame(parent, text="Configuración de Macronutrientes", padding=15)
        config_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Proteína
        self.crear_seccion_proteina(config_frame)
        
        # Separador
        ttk.Separator(config_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Grasa
        self.crear_seccion_grasa(config_frame)
        
        # Separador
        ttk.Separator(config_frame, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Información sobre carbohidratos
        ttk.Label(
            config_frame,
            text="CARBOHIDRATOS:",
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        ttk.Label(
            config_frame,
            text="Los carbohidratos se calculan automáticamente con las calorías restantes",
            font=('Arial', 10),
            foreground='#666666'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # Botón calcular
        btn_calcular = ttk.Button(
            config_frame,
            text="Calcular Macronutrientes",
            command=self.calcular_macronutrientes
        )
        btn_calcular.pack(pady=(20, 0))
    
    def crear_seccion_proteina(self, parent):
        """Crea la sección de configuración de proteína"""
        ttk.Label(
            parent,
            text="PROTEÍNA:",
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        # Explicación según objetivo
        objetivo = self.usuario['objetivo']
        if objetivo == "Pérdida de grasa":
            explicacion = "En déficit calórico: 2.2 - 2.6 g/kg para preservar masa muscular"
        elif objetivo == "Ganancia muscular":
            explicacion = "En superávit calórico: 1.6 - 2.2 g/kg es suficiente"
        else:
            explicacion = "Para mantenimiento: 1.8 - 2.2 g/kg es adecuado"
        
        ttk.Label(
            parent,
            text=explicacion,
            font=('Arial', 10),
            foreground='#666666'
        ).pack(anchor=tk.W, pady=(5, 10))
        
        # Frame para controles de proteína
        proteina_frame = ttk.Frame(parent)
        proteina_frame.pack(fill=tk.X)
        
        # Método de cálculo
        ttk.Label(
            proteina_frame,
            text="Método de cálculo:",
            font=('Arial', 10, 'bold')
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        metodo_frame = ttk.Frame(proteina_frame)
        metodo_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        ttk.Radiobutton(
            metodo_frame,
            text="Gramos por kg de peso corporal",
            variable=self.vars['proteina_metodo'],
            value="peso_corporal"
        ).pack(anchor=tk.W)
        
        ttk.Radiobutton(
            metodo_frame,
            text="Altura en cm = gramos de proteína (método alternativo)",
            variable=self.vars['proteina_metodo'],
            value="altura_cm"
        ).pack(anchor=tk.W)
        
        # Control de gramos por kg
        ttk.Label(
            proteina_frame,
            text="Gramos por kg de peso:",
            font=('Arial', 10, 'bold')
        ).grid(row=2, column=0, sticky="w", pady=(10, 5))
        
        self.proteina_scale = tk.Scale(
            proteina_frame,
            from_=1.6,
            to=2.6,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=self.vars['proteina_gramos_kg'],
            length=300
        )
        self.proteina_scale.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        # Mostrar valor actual
        self.proteina_valor_label = ttk.Label(
            proteina_frame,
            text="",
            font=('Arial', 9),
            foreground='#666666'
        )
        self.proteina_valor_label.grid(row=4, column=0, columnspan=2, sticky="w")
        
        # Actualizar label inicial
        self.actualizar_proteina_label()
        self.vars['proteina_gramos_kg'].trace('w', lambda *args: self.actualizar_proteina_label())
    
    def crear_seccion_grasa(self, parent):
        """Crea la sección de configuración de grasa"""
        ttk.Label(
            parent,
            text="GRASA:",
            font=('Arial', 12, 'bold')
        ).pack(anchor=tk.W)
        
        # Explicación según objetivo
        objetivo = self.usuario['objetivo']
        if objetivo == "Pérdida de grasa":
            explicacion = "En déficit: 15-25% de las calorías totales (mínimo 0.5 g/kg)"
        elif objetivo == "Ganancia muscular":
            explicacion = "En superávit: 20-30% de las calorías totales"
        else:
            explicacion = "Para mantenimiento: 20-30% de las calorías totales"
        
        ttk.Label(
            parent,
            text=explicacion,
            font=('Arial', 10),
            foreground='#666666'
        ).pack(anchor=tk.W, pady=(5, 10))
        
        # Frame para controles de grasa
        grasa_frame = ttk.Frame(parent)
        grasa_frame.pack(fill=tk.X)
        
        ttk.Label(
            grasa_frame,
            text="Porcentaje de calorías totales:",
            font=('Arial', 10, 'bold')
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.grasa_scale = tk.Scale(
            grasa_frame,
            from_=15,
            to=40,
            resolution=1,
            orient=tk.HORIZONTAL,
            variable=self.vars['grasa_porcentaje'],
            length=300
        )
        self.grasa_scale.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        # Mostrar valor actual
        self.grasa_valor_label = ttk.Label(
            grasa_frame,
            text="",
            font=('Arial', 9),
            foreground='#666666'
        )
        self.grasa_valor_label.grid(row=2, column=0, columnspan=2, sticky="w")
        
        # Actualizar label inicial
        self.actualizar_grasa_label()
        self.vars['grasa_porcentaje'].trace('w', lambda *args: self.actualizar_grasa_label())
    
    def actualizar_proteina_label(self):
        """Actualiza el label de proteína"""
        gramos_kg = self.vars['proteina_gramos_kg'].get()
        peso = self.usuario['peso']
        gramos_totales = gramos_kg * peso
        
        self.proteina_valor_label.config(
            text=f"{gramos_kg} g/kg × {peso} kg = {gramos_totales:.1f} g de proteína"
        )
    
    def actualizar_grasa_label(self):
        """Actualiza el label de grasa"""
        porcentaje = self.vars['grasa_porcentaje'].get()
        calorias_objetivo = self.datos_nivel1['calorias_objetivo']
        calorias_grasa = calorias_objetivo * (porcentaje / 100)
        gramos_grasa = calorias_grasa / 9
        
        self.grasa_valor_label.config(
            text=f"{porcentaje}% × {int(calorias_objetivo)} kcal = {calorias_grasa:.0f} kcal = {gramos_grasa:.1f} g de grasa"
        )
    
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
            text="Volver al Nivel 1",
            command=self.volver_nivel1
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            botones_frame,
            text="Cerrar",
            command=self.ventana.destroy
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        self.btn_guardar = ttk.Button(
            botones_frame,
            text="Guardar y Continuar al Nivel 3",
            command=self.guardar_resultados,
            state=tk.DISABLED
        )
        self.btn_guardar.pack(side=tk.RIGHT)
    
    def calcular_macronutrientes(self):
        """Calcula la distribución de macronutrientes"""
        try:
            calorias_objetivo = self.datos_nivel1['calorias_objetivo']
            peso = self.usuario['peso']
            altura = self.usuario['altura']
            
            # Calcular proteína
            if self.vars['proteina_metodo'].get() == "altura_cm":
                proteina_gramos = altura
            else:
                proteina_gramos = self.vars['proteina_gramos_kg'].get() * peso
            
            proteina_calorias = proteina_gramos * 4
            
            # Calcular grasa
            grasa_porcentaje = self.vars['grasa_porcentaje'].get()
            grasa_calorias = calorias_objetivo * (grasa_porcentaje / 100)
            grasa_gramos = grasa_calorias / 9
            
            # Verificar mínimo de grasa (0.5 g/kg)
            grasa_minima = 0.5 * peso
            if grasa_gramos < grasa_minima:
                messagebox.showwarning(
                    "Grasa insuficiente",
                    f"La cantidad de grasa calculada ({grasa_gramos:.1f}g) es menor al mínimo "
                    f"recomendado ({grasa_minima:.1f}g = 0.5g/kg).\\n"
                    f"Se ajustará automáticamente al mínimo."
                )
                grasa_gramos = grasa_minima
                grasa_calorias = grasa_gramos * 9
                grasa_porcentaje = (grasa_calorias / calorias_objetivo) * 100
            
            # Calcular carbohidratos (resto de calorías)
            carbohidratos_calorias = calorias_objetivo - proteina_calorias - grasa_calorias
            carbohidratos_gramos = carbohidratos_calorias / 4
            
            # Verificar mínimo de carbohidratos (1 g/kg)
            carbohidratos_minimos = 1.0 * peso
            if carbohidratos_gramos < carbohidratos_minimos:
                messagebox.showwarning(
                    "Carbohidratos insuficientes",
                    f"La cantidad de carbohidratos calculada ({carbohidratos_gramos:.1f}g) es menor "
                    f"al mínimo recomendado ({carbohidratos_minimos:.1f}g = 1g/kg).\\n"
                    f"Considera reducir la proteína o grasa, o aumentar las calorías totales."
                )
            
            # Calcular porcentajes
            proteina_porcentaje = (proteina_calorias / calorias_objetivo) * 100
            grasa_porcentaje_calc = (grasa_calorias / calorias_objetivo) * 100
            carbohidratos_porcentaje = (carbohidratos_calorias / calorias_objetivo) * 100
            
            # Guardar resultados
            self.vars['proteina_gramos'].set(proteina_gramos)
            self.vars['proteina_calorias'].set(proteina_calorias)
            self.vars['grasa_gramos'].set(grasa_gramos)
            self.vars['grasa_calorias'].set(grasa_calorias)
            self.vars['carbohidratos_gramos'].set(carbohidratos_gramos)
            self.vars['carbohidratos_calorias'].set(carbohidratos_calorias)
            self.vars['proteina_porcentaje'].set(proteina_porcentaje)
            self.vars['grasa_porcentaje_calc'].set(grasa_porcentaje_calc)
            self.vars['carbohidratos_porcentaje'].set(carbohidratos_porcentaje)
            
            # Mostrar resultados
            self.mostrar_resultados()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en el cálculo: {str(e)}")
    
    def mostrar_resultados(self):
        """Muestra los resultados del cálculo"""
        # Limpiar frame de resultados
        for widget in self.resultados_frame.winfo_children():
            widget.destroy()
        
        # Crear notebook para organizar resultados
        notebook = ttk.Notebook(self.resultados_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de resumen
        self.crear_pestana_resumen(notebook)
        
        # Pestaña de gráfico
        self.crear_pestana_grafico(notebook)
        
        # Pestaña de ejemplos
        self.crear_pestana_ejemplos(notebook)
        
        # Habilitar botón guardar
        self.btn_guardar.config(state=tk.NORMAL)
        self.resultados_visibles = True
    
    def crear_pestana_resumen(self, notebook):
        """Crea la pestaña de resumen de resultados"""
        resumen_frame = ttk.Frame(notebook)
        notebook.add(resumen_frame, text="Resumen")
        
        # Título
        ttk.Label(
            resumen_frame,
            text="Distribución de Macronutrientes",
            font=('Arial', 14, 'bold')
        ).pack(pady=(10, 20))
        
        # Tabla de resultados
        tabla_frame = ttk.Frame(resumen_frame)
        tabla_frame.pack(pady=(0, 20))
        
        # Headers
        headers = ["Macronutriente", "Gramos", "Calorías", "Porcentaje"]
        for i, header in enumerate(headers):
            ttk.Label(
                tabla_frame,
                text=header,
                font=('Arial', 11, 'bold')
            ).grid(row=0, column=i, padx=10, pady=5, sticky="w")
        
        # Datos
        datos = [
            ("Proteína", f"{self.vars['proteina_gramos'].get():.1f}g", 
             f"{self.vars['proteina_calorias'].get():.0f} kcal", 
             f"{self.vars['proteina_porcentaje'].get():.1f}%"),
            ("Grasa", f"{self.vars['grasa_gramos'].get():.1f}g", 
             f"{self.vars['grasa_calorias'].get():.0f} kcal", 
             f"{self.vars['grasa_porcentaje_calc'].get():.1f}%"),
            ("Carbohidratos", f"{self.vars['carbohidratos_gramos'].get():.1f}g", 
             f"{self.vars['carbohidratos_calorias'].get():.0f} kcal", 
             f"{self.vars['carbohidratos_porcentaje'].get():.1f}%")
        ]
        
        colores = ['#e74c3c', '#f39c12', '#27ae60']
        
        for i, (macro, gramos, calorias, porcentaje) in enumerate(datos):
            row = i + 1
            
            ttk.Label(tabla_frame, text=macro, font=('Arial', 10, 'bold')).grid(
                row=row, column=0, padx=10, pady=5, sticky="w"
            )
            ttk.Label(tabla_frame, text=gramos).grid(
                row=row, column=1, padx=10, pady=5, sticky="w"
            )
            ttk.Label(tabla_frame, text=calorias).grid(
                row=row, column=2, padx=10, pady=5, sticky="w"
            )
            ttk.Label(tabla_frame, text=porcentaje, foreground=colores[i]).grid(
                row=row, column=3, padx=10, pady=5, sticky="w"
            )
        
        # Total
        ttk.Separator(tabla_frame, orient='horizontal').grid(
            row=4, column=0, columnspan=4, sticky="ew", pady=10
        )
        
        total_calorias = (self.vars['proteina_calorias'].get() + 
                         self.vars['grasa_calorias'].get() + 
                         self.vars['carbohidratos_calorias'].get())
        
        ttk.Label(tabla_frame, text="TOTAL", font=('Arial', 11, 'bold')).grid(
            row=5, column=0, padx=10, pady=5, sticky="w"
        )
        ttk.Label(tabla_frame, text=f"{total_calorias:.0f} kcal", 
                 font=('Arial', 10, 'bold')).grid(
            row=5, column=2, padx=10, pady=5, sticky="w"
        )
        ttk.Label(tabla_frame, text="100%", font=('Arial', 10, 'bold')).grid(
            row=5, column=3, padx=10, pady=5, sticky="w"
        )
    
    def crear_pestana_grafico(self, notebook):
        """Crea la pestaña con gráfico de distribución"""
        grafico_frame = ttk.Frame(notebook)
        notebook.add(grafico_frame, text="Gráfico")
        
        # Crear gráfico de pastel
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Datos para el gráfico
        sizes = [
            self.vars['proteina_porcentaje'].get(),
            self.vars['grasa_porcentaje_calc'].get(),
            self.vars['carbohidratos_porcentaje'].get()
        ]
        labels = ['Proteína', 'Grasa', 'Carbohidratos']
        colors = ['#e74c3c', '#f39c12', '#27ae60']
        
        # Crear gráfico
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct='%1.1f%%',
            startangle=90, textprops={'fontsize': 12}
        )
        
        ax.set_title('Distribución de Macronutrientes', fontsize=14, fontweight='bold')
        
        # Agregar leyenda con gramos
        leyenda_labels = [
            f'Proteína: {self.vars["proteina_gramos"].get():.1f}g',
            f'Grasa: {self.vars["grasa_gramos"].get():.1f}g',
            f'Carbohidratos: {self.vars["carbohidratos_gramos"].get():.1f}g'
        ]
        ax.legend(wedges, leyenda_labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        
        # Integrar gráfico en tkinter
        canvas = FigureCanvasTkAgg(fig, grafico_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def crear_pestana_ejemplos(self, notebook):
        """Crea la pestaña con ejemplos de alimentos"""
        ejemplos_frame = ttk.Frame(notebook)
        notebook.add(ejemplos_frame, text="Ejemplos de Alimentos")
        
        # Scroll para ejemplos
        canvas = tk.Canvas(ejemplos_frame)
        scrollbar = ttk.Scrollbar(ejemplos_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Ejemplos de proteína
        self.crear_ejemplos_proteina(scrollable_frame)
        
        # Ejemplos de grasa
        self.crear_ejemplos_grasa(scrollable_frame)
        
        # Ejemplos de carbohidratos
        self.crear_ejemplos_carbohidratos(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def crear_ejemplos_proteina(self, parent):
        """Crea ejemplos de fuentes de proteína"""
        frame = ttk.LabelFrame(parent, text="Fuentes de Proteína", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        proteina_objetivo = self.vars['proteina_gramos'].get()
        
        ttk.Label(
            frame,
            text=f"Objetivo: {proteina_objetivo:.1f}g de proteína",
            font=('Arial', 11, 'bold')
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ejemplos = [
            "• Pechuga de pollo (100g) = 23g proteína",
            "• Huevos enteros (2 unidades) = 12g proteína",
            "• Atún en agua (100g) = 25g proteína",
            "• Proteína whey (1 scoop ~30g) = 20-25g proteína",
            "• Carne magra (100g) = 20-25g proteína",
            "• Pescado blanco (100g) = 18-22g proteína",
            "• Queso cottage (100g) = 11g proteína",
            "• Legumbres cocidas (100g) = 8-10g proteína"
        ]
        
        for ejemplo in ejemplos:
            ttk.Label(frame, text=ejemplo, font=('Arial', 9)).pack(anchor=tk.W, pady=1)
    
    def crear_ejemplos_grasa(self, parent):
        """Crea ejemplos de fuentes de grasa"""
        frame = ttk.LabelFrame(parent, text="Fuentes de Grasa", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        grasa_objetivo = self.vars['grasa_gramos'].get()
        
        ttk.Label(
            frame,
            text=f"Objetivo: {grasa_objetivo:.1f}g de grasa",
            font=('Arial', 11, 'bold')
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ejemplos = [
            "• Aceite de oliva (1 cucharada ~15ml) = 14g grasa",
            "• Aguacate (1/2 unidad ~100g) = 15g grasa",
            "• Nueces (30g) = 18g grasa",
            "• Almendras (30g) = 16g grasa",
            "• Mantequilla de cacahuete (2 cucharadas) = 16g grasa",
            "• Salmón (100g) = 12g grasa",
            "• Yemas de huevo (2 unidades) = 10g grasa",
            "• Aceitunas (50g) = 8g grasa"
        ]
        
        for ejemplo in ejemplos:
            ttk.Label(frame, text=ejemplo, font=('Arial', 9)).pack(anchor=tk.W, pady=1)
    
    def crear_ejemplos_carbohidratos(self, parent):
        """Crea ejemplos de fuentes de carbohidratos"""
        frame = ttk.LabelFrame(parent, text="Fuentes de Carbohidratos", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        carbs_objetivo = self.vars['carbohidratos_gramos'].get()
        
        ttk.Label(
            frame,
            text=f"Objetivo: {carbs_objetivo:.1f}g de carbohidratos",
            font=('Arial', 11, 'bold')
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ejemplos = [
            "• Arroz blanco cocido (100g) = 28g carbohidratos",
            "• Avena (50g en seco) = 32g carbohidratos",
            "• Pan integral (2 rebanadas) = 24g carbohidratos",
            "• Plátano (1 unidad mediana) = 27g carbohidratos",
            "• Pasta cocida (100g) = 25g carbohidratos",
            "• Patata cocida (150g) = 30g carbohidratos",
            "• Manzana (1 unidad mediana) = 25g carbohidratos",
            "• Quinoa cocida (100g) = 22g carbohidratos"
        ]
        
        for ejemplo in ejemplos:
            ttk.Label(frame, text=ejemplo, font=('Arial', 9)).pack(anchor=tk.W, pady=1)
    
    def cargar_datos_existentes(self):
        """Carga datos existentes si los hay"""
        datos_existentes = self.db.obtener_ultimo_calculo_nivel2(self.usuario_id)
        if datos_existentes:
            # Cargar valores en variables
            self.vars['proteina_gramos'].set(datos_existentes['proteina_gramos'])
            self.vars['grasa_gramos'].set(datos_existentes['grasa_gramos'])
            self.vars['carbohidratos_gramos'].set(datos_existentes['carbohidratos_gramos'])
            self.vars['proteina_calorias'].set(datos_existentes['proteina_calorias'])
            self.vars['grasa_calorias'].set(datos_existentes['grasa_calorias'])
            self.vars['carbohidratos_calorias'].set(datos_existentes['carbohidratos_calorias'])
            self.vars['proteina_porcentaje'].set(datos_existentes['proteina_porcentaje'])
            self.vars['grasa_porcentaje_calc'].set(datos_existentes['grasa_porcentaje'])
            self.vars['carbohidratos_porcentaje'].set(datos_existentes['carbohidratos_porcentaje'])
            
            # Calcular valores de entrada aproximados
            peso = self.usuario['peso']
            proteina_gramos_kg = datos_existentes['proteina_gramos'] / peso
            self.vars['proteina_gramos_kg'].set(proteina_gramos_kg)
            self.vars['grasa_porcentaje'].set(datos_existentes['grasa_porcentaje'])
            
            # Mostrar resultados
            self.mostrar_resultados()
    
    def guardar_resultados(self):
        """Guarda los resultados en la base de datos"""
        if not self.resultados_visibles:
            messagebox.showwarning("Sin resultados", "Primero debes calcular los macronutrientes")
            return
        
        try:
            datos_macros = {
                'proteina_gramos': self.vars['proteina_gramos'].get(),
                'grasa_gramos': self.vars['grasa_gramos'].get(),
                'carbohidratos_gramos': self.vars['carbohidratos_gramos'].get(),
                'proteina_calorias': self.vars['proteina_calorias'].get(),
                'grasa_calorias': self.vars['grasa_calorias'].get(),
                'carbohidratos_calorias': self.vars['carbohidratos_calorias'].get(),
                'proteina_porcentaje': self.vars['proteina_porcentaje'].get(),
                'grasa_porcentaje': self.vars['grasa_porcentaje_calc'].get(),
                'carbohidratos_porcentaje': self.vars['carbohidratos_porcentaje'].get()
            }
            
            self.db.guardar_calculo_nivel2(self.usuario_id, datos_macros)
            
            messagebox.showinfo(
                "Guardado exitoso",
                "Los cálculos del Nivel 2 han sido guardados correctamente.\\n"
                "Ahora puedes continuar al Nivel 3 - Micronutrientes."
            )
            
            # Llamar callback si existe
            if self.callback_actualizado:
                self.callback_actualizado()
            
            # Preguntar si quiere continuar al Nivel 3
            respuesta = messagebox.askyesno(
                "Continuar",
                "¿Quieres continuar al Nivel 3 - Micronutrientes y Agua?"
            )
            
            if respuesta:
                self.ventana.destroy()
                from nivel3_micros import Nivel3Micros
                Nivel3Micros(self.parent, self.usuario_id, self.db, self.callback_actualizado)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")
    
    def volver_nivel1(self):
        """Vuelve al Nivel 1"""
        self.ventana.destroy()
        from nivel1_balance import Nivel1Balance
        Nivel1Balance(self.parent, self.usuario_id, self.db, self.callback_actualizado)
    
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
    
    # Crear datos del nivel 1
    datos_nivel1 = {
        'calorias_mantenimiento': 2800,
        'calorias_objetivo': 3200,
        'factor_actividad': 1.7,
        'deficit_superavit_porcentaje': 15,
        'metodo_calculo': 'calculo_rapido'
    }
    
    db.guardar_calculo_nivel1(usuario_id, datos_nivel1)
    
    nivel2 = Nivel2Macros(root, usuario_id, db)
    root.mainloop()

