from django.urls import path
from . import views

urlpatterns = [
    # ── Signup ────────────────────────────────────────────────────
    path('signup/patient/', views.signup_patient,  name='signup_patient'),
    path('signup/doctor/',  views.signup_doctor,   name='signup_doctor'),
    # ── Login / Logout ────────────────────────────────────────────
    path('login/patient/',  views.login_patient,   name='login_patient'),
    path('login/doctor/',   views.login_doctor,    name='login_doctor'),
    path('login/admin/',    views.login_admin,     name='login_admin'),
    path('logout/',         views.logout_view,     name='logout'),
    # ── Profiles ──────────────────────────────────────────────────
    path('profile/patient/<str:username>/', views.patient_profile, name='patient_profile'),
    path('profile/doctor/<str:username>/',  views.doctor_profile,  name='doctor_profile'),
    # ── Email Verification (OTP) ──────────────────────────────────
    path('verify-email/',   views.verify_email,    name='verify_email'),
    path('resend-otp/',     views.resend_otp,      name='resend_otp'),
    # ── Forgot / Reset Password ───────────────────────────────────
    path('forgot-password/',                            views.forgot_password, name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/',    views.reset_password,  name='reset_password'),
    # ── Aadhaar Verification ──────────────────────────────────────
    path('aadhaar-verify/',              views.aadhaar_verify,            name='aadhaar_verify'),
    path('doctor-verification-status/', views.doctor_verification_status, name='doctor_verification_status'),
    path('pending-approval/',            views.doctor_pending_approval,    name='doctor_pending_approval'),
]
