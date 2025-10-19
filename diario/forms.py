# diario/forms.py

from django import forms
from .models import PersonaImportante, Interaccion


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
