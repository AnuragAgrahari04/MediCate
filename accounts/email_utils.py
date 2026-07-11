"""Email utilities for MediCate — OTP and notification emails."""
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def generate_otp(length=6):
    """Generate a numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def set_otp(profile):
    """Generate and save OTP + expiry (15 minutes) on a patient or doctor profile."""
    otp = generate_otp()
    profile.otp_code   = otp
    profile.otp_expiry = timezone.now() + timedelta(minutes=15)
    profile.save(update_fields=['otp_code', 'otp_expiry'])
    return otp


def send_otp_email(user_email, otp, name='User'):
    """Send OTP verification email."""
    subject = '🔐 Your MediCate Verification Code'
    message = f"""
Hi {name},

Your MediCate email verification code is:

        ━━━━━━━━━━━━━━━━
              {otp}
        ━━━━━━━━━━━━━━━━

This code expires in 15 minutes.

If you did not create a MediCate account, please ignore this email.

— The MediCate Team
"""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'OTP email failed to {user_email}: {e}')
        return False


def send_appointment_email_to_doctor(doctor_email, doctor_name, patient_name, slot_date, slot_time, appointment_id):
    """Notify doctor of a new appointment request."""
    subject = f'📅 New Appointment Request — MediCate'
    message = f"""
Dear Dr. {doctor_name},

You have a new appointment request on MediCate!

Patient  : {patient_name}
Date     : {slot_date}
Time     : {slot_time}
Ref #    : {appointment_id}

Please log in to your dashboard to Accept or Reject this appointment.

👉 http://127.0.0.1:8000/doctor-appointments/

— The MediCate Team
"""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [doctor_email], fail_silently=True)
    except Exception:
        pass


def send_appointment_status_email(patient_email, patient_name, doctor_name, status, slot_date, slot_time, gate_pass=None, reason=None):
    """Notify patient when doctor accepts or rejects appointment."""
    if status == 'accepted':
        subject = '✅ Appointment Confirmed — MediCate'
        message = f"""
Dear {patient_name},

Great news! Dr. {doctor_name} has confirmed your appointment.

Date      : {slot_date}
Time      : {slot_time}
Gate Pass : {gate_pass or 'N/A'}

Please arrive 10 minutes early. Your gate pass will be required at reception.

— The MediCate Team
"""
    else:
        subject = '❌ Appointment Not Available — MediCate'
        message = f"""
Dear {patient_name},

Unfortunately, Dr. {doctor_name} could not accept your appointment for {slot_date} at {slot_time}.

Reason: {reason or 'Schedule not available'}

Your payment will be refunded within 5–7 business days.

Please book another slot at your convenience.

👉 http://127.0.0.1:8000/find-doctors/

— The MediCate Team
"""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [patient_email], fail_silently=True)
    except Exception:
        pass


def send_welcome_email(user_email, name, role='patient'):
    """Send welcome email after email verification."""
    subject = '🎉 Welcome to MediCate!'
    message = f"""
Hi {name},

Welcome to MediCate! Your email has been verified successfully.

{"As a patient, you can now:" if role == "patient" else "As a doctor, your account is under review. Once verified by our team, you can:"}

{"• Check your symptoms with AI-powered disease prediction" if role == "patient" else "• Accept/Reject appointment requests"}
{"• Find nearby doctors by location" if role == "patient" else "• Manage your availability slots"}
{"• Book appointments with verified doctors" if role == "patient" else "• Conduct video consultations with patients"}
{"• Consult via secure video calls" if role == "patient" else "• Receive consultation fees securely"}

Get started: http://127.0.0.1:8000/

— The MediCate Team
"""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email], fail_silently=True)
    except Exception:
        pass
