from django.db import models
from django.contrib.auth.models import User
from datetime import date
from core.utils import geocode_address

SPECIALIZATION_CHOICES = [
    ('General Physician',       'General Physician'),
    ('Cardiologist',            'Cardiologist'),
    ('Gastroenterologist',      'Gastroenterologist'),
    ('Neurologist',             'Neurologist'),
    ('Endocrinologist',         'Endocrinologist'),
    ('Pulmonologist',           'Pulmonologist'),
    ('Orthopedic',              'Orthopedic'),
    ('Dermatologist',           'Dermatologist'),
    ('Urologist',               'Urologist'),
    ('Ophthalmologist',         'Ophthalmologist'),
    ('ENT Specialist',          'ENT Specialist'),
    ('Psychiatrist',            'Psychiatrist'),
    ('Pediatrician',            'Pediatrician'),
    ('Gynecologist',            'Gynecologist'),
    ('Oncologist',              'Oncologist'),
    ('Rheumatologist',          'Rheumatologist'),
    ('Nephrologist',            'Nephrologist'),
    ('Hematologist',            'Hematologist'),
    ('Hepatologist',            'Hepatologist'),
    ('Infectious Disease',      'Infectious Disease Specialist'),
]

GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

VERIFICATION_STATUS = [
    ('pending',      'Pending'),
    ('under_review', 'Under Review'),
    ('approved',     'Approved'),
    ('rejected',     'Rejected'),
]


class PatientProfile(models.Model):
    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    name               = models.CharField(max_length=100)
    email              = models.EmailField()
    dob                = models.DateField(null=True, blank=True)
    address            = models.CharField(max_length=300, blank=True)
    city               = models.CharField(max_length=100, blank=True)
    state              = models.CharField(max_length=100, blank=True)
    country            = models.CharField(max_length=100, blank=True, default='India')
    pincode            = models.CharField(max_length=10, blank=True)
    latitude           = models.FloatField(null=True, blank=True)
    longitude          = models.FloatField(null=True, blank=True)
    mobile_no          = models.CharField(max_length=15, blank=True)
    gender             = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    img                = models.ImageField(upload_to='patients/', null=True, blank=True)
    blood_group        = models.CharField(max_length=5, blank=True)
    # ── Email Verification ────────────────────────────────────────
    is_email_verified  = models.BooleanField(default=False)
    otp_code           = models.CharField(max_length=6, blank=True)
    otp_expiry         = models.DateTimeField(null=True, blank=True)
    # ── Aadhaar Verification ──────────────────────────────────────
    aadhaar_image      = models.ImageField(upload_to='aadhaar/patients/', null=True, blank=True)
    selfie_image       = models.ImageField(upload_to='selfies/patients/', null=True, blank=True)
    is_aadhaar_verified = models.BooleanField(default=False)
    aadhaar_verified_at = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} (Patient)'

    @property
    def age(self):
        if self.dob:
            today = date.today()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None

    @property
    def full_address(self):
        parts = [p for p in [self.address, self.city, self.state, self.pincode, self.country] if p]
        return ', '.join(parts)


class DoctorProfile(models.Model):
    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    name               = models.CharField(max_length=100)
    email              = models.EmailField()
    dob                = models.DateField(null=True, blank=True)
    img                = models.ImageField(upload_to='doctors/', null=True, blank=True)
    address            = models.CharField(max_length=300, blank=True)
    city               = models.CharField(max_length=100, blank=True)
    state              = models.CharField(max_length=100, blank=True)
    country            = models.CharField(max_length=100, blank=True, default='India')
    pincode            = models.CharField(max_length=10, blank=True)
    latitude           = models.FloatField(null=True, blank=True)
    longitude          = models.FloatField(null=True, blank=True)
    mobile_no          = models.CharField(max_length=15, blank=True)
    specialization     = models.CharField(max_length=100, choices=SPECIALIZATION_CHOICES, blank=True)
    qualification      = models.CharField(max_length=200, blank=True)
    experience_yrs     = models.PositiveIntegerField(default=0)
    bio                = models.TextField(blank=True)
    hospital_name      = models.CharField(max_length=200, blank=True)
    fee                = models.PositiveIntegerField(default=0, help_text='Consultation fee in INR')
    available_from     = models.TimeField(null=True, blank=True)
    available_to       = models.TimeField(null=True, blank=True)
    rating             = models.FloatField(default=0.0)
    total_ratings      = models.PositiveIntegerField(default=0)
    video_consult      = models.BooleanField(default=True, help_text='Offers video consultation')
    video_consult_enabled = models.BooleanField(default=False)
    video_consult_fee  = models.DecimalField(max_digits=10, decimal_places=2, default=200.00)
    chat_consult       = models.BooleanField(default=True, help_text='Offers chat consultation')
    # ── Verification ──────────────────────────────────────────────
    is_verified        = models.BooleanField(default=False)
    is_email_verified  = models.BooleanField(default=False)
    otp_code           = models.CharField(max_length=6, blank=True)
    otp_expiry         = models.DateTimeField(null=True, blank=True)
    aadhaar_image      = models.ImageField(upload_to='aadhaar/doctors/', null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    admin_notes        = models.TextField(blank=True)
    # ── Payment Setup ─────────────────────────────────────────────
    upi_id             = models.CharField(max_length=100, blank=True, help_text='UPI ID e.g. name@upi')
    bank_account_name  = models.CharField(max_length=200, blank=True)
    bank_account_no    = models.CharField(max_length=30, blank=True)
    bank_ifsc          = models.CharField(max_length=15, blank=True)
    payment_setup_done = models.BooleanField(default=False)
    created_at         = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Dr. {self.name} ({self.specialization})'

    @property
    def full_address(self):
        parts = [p for p in [self.address, self.city, self.state, self.pincode, self.country] if p]
        return ', '.join(parts)

    def distance_from(self, lat, lon):
        """Return distance in km from given coords. Returns None if no location."""
        if self.latitude and self.longitude and lat and lon:
            from geopy.distance import geodesic
            return round(geodesic((lat, lon), (self.latitude, self.longitude)).km, 1)
        return None

    def save(self, *args, **kwargs):
        # Auto set payment_setup_done
        if self.upi_id or (self.bank_account_no and self.bank_ifsc):
            self.payment_setup_done = True
        # Automatically get lat/lon if address is provided but coords are missing
        if self.address and (self.latitude is None or self.longitude is None):
            lat, lon = geocode_address(self.full_address)
            self.latitude = lat
            self.longitude = lon
        super().save(*args, **kwargs)