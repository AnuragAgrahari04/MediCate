"""Email utilities for MediCate — Brevo HTTPS API with Django SMTP fallback."""
import logging
import random
import string
import threading
from datetime import timedelta
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_email(to, subject, text, html=None):
    """
    Send an email via Brevo HTTPS API when BREVO_API_KEY is configured,
    otherwise fall back to Django's send_mail (local SMTP).
    Returns True on success, False on failure. Never logs API keys.
    """
    recipients = [to] if isinstance(to, str) else list(to or [])
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        logger.error('send_email called with no valid recipients.')
        return False

    brevo_key = (getattr(settings, 'BREVO_API_KEY', '') or '').strip()
    if brevo_key:
        sender_email = (
            getattr(settings, 'BREVO_SENDER_EMAIL', '')
            or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
            or getattr(settings, 'EMAIL_HOST_USER', '')
        ).strip()
        if not sender_email or '@' not in sender_email:
            logger.error('BREVO_SENDER_EMAIL is not configured cleanly.')
            return False

        payload = {
            'sender': {'name': 'MediCate', 'email': sender_email},
            'to': [{'email': addr} for addr in recipients],
            'subject': subject,
            'textContent': text,
        }
        if html:
            payload['htmlContent'] = html

        try:
            resp = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'api-key': brevo_key,
                    'accept': 'application/json',
                    'content-type': 'application/json',
                },
                json=payload,
                timeout=10,
            )
            if 200 <= resp.status_code < 300:
                return True
            logger.error(
                'Brevo send_email failed (status=%s) for %s: %s',
                resp.status_code,
                recipients,
                resp.text,
            )
            return False
        except requests.RequestException as exc:
            logger.error('Brevo send_email request error for %s: %s', recipients, exc)
            return False

    try:
        sent_count = send_mail(
            subject,
            text,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            html_message=html,
            fail_silently=False,
        )
        return bool(sent_count)
    except Exception as exc:
        logger.error('Django send_mail failed for %s: %s', recipients, exc)
        return False


def _send_async(to, subject, text, html=None):
    """Send non-blocking notification emails in a background thread via send_email."""
    threading.Thread(
        target=send_email,
        args=(to, subject, text),
        kwargs={'html': html},
        daemon=True,
    ).start()


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
    """Send OTP verification email synchronously via send_email and return True/False."""
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
    return send_email(user_email, subject, message)


def send_appointment_email_to_doctor(doctor_email, doctor_name, patient_name, slot_date, slot_time, appointment_id):
    """Notify doctor of a new appointment request."""
    subject = '📅 New Appointment Request — MediCate'
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
    _send_async(doctor_email, subject, message)


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
    _send_async(patient_email, subject, message)


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
    _send_async(user_email, subject, message)


def send_password_reset_email(user_email, username, reset_url):
    """Send password reset link synchronously via send_email and return True/False."""
    subject = '🔑 Reset Your MediCate Password'
    message = f"""Hi {username},

Click the link below to reset your password (valid for 24 hours):

{reset_url}

If you did not request a password reset, please ignore this email.

— The MediCate Team
"""
    return send_email(user_email, subject, message)
