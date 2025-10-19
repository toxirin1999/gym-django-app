#!/usr/bin/env python3
"""
Script para implementar el formulario completo de entrada del diario Prosoche
basado en el diseño de Notion
"""

import os
import shutil

def actualizar_modelo_prosoche_diario():
    """Actualizar el modelo ProsocheDiario con todos los campos necesarios"""
    print("🔄 ACTUALIZANDO MODELO PROSOCHE DIARIO")
    print("=" * 60)
    
    try:
        # Leer el archivo models.py actual
        with open('diario/models.py', 'r', encoding='utf-8') as f:
            models_content = f.read()
        
        # Leer el nuevo modelo completo
        with open('prosoche_diario_modelo_completo.py', 'r', encoding='utf-8') as f:
            nuevo_modelo = f.read()
        
        # Buscar y reemplazar la clase ProsocheDiario
        inicio_clase = models_content.find('class ProsocheDiario(models.Model):')
        if inicio_clase != -1:
            # Encontrar el final de la clase (siguiente class o final del archivo)
            siguiente_clase = models_content.find('\nclass ', inicio_clase + 1)
            if siguiente_clase == -1:
                siguiente_clase = len(models_content)
            
            # Reemplazar la clase completa
            models_actualizado = (
                models_content[:inicio_clase] + 
                nuevo_modelo[nuevo_modelo.find('class ProsocheDiario'):] + 
                models_content[siguiente_clase:]
            )
        else:
            # Si no existe, agregar al final
            models_actualizado = models_content + '\n\n' + nuevo_modelo
        
        # Guardar archivo actualizado
        with open('diario/models.py', 'w', encoding='utf-8') as f:
            f.write(models_actualizado)
        
        print("✅ Modelo ProsocheDiario actualizado con todos los campos")
        return True
        
    except Exception as e:
        print(f"❌ Error al actualizar modelo: {e}")
        return False

def crear_template_filters():
    """Crear archivo de filtros personalizados para templates"""
    print("\n🔄 CREANDO FILTROS PERSONALIZADOS")
    print("=" * 60)
    
    try:
        # Crear directorio templatetags si no existe
        os.makedirs('diario/templatetags', exist_ok=True)
        
        # Crear __init__.py
        with open('diario/templatetags/__init__.py', 'w') as f:
            f.write('')
        
        # Crear filtros personalizados
        filtros_content = '''from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Filtro para acceder a valores dinámicos en templates"""
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return dictionary.get(key, '') if hasattr(dictionary, 'get') else ''

@register.filter
def add(value, arg):
    """Filtro para sumar valores"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def get_item(dictionary, key):
    """Obtener item de diccionario"""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key, '')
    return ''

@register.filter
def multiply(value, arg):
    """Multiplicar valores"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
'''
        
        with open('diario/templatetags/diario_filters.py', 'w', encoding='utf-8') as f:
            f.write(filtros_content)
        
        print("✅ Filtros personalizados creados")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear filtros: {e}")
        return False

def actualizar_vistas():
    """Actualizar vistas con las nuevas funciones para entrada completa"""
    print("\n🔄 ACTUALIZANDO VISTAS")
    print("=" * 60)
    
    try:
        # Leer archivo views.py actual
        with open('diario/views.py', 'r', encoding='utf-8') as f:
            views_content = f.read()
        
        # Leer nuevas vistas
        with open('prosoche_views_entrada_completa.py', 'r', encoding='utf-8') as f:
            nuevas_vistas = f.read()
        
        # Agregar imports necesarios al inicio
        imports_necesarios = '''import json
from datetime import datetime, date
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
'''
        
        # Verificar si los imports ya existen
        if 'import json' not in views_content:
            # Agregar imports después de los imports existentes
            ultimo_import = views_content.rfind('from ')
            fin_ultimo_import = views_content.find('\n', ultimo_import)
            views_content = (
                views_content[:fin_ultimo_import] + 
                '\n' + imports_necesarios + 
                views_content[fin_ultimo_import:]
            )
        
        # Buscar y reemplazar función prosoche_nueva_entrada
        inicio_funcion = views_content.find('def prosoche_nueva_entrada(')
        if inicio_funcion != -1:
            # Encontrar el final de la función
            siguiente_funcion = views_content.find('\n@', inicio_funcion + 1)
            if siguiente_funcion == -1:
                siguiente_funcion = views_content.find('\ndef ', inicio_funcion + 1)
            if siguiente_funcion == -1:
                siguiente_funcion = len(views_content)
            
            # Extraer solo las funciones de Prosoche de las nuevas vistas
            nuevas_funciones = nuevas_vistas[nuevas_vistas.find('@login_required\ndef prosoche_nueva_entrada'):]
            
            # Reemplazar
            views_actualizado = (
                views_content[:inicio_funcion] + 
                nuevas_funciones + 
                views_content[siguiente_funcion:]
            )
        else:
            # Si no existe, agregar al final
            views_actualizado = views_content + '\n\n' + nuevas_vistas
        
        # Guardar archivo actualizado
        with open('diario/views.py', 'w', encoding='utf-8') as f:
            f.write(views_actualizado)
        
        print("✅ Vistas actualizadas con funciones de entrada completa")
        return True
        
    except Exception as e:
        print(f"❌ Error al actualizar vistas: {e}")
        return False

def instalar_template():
    """Instalar template del formulario de entrada"""
    print("\n🔄 INSTALANDO TEMPLATE DE ENTRADA")
    print("=" * 60)
    
    try:
        # Crear directorio de templates si no existe
        os.makedirs('diario/templates/diario', exist_ok=True)
        
        # Copiar template
        shutil.copy('prosoche_entrada_form.html', 'diario/templates/diario/prosoche_entrada_form.html')
        
        print("✅ Template de entrada instalado")
        return True
        
    except Exception as e:
        print(f"❌ Error al instalar template: {e}")
        return False

def actualizar_urls():
    """Actualizar URLs con las nuevas rutas"""
    print("\n🔄 ACTUALIZANDO URLS")
    print("=" * 60)
    
    try:
        # Leer archivo urls.py actual
        with open('diario/urls.py', 'r', encoding='utf-8') as f:
            urls_content = f.read()
        
        # Nuevas URLs para entrada completa
        nuevas_urls = '''    # Entrada completa del diario
    path('prosoche/entrada/nueva/', views.prosoche_nueva_entrada, name='prosoche_nueva_entrada'),
    path('prosoche/entrada/editar/<int:entrada_id>/', views.prosoche_editar_entrada, name='prosoche_editar_entrada'),
    path('prosoche/entrada/detalle/<int:entrada_id>/', views.prosoche_entrada_detalle, name='prosoche_entrada_detalle'),
    path('prosoche/entrada/auto-save/', views.prosoche_auto_save_entrada, name='prosoche_auto_save_entrada'),
    path('prosoche/entrada/toggle-tarea/', views.prosoche_toggle_tarea, name='prosoche_toggle_tarea'),
    path('prosoche/entradas/<str:mes>/<int:año>/', views.prosoche_entradas_mes, name='prosoche_entradas_mes'),'''
        
        # Buscar sección de Prosoche y agregar URLs
        prosoche_section = urls_content.find('# PROSOCHE')
        if prosoche_section != -1:
            # Encontrar el final de la sección Prosoche
            fin_prosoche = urls_content.find('# EUDAIMONIA', prosoche_section)
            if fin_prosoche == -1:
                fin_prosoche = urls_content.find(']', prosoche_section)
            
            # Verificar si las URLs ya existen
            if 'prosoche_nueva_entrada' not in urls_content:
                urls_actualizado = (
                    urls_content[:fin_prosoche] + 
                    nuevas_urls + '\n    \n    ' +
                    urls_content[fin_prosoche:]
                )
            else:
                urls_actualizado = urls_content
        else:
            urls_actualizado = urls_content
        
        # Guardar archivo actualizado
        with open('diario/urls.py', 'w', encoding='utf-8') as f:
            f.write(urls_actualizado)
        
        print("✅ URLs actualizadas con rutas de entrada completa")
        return True
        
    except Exception as e:
        print(f"❌ Error al actualizar URLs: {e}")
        return False

def crear_migracion():
    """Crear migración para los nuevos campos"""
    print("\n🔄 CREANDO MIGRACIÓN")
    print("=" * 60)
    
    try:
        os.system('python manage.py makemigrations diario --name prosoche_entrada_completa')
        print("✅ Migración creada")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear migración: {e}")
        return False

def ejecutar_migracion():
    """Ejecutar migración"""
    print("\n🔄 EJECUTANDO MIGRACIÓN")
    print("=" * 60)
    
    try:
        os.system('python manage.py migrate')
        print("✅ Migración ejecutada")
        return True
        
    except Exception as e:
        print(f"❌ Error al ejecutar migración: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 IMPLEMENTANDO FORMULARIO COMPLETO DE ENTRADA DEL DIARIO")
    print("=" * 70)
    
    # Verificar archivos necesarios
    archivos_necesarios = [
        'prosoche_diario_modelo_completo.py',
        'prosoche_entrada_form.html',
        'prosoche_views_entrada_completa.py'
    ]
    
    for archivo in archivos_necesarios:
        if not os.path.exists(archivo):
            print(f"❌ Error: No se encontró {archivo}")
            return
    
    # Ejecutar pasos
    pasos = [
        ("Actualizar modelo ProsocheDiario", actualizar_modelo_prosoche_diario),
        ("Crear filtros personalizados", crear_template_filters),
        ("Actualizar vistas", actualizar_vistas),
        ("Instalar template", instalar_template),
        ("Actualizar URLs", actualizar_urls),
        ("Crear migración", crear_migracion),
        ("Ejecutar migración", ejecutar_migracion)
    ]
    
    exitos = 0
    for nombre, funcion in pasos:
        print(f"\n📋 {nombre}...")
        if funcion():
            exitos += 1
        else:
            print(f"❌ Error en: {nombre}")
            break
    
    if exitos == len(pasos):
        print("\n" + "=" * 70)
        print("🎉 ¡FORMULARIO DE ENTRADA IMPLEMENTADO EXITOSAMENTE!")
        print("=" * 70)
        print("\n✅ CARACTERÍSTICAS IMPLEMENTADAS:")
        print("- 📝 Formulario completo idéntico a Notion")
        print("- 🌅 Journaling mañana: '¿Qué persona quiero ser hoy?'")
        print("- ✅ Tareas del día con checkboxes interactivos")
        print("- 🙏 Gratitud: 5 puntos de agradecimiento")
        print("- 🌙 Journaling noche: Podcast, felicidad, reflexiones")
        print("- 😊 Estado de ánimo con botones interactivos")
        print("- 🏷️ Etiquetas y fecha automática")
        print("- 💾 Auto-guardado y validación")
        print("- 🎨 Diseño cyberpunk idéntico a tu app")
        print("\n🚀 URLS DISPONIBLES:")
        print("- /diario/prosoche/entrada/nueva/ - Crear nueva entrada")
        print("- /diario/prosoche/entrada/editar/<id>/ - Editar entrada")
        print("- /diario/prosoche/entrada/detalle/<id>/ - Ver detalle")
        print("\n✨ ¡Tu diario ahora tiene el formulario completo de Notion!")
    else:
        print(f"\n❌ Se completaron {exitos}/{len(pasos)} pasos")

if __name__ == "__main__":
    main()
