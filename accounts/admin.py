from django.contrib import admin
from .models import PatientProfile, DoctorProfile


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'specialization', 'verification_status', 'is_verified', 'created_at']
    list_filter   = ['verification_status', 'specialization', 'is_verified']
    search_fields = ['name', 'email', 'specialization']
    list_editable = ['verification_status', 'is_verified']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Basic Info',   {'fields': ('user', 'name', 'email', 'specialization', 'qualification', 'experience_yrs', 'hospital_name', 'fee', 'bio', 'img')}),
        ('Contact',      {'fields': ('mobile_no', 'address', 'city', 'state', 'pincode', 'country')}),
        ('Approval',     {'fields': ('verification_status', 'is_verified', 'admin_notes')}),
        ('Payment',      {'fields': ('upi_id', 'bank_account_name', 'bank_account_no', 'bank_ifsc', 'payment_setup_done')}),
        ('Timestamps',   {'fields': ('created_at',)}),
    )
    actions = ['approve_doctors', 'reject_doctors']

    def approve_doctors(self, request, queryset):
        updated = queryset.update(verification_status='approved', is_verified=True)
        self.message_user(request, f'{updated} doctor(s) approved successfully.')
    approve_doctors.short_description = 'Approve selected doctors'

    def reject_doctors(self, request, queryset):
        updated = queryset.update(verification_status='rejected', is_verified=False)
        self.message_user(request, f'{updated} doctor(s) rejected.')
    reject_doctors.short_description = 'Reject selected doctors'


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'city', 'is_email_verified', 'created_at']
    list_filter   = ['is_email_verified', 'gender']
    search_fields = ['name', 'email']
    readonly_fields = ['created_at']