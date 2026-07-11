from django.contrib import admin
from .models import Consultation, ChatMessage, Rating, Feedback

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ['id', 'predicted_disease', 'patient', 'doctor', 'consult_type', 'status', 'date']
    list_filter  = ['status', 'consult_type', 'date']
    search_fields = ['predicted_disease', 'patient__name', 'doctor__name']

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['consultation', 'sender', 'message', 'timestamp']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'patient', 'score', 'created_at']

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'created_at']
