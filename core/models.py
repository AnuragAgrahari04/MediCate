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
