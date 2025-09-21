from django import forms
from .models import EstadoEmocional, Entrenamiento

from django import forms


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        label="¿Por qué entrenas hoy?",
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'input'}),
        required=False
    )


class EstadoEmocionalForm(forms.ModelForm):
    class Meta:
        model = EstadoEmocional
        fields = ['emocion', 'nota']
        widgets = {
            'emocion': forms.TextInput(attrs={'class': 'input'}),
            'nota': forms.Textarea(attrs={'rows': 3, 'class': 'textarea'}),
        }


class EntrenamientoForm(forms.ModelForm):
    class Meta:
        model = Entrenamiento
        fields = ['tipo', 'duracion', 'intensidad', 'completado']
        widgets = {
            'tipo': forms.TextInput(attrs={'class': 'input'}),
            'duracion': forms.NumberInput(attrs={'class': 'input'}),
            'intensidad': forms.TextInput(attrs={'class': 'input'}),
            'completado': forms.CheckboxInput(attrs={'class': 'checkbox'}),
        }
