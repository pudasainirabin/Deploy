from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver

BLOOD_TYPE_CHOICES = [
    ('A+', 'A+'), ('A-', 'A-'),
    ('B+', 'B+'), ('B-', 'B-'),
    ('AB+', 'AB+'), ('AB-', 'AB-'),
    ('O+', 'O+'), ('O-', 'O-'),
]

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        DONOR = 'DONOR', _('Donor')
        PATIENT = 'PATIENT', _('Patient')
    
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.DONOR
    )
    phone_number = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email = models.CharField(blank=True, max_length=254, verbose_name='email address')

    def __str__(self):
        return f"{self.username} ({self.role})"

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.user.email}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    blood_group = models.CharField(max_length=5, blank=True, choices=BLOOD_TYPE_CHOICES)
    last_donation_date = models.DateField(null=True, blank=True)
    medical_conditions = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

class DonationCenter(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    # Optionally add location fields (latitude, longitude) for future use
    def __str__(self):
        return self.name

class DonationAppointment(models.Model):
    donor = models.ForeignKey('User', on_delete=models.CASCADE)
    center = models.ForeignKey(DonationCenter, on_delete=models.CASCADE)
    date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed'), ('CANCELLED', 'Cancelled')], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.donor.username} - {self.center.name} on {self.date}"

class Notification(models.Model):
    NOTIF_TYPE_CHOICES = [
        ('donation', 'Donation'),
        ('appointment', 'Appointment'),
        ('blood_request', 'Blood Request'),
        ('system', 'System'),
    ]
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=20, choices=NOTIF_TYPE_CHOICES)
    read = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class BloodStock(models.Model):
    type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, unique=True)
    units = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.type}: {self.units} units"

class BloodRequest(models.Model):
    patient = models.ForeignKey('User', on_delete=models.CASCADE, limit_choices_to={'role': 'PATIENT'})
    blood_group = models.CharField(max_length=5, choices=BLOOD_TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    request_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('FULFILLED', 'Fulfilled')], default='PENDING')
    notes = models.TextField(blank=True)
    prescription = models.FileField(upload_to='prescriptions/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_center = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self):
        return f"{self.patient.username} - {self.blood_group} ({self.quantity} units)"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
