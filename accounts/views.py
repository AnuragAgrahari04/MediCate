from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator

from .forms import (
    PatientSignupForm, DoctorSignupForm,
    PatientProfileForm, DoctorProfileForm, DoctorPaymentForm,
    OTPVerifyForm, ForgotPasswordForm, ResetPasswordForm,
)
from .models import PatientProfile, DoctorProfile
from .email_utils import set_otp, send_otp_email, send_welcome_email
from core.utils import geocode_address


# ─────────────────────────────────────────────────────────────────────────────
# SIGNUP VIEWS
# ─────────────────────────────────────────────────────────────────────────────

def signup_patient(request):
    form = PatientSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=d['password'])
        lat, lon = d.get('latitude'), d.get('longitude')
        if not lat or not lon:
            addr = f"{d.get('address','')}, {d.get('city','')}, {d.get('state','')}, {d.get('country','India')}"
            lat, lon = geocode_address(addr)
        profile = PatientProfile.objects.create(
            user=user, name=d['name'], email=d['email'],
            dob=d.get('dob'), gender=d.get('gender',''),
            mobile_no=d.get('mobile_no',''), address=d.get('address',''),
            city=d.get('city',''), state=d.get('state',''),
            pincode=d.get('pincode',''), country=d.get('country','India'),
            blood_group=d.get('blood_group',''),
            latitude=lat, longitude=lon,
        )
        # Send OTP
        otp = set_otp(profile)
        ok  = send_otp_email(user.email, otp, name=d['name'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        if ok:
            messages.success(request, f'Account created! We sent a verification code to {user.email}.')
        else:
            messages.warning(request, 'Account created but we could not send the OTP email. You can resend it below.')
        return redirect('verify_email')
    return render(request, 'accounts/signup_patient.html', {'form': form})


def signup_doctor(request):
    form = DoctorSignupForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=d['password'])
        lat, lon = d.get('latitude'), d.get('longitude')
        if not lat or not lon:
            addr = f"{d.get('address','')}, {d.get('city','')}, {d.get('state','')}, {d.get('country','India')}"
            lat, lon = geocode_address(addr)
        profile = DoctorProfile.objects.create(
            user=user, name=d['name'], email=d['email'],
            specialization=d.get('specialization',''),
            qualification=d.get('qualification',''),
            experience_yrs=d.get('experience_yrs') or 0,
            hospital_name=d.get('hospital_name',''),
            fee=d.get('fee') or 0,
            bio=d.get('bio',''),
            mobile_no=d.get('mobile_no',''),
            address=d.get('address',''),
            city=d.get('city',''), state=d.get('state',''),
            pincode=d.get('pincode',''), country=d.get('country','India'),
            video_consult_enabled=d.get('video_consult_enabled', True),
            video_consult_fee=d.get('video_consult_fee') or 0,
            chat_consult=d.get('chat_consult', True),
            latitude=lat, longitude=lon,
            is_verified=False,
            verification_status='pending',
        )
        # Send OTP
        otp = set_otp(profile)
        ok  = send_otp_email(user.email, otp, name=d['name'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        if ok:
            messages.success(request, f'Account created! We sent a verification code to {user.email}.')
        else:
            messages.warning(request, 'Account created but we could not send the OTP email. You can resend it below.')
        return redirect('verify_email')
    return render(request, 'accounts/signup_doctor.html', {'form': form})


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL VERIFICATION (OTP)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def verify_email(request):
    """Show OTP entry form and verify it."""
    user = request.user

    # Determine which profile to update
    profile = None
    if hasattr(user, 'patient_profile'):
        profile = user.patient_profile
        if profile.is_email_verified:
            return redirect('patient_dashboard')
    elif hasattr(user, 'doctor_profile'):
        profile = user.doctor_profile
        if profile.is_email_verified:
            return redirect('doctor_dashboard')
    else:
        return redirect('home')

    form = OTPVerifyForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        entered = form.cleaned_data['otp'].strip()
        now     = timezone.now()

        if not profile.otp_code:
            error = 'No OTP found. Please request a new one.'
        elif profile.otp_expiry and now > profile.otp_expiry:
            error = 'This OTP has expired. Please request a new code.'
        elif entered != profile.otp_code:
            error = 'Incorrect OTP. Please try again.'
        else:
            # Mark verified
            profile.is_email_verified = True
            profile.otp_code  = ''
            profile.otp_expiry = None
            profile.save(update_fields=['is_email_verified', 'otp_code', 'otp_expiry'])
            send_welcome_email(user.email, profile.name,
                               role='patient' if hasattr(user, 'patient_profile') else 'doctor')
            messages.success(request, '✅ Email verified successfully! Welcome to MediCate.')
            if hasattr(user, 'patient_profile'):
                return redirect('patient_dashboard')
            return redirect('doctor_dashboard')

    return render(request, 'accounts/verify_email.html', {
        'form': form, 'error': error, 'email': user.email,
    })


@login_required
def resend_otp(request):
    """Resend OTP to the user's email."""
    user    = request.user
    profile = None
    if hasattr(user, 'patient_profile'):
        profile = user.patient_profile
    elif hasattr(user, 'doctor_profile'):
        profile = user.doctor_profile

    if profile and not profile.is_email_verified:
        otp = set_otp(profile)
        ok  = send_otp_email(user.email, otp, name=profile.name)
        if ok:
            messages.success(request, f'A new verification code has been sent to {user.email}.')
        else:
            messages.error(request, 'Could not send email. Please check your email address or try again later.')
    return redirect('verify_email')


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN VIEWS (with email-verified guard)
# ─────────────────────────────────────────────────────────────────────────────

def login_patient(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and hasattr(user, 'patient_profile'):
            profile = user.patient_profile
            if not profile.is_email_verified:
                login(request, user)
                messages.warning(request, 'Please verify your email before logging in.')
                return redirect('verify_email')
            login(request, user)
            return redirect('patient_dashboard')
        messages.error(request, 'Invalid credentials or not a patient account.')
    return render(request, 'accounts/login_patient.html')


def login_doctor(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and hasattr(user, 'doctor_profile'):
            profile = user.doctor_profile
            if not profile.is_email_verified:
                login(request, user)
                messages.warning(request, 'Please verify your email before logging in.')
                return redirect('verify_email')
                
            if profile.verification_status != 'approved':
                login(request, user)
                return redirect('doctor_pending_approval')
                
            login(request, user)
            return redirect('doctor_dashboard')
        messages.error(request, 'Invalid credentials or not a doctor account.')
    return render(request, 'accounts/login_doctor.html')


def login_admin(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and user.is_staff:
            login(request, user)
            return redirect('/admin/')
        messages.error(request, 'Invalid admin credentials.')
    return render(request, 'accounts/login_admin.html')


def logout_view(request):
    logout(request)
    return redirect('home')


# ─────────────────────────────────────────────────────────────────────────────
# FORGOT / RESET PASSWORD
# ─────────────────────────────────────────────────────────────────────────────

def forgot_password(request):
    """Step 1: User enters email → we send reset link."""
    form = ForgotPasswordForm(request.POST or None)
    sent = False
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        try:
            user = User.objects.get(email__iexact=email)
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(f'/accounts/reset-password/{uid}/{token}/')
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                '🔑 Reset Your MediCate Password',
                f"""Hi {user.username},

Click the link below to reset your password (valid for 24 hours):

{reset_url}

If you did not request a password reset, please ignore this email.

— The MediCate Team
""",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
        except User.DoesNotExist:
            pass  # Don't reveal if email exists
        sent = True
    return render(request, 'accounts/forgot_password.html', {'form': form, 'sent': sent})


def reset_password(request, uidb64, token):
    """Step 2: User clicks link → enter new password."""
    try:
        uid  = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('forgot_password')

    if not default_token_generator.check_token(user, token):
        messages.error(request, 'This reset link has expired. Please request a new one.')
        return redirect('forgot_password')

    form = ResetPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['password'])
        user.save()
        messages.success(request, 'Password reset successfully! Please log in.')
        return redirect('home')

    return render(request, 'accounts/reset_password.html', {'form': form})


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def patient_profile(request, username):
    profile  = get_object_or_404(PatientProfile, user__username=username)
    is_owner = request.user == profile.user
    form = None
    if is_owner and request.method == 'POST':
        form = PatientProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            prof = form.save(commit=False)
            addr = f"{prof.address}, {prof.city}, {prof.state}, {prof.country}"
            lat, lon = geocode_address(addr)
            if lat:
                prof.latitude, prof.longitude = lat, lon
            prof.save()
            messages.success(request, 'Profile updated.')
            return redirect('patient_profile', username=username)
    elif is_owner:
        form = PatientProfileForm(instance=profile)
    return render(request, 'accounts/patient_profile.html', {'profile': profile, 'form': form, 'is_owner': is_owner})


@login_required
def doctor_profile(request, username):
    profile  = get_object_or_404(DoctorProfile, user__username=username)
    is_owner = request.user == profile.user
    form = None
    payment_form = None

    if is_owner and request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'payment':
            payment_form = DoctorPaymentForm(request.POST, instance=profile)
            if payment_form.is_valid():
                payment_form.save()
                messages.success(request, 'Payment details saved.')
                return redirect('doctor_profile', username=username)
        else:
            form = DoctorProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                prof = form.save(commit=False)
                addr = f"{prof.address}, {prof.city}, {prof.state}, {prof.country}"
                try:
                    lat, lon = geocode_address(addr)
                except (NameError, Exception):
                    lat, lon = None, None
                if lat:
                    prof.latitude, prof.longitude = lat, lon
                prof.save()

                # Re-attempt geocoding if coords still missing
                if not prof.latitude or not prof.longitude:
                    if prof.full_address.strip(', '):
                        from core.utils import geocode_address
                        try:
                            lat, lon = geocode_address(prof.full_address)
                        except (NameError, Exception):
                            lat, lon = None, None
                        if lat and lon:
                            DoctorProfile.objects.filter(pk=prof.pk).update(
                                latitude=lat, longitude=lon
                            )
                
                # Save UPI ID separately (not part of DoctorProfileForm fields)
                upi_id = request.POST.get('upi_id', '').strip()
                if upi_id:
                    DoctorProfile.objects.filter(pk=prof.pk).update(
                        upi_id=upi_id,
                        payment_setup_done=True
                    )
                
                messages.success(request, 'Profile updated.')
                return redirect('doctor_profile', username=username)
    elif is_owner:
        form         = DoctorProfileForm(instance=profile)
        payment_form = DoctorPaymentForm(instance=profile)

    return render(request, 'accounts/doctor_profile.html', {
        'profile': profile, 'form': form,
        'payment_form': payment_form, 'is_owner': is_owner,
    })


# ─────────────────────────────────────────────────────────────────────────────
# AADHAAR VERIFICATION (Simulated)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def aadhaar_verify(request):
    """Patient uploads Aadhaar + selfie → simulated instant verification."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can verify Aadhaar here.')
        return redirect('home')

    profile = request.user.patient_profile
    if profile.is_aadhaar_verified:
        messages.info(request, '✅ Your Aadhaar is already verified.')
        return redirect('patient_dashboard')

    if request.method == 'POST':
        aadhaar_img = request.FILES.get('aadhaar_image')
        selfie_img  = request.FILES.get('selfie_image')

        if not aadhaar_img or not selfie_img:
            messages.error(request, 'Please upload both your Aadhaar card image and a selfie photo.')
            return render(request, 'accounts/aadhaar_verify.html', {'profile': profile})

        profile.aadhaar_image = aadhaar_img
        profile.selfie_image  = selfie_img
        profile.is_aadhaar_verified  = True
        profile.aadhaar_verified_at  = timezone.now()
        profile.save(update_fields=['aadhaar_image', 'selfie_image', 'is_aadhaar_verified', 'aadhaar_verified_at'])

        messages.success(request, '✅ Aadhaar verified successfully! Your profile now has a verified badge.')
        return redirect('patient_dashboard')

    return render(request, 'accounts/aadhaar_verify.html', {'profile': profile})


@login_required
def doctor_verification_status(request):
    """Show the doctor's current credential verification status."""
    if not hasattr(request.user, 'doctor_profile'):
        return redirect('home')
    profile = request.user.doctor_profile
    return render(request, 'accounts/doctor_verification_status.html', {'profile': profile})

@login_required
def doctor_pending_approval(request):
    """Show the waiting page for unapproved doctors."""
    if not hasattr(request.user, 'doctor_profile'):
        return redirect('home')
        
    profile = request.user.doctor_profile
    if profile.verification_status == 'approved':
        return redirect('doctor_dashboard')
        
    return render(request, 'accounts/doctor_pending_approval.html', {'profile': profile})
