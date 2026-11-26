from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.home,                  name='home'),
    path('dashboard/patient/',                  views.patient_dashboard,     name='patient_dashboard'),
    path('dashboard/doctor/',                   views.doctor_dashboard,      name='doctor_dashboard'),
    path('check-disease/',                      views.check_disease,         name='check_disease'),
    path('find-doctors/',                       views.find_doctors,          name='find_doctors'),
    path('consult/',                            views.consult_doctor,        name='consult_doctor'),
    # ── Appointment Booking & Payment ─────────────────────────────
    path('book-osm-doctor/',                    views.auto_register_osm_doctor, name='auto_register_osm_doctor'),
    path('book-slot/<int:doctor_id>/',          views.book_slot,             name='book_slot'),
    path('book-video-slot/<int:doctor_id>/',    views.book_video_slot,       name='book_video_slot'),
    path('booking-success/<int:pk>/',           views.booking_success,       name='booking_success'),
    path('payment-callback/',                   views.payment_callback,      name='payment_callback'),
    path('razorpay/verify/',                    views.razorpay_verify,       name='razorpay_verify'),
    path('appointment/<int:pk>/',               views.appointment_detail,    name='appointment_detail'),
    path('appointment/<int:pk>/cancel/',        views.cancel_appointment,    name='cancel_appointment'),
    path('appointment/<int:appointment_id>/upi-payment/', views.upi_payment, name='upi_payment'),
    path('appointment/<int:appointment_id>/mark-paid/', views.mark_upi_paid, name='mark_upi_paid'),
    path('appointment/<int:appointment_id>/no-upi/', views.no_upi_fallback, name='no_upi_fallback'),
    path('appointments/<int:pk>/video/',         views.appointment_video,     name='appointment_video'),
    path('appointments/<int:pk>/video/end/',     views.end_appointment_video, name='end_appointment_video'),
    # ── Doctor Appointment Management ─────────────────────────────
    path('doctor-appointments/',               views.doctor_appointments,    name='doctor_appointments'),
    path('appointment/<int:pk>/action/',        views.appointment_action,    name='appointment_action'),
    # ── Consultations ─────────────────────────────────────────────
    path('consult/start/',                      views.start_consultation,    name='start_consultation'),
    path('consultation/<int:pk>/',              views.consultation_view,     name='consultation_view'),
    path('consultation/<int:pk>/close/',        views.close_consultation,    name='close_consultation'),
    path('consultation/<int:pk>/rate/',         views.rate_doctor,           name='rate_doctor'),
    path('history/',                            views.consultation_history,  name='consultation_history'),
    path('feedback/',                           views.give_feedback,         name='give_feedback'),
    path('contact/',                            views.contact_us,            name='contact_us'),
    # ── Medical Reports AI Analyzer ───────────────────────────────
    path('reports/',                            views.medical_reports,        name='medical_reports'),
    path('reports/<int:pk>/',                   views.medical_report_detail,  name='medical_report_detail'),
    path('reports/<int:pk>/delete/',            views.delete_medical_report,  name='delete_medical_report'),
    # ── API ───────────────────────────────────────────────────────
    path('api/symptoms/',                       views.api_symptoms,          name='api_symptoms'),
    path('api/remedies/',                       views.api_remedies,          name='api_remedies'),
    path('api/ai-chat/<int:pk>/',               views.api_ai_chat,           name='api_ai_chat'),
    path('api/chatbot/',                        views.api_chatbot,           name='api_chatbot'),
    path('api/doctors/map/',                    views.api_doctors_map,       name='api_doctors_map'),
    path('debug/doctors/',                      views.debug_doctors,         name='debug_doctors'),
]