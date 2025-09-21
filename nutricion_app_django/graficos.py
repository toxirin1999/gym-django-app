#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Gráficos
Genera visualizaciones para la aplicación de nutrición
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

class GeneradorGraficos:
    def __init__(self):
        """Inicializa el generador de gráficos"""
        # Configurar estilo de matplotlib
        plt.style.use('default')
        self.colores_piramide = {
            'nivel1': '#2E8B57',  # Verde oscuro - Balance Energético
            'nivel2': '#4682B4',  # Azul acero - Macronutrientes
            'nivel3': '#DAA520',  # Dorado - Micronutrientes
            'nivel4': '#CD853F',  # Marrón claro - Timing
            'nivel5': '#B22222'   # Rojo ladrillo - Suplementos
        }
    
    def crear_grafico_macros(self, proteina_g, grasa_g, carbohidratos_g):
        """
        Crea un gráfico de pastel para la distribución de macronutrientes
        
        Args:
            proteina_g: Gramos de proteína
            grasa_g: Gramos de grasa
            carbohidratos_g: Gramos de carbohidratos
            
        Returns:
            Figure de matplotlib
        """
        # Calcular calorías
        proteina_cal = proteina_g * 4
        grasa_cal = grasa_g * 9
        carbohidratos_cal = carbohidratos_g * 4
        total_cal = proteina_cal + grasa_cal + carbohidratos_cal
        
        # Calcular porcentajes
        porcentajes = [
            (proteina_cal / total_cal) * 100,
            (grasa_cal / total_cal) * 100,
            (carbohidratos_cal / total_cal) * 100
        ]
        
        # Crear figura
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Colores y etiquetas
        colores = ['#e74c3c', '#f39c12', '#27ae60']
        labels = ['Proteína', 'Grasa', 'Carbohidratos']
        
        # Crear gráfico de pastel
        wedges, texts, autotexts = ax.pie(
            porcentajes,
            labels=labels,
            colors=colores,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 12}
        )
        
        # Título
        ax.set_title('Distribución de Macronutrientes', fontsize=14, fontweight='bold')
        
        # Leyenda con gramos
        leyenda_labels = [
            f'Proteína: {proteina_g:.1f}g ({proteina_cal:.0f} kcal)',
            f'Grasa: {grasa_g:.1f}g ({grasa_cal:.0f} kcal)',
            f'Carbohidratos: {carbohidratos_g:.1f}g ({carbohidratos_cal:.0f} kcal)'
        ]
        ax.legend(wedges, leyenda_labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        
        plt.tight_layout()
        return fig
    
    def crear_grafico_calorias(self, calorias_mantenimiento, calorias_objetivo, objetivo):
        """
        Crea un gráfico de barras para mostrar calorías de mantenimiento vs objetivo
        
        Args:
            calorias_mantenimiento: Calorías de mantenimiento
            calorias_objetivo: Calorías objetivo
            objetivo: Objetivo del usuario
            
        Returns:
            Figure de matplotlib
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Datos
        categorias = ['Mantenimiento', 'Objetivo']
        valores = [calorias_mantenimiento, calorias_objetivo]
        
        # Colores según objetivo
        if objetivo == "Pérdida de grasa":
            colores = ['#3498db', '#e74c3c']
        elif objetivo == "Ganancia muscular":
            colores = ['#3498db', '#27ae60']
        else:
            colores = ['#3498db', '#3498db']
        
        # Crear barras
        barras = ax.bar(categorias, valores, color=colores, alpha=0.8)
        
        # Añadir valores en las barras
        for barra, valor in zip(barras, valores):
            height = barra.get_height()
            ax.text(barra.get_x() + barra.get_width()/2., height + 20,
                   f'{int(valor)} kcal',
                   ha='center', va='bottom', fontweight='bold')
        
        # Configurar ejes
        ax.set_ylabel('Calorías (kcal)', fontsize=12)
        ax.set_title(f'Calorías para {objetivo}', fontsize=14, fontweight='bold')
        
        # Añadir línea de diferencia si hay
        if calorias_objetivo != calorias_mantenimiento:
            diferencia = calorias_objetivo - calorias_mantenimiento
            signo = "+" if diferencia > 0 else ""
            tipo = "Superávit" if diferencia > 0 else "Déficit"
            
            ax.annotate(f'{tipo}: {signo}{int(diferencia)} kcal',
                       xy=(0.5, max(valores) * 0.8),
                       xycoords='data',
                       ha='center',
                       fontsize=12,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='yellow', alpha=0.7))
        
        plt.tight_layout()
        return fig
    
    def crear_grafico_progreso_peso(self, historial_peso):
        """
        Crea un gráfico de línea para el progreso del peso
        
        Args:
            historial_peso: Lista de diccionarios con 'fecha', 'peso'
            
        Returns:
            Figure de matplotlib
        """
        if not historial_peso or len(historial_peso) < 2:
            # Crear gráfico vacío si no hay datos suficientes
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, 'Registra tu peso regularmente\npara ver el progreso aquí',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=14, style='italic')
            ax.set_title('Progreso de Peso', fontsize=14, fontweight='bold')
            return fig
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Extraer datos (invertir para orden cronológico)
        historial_peso.reverse()
        fechas = [registro['fecha'] for registro in historial_peso]
        pesos = [registro['peso'] for registro in historial_peso]
        
        # Crear línea de progreso
        ax.plot(range(len(pesos)), pesos, marker='o', linewidth=2, markersize=6, color='#3498db')
        
        # Configurar ejes
        ax.set_xlabel('Registros', fontsize=12)
        ax.set_ylabel('Peso (kg)', fontsize=12)
        ax.set_title('Progreso de Peso', fontsize=14, fontweight='bold')
        
        # Añadir grid
        ax.grid(True, alpha=0.3)
        
        # Mostrar tendencia si hay suficientes datos
        if len(pesos) >= 3:
            # Calcular línea de tendencia
            x = np.array(range(len(pesos)))
            y = np.array(pesos)
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            
            ax.plot(x, p(x), "--", alpha=0.8, color='red', linewidth=2, label='Tendencia')
            
            # Mostrar cambio total
            cambio_total = pesos[-1] - pesos[0]
            signo = "+" if cambio_total > 0 else ""
            ax.text(0.02, 0.98, f'Cambio total: {signo}{cambio_total:.1f} kg',
                   transform=ax.transAxes, va='top',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue', alpha=0.7))
            
            ax.legend()
        
        plt.tight_layout()
        return fig
    
    def crear_grafico_piramide_progreso(self, progreso_niveles):
        """
        Crea un gráfico visual de la pirámide con el progreso
        
        Args:
            progreso_niveles: Diccionario con el progreso de cada nivel
            
        Returns:
            Figure de matplotlib
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Configurar la pirámide
        niveles = [
            {'y': 0, 'width': 10, 'height': 1.5, 'nivel': 1, 'texto': 'BALANCE ENERGÉTICO'},
            {'y': 1.5, 'width': 8, 'height': 1.5, 'nivel': 2, 'texto': 'MACRONUTRIENTES'},
            {'y': 3, 'width': 6, 'height': 1.5, 'nivel': 3, 'texto': 'MICRONUTRIENTES'},
            {'y': 4.5, 'width': 4, 'height': 1.5, 'nivel': 4, 'texto': 'TIMING'},
            {'y': 6, 'width': 2, 'height': 1.5, 'nivel': 5, 'texto': 'SUPLEMENTOS'}
        ]
        
        for nivel in niveles:
            x = (10 - nivel['width']) / 2  # Centrar
            
            # Determinar color según progreso
            nivel_key = f'nivel_{nivel["nivel"]}_completado'
            completado = progreso_niveles.get(nivel_key, False)
            
            color_key = f"nivel{nivel['nivel']}"
            color_base = self.colores_piramide[color_key]
            
            if completado:
                color = color_base
                alpha = 1.0
                edge_color = 'gold'
                edge_width = 3
            else:
                color = color_base
                alpha = 0.3
                edge_color = 'black'
                edge_width = 1
            
            # Crear rectángulo del nivel
            rect = patches.Rectangle(
                (x, nivel['y']), nivel['width'], nivel['height'],
                linewidth=edge_width, edgecolor=edge_color,
                facecolor=color, alpha=alpha
            )
            ax.add_patch(rect)
            
            # Añadir texto
            ax.text(5, nivel['y'] + nivel['height']/2, 
                   f"NIVEL {nivel['nivel']}: {nivel['texto']}",
                   ha='center', va='center', fontweight='bold',
                   color='white' if completado else 'black',
                   fontsize=10)
            
            # Añadir marca de completado
            if completado:
                ax.text(x + nivel['width'] - 0.3, nivel['y'] + nivel['height'] - 0.3,
                       '✓', ha='center', va='center', fontsize=20, color='gold',
                       fontweight='bold')
        
        # Configurar ejes
        ax.set_xlim(-0.5, 10.5)
        ax.set_ylim(-0.5, 8)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Título
        ax.text(5, 8.5, 'THE MUSCLE & STRENGTH PYRAMID - NUTRICIÓN',
               ha='center', va='center', fontsize=16, fontweight='bold')
        
        # Leyenda
        completados = sum(1 for key, value in progreso_niveles.items() 
                         if key.endswith('_completado') and value)
        ax.text(5, -1, f'Progreso: {completados}/5 niveles completados',
               ha='center', va='center', fontsize=12, style='italic')
        
        plt.tight_layout()
        return fig
    
    def integrar_en_tkinter(self, figura, parent_widget):
        """
        Integra una figura de matplotlib en un widget de tkinter
        
        Args:
            figura: Figure de matplotlib
            parent_widget: Widget padre de tkinter
            
        Returns:
            Canvas de tkinter con el gráfico
        """
        canvas = FigureCanvasTkAgg(figura, parent_widget)
        canvas.draw()
        return canvas.get_tk_widget()

# Función de prueba
if __name__ == "__main__":
    import tkinter as tk
    
    # Crear ventana de prueba
    root = tk.Tk()
    root.title("Prueba de Gráficos")
    root.geometry("800x600")
    
    # Crear generador
    generador = GeneradorGraficos()
    
    # Crear gráfico de prueba
    fig = generador.crear_grafico_macros(150, 80, 300)
    
    # Integrar en tkinter
    canvas_widget = generador.integrar_en_tkinter(fig, root)
    canvas_widget.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()

