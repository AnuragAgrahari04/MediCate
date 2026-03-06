from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.home,                  name='home'),
    path('dashboard/patient/',                  views.patient_dashboard,     name='patient_dashboard'),
    path('dashboard/doctor/',                   views.doctor_dashboard,      name='doctor_dashboard'),
    path('check-disease/',                      views.check_disease,         name='check_disease'),
    path('consult/',                            views.consult_doctor,        name='consult_doctor'),
    path('consult/start/',                      views.start_consultation,    name='start_consultation'),
    path('consultation/<int:pk>/',              views.consultation_view,     name='consultation_view'),
    path('consultation/<int:pk>/close/',        views.close_consultation,    name='close_consultation'),
    path('consultation/<int:pk>/rate/',         views.rate_doctor,           name='rate_doctor'),
    path('history/',                            views.consultation_history,  name='consultation_history'),
    path('feedback/',                           views.give_feedback,         name='give_feedback'),
    # API
    path('api/symptoms/',                       views.api_symptoms,          name='api_symptoms'),
    path('api/ai-chat/<int:pk>/',               views.api_ai_chat,           name='api_ai_chat'),
    path('api/doctors/map/',                    views.api_doctors_map,       name='api_doctors_map'),
    path('debug/doctors/',                      views.debug_doctors,         name='debug_doctors'),
]