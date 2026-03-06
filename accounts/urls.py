from django.urls import path
from . import views

urlpatterns = [
    path('signup/patient/', views.signup_patient,  name='signup_patient'),
    path('signup/doctor/',  views.signup_doctor,   name='signup_doctor'),
    path('login/patient/',  views.login_patient,   name='login_patient'),
    path('login/doctor/',   views.login_doctor,    name='login_doctor'),
    path('login/admin/',    views.login_admin,     name='login_admin'),
    path('logout/',         views.logout_view,     name='logout'),
    path('profile/patient/<str:username>/', views.patient_profile, name='patient_profile'),
    path('profile/doctor/<str:username>/',  views.doctor_profile,  name='doctor_profile'),
]
