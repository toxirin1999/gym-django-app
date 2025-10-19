#!/usr/bin/env python3
"""
Script de sincronización para aplicar solo los cambios faltantes en Prosoche
"""

import os
import shutil

def verificar_y_corregir_views():
    """Verificar y corregir las vistas que faltan"""
    print("🔄 VERIFICANDO Y CORRIGIENDO VIEWS.PY")
    print("=" * 60)
    
    try:
        # Leer archivo views.py actual
        with open('diario/views.py', 'r', encoding='utf-8') as f:
            views_content = f.read()
        
        # Verificar si faltan imports
        imports_faltantes = []
        if 'from datetime import datetime, date' not in views_content:
            imports_faltantes.append('from datetime import datetime, date')
        if 'from django.urls import reverse' not in views_content:
            imports_faltantes.append('from django.urls import reverse')
        
        # Agregar imports faltantes
        if imports_faltantes:
            ultimo_import = views_content.rfind('from ')
            fin_ultimo_import = views_content.find('\n', ultimo_import)
            nuevos_imports = '\n' + '\n'.join(imports_faltantes) + '\n'
            views_content = (
                views_content[:fin_ultimo_import] + 
                nuevos_imports + 
                views_content[fin_ultimo_import:]
            )
        
        # Verificar si falta la función prosoche_nueva_entrada completa
        if 'def prosoche_nueva_entrada(' in views_content:
            # Buscar si la función está incompleta
            inicio_funcion = views_content.find('def prosoche_nueva_entrada(')
            siguiente_def = views_content.find('\ndef ', inicio_funcion + 1)
            siguiente_at = views_content.find('\n@', inicio_funcion + 1)
            
            fin_funcion = min(x for x in [siguiente_def, siguiente_at] if x > 0)
            if fin_funcion == float('inf'):
                fin_funcion = len(views_content)
            
            funcion_actual = views_content[inicio_funcion:fin_funcion]
            
            # Si la función está incompleta, reemplazarla
            if 'tareas_dia' not in funcion_actual or 'gratitud_1' not in funcion_actual:
                print("⚠️ Función prosoche_nueva_entrada incompleta, actualizando...")
                
                nueva_funcion = '''def prosoche_nueva_entrada(request):
    """Vista para crear nueva entrada del diario"""
    from datetime import date
    
    # Obtener fecha actual o fecha específica
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha = date.today()
    else:
        fecha = date.today()
    
    # Obtener o crear el mes de Prosoche
    mes_nombre = fecha.strftime('%B')
    año = fecha.year
    
    prosoche_mes, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_nombre,
        año=año,
        defaults={
            'objetivo_mes_1': '',
            'objetivo_mes_2': '',
            'objetivo_mes_3': ''
        }
    )
    
    # Verificar si ya existe una entrada para esta fecha
    entrada_existente = ProsocheDiario.objects.filter(
        prosoche_mes=prosoche_mes,
        fecha=fecha
    ).first()
    
    if request.method == 'POST':
        try:
            # Procesar datos del formulario
            data = {
                'etiquetas': request.POST.get('etiquetas', ''),
                'estado_animo': int(request.POST.get('estado_animo', 3)),
                'persona_quiero_ser': request.POST.get('persona_quiero_ser', ''),
                'gratitud_1': request.POST.get('gratitud_1', ''),
                'gratitud_2': request.POST.get('gratitud_2', ''),
                'gratitud_3': request.POST.get('gratitud_3', ''),
                'gratitud_4': request.POST.get('gratitud_4', ''),
                'gratitud_5': request.POST.get('gratitud_5', ''),
                'podcast_libro_dia': request.POST.get('podcast_libro_dia', ''),
                'felicidad': request.POST.get('felicidad', ''),
                'que_ha_ido_bien': request.POST.get('que_ha_ido_bien', ''),
                'que_puedo_mejorar': request.POST.get('que_puedo_mejorar', ''),
                'reflexiones_dia': request.POST.get('reflexiones_dia', ''),
            }
            
            # Procesar tareas del día
            tareas_json = request.POST.get('tareas_dia', '[]')
            try:
                data['tareas_dia'] = json.loads(tareas_json)
            except json.JSONDecodeError:
                data['tareas_dia'] = []
            
            # Crear o actualizar entrada
            if entrada_existente:
                # Actualizar entrada existente
                for key, value in data.items():
                    setattr(entrada_existente, key, value)
                entrada_existente.save()
                messages.success(request, f'Entrada del {fecha.strftime("%d/%m/%Y")} actualizada correctamente.')
            else:
                # Crear nueva entrada
                data['prosoche_mes'] = prosoche_mes
                data['fecha'] = fecha
                ProsocheDiario.objects.create(**data)
                messages.success(request, f'Nueva entrada del {fecha.strftime("%d/%m/%Y")} creada correctamente.')
            
            return redirect('prosoche_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error al guardar la entrada: {str(e)}')
    
    # Preparar datos para el formulario
    form_data = {}
    if entrada_existente:
        form_data = {
            'etiquetas': entrada_existente.etiquetas,
            'estado_animo': entrada_existente.estado_animo,
            'persona_quiero_ser': entrada_existente.persona_quiero_ser,
            'tareas_dia': entrada_existente.tareas_dia,
            'gratitud_1': entrada_existente.gratitud_1,
            'gratitud_2': entrada_existente.gratitud_2,
            'gratitud_3': entrada_existente.gratitud_3,
            'gratitud_4': entrada_existente.gratitud_4,
            'gratitud_5': entrada_existente.gratitud_5,
            'podcast_libro_dia': entrada_existente.podcast_libro_dia,
            'felicidad': entrada_existente.felicidad,
            'que_ha_ido_bien': entrada_existente.que_ha_ido_bien,
            'que_puedo_mejorar': entrada_existente.que_puedo_mejorar,
            'reflexiones_dia': entrada_existente.reflexiones_dia,
        }
    
    context = {
        'fecha': fecha,
        'prosoche_mes': prosoche_mes,
        'form': type('Form', (), form_data)(),
        'entrada_existente': entrada_existente,
        'es_edicion': entrada_existente is not None,
    }
    
    return render(request, 'diario/prosoche_entrada_form.html', context)

'''
                
                # Reemplazar la función
                views_content = (
                    views_content[:inicio_funcion] + 
                    nueva_funcion + 
                    views_content[fin_funcion:]
                )
        
        # Guardar archivo actualizado
        with open('diario/views.py', 'w', encoding='utf-8') as f:
            f.write(views_content)
        
        print("✅ Views.py verificado y corregido")
        return True
        
    except Exception as e:
        print(f"❌ Error al verificar views.py: {e}")
        return False

def crear_template_filters():
    """Crear filtros personalizados para templates"""
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
'''
        
        with open('diario/templatetags/diario_filters.py', 'w', encoding='utf-8') as f:
            f.write(filtros_content)
        
        print("✅ Filtros personalizados creados")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear filtros: {e}")
        return False

def actualizar_template_entrada():
    """Actualizar template de entrada con el formulario completo"""
    print("\n🔄 ACTUALIZANDO TEMPLATE DE ENTRADA")
    print("=" * 60)
    
    try:
        # Verificar si existe el template actual
        template_path = 'diario/templates/diario/prosoche_entrada_form.html'
        
        if os.path.exists(template_path):
            # Leer template actual
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Verificar si tiene los campos completos
            campos_necesarios = [
                'persona_quiero_ser',
                'gratitud_1',
                'tareas_dia',
                'podcast_libro_dia',
                'felicidad',
                'que_ha_ido_bien',
                'que_puedo_mejorar',
                'reflexiones_dia'
            ]
            
            faltan_campos = [campo for campo in campos_necesarios if campo not in template_content]
            
            if faltan_campos:
                print(f"⚠️ Template incompleto, faltan campos: {faltan_campos}")
                # Copiar template completo
                shutil.copy('prosoche_entrada_form.html', template_path)
                print("✅ Template actualizado con formulario completo")
            else:
                print("✅ Template ya está completo")
        else:
            # Crear template desde cero
            os.makedirs('diario/templates/diario', exist_ok=True)
            shutil.copy('prosoche_entrada_form.html', template_path)
            print("✅ Template creado con formulario completo")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al actualizar template: {e}")
        return False

def verificar_urls():
    """Verificar que las URLs estén correctas"""
    print("\n🔄 VERIFICANDO URLS")
    print("=" * 60)
    
    try:
        # Leer archivo urls.py
        with open('diario/urls.py', 'r', encoding='utf-8') as f:
            urls_content = f.read()
        
        # Verificar URLs necesarias
        urls_necesarias = [
            'prosoche_nueva_entrada',
            'prosoche_dashboard'
        ]
        
        urls_faltantes = [url for url in urls_necesarias if url not in urls_content]
        
        if urls_faltantes:
            print(f"⚠️ URLs faltantes: {urls_faltantes}")
            
            # Agregar URLs faltantes
            if 'prosoche_nueva_entrada' not in urls_content:
                nueva_url = "    path('prosoche/entrada/nueva/', views.prosoche_nueva_entrada, name='prosoche_nueva_entrada'),"
                
                # Buscar donde insertar
                prosoche_section = urls_content.find('# PROSOCHE')
                if prosoche_section != -1:
                    fin_prosoche = urls_content.find('# EUDAIMONIA', prosoche_section)
                    if fin_prosoche == -1:
                        fin_prosoche = urls_content.find(']', prosoche_section)
                    
                    urls_content = (
                        urls_content[:fin_prosoche] + 
                        '    ' + nueva_url + '\n    \n' +
                        urls_content[fin_prosoche:]
                    )
            
            # Guardar URLs actualizadas
            with open('diario/urls.py', 'w', encoding='utf-8') as f:
                f.write(urls_content)
            
            print("✅ URLs actualizadas")
        else:
            print("✅ URLs ya están correctas")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al verificar URLs: {e}")
        return False

def actualizar_dashboard_prosoche():
    """Actualizar dashboard de Prosoche con botón de nueva entrada"""
    print("\n🔄 ACTUALIZANDO DASHBOARD PROSOCHE")
    print("=" * 60)
    
    try:
        dashboard_path = 'diario/templates/diario/prosoche_dashboard.html'
        
        if os.path.exists(dashboard_path):
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                dashboard_content = f.read()
            
            # Verificar si tiene el botón de nueva entrada
            if 'prosoche_nueva_entrada' not in dashboard_content:
                print("⚠️ Dashboard sin botón de nueva entrada, actualizando...")
                
                # Buscar sección del diario mensual y agregar botón
                if 'Diario Mensual' in dashboard_content:
                    # Agregar botón después del título
                    dashboard_content = dashboard_content.replace(
                        'Diario Mensual</h3>',
                        '''Diario Mensual</h3>
                        <div class="mb-3">
                            <a href="{% url 'prosoche_nueva_entrada' %}" class="btn btn-primary">
                                <i class="fas fa-plus"></i> Nueva Entrada
                            </a>
                        </div>'''
                    )
                
                # Guardar dashboard actualizado
                with open(dashboard_path, 'w', encoding='utf-8') as f:
                    f.write(dashboard_content)
                
                print("✅ Dashboard actualizado con botón de nueva entrada")
            else:
                print("✅ Dashboard ya tiene botón de nueva entrada")
        else:
            print("⚠️ Dashboard no encontrado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al actualizar dashboard: {e}")
        return False

def ejecutar_migraciones():
    """Ejecutar migraciones si es necesario"""
    print("\n🔄 EJECUTANDO MIGRACIONES")
    print("=" * 60)
    
    try:
        # Verificar si hay migraciones pendientes
        os.system('python manage.py makemigrations diario')
        os.system('python manage.py migrate')
        print("✅ Migraciones ejecutadas")
        return True
        
    except Exception as e:
        print(f"❌ Error en migraciones: {e}")
        return False

def main():
    """Función principal de sincronización"""
    print("🔄 SINCRONIZANDO CAMBIOS DE PROSOCHE")
    print("=" * 70)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists('manage.py'):
        print("❌ Error: No se encontró manage.py. Ejecuta desde el directorio raíz del proyecto.")
        return
    
    # Verificar archivos necesarios
    archivos_necesarios = ['prosoche_entrada_form.html']
    for archivo in archivos_necesarios:
        if not os.path.exists(archivo):
            print(f"❌ Error: No se encontró {archivo}")
            return
    
    # Ejecutar sincronización
    pasos = [
        ("Verificar y corregir views.py", verificar_y_corregir_views),
        ("Crear filtros personalizados", crear_template_filters),
        ("Actualizar template de entrada", actualizar_template_entrada),
        ("Verificar URLs", verificar_urls),
        ("Actualizar dashboard Prosoche", actualizar_dashboard_prosoche),
        ("Ejecutar migraciones", ejecutar_migraciones)
    ]
    
    exitos = 0
    for nombre, funcion in pasos:
        print(f"\n📋 {nombre}...")
        if funcion():
            exitos += 1
        else:
            print(f"❌ Error en: {nombre}")
    
    if exitos == len(pasos):
        print("\n" + "=" * 70)
        print("🎉 ¡SINCRONIZACIÓN COMPLETADA!")
        print("=" * 70)
        print("\n✅ CAMBIOS APLICADOS:")
        print("- ✅ Views.py actualizado con función completa")
        print("- ✅ Filtros personalizados creados")
        print("- ✅ Template de entrada completo")
        print("- ✅ URLs verificadas y corregidas")
        print("- ✅ Dashboard con botón de nueva entrada")
        print("- ✅ Migraciones ejecutadas")
        print("\n🚀 AHORA PUEDES:")
        print("1. python manage.py runserver")
        print("2. Ir a /diario/prosoche/")
        print("3. Hacer clic en 'Nueva Entrada'")
        print("4. ¡Disfrutar del formulario completo!")
    else:
        print(f"\n⚠️ Se completaron {exitos}/{len(pasos)} pasos")
        print("Algunos cambios pueden no haberse aplicado correctamente.")

if __name__ == "__main__":
    main()
