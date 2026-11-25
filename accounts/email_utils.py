"""Email utilities for MediCate — OTP and notification emails."""
import logging
import random
import string
import threading
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_async(subject, message, recipient_list, fail_silently=True):
    """Send email in a background daemon thread so HTTP requests do not block on SMTP."""
    def _worker():
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                recipient_list,
                fail_silently=fail_silently,
            )
        except Exception as e:
            logger.error(f'Async email failed to {recipient_list}: {e}')

    threading.Thread(target=_worker, daemon=True).start()


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


def send_otp_email(user_email, otp, name='User', sync=False):
    """Send OTP verification email (non-blocking by default for instant signup)."""
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
    if not sync:
        _send_async(subject, message, [user_email], fail_silently=False)
        return True
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
        logger.error(f'OTP email failed to {user_email}: {e}')
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

👉 https://medicate-moa4.onrender.com/doctor-appointments/

— The MediCate Team
"""
    _send_async(subject, message, [doctor_email], fail_silently=True)


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

👉 https://medicate-moa4.onrender.com/find-doctors/

— The MediCate Team
"""
    _send_async(subject, message, [patient_email], fail_silently=True)


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

Get started: https://medicate-moa4.onrender.com/

— The MediCate Team
"""
    _send_async(subject, message, [user_email], fail_silently=True)


def send_password_reset_email(user_email, username, reset_url):
    """Send password reset link asynchronously."""
    subject = '🔑 Reset Your MediCate Password'
    message = f"""Hi {username},

Click the link below to reset your password (valid for 24 hours):

{reset_url}

If you did not request a password reset, please ignore this email.

— The MediCate Team
"""
    _send_async(subject, message, [user_email], fail_silently=False)
