from django import forms
from .models import TriggerHabito


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
