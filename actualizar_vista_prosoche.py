#!/usr/bin/env python3
"""
Script para actualizar la vista prosoche_nueva_entrada para manejar todos los campos del formulario
"""

import os
import re

def actualizar_vista_prosoche():
    """Actualizar la vista prosoche_nueva_entrada"""
    print("🔧 ACTUALIZANDO VISTA PROSOCHE_NUEVA_ENTRADA")
    print("=" * 60)
    
    try:
        # Leer el archivo views.py
        with open('diario/views.py', 'r', encoding='utf-8') as f:
            views_content = f.read()
        
        # Nueva función prosoche_nueva_entrada completa
        nueva_funcion = '''@login_required
def prosoche_nueva_entrada(request):
    """Crear nueva entrada del diario con todos los campos"""
    # Obtener mes actual
    hoy = timezone.now()
    mes_actual = hoy.strftime('%B')
    año_actual = hoy.year
    
    # Obtener o crear el mes actual
    prosoche_mes, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_actual,
        año=año_actual
    )
    
    if request.method == 'POST':
        # Obtener fecha del formulario o usar hoy
        fecha_str = request.POST.get('fecha')
        if fecha_str:
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except:
                fecha = hoy.date()
        else:
            fecha = hoy.date()

        # Crear o actualizar entrada
        entrada, created = ProsocheDiario.objects.get_or_create(
            prosoche_mes=prosoche_mes,
            fecha=fecha,
            defaults={
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
                'tareas_dia': request.POST.get('tareas_dia', '[]')  # JSON string
            }
        )

        if not created:
            # Actualizar entrada existente
            entrada.etiquetas = request.POST.get('etiquetas', '')
            entrada.estado_animo = int(request.POST.get('estado_animo', 3))
            entrada.persona_quiero_ser = request.POST.get('persona_quiero_ser', '')
            entrada.gratitud_1 = request.POST.get('gratitud_1', '')
            entrada.gratitud_2 = request.POST.get('gratitud_2', '')
            entrada.gratitud_3 = request.POST.get('gratitud_3', '')
            entrada.gratitud_4 = request.POST.get('gratitud_4', '')
            entrada.gratitud_5 = request.POST.get('gratitud_5', '')
            entrada.podcast_libro_dia = request.POST.get('podcast_libro_dia', '')
            entrada.felicidad = request.POST.get('felicidad', '')
            entrada.que_ha_ido_bien = request.POST.get('que_ha_ido_bien', '')
            entrada.que_puedo_mejorar = request.POST.get('que_puedo_mejorar', '')
            entrada.reflexiones_dia = request.POST.get('reflexiones_dia', '')
            entrada.tareas_dia = request.POST.get('tareas_dia', '[]')
            entrada.save()

        messages.success(request, 'Entrada del diario guardada correctamente.')
        return redirect('prosoche_dashboard')
    
    else:
        # GET request - mostrar formulario
        fecha = request.GET.get('fecha', hoy.date())
        
        # Buscar entrada existente para esta fecha
        entrada_existente = ProsocheDiario.objects.filter(
            prosoche_mes=prosoche_mes,
            fecha=fecha
        ).first()
        
        context = {
            'prosoche_mes': prosoche_mes,
            'fecha': fecha,
            'entrada_existente': entrada_existente
        }
        
        return render(request, 'diario/prosoche_entrada_form.html', context)'''
        
        # Buscar y reemplazar la función más reciente
        patron = r'@login_required\s*\ndef prosoche_nueva_entrada\(request\):.*?(?=@login_required|def \w+|class \w+|\Z)'
        
        # Encontrar todas las ocurrencias
        matches = list(re.finditer(patron, views_content, re.DOTALL))
        
        if matches:
            # Reemplazar la última ocurrencia (más reciente)
            ultima_match = matches[-1]
            views_content = views_content[:ultima_match.start()] + nueva_funcion + views_content[ultima_match.end():]
            
            # Crear backup
            backup_path = 'diario/views.py.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(views_content)
            
            # Escribir archivo actualizado
            with open('diario/views.py', 'w', encoding='utf-8') as f:
                f.write(views_content)
            
            print("✅ Vista prosoche_nueva_entrada actualizada correctamente")
            print(f"✅ Backup creado: {backup_path}")
            
            return True
        else:
            print("❌ No se encontró la función prosoche_nueva_entrada")
            return False
            
    except Exception as e:
        print(f"❌ Error al actualizar vista: {e}")
        return False

def verificar_urls():
    """Verificar que la URL para nueva entrada existe"""
    print("\n🔍 VERIFICANDO URLs")
    print("=" * 60)
    
    try:
        with open('diario/urls.py', 'r', encoding='utf-8') as f:
            urls_content = f.read()
        
        # Buscar URL para nueva entrada
        if 'entrada/nueva/' in urls_content:
            print("✅ URL 'entrada/nueva/' encontrada")
            return True
        else:
            print("❌ URL 'entrada/nueva/' NO encontrada")
            
            # Agregar URL si no existe
            nueva_url = "    path('prosoche/entrada/nueva/', views.prosoche_nueva_entrada, name='prosoche_nueva_entrada'),"
            
            # Buscar donde insertar
            if 'urlpatterns = [' in urls_content:
                # Insertar después de urlpatterns = [
                insert_pos = urls_content.find('urlpatterns = [') + len('urlpatterns = [')
                urls_content = urls_content[:insert_pos] + '\\n    ' + nueva_url + urls_content[insert_pos:]
                
                with open('diario/urls.py', 'w', encoding='utf-8') as f:
                    f.write(urls_content)
                
                print("✅ URL agregada a urls.py")
                return True
            else:
                print("❌ No se pudo agregar URL automáticamente")
                return False
                
    except Exception as e:
        print(f"❌ Error al verificar URLs: {e}")
        return False

def verificar_template_dashboard():
    """Verificar que el dashboard tiene el botón Nueva Entrada"""
    print("\\n🔍 VERIFICANDO BOTÓN NUEVA ENTRADA EN DASHBOARD")
    print("=" * 60)
    
    try:
        dashboard_path = 'diario/templates/diario/prosoche_dashboard.html'
        if not os.path.exists(dashboard_path):
            print("❌ Dashboard template no encontrado")
            return False
        
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            dashboard_content = f.read()
        
        if 'NUEVA ENTRADA' in dashboard_content:
            print("✅ Botón 'NUEVA ENTRADA' encontrado en dashboard")
            return True
        else:
            print("❌ Botón 'NUEVA ENTRADA' NO encontrado")
            
            # Buscar donde agregar el botón
            if 'Diario mensual' in dashboard_content:
                # Agregar botón después del título
                boton_html = '''
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h3 class="seccion-titulo">
                        <i class="fas fa-book"></i>
                        Diario mensual
                    </h3>
                    <a href="{% url 'prosoche_nueva_entrada' %}" class="btn btn-primary">
                        <i class="fas fa-plus"></i> NUEVA ENTRADA
                    </a>
                </div>'''
                
                # Reemplazar solo el título
                dashboard_content = dashboard_content.replace(
                    '<h3 class="seccion-titulo">\\n                        <i class="fas fa-book"></i>\\n                        Diario mensual\\n                    </h3>',
                    boton_html
                )
                
                with open(dashboard_path, 'w', encoding='utf-8') as f:
                    f.write(dashboard_content)
                
                print("✅ Botón 'NUEVA ENTRADA' agregado al dashboard")
                return True
            else:
                print("❌ No se pudo agregar botón automáticamente")
                return False
                
    except Exception as e:
        print(f"❌ Error al verificar dashboard: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 ACTUALIZANDO SISTEMA PROSOCHE PARA FORMULARIO COMPLETO")
    print("=" * 70)
    
    # Actualizar vista
    vista_ok = actualizar_vista_prosoche()
    
    # Verificar URLs
    urls_ok = verificar_urls()
    
    # Verificar dashboard
    dashboard_ok = verificar_template_dashboard()
    
    print("\\n🎉 RESUMEN DE ACTUALIZACIONES")
    print("=" * 70)
    print(f"✅ Vista actualizada: {'SÍ' if vista_ok else 'NO'}")
    print(f"✅ URLs verificadas: {'SÍ' if urls_ok else 'NO'}")
    print(f"✅ Dashboard actualizado: {'SÍ' if dashboard_ok else 'NO'}")
    
    if vista_ok and urls_ok:
        print("\\n🎯 ¡ACTUALIZACIÓN COMPLETADA!")
        print("=" * 70)
        print("\\n✅ AHORA LA VISTA MANEJA TODOS LOS CAMPOS:")
        print("- 📝 Etiquetas")
        print("- 😊 Estado de ánimo (1-5)")
        print("- 🌅 Persona que quiero ser (journaling mañana)")
        print("- 🙏 Gratitud (5 campos)")
        print("- 🌙 Journaling noche (podcast, felicidad, reflexiones)")
        print("- ✅ Tareas del día (JSON)")
        print("\\n🚀 PARA PROBAR:")
        print("1. python manage.py runserver")
        print("2. Ir a /diario/prosoche/")
        print("3. Hacer clic en 'NUEVA ENTRADA'")
        print("4. ¡Llenar el formulario completo!")
        print("5. Guardar y ver que todos los campos se guardan")
    else:
        print("\\n⚠️ ALGUNAS ACTUALIZACIONES FALLARON")
        print("Revisa los errores arriba y corrige manualmente si es necesario")

if __name__ == "__main__":
    main()
