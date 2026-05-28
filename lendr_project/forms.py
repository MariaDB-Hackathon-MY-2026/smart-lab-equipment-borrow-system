from django import forms
from django.contrib.auth import authenticate, get_user_model

from dashboard.models import BorrowRequest, Member


User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': 'Please enter a correct username and password. Note that both fields may be case-sensitive.',
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages['invalid_login'])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class UserRegistrationForm(forms.Form):
    name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('That username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('That email address is already registered.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')

        return cleaned_data

    def save(self):
        full_name = self.cleaned_data['name'].strip()
        first_name, _, last_name = full_name.partition(' ')

        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            first_name=first_name,
            last_name=last_name,
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
        )

        Member.objects.create(
            user=user,
            member_id=f"USR{user.id:05d}",
        )
        return user


class BorrowRequestForm(forms.ModelForm):
    equipment_serial_number = forms.CharField(max_length=80, required=True)

    class Meta:
        model = BorrowRequest
        fields = (
            'full_name',
            'student_id',
            'faculty_department',
            'email',
            'phone_number',
            'purpose',
            'duration_days',
        )
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Your full name'}),
            'student_id': forms.TextInput(attrs={'placeholder': 'Student ID or Staff ID'}),
            'faculty_department': forms.TextInput(attrs={'placeholder': 'Faculty or department name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone number'}),
            'purpose': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us why you need this item'}),
            'duration_days': forms.NumberInput(attrs={'min': 1, 'max': 10, 'placeholder': 'Days'}),
        }

    def __init__(self, *args, equipment=None, **kwargs):
        self.equipment = equipment
        super().__init__(*args, **kwargs)
        if equipment:
            self.fields['equipment_serial_number'].initial = equipment.serial_number or ''

    def clean_full_name(self):
        full_name = self.cleaned_data['full_name'].strip()
        if len(full_name) < 2:
            raise forms.ValidationError('Full name is required.')
        return full_name

    def clean_student_id(self):
        student_id = self.cleaned_data['student_id'].strip()
        if len(student_id) < 2:
            raise forms.ValidationError('Student ID or Staff ID is required.')
        return student_id

    def clean_faculty_department(self):
        return self.cleaned_data.get('faculty_department', '').strip()

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_equipment_serial_number(self):
        serial_number = self.cleaned_data['equipment_serial_number'].strip()
        if not self.equipment or not self.equipment.serial_number:
            raise forms.ValidationError('This equipment does not have a valid serial number.')
        if serial_number != self.equipment.serial_number:
            raise forms.ValidationError('The equipment serial number does not match the selected item.')
        return serial_number

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number'].strip()
        allowed_chars = set('0123456789+-() ')
        if len(phone_number) < 7 or any(char not in allowed_chars for char in phone_number):
            raise forms.ValidationError('Enter a valid phone number.')
        return phone_number

    def clean_purpose(self):
        purpose = self.cleaned_data['purpose'].strip()
        if len(purpose) < 5:
            raise forms.ValidationError('Purpose must be at least 5 characters.')
        return purpose

    def clean_duration_days(self):
        duration_days = self.cleaned_data['duration_days']
        if duration_days < 1:
            raise forms.ValidationError('Duration must be at least 1 day.')
        if duration_days > 10:
            raise forms.ValidationError('Duration cannot exceed 10 days.')
        return duration_days


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        exists = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if exists:
            raise forms.ValidationError('That email address is already used by another account.')
        return email
