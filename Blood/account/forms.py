from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, OTP, DonationCenter, DonationAppointment, UserProfile, BloodRequest
from django.utils import timezone
from django.contrib.auth import password_validation

class UserRegistrationForm(UserCreationForm):
    email = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'password1', 'password2',
                 'first_name', 'last_name', 'date_of_birth', 'address', 'profile_picture')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)
        if self.role:
            self.instance.role = self.role

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Enter 6-digit OTP'}
    ))

class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Username'}
    ))
    password = forms.CharField(widget=forms.PasswordInput(
        attrs={'class': 'form-control', 'placeholder': 'Password'}
    ))

class ScheduleDonationForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    center = forms.ModelChoiceField(queryset=DonationCenter.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}))
    notes = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)

    class Meta:
        model = DonationAppointment
        fields = ['date', 'center', 'notes']

    def __init__(self, *args, **kwargs):
        self.donor = kwargs.pop('donor', None)
        self.next_eligible_date = kwargs.pop('next_eligible_date', None)
        super().__init__(*args, **kwargs)

    def clean_date(self):
        date = self.cleaned_data['date']
        today = timezone.now().date()
        if date < today:
            raise forms.ValidationError('You cannot select a past date.')
        if self.next_eligible_date and date < self.next_eligible_date:
            raise forms.ValidationError(f'You are only eligible after {self.next_eligible_date}.')
        return date

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        center = cleaned_data.get('center')
        if self.donor and date and center:
            # Prevent duplicate/overlapping appointments
            exists = DonationAppointment.objects.filter(donor=self.donor, date=date, center=center, status__in=['PENDING', 'CONFIRMED']).exists()
            if exists:
                raise forms.ValidationError('You already have an appointment at this center on this date.')
        return cleaned_data 

BLOOD_GROUP_CHOICES = [
    ('A+', 'A+'), ('A-', 'A-'),
    ('B+', 'B+'), ('B-', 'B-'),
    ('AB+', 'AB+'), ('AB-', 'AB-'),
    ('O+', 'O+'), ('O-', 'O-'),
]

class EditProfileForm(forms.ModelForm):
    blood_group = forms.ChoiceField(
        choices=BLOOD_GROUP_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth', 'address', 'profile_picture', 'blood_group']

    def __init__(self, *args, **kwargs):
        user_profile = kwargs.pop('user_profile', None)
        super().__init__(*args, **kwargs)
        if user_profile:
            self.fields['blood_group'].initial = user_profile.blood_group
            if user_profile.blood_group:
                self.fields['blood_group'].disabled = True  # Disable the field if blood group is already set

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture and picture.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Profile picture must be less than 2MB.')
        return picture
    def save(self, commit=True):
        user = super().save(commit)
        blood_group = self.cleaned_data.get('blood_group')
        if hasattr(user, 'userprofile') and blood_group and not user.userprofile.blood_group:
            user.userprofile.blood_group = blood_group
            user.userprofile.save()
        return user

class ChangePasswordWithOTPForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    otp = forms.CharField(max_length=6, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter OTP'}))
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Old password is incorrect.')
        return old_password
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('New passwords do not match.')
            password_validation.validate_password(new_password1, self.user)
        return cleaned_data 

class DonationCenterForm(forms.ModelForm):
    class Meta:
        model = DonationCenter
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Center Name'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Address', 'rows': 3}),
        } 

class BloodRequestForm(forms.ModelForm):
    blood_group = forms.ChoiceField(choices=BLOOD_GROUP_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    quantity = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity (units)'}))
    notes = forms.CharField(label='Reason for request', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for request'}), required=True)
    preferred_center = forms.ModelChoiceField(queryset=DonationCenter.objects.all(), label='Preferred hospital/center', widget=forms.Select(attrs={'class': 'form-control'}), required=True)
    prescription = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = BloodRequest
        fields = ['blood_group', 'quantity', 'notes', 'preferred_center', 'prescription']

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None or quantity < 1:
            raise forms.ValidationError('Quantity must be a positive integer.')
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        # Ensure all required fields are filled
        for field in ['blood_group', 'quantity', 'notes', 'preferred_center', 'prescription']:
            if not cleaned_data.get(field):
                self.add_error(field, 'This field is required.')
        return cleaned_data 

class ForgotPasswordForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))

class ResetPasswordForm(forms.Form):
    otp = forms.CharField(max_length=6, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OTP'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}))

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password1') != cleaned_data.get('new_password2'):
            self.add_error('new_password2', "Passwords do not match.")
        return cleaned_data