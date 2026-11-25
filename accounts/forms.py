import re
from django import forms
from django.contrib.auth.models import User
from .models import PatientProfile, DoctorProfile, SPECIALIZATION_CHOICES, GENDER_CHOICES


def _email_unique(email, exclude_user=None):
    """Check that the email is not already used by any User or Profile."""
    user_qs = User.objects.filter(email__iexact=email)
    pat_qs = PatientProfile.objects.filter(email__iexact=email)
    doc_qs = DoctorProfile.objects.filter(email__iexact=email)
    if exclude_user:
        user_qs = user_qs.exclude(pk=exclude_user.pk)
        pat_qs = pat_qs.exclude(user=exclude_user)
        doc_qs = doc_qs.exclude(user=exclude_user)
    return not (user_qs.exists() or pat_qs.exists() or doc_qs.exists())


def normalize_phone(raw_phone):
    """Strip formatting and return canonical 10-digit Indian mobile or E.164 digits."""
    digits = re.sub(r'\D', '', (raw_phone or '').strip())
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    return digits


def _validate_and_check_phone(raw_phone, exclude_user=None):
    """Validate phone format (10 digits starting with 6-9) and check uniqueness across patients & doctors."""
    digits = normalize_phone(raw_phone)
    if not digits:
        raise forms.ValidationError('Mobile number is required.')
    if not re.fullmatch(r'[6-9]\d{9}', digits):
        raise forms.ValidationError('Please enter a valid 10-digit mobile number (e.g. 9876543210 or +91 9876543210).')

    pat_qs = PatientProfile.objects.exclude(mobile_no='')
    doc_qs = DoctorProfile.objects.exclude(mobile_no='')
    if exclude_user:
        pat_qs = pat_qs.exclude(user=exclude_user)
        doc_qs = doc_qs.exclude(user=exclude_user)

    for existing in pat_qs.values_list('mobile_no', flat=True):
        if normalize_phone(existing) == digits:
            raise forms.ValidationError('An account with this mobile number already exists. Please use a different number or sign in.')
    for existing in doc_qs.values_list('mobile_no', flat=True):
        if normalize_phone(existing) == digits:
            raise forms.ValidationError('An account with this mobile number already exists. Please use a different number or sign in.')

    return digits


class PatientSignupForm(forms.Form):
    username    = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Username'}))
    name        = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Full Name'}))
    email       = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
    password    = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2   = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))
    dob         = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    gender      = forms.ChoiceField(choices=[('', 'Select Gender')] + list(GENDER_CHOICES))
    mobile_no   = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'placeholder': '+91 9876543210'}))
    address     = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={'placeholder': 'Street Address'}))
    city        = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'placeholder': 'City'}))
    state       = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'placeholder': 'State'}))
    pincode     = forms.CharField(max_length=10, required=False, widget=forms.TextInput(attrs={'placeholder': 'Pincode'}))
    country     = forms.CharField(max_length=100, required=False, initial='India', widget=forms.TextInput(attrs={'placeholder': 'Country'}))
    blood_group = forms.CharField(max_length=5, required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g. A+'}))
    latitude    = forms.FloatField(required=False, widget=forms.HiddenInput())
    longitude   = forms.FloatField(required=False, widget=forms.HiddenInput())

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken. Please choose another.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not _email_unique(email):
            raise forms.ValidationError('An account with this email already exists. Please log in or use a different email.')
        return email

    def clean_mobile_no(self):
        return _validate_and_check_phone(self.cleaned_data.get('mobile_no'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        if len(cleaned.get('password', '')) < 8:
            raise forms.ValidationError('Password must be at least 8 characters long.')
        return cleaned


class DoctorSignupForm(forms.Form):
    username        = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Username'}))
    name            = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Full Name'}))
    email           = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email'}))
    password        = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2       = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))
    specialization  = forms.ChoiceField(choices=[('', 'Select Specialization')] + list(SPECIALIZATION_CHOICES))
    qualification   = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g. MBBS, MD'}))
    experience_yrs  = forms.IntegerField(min_value=0, required=False, widget=forms.NumberInput(attrs={'placeholder': 'Years of Experience'}))
    hospital_name   = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'placeholder': 'Hospital / Clinic Name'}))
    fee             = forms.IntegerField(min_value=0, required=False, widget=forms.NumberInput(attrs={'placeholder': 'Consultation Fee (INR)'}))
    mobile_no       = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'placeholder': '+91 9876543210'}))
    address         = forms.CharField(max_length=300, required=False)
    city            = forms.CharField(max_length=100, required=False)
    state           = forms.CharField(max_length=100, required=False)
    pincode         = forms.CharField(max_length=10, required=False)
    country         = forms.CharField(max_length=100, required=False, initial='India')
    video_consult_enabled = forms.BooleanField(required=False, initial=True, label="Offer Video Consultations")
    video_consult_fee = forms.DecimalField(min_value=0, decimal_places=2, required=False, initial=0, widget=forms.NumberInput(attrs={'placeholder': 'Video Consult Fee (INR)'}))
    chat_consult    = forms.BooleanField(required=False, initial=True)
    bio             = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Brief bio / about yourself'}))
    latitude        = forms.FloatField(required=False, widget=forms.HiddenInput())
    longitude       = forms.FloatField(required=False, widget=forms.HiddenInput())

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken. Please choose another.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not _email_unique(email):
            raise forms.ValidationError('An account with this email already exists. Please log in or use a different email.')
        return email

    def clean_mobile_no(self):
        return _validate_and_check_phone(self.cleaned_data.get('mobile_no'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        if len(cleaned.get('password', '')) < 8:
            raise forms.ValidationError('Password must be at least 8 characters long.')
        return cleaned


class PatientProfileForm(forms.ModelForm):
    class Meta:
        model  = PatientProfile
        fields = ['name', 'email', 'dob', 'gender', 'mobile_no', 'address',
                  'city', 'state', 'pincode', 'country', 'blood_group', 'img']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'img': forms.FileInput(),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        exclude_user = self.instance.user if self.instance and self.instance.pk else None
        if not _email_unique(email, exclude_user=exclude_user):
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_mobile_no(self):
        raw = (self.cleaned_data.get('mobile_no') or '').strip()
        if not raw:
            return ''
        exclude_user = self.instance.user if self.instance and self.instance.pk else None
        return _validate_and_check_phone(raw, exclude_user=exclude_user)


class DoctorProfileForm(forms.ModelForm):
    class Meta:
        model  = DoctorProfile
        fields = ['name', 'email', 'dob', 'specialization', 'qualification',
                  'experience_yrs', 'hospital_name', 'fee', 'bio',
                  'mobile_no', 'address', 'city', 'state', 'pincode', 'country',
                  'available_from', 'available_to', 'video_consult_enabled', 'video_consult_fee', 'chat_consult', 'img']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'available_from': forms.TimeInput(attrs={'type': 'time'}),
            'available_to':   forms.TimeInput(attrs={'type': 'time'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'img': forms.FileInput(),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        exclude_user = self.instance.user if self.instance and self.instance.pk else None
        if not _email_unique(email, exclude_user=exclude_user):
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_mobile_no(self):
        raw = (self.cleaned_data.get('mobile_no') or '').strip()
        if not raw:
            return ''
        exclude_user = self.instance.user if self.instance and self.instance.pk else None
        return _validate_and_check_phone(raw, exclude_user=exclude_user)


class DoctorPaymentForm(forms.ModelForm):
    class Meta:
        model  = DoctorProfile
        fields = ['upi_id', 'bank_account_name', 'bank_account_no', 'bank_ifsc']
        widgets = {
            'upi_id':            forms.TextInput(attrs={'placeholder': 'yourname@upi'}),
            'bank_account_name': forms.TextInput(attrs={'placeholder': 'Account Holder Name'}),
            'bank_account_no':   forms.TextInput(attrs={'placeholder': 'Account Number'}),
            'bank_ifsc':         forms.TextInput(attrs={'placeholder': 'IFSC Code e.g. SBIN0001234'}),
        }


class OTPVerifyForm(forms.Form):
    otp = forms.CharField(
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={'placeholder': '6-digit OTP', 'maxlength': '6', 'inputmode': 'numeric'})
    )


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Your registered email'}))


class ResetPasswordForm(forms.Form):
    password  = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'New Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm New Password'}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        if len(cleaned.get('password', '')) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        return cleaned
