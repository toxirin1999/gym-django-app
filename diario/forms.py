# diario/forms.py

from django import forms
from .models import PersonaImportante, Interaccion, ProsocheHabito, TriggerHabito


class PersonaImportanteForm(forms.ModelForm):
    class Meta:
        model = PersonaImportante
        fields = ['nombre', 'tipo_relacion', 'salud_relacion', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Marco Aurelio'}),
            'tipo_relacion': forms.Select(attrs={'class': 'form-select'}),
            'salud_relacion': forms.NumberInput(
                attrs={'class': 'form-control', 'type': 'range', 'min': '1', 'max': '5'}),
            'notas': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Qué representa esta persona para ti?'}),
        }
        labels = {
            'nombre': 'Nombre de la Persona',
            'tipo_relacion': 'Tipo de Relación',
            'salud_relacion': 'Salud de la Relación (1=Mala, 5=Excelente)',
            'notas': 'Notas Adicionales',
        }


class InteraccionForm(forms.ModelForm):
    class Meta:
        model = Interaccion
        # Excluimos 'usuario' porque se asignará automáticamente en la vista
        fields = ['titulo', 'fecha', 'personas', 'tipo_interaccion', 'descripcion', 'mi_sentir', 'aprendizaje']

        # Usamos widgets para dar estilo y mejorar la usabilidad
        widgets = {
            'titulo': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: Conversación sobre el futuro'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'personas': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'tipo_interaccion': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4, 'placeholder': '¿Qué sucedió exactamente?'}),
            'mi_sentir': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Cómo me hizo sentir esto?'}),
            'aprendizaje': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': '¿Qué lección o idea extraigo de esto?'}),
        }

    def __init__(self, *args, **kwargs):
        # --- LÓGICA CLAVE PARA FILTRAR LAS PERSONAS ---
        # Extraemos el usuario que se pasa desde la vista
        usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)

        # Si se proporcionó un usuario, filtramos el queryset del campo 'personas'
        # para mostrar solo las personas importantes de ESE usuario.
        if usuario:
            self.fields['personas'].queryset = PersonaImportante.objects.filter(usuario=usuario)


class ProsocheHabitoForm(forms.ModelForm):
    """Formulario para crear/editar hábitos con soporte para hábitos positivos y negativos"""
    
    class Meta:
        model = ProsocheHabito
        fields = ['nombre', 'descripcion', 'tipo_habito', 'objetivo_dias', 'fecha_objetivo', 'color']
        
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Hacer ejercicio, Fumar, Leer...'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Por qué es importante este hábito para ti?'
            }),
            'tipo_habito': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_tipo_habito'
            }),
            'objetivo_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365',
                'value': '30'
            }),
            'fecha_objetivo': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            })
        }
        
        labels = {
            'nombre': 'Nombre del Hábito',
            'descripcion': 'Descripción',
            'tipo_habito': 'Tipo de Hábito',
            'objetivo_dias': 'Días Objetivo',
            'fecha_objetivo': 'Fecha Objetivo (Opcional)',
            'color': 'Color'
        }
        
        help_texts = {
            'tipo_habito': '¿Es un hábito que quieres formar o eliminar?',
            'objetivo_dias': 'Número de días para establecer/eliminar el hábito (recomendado: 21-90 días)',
            'fecha_objetivo': 'Fecha en la que quieres completar el desafío'
        }


class TriggerHabitoForm(forms.ModelForm):
    """Formulario para registrar triggers/recaídas de hábitos negativos"""
    
    class Meta:
        model = TriggerHabito
        fields = [
            'fecha', 'hora', 'emocion_previa', 'situacion', 
            'personas_presentes', 'intensidad_deseo', 'cediste',
            'estrategia_usada', 'aprendizaje'
        ]
        
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'hora': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'emocion_previa': forms.Select(attrs={
                'class': 'form-select'
            }),
            'situacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué estaba pasando? ¿Dónde estabas?'
            }),
            'personas_presentes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '¿Estabas solo o acompañado? ¿Con quién?'
            }),
            'intensidad_deseo': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cediste': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'estrategia_usada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué hiciste para resistir? (si resististe)'
            }),
            'aprendizaje': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '¿Qué aprendiste de esta experiencia?'
            })
        }
        
        labels = {
            'fecha': 'Fecha del impulso',
            'hora': 'Hora del impulso',
            'emocion_previa': 'Emoción que sentías',
            'situacion': 'Situación',
            'personas_presentes': 'Personas presentes',
            'intensidad_deseo': 'Intensidad del deseo (1-10)',
            'cediste': '¿Cediste al impulso?',
            'estrategia_usada': 'Estrategia usada',
            'aprendizaje': 'Aprendizaje'
        }
