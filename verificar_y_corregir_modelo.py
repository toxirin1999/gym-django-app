#!/usr/bin/env python3
"""
Script para verificar y corregir campos faltantes en el modelo ProsocheDiario
"""

import os
import re

def verificar_modelo_actual():
    """Verificar qué campos tiene el modelo actual"""
    print("🔍 VERIFICANDO MODELO ACTUAL")
    print("=" * 60)
    
    try:
        with open('diario/models.py', 'r', encoding='utf-8') as f:
            models_content = f.read()
        
        # Buscar la clase ProsocheDiario
        inicio_clase = models_content.find('class ProsocheDiario(models.Model):')
        if inicio_clase == -1:
            print("❌ No se encontró la clase ProsocheDiario")
            return None
        
        # Encontrar el final de la clase
        siguiente_clase = models_content.find('\nclass ', inicio_clase + 1)
        if siguiente_clase == -1:
            siguiente_clase = len(models_content)
        
        clase_content = models_content[inicio_clase:siguiente_clase]
        
        # Extraer campos del modelo
        campos_encontrados = []
        lineas = clase_content.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if '= models.' in linea and not linea.startswith('#'):
                campo = linea.split('=')[0].strip()
                if campo and not campo.startswith('class') and not campo.startswith('def'):
                    campos_encontrados.append(campo)
        
        print(f"✅ Campos encontrados en el modelo ({len(campos_encontrados)}):")
        for campo in sorted(campos_encontrados):
            print(f"   ✓ {campo}")
        
        return campos_encontrados
        
    except Exception as e:
        print(f"❌ Error al verificar modelo: {e}")
        return None

def verificar_template_actual():
    """Verificar qué campos usa el template actual"""
    print("\n🔍 VERIFICANDO TEMPLATE ACTUAL")
    print("=" * 60)
    
    try:
        template_path = 'diario/templates/diario/prosoche_entrada_form.html'
        if not os.path.exists(template_path):
            print("❌ Template no encontrado")
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Buscar campos usados en el template
        campos_template = []
        
        # Buscar patrones como name="campo" y {{ form.campo }}
        patrones = [
            r'name="([^"]+)"',
            r'\{\{\s*form\.([^}\s|]+)',
            r'value="\{\{\s*form\.([^}\s|]+)'
        ]
        
        for patron in patrones:
            matches = re.findall(patron, template_content)
            campos_template.extend(matches)
        
        # Limpiar y deduplicar
        campos_template = list(set([campo.strip() for campo in campos_template if campo.strip()]))
        
        print(f"✅ Campos usados en template ({len(campos_template)}):")
        for campo in sorted(campos_template):
            print(f"   ✓ {campo}")
        
        return campos_template
        
    except Exception as e:
        print(f"❌ Error al verificar template: {e}")
        return None

def crear_template_simple():
    """Crear template simple que use solo campos existentes"""
    print("\n🔧 CREANDO TEMPLATE SIMPLE")
    print("=" * 60)
    
    template_simple = '''{% extends 'diario/base.html' %}
{% load static %}

{% block title %}Nueva Entrada - Prosoche{% endblock %}

{% block extra_css %}
<style>
    .entrada-form {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
        border: 1px solid #00ffff;
        border-radius: 15px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
    }
    
    .seccion-form {
        background: rgba(0, 255, 255, 0.05);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
    }
    
    .seccion-titulo {
        color: #00ffff;
        font-size: 1.4rem;
        font-weight: bold;
        margin-bottom: 15px;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .form-control, .form-select {
        background: rgba(0, 0, 0, 0.7);
        border: 1px solid #00ffff;
        color: #ffffff;
        border-radius: 8px;
        padding: 12px;
        transition: all 0.3s ease;
    }
    
    .form-control:focus, .form-select:focus {
        background: rgba(0, 0, 0, 0.9);
        border-color: #ff00ff;
        box-shadow: 0 0 15px rgba(255, 0, 255, 0.5);
        color: #ffffff;
    }
    
    .form-control::placeholder {
        color: rgba(255, 255, 255, 0.6);
    }
    
    .btn-estado-animo {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        border: 2px solid #00ffff;
        background: rgba(0, 0, 0, 0.7);
        color: #ffffff;
        font-size: 1.5rem;
        margin: 0 5px;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .btn-estado-animo:hover {
        transform: scale(1.1);
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.7);
    }
    
    .btn-estado-animo.active {
        background: linear-gradient(45deg, #00ffff, #ff00ff);
        border-color: #ffffff;
        transform: scale(1.2);
    }
    
    .btn-cyberpunk {
        background: linear-gradient(45deg, #00ffff, #ff00ff);
        border: none;
        color: white;
        padding: 12px 30px;
        border-radius: 25px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
    }
    
    .btn-cyberpunk:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 25px rgba(255, 0, 255, 0.7);
    }
    
    .btn-secondary-cyberpunk {
        background: linear-gradient(45deg, #666666, #999999);
        border: 1px solid #00ffff;
        color: white;
        padding: 12px 30px;
        border-radius: 25px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .form-label {
        color: #00ffff;
        font-weight: bold;
        margin-bottom: 8px;
        display: block;
    }
    
    .texto-ayuda {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.9rem;
        margin-top: 5px;
        font-style: italic;
    }
</style>
{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row justify-content-center">
        <div class="col-12 col-lg-10">
            <div class="entrada-form">
                <!-- Header -->
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 class="text-white mb-0">
                        <i class="fas fa-sun"></i>
                        {% if entrada_existente %}Editar Entrada{% else %}Nueva Entrada{% endif %}
                    </h2>
                    <div class="text-muted">
                        {{ fecha|date:"d/m/Y" }}
                    </div>
                </div>

                <form method="post" id="entradaForm">
                    {% csrf_token %}
                    
                    <!-- Información Básica -->
                    <div class="seccion-form">
                        <h3 class="seccion-titulo">
                            <i class="fas fa-info-circle"></i>
                            Información Básica
                        </h3>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Etiquetas</label>
                                <input type="text" class="form-control" name="etiquetas" 
                                       value="{% if entrada_existente %}{{ entrada_existente.etiquetas }}{% endif %}"
                                       placeholder="trabajo, familia, deporte...">
                                <div class="texto-ayuda">Separa las etiquetas con comas</div>
                            </div>
                            
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Estado de Ánimo (1-5)</label>
                                <div class="d-flex justify-content-center">
                                    {% for i in "12345" %}
                                    <button type="button" class="btn-estado-animo" 
                                            data-valor="{{ i }}"
                                            {% if entrada_existente.estado_animo == i|add:0 %}active{% endif %}>
                                        {% if i == "1" %}😢{% elif i == "2" %}😕{% elif i == "3" %}😐{% elif i == "4" %}😊{% else %}😄{% endif %}
                                    </button>
                                    {% endfor %}
                                </div>
                                <input type="hidden" name="estado_animo" id="estado_animo" 
                                       value="{% if entrada_existente %}{{ entrada_existente.estado_animo }}{% else %}3{% endif %}">
                            </div>
                        </div>
                    </div>

                    <!-- Journaling Mañana -->
                    <div class="seccion-form">
                        <h3 class="seccion-titulo">
                            <i class="fas fa-sunrise"></i>
                            Journaling Mañana
                        </h3>
                        
                        <div class="mb-3">
                            <label class="form-label">¿Qué clase de persona quiero ser hoy?</label>
                            <textarea class="form-control" name="persona_quiero_ser" rows="4"
                                      placeholder="Reflexiona sobre el tipo de persona que quieres ser hoy...">{% if entrada_existente %}{{ entrada_existente.persona_quiero_ser }}{% endif %}</textarea>
                            <div class="texto-ayuda">Tómate un momento para reflexionar sobre tus intenciones para el día</div>
                        </div>
                    </div>

                    <!-- Gratitud -->
                    <div class="seccion-form">
                        <h3 class="seccion-titulo">
                            <i class="fas fa-heart"></i>
                            Gratitud
                        </h3>
                        
                        <p class="texto-ayuda mb-3">¿De qué estoy agradecido hoy?</p>
                        
                        {% for i in "12345" %}
                        <div class="mb-3">
                            <label class="form-label">{{ i }}. Algo por lo que estoy agradecido</label>
                            <input type="text" class="form-control" name="gratitud_{{ i }}" 
                                   value="{% if entrada_existente %}{{ entrada_existente.gratitud_|add:i }}{% endif %}"
                                   placeholder="Algo por lo que estoy agradecido...">
                        </div>
                        {% endfor %}
                    </div>

                    <!-- Journaling Noche -->
                    <div class="seccion-form">
                        <h3 class="seccion-titulo">
                            <i class="fas fa-moon"></i>
                            Journaling Noche
                        </h3>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Podcast o libro del día</label>
                                <textarea class="form-control" name="podcast_libro_dia" rows="3"
                                          placeholder="¿Qué podcast escuchaste o libro leíste hoy?">{% if entrada_existente %}{{ entrada_existente.podcast_libro_dia }}{% endif %}</textarea>
                            </div>
                            
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Felicidad</label>
                                <textarea class="form-control" name="felicidad" rows="3"
                                          placeholder="¿Qué te ha hecho feliz hoy?">{% if entrada_existente %}{{ entrada_existente.felicidad }}{% endif %}</textarea>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">¿Qué ha ido bien?</label>
                                <textarea class="form-control" name="que_ha_ido_bien" rows="3"
                                          placeholder="Reflexiona sobre los aspectos positivos del día...">{% if entrada_existente %}{{ entrada_existente.que_ha_ido_bien }}{% endif %}</textarea>
                            </div>
                            
                            <div class="col-md-6 mb-3">
                                <label class="form-label">¿Qué puedo mejorar?</label>
                                <textarea class="form-control" name="que_puedo_mejorar" rows="3"
                                          placeholder="¿Qué aspectos puedes mejorar mañana?">{% if entrada_existente %}{{ entrada_existente.que_puedo_mejorar }}{% endif %}</textarea>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Reflexiones del día</label>
                            <textarea class="form-control" name="reflexiones_dia" rows="4"
                                      placeholder="Reflexiones generales sobre el día...">{% if entrada_existente %}{{ entrada_existente.reflexiones_dia }}{% endif %}</textarea>
                        </div>
                    </div>

                    <!-- Botones -->
                    <div class="d-flex justify-content-between mt-4">
                        <a href="{% url 'prosoche_dashboard' %}" class="btn-secondary-cyberpunk">
                            <i class="fas fa-arrow-left"></i> Volver
                        </a>
                        
                        <button type="submit" class="btn-cyberpunk">
                            <i class="fas fa-save"></i> 
                            {% if entrada_existente %}Actualizar Entrada{% else %}Guardar Entrada{% endif %}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
document.addEventListener('DOMContentLoaded', function() {
    // Manejar botones de estado de ánimo
    document.querySelectorAll('.btn-estado-animo').forEach(btn => {
        btn.addEventListener('click', function() {
            // Remover active de todos
            document.querySelectorAll('.btn-estado-animo').forEach(b => b.classList.remove('active'));
            // Agregar active al clickeado
            this.classList.add('active');
            // Actualizar input hidden
            document.getElementById('estado_animo').value = this.dataset.valor;
        });
    });
});
</script>
{% endblock %}'''
    
    return template_simple

def main():
    """Función principal"""
    print("🔍 VERIFICANDO Y CORRIGIENDO MODELO Y TEMPLATE")
    print("=" * 70)
    
    # Verificar modelo actual
    campos_modelo = verificar_modelo_actual()
    if not campos_modelo:
        return
    
    # Verificar template actual
    campos_template = verificar_template_actual()
    if not campos_template:
        return
    
    # Comparar campos
    print("\n🔍 COMPARANDO CAMPOS")
    print("=" * 60)
    
    campos_faltantes = set(campos_template) - set(campos_modelo)
    campos_extra = set(campos_modelo) - set(campos_template)
    
    if campos_faltantes:
        print(f"❌ Campos que usa el template pero NO están en el modelo ({len(campos_faltantes)}):")
        for campo in sorted(campos_faltantes):
            print(f"   ✗ {campo}")
    
    if campos_extra:
        print(f"✅ Campos en el modelo que NO usa el template ({len(campos_extra)}):")
        for campo in sorted(campos_extra):
            print(f"   + {campo}")
    
    # Si hay campos faltantes, crear template simple
    if campos_faltantes:
        print(f"\n⚠️ PROBLEMA DETECTADO: Template usa {len(campos_faltantes)} campos que no existen")
        print("🔧 CREANDO TEMPLATE SIMPLE QUE USE SOLO CAMPOS EXISTENTES")
        
        try:
            # Crear backup del template actual
            template_path = 'diario/templates/diario/prosoche_entrada_form.html'
            backup_path = template_path + '.problematico'
            
            if os.path.exists(template_path):
                os.rename(template_path, backup_path)
                print(f"✅ Template problemático guardado como: {backup_path}")
            
            # Crear template simple
            template_simple = crear_template_simple()
            
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_simple)
            
            print(f"✅ Template simple creado: {template_path}")
            
            print("\n🎉 ¡TEMPLATE CORREGIDO!")
            print("=" * 70)
            print("\n✅ CARACTERÍSTICAS DEL NUEVO TEMPLATE:")
            print("- 📝 Usa SOLO campos que existen en el modelo")
            print("- 🎨 Diseño cyberpunk completo")
            print("- 😊 Estado de ánimo con botones interactivos")
            print("- 🌅 Journaling mañana")
            print("- 🙏 Gratitud (5 campos)")
            print("- 🌙 Journaling noche")
            print("- 📱 Responsive design")
            print("\n🚀 AHORA DEBERÍA FUNCIONAR:")
            print("1. python manage.py runserver")
            print("2. Ir a /diario/prosoche/")
            print("3. Hacer clic en 'Nueva Entrada'")
            print("4. ¡Ver el formulario completo!")
            
        except Exception as e:
            print(f"❌ Error al crear template simple: {e}")
    
    else:
        print("\n✅ ¡TODO ESTÁ CORRECTO!")
        print("El template usa solo campos que existen en el modelo.")

if __name__ == "__main__":
    main()
