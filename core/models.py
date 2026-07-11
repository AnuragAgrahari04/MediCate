from django.db import models
from django.contrib.auth.models import User
from accounts.models import PatientProfile, DoctorProfile


CONSULT_TYPE_CHOICES = [('chat', 'Chat'), ('video', 'Video')]
STATUS_CHOICES       = [('active', 'Active'), ('closed', 'Closed'), ('pending', 'Pending')]


class Consultation(models.Model):
    patient            = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='consultations')
    doctor             = models.ForeignKey(DoctorProfile,  on_delete=models.CASCADE, related_name='consultations')
    predicted_disease  = models.CharField(max_length=150)
    symptoms           = models.TextField(help_text='Comma-separated symptom names')
    confident_score    = models.FloatField(default=0.0)
    top_predictions    = models.JSONField(default=list, blank=True,
                          help_text='List of {disease, confidence} dicts (top-5 ML outputs)')
    consult_type       = models.CharField(max_length=10, choices=CONSULT_TYPE_CHOICES, default='chat')
    date               = models.DateField(auto_now_add=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    status             = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    # Video call
    video_channel      = models.CharField(max_length=100, blank=True)
    video_token_patient = models.TextField(blank=True)
    video_token_doctor  = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient.name} ↔ Dr.{self.doctor.name} [{self.predicted_disease}]'

    @property
    def symptoms_list(self):
        return [s.strip() for s in self.symptoms.split(',') if s.strip()]


class ChatMessage(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(User, on_delete=models.CASCADE)
    message      = models.TextField()
    timestamp    = models.DateTimeField(auto_now_add=True)
    is_ai        = models.BooleanField(default=False, help_text='True if message from AI assistant')

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'[{self.timestamp:%H:%M}] {self.sender.username}: {self.message[:40]}'


class Rating(models.Model):
    consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='rating')
    doctor       = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='ratings')
    patient      = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='ratings_given')
    score        = models.PositiveSmallIntegerField()          # 1-5
    review       = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.score}★ by {self.patient.name} for Dr.{self.doctor.name}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recompute doctor's average rating
        from django.db.models import Avg
        agg = Rating.objects.filter(doctor=self.doctor).aggregate(avg=Avg('score'), cnt=models.Count('id'))
        self.doctor.rating       = round(agg['avg'] or 0, 1)
        self.doctor.total_ratings = agg['cnt'] or 0
        self.doctor.save(update_fields=['rating', 'total_ratings'])


class Feedback(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE)
    message   = models.TextField()
    rating    = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Feedback from {self.user.username}'


class AppointmentSlot(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.doctor.user.username} - {self.date} {self.start_time}"

class Appointment(models.Model):
    APPT_STATUS = [
        ('pending_payment',  'Pending Payment'),
        ('payment_done',     'Payment Done'),
        ('confirmed',        'Confirmed'),
        ('rejected',         'Rejected'),
        ('completed',        'Completed'),
        ('cancelled',        'Cancelled'),
    ]


    patient            = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    slot               = models.ForeignKey(AppointmentSlot, on_delete=models.CASCADE, related_name='appointments')
    status             = models.CharField(max_length=20, choices=APPT_STATUS, default='pending_payment')
    queue_position     = models.IntegerField(default=0)
    appointment_type   = models.CharField(choices=[('in_person', 'In Person'), ('video', 'Video Consult')], default='in_person', max_length=20)
    fee                = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    video_room_url     = models.URLField(blank=True, null=True)
    video_room_name    = models.CharField(blank=True, null=True, max_length=255)
    refund_eligible    = models.BooleanField(default=False)
    cancellation_time  = models.DateTimeField(null=True, blank=True)
    # ── Payment ───────────────────────────────────────────────────
    razorpay_order_id   = models.CharField(
        max_length=100, blank=True, default='')
    razorpay_payment_id = models.CharField(
        max_length=100, blank=True, default='')
    razorpay_refund_id  = models.CharField(
        max_length=100, blank=True, default='')
    payment_status = models.CharField(
        max_length=30,
        choices=[
            ('pending',         'Pending'),
            ('paid',            'Paid'),
            ('refund_pending',  'Refund Pending'),
            ('refunded',        'Refunded'),
            ('no_refund',       'No Refund'),
            ('failed',          'Failed'),
        ],
        default='pending'
    )
    refund_amount  = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    cancelled_at   = models.DateTimeField(
        null=True, blank=True
    )
    # ── Doctor Response ───────────────────────────────────────────
    rejection_reason   = models.TextField(blank=True)
    doctor_notes       = models.TextField(blank=True)
    # ── Gate Pass ─────────────────────────────────────────────────
    gate_pass_code     = models.CharField(max_length=10, blank=True, null=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.gate_pass_code:
            import random
            self.gate_pass_code = f"MND-{str(random.randint(1000, 9999)).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Appt #{self.id} — {self.patient.user.username} ↔ Dr.{self.slot.doctor.user.username} [{self.status}]"



class ContactMessage(models.Model):
    TOPIC_CHOICES = [
        ('booking', 'Booking Help'),
        ('diagnosis', 'Diagnosis Query'),
        ('refund', 'Disputes & Refunds'),
        ('other', 'Other Support'),
    ]
    name       = models.CharField(max_length=100)
    email      = models.EmailField(blank=True)
    topic      = models.CharField(max_length=20, choices=TOPIC_CHOICES, default='other')
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'[{self.topic}] {self.name} — {self.message[:40]}'
