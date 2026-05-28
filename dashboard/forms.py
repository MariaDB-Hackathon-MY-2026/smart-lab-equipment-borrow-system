from django import forms

from .models import Equipment


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = (
            'name',
            'category',
            'serial_number',
            'status',
            'condition',
            'condition_remarks',
            'daily_penalty',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Canon EOS R'}),
            'category': forms.TextInput(attrs={'placeholder': 'e.g. Camera'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'CAM FCDT 1'}),
            'condition_remarks': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional condition notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = field_name != 'condition_remarks'

    def clean_serial_number(self):
        serial_number = self.cleaned_data.get('serial_number')
        return serial_number
