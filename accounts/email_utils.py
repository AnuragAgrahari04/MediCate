"""Email utilities for MediCate — HTTPS email APIs (Render-safe) + SMTP fallback."""
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


def _deliver_via_webhook(subject, message, recipient_list):
    """Deliver email via HTTPS webhook (e.g. Google Apps Script Gmail relay)."""
    url = getattr(settings, 'EMAIL_WEBHOOK_URL', '').strip()
    if not url:
        return None
    secret = getattr(settings, 'EMAIL_WEBHOOK_SECRET', '').strip()
    for to_addr in recipient_list:
        resp = requests.post(
            url,
            json={'to': to_addr, 'subject': subject, 'body': message, 'secret': secret},
            timeout=10,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f'Webhook HTTP {resp.status_code}: {resp.text[:200]}')
        # Google Apps Script returns 200 JSON; check ok flag if JSON
        try:
            data = resp.json()
            if isinstance(data, dict) and data.get('ok') is False:
                raise RuntimeError(data.get('error', 'Webhook returned ok=false'))
        except ValueError:
            pass
    return True


def _deliver_via_brevo(subject, message, recipient_list):
    """Deliver email over HTTPS port 443 using Brevo transactional email API."""
    api_key = getattr(settings, 'BREVO_API_KEY', '').strip()
    if not api_key:
        return None
    sender_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', '')
    if not sender_email or '@' not in sender_email:
        raise RuntimeError('DEFAULT_FROM_EMAIL / EMAIL_HOST_USER must be set for Brevo.')
    resp = requests.post(
        'https://api.brevo.com/v3/smtp/email',
        headers={'api-key': api_key, 'Content-Type': 'application/json'},
        json={
            'sender': {'name': 'MediCate', 'email': sender_email},
            'to': [{'email': addr} for addr in recipient_list],
            'subject': subject,
            'textContent': message,
        },
        timeout=10,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f'Brevo API {resp.status_code}: {resp.text[:200]}')
    return True


def _deliver_via_resend(subject, message, recipient_list):
    """Deliver email over HTTPS port 443 using Resend API."""
    api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
    if not api_key:
        return None
    sender_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'MediCate <onboarding@resend.dev>'
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'from': sender_email,
            'to': list(recipient_list),
            'subject': subject,
            'text': message,
        },
        timeout=10,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f'Resend API {resp.status_code}: {resp.text[:200]}')
    return True


def _deliver_email(subject, message, recipient_list):
    """
    Send email via configured HTTPS API first (works on Render free tier where
    SMTP ports 25/465/587 are blocked), falling back to Django SMTP.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    recipients = [r for r in (recipient_list or []) if r]
    if not recipients:
        return False, 'No recipient email provided.'

    errors = []
    for name, fn in (
        ('Webhook', _deliver_via_webhook),
        ('Brevo', _deliver_via_brevo),
        ('Resend', _deliver_via_resend),
    ):
        try:
            result = fn(subject, message, recipients)
            if result:
                return True, None
        except Exception as exc:
            logger.error(f'{name} email failed to {recipients}: {exc}')
            errors.append(f'{name}: {exc}')

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        return True, None
    except Exception as exc:
        logger.error(f'SMTP email failed to {recipients}: {exc}')
        errors.append(f'SMTP: {exc}')
        return False, '; '.join(errors)


def _send_async(subject, message, recipient_list, fail_silently=True):
    """Send email in a background daemon thread so HTTP requests do not block."""
    def _worker():
        ok, err = _deliver_email(subject, message, recipient_list)
        if not ok and not fail_silently:
            logger.error(f'Async email delivery failed to {recipient_list}: {err}')

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
    ok, _ = _deliver_email(subject, message, [user_email])
    return ok


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
    """
    Send password reset link synchronously using HTTPS email APIs or SMTP fallback.
    Returns (True, None) on success or (False, error_detail) if delivery fails.
    """
    subject = '🔑 Reset Your MediCate Password'
    message = f"""Hi {username},

Click the link below to reset your password (valid for 24 hours):

{reset_url}

If you did not request a password reset, please ignore this email.

— The MediCate Team
"""
    return _deliver_email(subject, message, [user_email])
