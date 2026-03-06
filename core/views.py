import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from accounts.models import PatientProfile, DoctorProfile
from .models import Consultation, ChatMessage, Rating, Feedback
from .utils import find_nearby_doctors, generate_video_token, ai_medical_response
from ml.disease_data import ALL_SYMPTOMS, DISEASE_SPECIALIST
from ml.predictor import predict_disease, get_disease_info


def home(request):
    return render(request, 'core/home.html')


@login_required
def patient_dashboard(request):
    try:
        profile = request.user.patient_profile
    except PatientProfile.DoesNotExist:
        messages.error(request, 'Patient profile not found. Please sign up correctly.')
        return redirect('home')
    recent = profile.consultations.select_related('doctor').order_by('-created_at')[:5]
    return render(request, 'core/patient_dashboard.html', {'profile': profile, 'recent': recent})


@login_required
def doctor_dashboard(request):
    try:
        profile = request.user.doctor_profile
    except DoctorProfile.DoesNotExist:
        messages.error(request, 'Doctor profile not found.')
        return redirect('home')
    recent = profile.consultations.select_related('patient').order_by('-created_at')[:5]
    pending = profile.consultations.filter(status='active').count()
    return render(request, 'core/doctor_dashboard.html', {
        'profile': profile, 'recent': recent, 'pending': pending
    })


@login_required
def check_disease(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can use the symptom checker.')
        return redirect('home')

    symptoms     = ALL_SYMPTOMS
    result       = None
    predictions  = []
    selected     = []

    if request.method == 'POST':
        selected = request.POST.getlist('symptoms')
        if len(selected) < 2:
            messages.warning(request, 'Please select at least 2 symptoms.')
        else:
            predictions = predict_disease(selected, top_n=5)
            if predictions:
                top_disease, top_conf = predictions[0]
                specialist  = DISEASE_SPECIALIST.get(top_disease, 'General Physician')
                disease_info = get_disease_info(top_disease)
                result = {
                    'disease':       top_disease,
                    'confidence':    top_conf,
                    'specialist':    specialist,
                    'disease_info':  disease_info,
                    'predictions':   predictions,
                    'selected':      selected,
                }
                request.session['last_prediction'] = {
                    'disease':    top_disease,
                    'confidence': top_conf,
                    'specialist': specialist,
                    'symptoms':   selected,
                    'predictions': predictions,
                }

    return render(request, 'core/check_disease.html', {
        'symptoms': symptoms,
        'result':   result,
        'selected': selected,
    })


@login_required
def consult_doctor(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can consult doctors.')
        return redirect('home')

    patient   = request.user.patient_profile
    specialist = request.GET.get('specialist', '')
    disease    = request.GET.get('disease', '')

    doctors = find_nearby_doctors(
        patient_lat=patient.latitude,
        patient_lon=patient.longitude,
        specialization=specialist,
        limit=10,
    )

    # If no verified doctors found, fall back to all registered doctors
    if not doctors:
        qs = DoctorProfile.objects.all()
        if specialist:
            qs = qs.filter(specialization__icontains=specialist)
        doctors = list(qs.order_by('-rating')[:10])
        for doc in doctors:
            doc.distance_km = None

    # Fetch real doctors from Google Places API
    from .utils import fetch_real_doctors
    real_doctors = fetch_real_doctors(
        lat=patient.latitude,
        lon=patient.longitude,
        specialization=specialist,
        city=patient.city or '',
    )

    return render(request, 'core/consult_doctor.html', {
        'doctors':      doctors,
        'real_doctors': real_doctors,
        'specialist':   specialist,
        'disease':      disease,
        'patient':      patient,
    })


@login_required
@require_POST
def start_consultation(request):
    if not hasattr(request.user, 'patient_profile'):
        return JsonResponse({'error': 'Not a patient'}, status=403)

    patient    = request.user.patient_profile
    doctor_id  = request.POST.get('doctor_id')
    consult_type = request.POST.get('consult_type', 'chat')

    # Retrieve from session
    pred = request.session.get('last_prediction', {})
    disease    = pred.get('disease', request.POST.get('disease', 'Unknown'))
    symptoms   = pred.get('symptoms', [])
    confidence = pred.get('confidence', 0)
    predictions = pred.get('predictions', [])

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)

    c = Consultation.objects.create(
        patient=patient, doctor=doctor,
        predicted_disease=disease,
        symptoms=', '.join(symptoms),
        confident_score=confidence,
        top_predictions=predictions,
        consult_type=consult_type,
        status='active',
    )

    # Video token generation
    if consult_type == 'video':
        import uuid
        channel = f'consult_{c.id}_{uuid.uuid4().hex[:8]}'
        c.video_channel       = channel
        c.video_token_patient = generate_video_token(channel, uid=patient.user.id)
        c.video_token_doctor  = generate_video_token(channel, uid=doctor.user.id)
        c.save()

    messages.success(request, f'Consultation started with Dr. {doctor.name}.')
    return redirect('consultation_view', pk=c.pk)


@login_required
def consultation_view(request, pk):
    c = get_object_or_404(Consultation, pk=pk)
    user = request.user
    is_patient = hasattr(user, 'patient_profile') and c.patient.user == user
    is_doctor  = hasattr(user, 'doctor_profile')  and c.doctor.user == user

    if not (is_patient or is_doctor):
        messages.error(request, 'Access denied.')
        return redirect('home')

    messages_qs = c.messages.select_related('sender').order_by('timestamp')

    try:
        already_rated = bool(c.rating)
    except Exception:
        already_rated = False

    return render(request, 'core/consultation_view.html', {
        'consultation': c,
        'messages_qs':  messages_qs,
        'is_patient':   is_patient,
        'is_doctor':    is_doctor,
        'already_rated': already_rated,
        'agora_app_id': getattr(__import__('django.conf', fromlist=['settings']).settings, 'AGORA_APP_ID', ''),
    })


@login_required
def close_consultation(request, pk):
    c = get_object_or_404(Consultation, pk=pk)
    if c.patient.user == request.user or c.doctor.user == request.user:
        c.status = 'closed'
        c.save()
        messages.success(request, 'Consultation closed.')
    return redirect('consultation_history')


@login_required
def consultation_history(request):
    user = request.user
    if hasattr(user, 'patient_profile'):
        consultations = user.patient_profile.consultations.select_related('doctor').order_by('-created_at')
        role = 'patient'
    elif hasattr(user, 'doctor_profile'):
        consultations = user.doctor_profile.consultations.select_related('patient').order_by('-created_at')
        role = 'doctor'
    else:
        return redirect('home')

    return render(request, 'core/consultation_history.html', {
        'consultations': consultations, 'role': role
    })


@login_required
def rate_doctor(request, pk):
    c = get_object_or_404(Consultation, pk=pk)
    if c.patient.user != request.user:
        messages.error(request, 'Only the patient can rate this consultation.')
        return redirect('consultation_view', pk=pk)

    try:
        _ = c.rating
        messages.info(request, 'You have already rated this consultation.')
        return redirect('consultation_view', pk=pk)
    except Exception:
        pass

    if request.method == 'POST':
        score  = int(request.POST.get('score', 5))
        review = request.POST.get('review', '')
        Rating.objects.create(consultation=c, doctor=c.doctor, patient=c.patient,
                               score=score, review=review)
        messages.success(request, 'Thank you for your rating!')
        return redirect('consultation_view', pk=pk)

    return render(request, 'core/rate_doctor.html', {'consultation': c})


@login_required
def give_feedback(request):
    if request.method == 'POST':
        Feedback.objects.create(
            user=request.user,
            message=request.POST.get('message',''),
            rating=int(request.POST.get('rating', 5)),
        )
        messages.success(request, 'Thank you for your feedback!')
        return redirect('home')
    return render(request, 'core/feedback.html')


# ── AJAX / API views ──────────────────────────────────────────────

def api_symptoms(request):
    """Return symptom list as JSON for autocomplete."""
    q = request.GET.get('q', '').lower()
    filtered = [s for s in ALL_SYMPTOMS if q in s] if q else ALL_SYMPTOMS
    return JsonResponse({'symptoms': filtered})


@login_required
def api_ai_chat(request, pk):
    """POST: question → AI response JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    c = get_object_or_404(Consultation, pk=pk)
    body = json.loads(request.body)
    question = body.get('question', '')
    context  = f'Patient has {c.predicted_disease} with symptoms: {c.symptoms}'
    answer   = ai_medical_response(question, disease_context=context)
    return JsonResponse({'answer': answer})


@login_required
def api_doctors_map(request):
    """Return doctors with coords as GeoJSON for map."""
    specialist = request.GET.get('specialist', '')
    patient_lat = request.GET.get('lat', type=float)
    patient_lon = request.GET.get('lon', type=float)

    qs = DoctorProfile.objects.filter(latitude__isnull=False, longitude__isnull=False)
    if specialist:
        qs = qs.filter(specialization__icontains=specialist)

    features = []
    for doc in qs[:50]:
        dist = doc.distance_from(patient_lat, patient_lon)
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [doc.longitude, doc.latitude]},
            'properties': {
                'id': doc.id, 'name': f'Dr. {doc.name}',
                'specialization': doc.specialization,
                'city': doc.city, 'hospital': doc.hospital_name,
                'rating': doc.rating, 'fee': doc.fee,
                'distance_km': dist,
                'video': doc.video_consult,
            }
        })
    return JsonResponse({'type': 'FeatureCollection', 'features': features})


def debug_doctors(request):
    """Temporary debug endpoint — shows raw OSM results. Remove after testing."""
    from .utils import _fetch_osm_broadened, _fetch_nominatim
    import json

    lat  = request.GET.get('lat',  '25.3176')
    lon  = request.GET.get('lon',  '82.9739')
    spec = request.GET.get('spec', 'Dermatologist')
    city = request.GET.get('city', 'Varanasi')

    try:
        lat = float(lat)
        lon = float(lon)
    except Exception:
        lat, lon = 25.3176, 82.9739

    osm_results  = _fetch_osm_broadened(lat, lon, spec, city)
    nom_results  = _fetch_nominatim(spec, city)

    html = f"""
    <html><body style='font-family:monospace;padding:2rem;background:#111;color:#eee;'>
    <h2>Debug: Real Doctors for {spec} near {city} ({lat}, {lon})</h2>
    <h3>OSM Results ({len(osm_results)} found):</h3>
    <pre>{json.dumps(osm_results, indent=2, ensure_ascii=False)}</pre>
    <h3>Nominatim Results ({len(nom_results)} found):</h3>
    <pre>{json.dumps(nom_results, indent=2, ensure_ascii=False)}</pre>
    </body></html>
    """
    from django.http import HttpResponse
    return HttpResponse(html)