from django.contrib import admin
from .models import PatientProfile, DoctorProfile

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'city', 'state', 'gender', 'created_at']
    search_fields = ['name', 'email', 'city']

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialization', 'city', 'rating', 'is_verified', 'video_consult']
    search_fields = ['name', 'email', 'city', 'specialization']
    list_filter = ['specialization', 'is_verified', 'video_consult']
    list_editable = ['is_verified']