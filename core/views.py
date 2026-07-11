import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from accounts.models import PatientProfile, DoctorProfile
from .models import Consultation, ChatMessage, Rating, Feedback, Appointment, AppointmentSlot
from .utils import find_nearby_doctors, generate_video_token, ai_medical_response
from ml.disease_data import ALL_SYMPTOMS, DISEASE_SPECIALIST
from ml.predictor import predict_disease, get_disease_info



def home(request):
    from accounts.models import DoctorProfile
    top_doctors = DoctorProfile.objects.filter(is_verified=True).order_by('-rating')[:6]
    if top_doctors.count() < 3:
        top_doctors = DoctorProfile.objects.order_by('-rating')[:6]
    return render(request, 'core/home.html', {'top_doctors': top_doctors})


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


def find_doctors(request):
    """Smart Doctor Discovery Page (OSM + Platform)"""
    search_query = request.GET.get('search', '')
    specialist = request.GET.get('specialist', search_query)
    location_query = request.GET.get('location', '')

    # Try to get coordinates
    lat, lon = None, None
    city = ''
    if location_query:
        from core.utils import geocode_address
        lat, lon = geocode_address(location_query)
        city = location_query.split(',')[0].strip()
    elif request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        lat = request.user.patient_profile.latitude
        lon = request.user.patient_profile.longitude
        city = request.user.patient_profile.city

    # 1. Platform Doctors
    from core.utils import find_nearby_doctors
    platform_doctors = find_nearby_doctors(lat, lon, specialization=specialist, limit=20)
    
    # 2. OSM Real Doctors
    from core.utils import fetch_real_doctors
    osm_doctors = []
    if lat and lon or city:
        osm_doctors = fetch_real_doctors(lat=lat, lon=lon, specialization=specialist, city=city)

    return render(request, 'core/find_doctors.html', {
        'platform_doctors': platform_doctors,
        'osm_doctors': osm_doctors,
        'specialist': specialist,
        'location_query': location_query,
        'city': city,
        'lat': lat,
        'lon': lon,
    })


@login_required
@require_POST
def auto_register_osm_doctor(request):
    """Auto-register an OSM doctor to allow booking a slot."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can book slots.')
        return redirect('find_doctors')

    name = request.POST.get('name')
    speciality = request.POST.get('speciality', 'General Physician')
    lat = request.POST.get('lat')
    lon = request.POST.get('lon')
    address = request.POST.get('address', '')

    if not name:
        messages.error(request, 'Doctor name is missing.')
        return redirect('find_doctors')

    # Try to find existing dummy doctor
    doc = DoctorProfile.objects.filter(name=name, specialization__iexact=speciality).first()
    if not doc:
        import uuid
        dummy_email = f"osm_{uuid.uuid4().hex[:8]}@medicate.local"
        from django.contrib.auth.models import User
        user = User.objects.create_user(username=dummy_email, email=dummy_email, password=uuid.uuid4().hex)
        doc = DoctorProfile.objects.create(
            user=user,
            name=name,
            email=dummy_email,
            specialization=speciality.title(),
            hospital_name=name,
            address=address,
            latitude=lat or None,
            longitude=lon or None,
            fee=500,  # Default fee
            verification_status='pending',
            is_email_verified=False
        )
    
    return redirect('book_slot', doctor_id=doc.id)


@login_required
def book_slot(request, doctor_id):
    """Slot Booking with Razorpay payment."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can book slots.')
        return redirect('find_doctors')

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    from django.conf import settings
    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')

    if request.method == 'POST':
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')

        from datetime import datetime
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except Exception:
            messages.error(request, 'Invalid date or time selected.')
            return redirect('book_slot', doctor_id=doctor_id)

        # Get or create slot
        slot, _ = AppointmentSlot.objects.get_or_create(
            doctor=doctor, date=dt.date(), start_time=dt.time(),
            defaults={'end_time': dt.time(), 'is_booked': False}
        )

        if slot.is_booked:
            messages.error(request, 'This slot is fully booked. Please choose another time.')
            return redirect('book_slot', doctor_id=doctor_id)

        appt_type = request.POST.get('appointment_type', 'in_person')

        # Check if a cancelled/rejected appointment already exists
        # for this slot — if so, reuse it instead of creating new
        existing_appt = Appointment.objects.filter(slot=slot).first()
        if existing_appt:
            # Reset it for this patient
            existing_appt.patient        = request.user.patient_profile
            existing_appt.status         = 'pending_payment'
            existing_appt.payment_status = 'pending'
            existing_appt.rejection_reason = ''
            existing_appt.doctor_notes    = ''
            existing_appt.razorpay_order_id   = ''
            existing_appt.razorpay_payment_id = ''
            existing_appt.appointment_type = appt_type
            # Generate a new gate pass
            import random
            existing_appt.gate_pass_code = f"MND-{str(random.randint(1000,9999)).zfill(4)}"
            existing_appt.save()
            appointment = existing_appt
        else:
            appointment = Appointment.objects.create(
                patient=request.user.patient_profile,
                slot=slot,
                status='pending_payment',
                appointment_type=appt_type
            )

        fee = doctor.video_consult_fee if appt_type == 'video' else (doctor.fee or 0)
        appointment.fee = fee
        appointment.save(update_fields=['fee'])

        if fee > 0:
            return redirect('upi_payment', appointment_id=appointment.id)

        # Free appointment (fee = 0): go directly to confirmed
        appointment.status = 'confirmed'
        appointment.payment_status = 'paid'
        queue_pos = Appointment.objects.filter(slot=slot, status='confirmed').count() + 1
        appointment.queue_position = queue_pos
        
        if appointment.appointment_type == 'video':
            from core.video_utils import create_daily_room
            room_name = f"appt-{appointment.id}-{slot.date}-{slot.start_time.strftime('%H%M')}"
            url, name = create_daily_room(room_name)
            appointment.video_room_url = url
            appointment.video_room_name = name

        appointment.save(update_fields=['status', 'payment_status', 'queue_position', 'video_room_url', 'video_room_name'])
        messages.success(request, f'Appointment booked! Dr. {doctor.name} is confirmed.')

        # Re-evaluate slot capacity (max 6)
        active_count = Appointment.objects.filter(
            slot=slot,
            status__in=['pending_payment', 'payment_done', 'confirmed']
        ).count()
        if active_count >= 6:
            slot.is_booked = True
            slot.save(update_fields=['is_booked'])

        return redirect('booking_success', pk=appointment.pk)

    # Generate slots for next 7 days using doctor's actual availability
    from datetime import date, timedelta, time as dt_time, datetime
    import json

    today = date.today()
    days = [today + timedelta(days=i) for i in range(7)]

    # Determine slot range from doctor's profile
    slot_start = doctor.available_from if doctor.available_from else dt_time(10, 0)
    slot_end   = doctor.available_to   if doctor.available_to   else dt_time(20, 0)

    # Build list of all 30-min slot times between start and end
    def generate_time_slots(start, end):
        slots = []
        current = datetime.combine(date.today(), start)
        end_dt  = datetime.combine(date.today(), end)
        while current < end_dt:
            slots.append(current.time())
            current += timedelta(minutes=30)
        return slots

    all_slot_times = generate_time_slots(slot_start, slot_end)

    from django.db.models import Count, Q
    slot_counts = AppointmentSlot.objects.filter(
        doctor=doctor, date__in=days
    ).annotate(
        active_count=Count('appointments', filter=Q(appointments__status__in=['pending_payment', 'payment_done', 'confirmed']))
    ).values_list('date', 'start_time', 'active_count')

    booked_counts = {(d, t): cnt for d, t, cnt in slot_counts}

    now = datetime.now()

    day_slots = []
    for d in days:
        morning   = []
        afternoon = []
        evening   = []

        for t in all_slot_times:
            # Hide past slots for today
            if d == today:
                slot_dt = datetime.combine(d, t)
                if slot_dt <= now:
                    continue

            active_cnt = booked_counts.get((d, t), 0)
            is_booked = active_cnt >= 6
            spots_left = 6 - active_cnt

            # Windows-safe: strip leading zero manually
            raw = datetime.combine(date.today(), t).strftime('%I:%M %p')
            label = raw.lstrip('0')  # "09:00 AM" -> "9:00 AM"
            slot_data = {
                'time_str': t.strftime('%H:%M'),   # for form submission (24h)
                'label':    label,                  # for display (12h AM/PM)
                'booked':   is_booked,
                'spots':    spots_left,
            }

            if t < dt_time(12, 0):
                morning.append(slot_data)
            elif t < dt_time(17, 0):
                afternoon.append(slot_data)
            else:
                evening.append(slot_data)

        day_slots.append({
            'date':      d,
            'date_str':  d.strftime('%Y-%m-%d'),
            'day_name':  d.strftime('%a').upper(),
            'day_num':   str(d.day),  # Windows-safe, no leading zero
            'month':     d.strftime('%b'),
            'is_today':  d == today,
            'morning':   morning,
            'afternoon': afternoon,
            'evening':   evening,
        })

    return render(request, 'core/book_slot.html', {
        'doctor':      doctor,
        'day_slots':   day_slots,
        'razorpay_key': razorpay_key,
    })


@login_required
def book_video_slot(request, doctor_id):
    """Slot Booking with Razorpay payment."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can book slots.')
        return redirect('find_doctors')

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    from django.conf import settings
    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')

    if request.method == 'POST':
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')

        from datetime import datetime
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except Exception:
            messages.error(request, 'Invalid date or time selected.')
            return redirect('book_slot', doctor_id=doctor_id)

        # Get or create slot
        slot, _ = AppointmentSlot.objects.get_or_create(
            doctor=doctor, date=dt.date(), start_time=dt.time(),
            defaults={'end_time': dt.time(), 'is_booked': False}
        )

        if slot.is_booked:
            messages.error(request, 'This slot is fully booked. Please choose another time.')
            return redirect('book_slot', doctor_id=doctor_id)

        appt_type = request.POST.get('appointment_type', 'in_person')

        # Check if a cancelled/rejected appointment already exists
        # for this slot — if so, reuse it instead of creating new
        existing_appt = Appointment.objects.filter(slot=slot).first()
        if existing_appt:
            # Reset it for this patient
            existing_appt.patient        = request.user.patient_profile
            existing_appt.status         = 'pending_payment'
            existing_appt.payment_status = 'pending'
            existing_appt.rejection_reason = ''
            existing_appt.doctor_notes    = ''
            existing_appt.razorpay_order_id   = ''
            existing_appt.razorpay_payment_id = ''
            existing_appt.appointment_type = appt_type
            # Generate a new gate pass
            import random
            existing_appt.gate_pass_code = f"MND-{str(random.randint(1000,9999)).zfill(4)}"
            existing_appt.save()
            appointment = existing_appt
        else:
            appointment = Appointment.objects.create(
                patient=request.user.patient_profile,
                slot=slot,
                status='pending_payment',
                appointment_type=appt_type
            )

        fee = doctor.video_consult_fee if appt_type == 'video' else (doctor.fee or 0)
        appointment.fee = fee
        appointment.save(update_fields=['fee'])

        if fee > 0:
            return redirect('upi_payment', appointment_id=appointment.id)

        # Free appointment (fee = 0): go directly to confirmed
        appointment.status = 'confirmed'
        appointment.payment_status = 'paid'
        queue_pos = Appointment.objects.filter(slot=slot, status='confirmed').count() + 1
        appointment.queue_position = queue_pos
        
        if appointment.appointment_type == 'video':
            from core.video_utils import create_daily_room
            room_name = f"appt-{appointment.id}-{slot.date}-{slot.start_time.strftime('%H%M')}"
            url, name = create_daily_room(room_name)
            appointment.video_room_url = url
            appointment.video_room_name = name

        appointment.save(update_fields=['status', 'payment_status', 'queue_position', 'video_room_url', 'video_room_name'])
        messages.success(request, f'Appointment booked! Dr. {doctor.name} is confirmed.')

        # Re-evaluate slot capacity (max 6)
        active_count = Appointment.objects.filter(
            slot=slot,
            status__in=['pending_payment', 'payment_done', 'confirmed']
        ).count()
        if active_count >= 6:
            slot.is_booked = True
            slot.save(update_fields=['is_booked'])

        return redirect('booking_success', pk=appointment.pk)

    # Generate slots for next 7 days using doctor's actual availability
    from datetime import date, timedelta, time as dt_time, datetime
    import json

    today = date.today()
    days = [today + timedelta(days=i) for i in range(7)]

    # Determine slot range from doctor's profile
    slot_start = doctor.available_from if doctor.available_from else dt_time(10, 0)
    slot_end   = doctor.available_to   if doctor.available_to   else dt_time(20, 0)

    # Build list of all 30-min slot times between start and end
    def generate_time_slots(start, end):
        slots = []
        current = datetime.combine(date.today(), start)
        end_dt  = datetime.combine(date.today(), end)
        while current < end_dt:
            slots.append(current.time())
            current += timedelta(minutes=30)
        return slots

    all_slot_times = generate_time_slots(slot_start, slot_end)

    from django.db.models import Count, Q
    slot_counts = AppointmentSlot.objects.filter(
        doctor=doctor, date__in=days
    ).annotate(
        active_count=Count('appointments', filter=Q(appointments__status__in=['pending_payment', 'payment_done', 'confirmed']))
    ).values_list('date', 'start_time', 'active_count')

    booked_counts = {(d, t): cnt for d, t, cnt in slot_counts}

    now = datetime.now()

    day_slots = []
    for d in days:
        morning   = []
        afternoon = []
        evening   = []

        for t in all_slot_times:
            # Hide past slots for today
            if d == today:
                slot_dt = datetime.combine(d, t)
                if slot_dt <= now:
                    continue

            active_cnt = booked_counts.get((d, t), 0)
            is_booked = active_cnt >= 6
            spots_left = 6 - active_cnt

            # Windows-safe: strip leading zero manually
            raw = datetime.combine(date.today(), t).strftime('%I:%M %p')
            label = raw.lstrip('0')  # "09:00 AM" -> "9:00 AM"
            slot_data = {
                'time_str': t.strftime('%H:%M'),   # for form submission (24h)
                'label':    label,                  # for display (12h AM/PM)
                'booked':   is_booked,
                'spots':    spots_left,
            }

            if t < dt_time(12, 0):
                morning.append(slot_data)
            elif t < dt_time(17, 0):
                afternoon.append(slot_data)
            else:
                evening.append(slot_data)

        day_slots.append({
            'date':      d,
            'date_str':  d.strftime('%Y-%m-%d'),
            'day_name':  d.strftime('%a').upper(),
            'day_num':   str(d.day),  # Windows-safe, no leading zero
            'month':     d.strftime('%b'),
            'is_today':  d == today,
            'morning':   morning,
            'afternoon': afternoon,
            'evening':   evening,
        })

    return render(request, 'core/book_video_slot.html', {
        'doctor':      doctor,
        'day_slots':   day_slots,
        'razorpay_key': razorpay_key,
    })


@login_required
def payment_callback(request):
    """Handle Razorpay payment success callback."""
    if request.method != 'POST':
        return redirect('home')

    razorpay_order_id   = request.POST.get('razorpay_order_id', '')
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_signature  = request.POST.get('razorpay_signature', '')

    appointment = Appointment.objects.filter(razorpay_order_id=razorpay_order_id).first()
    if not appointment:
        messages.error(request, 'Appointment not found.')
        return redirect('patient_dashboard')

    from .razorpay_utils import verify_razorpay_payment
    if verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        appointment.razorpay_payment_id = razorpay_payment_id
        appointment.payment_status = 'paid'
        appointment.status         = 'confirmed'
        queue_pos = Appointment.objects.filter(slot=appointment.slot, status='confirmed').count() + 1
        appointment.queue_position = queue_pos

        if appointment.appointment_type == 'video':
            from core.video_utils import create_daily_room
            room_name = f"appt-{appointment.id}-{appointment.slot.date}-{appointment.slot.start_time.strftime('%H%M')}"
            url, name = create_daily_room(room_name)
            appointment.video_room_url = url
            appointment.video_room_name = name

        appointment.save(update_fields=['razorpay_payment_id', 'payment_status', 'status', 'queue_position', 'video_room_url', 'video_room_name'])

        # Notify doctor by email
        doctor  = appointment.slot.doctor
        patient = appointment.patient
        from accounts.email_utils import send_appointment_email_to_doctor
        send_appointment_email_to_doctor(
            doctor.email, doctor.name, patient.name,
            appointment.slot.date, appointment.slot.start_time,
            appointment.id
        )
        messages.success(request, f'✅ Payment successful! Dr. {doctor.name} is confirmed.')
        return redirect('booking_success', pk=appointment.pk)
    else:
        appointment.status = 'pending_payment'
        appointment.save(update_fields=['status'])
        messages.error(request, 'Payment verification failed. Please try again or contact support.')
        return redirect('patient_dashboard')


@login_required
def booking_success(request, pk):
    """Show booking success page with queue position."""
    appointment = get_object_or_404(Appointment, pk=pk)
    if appointment.patient.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('home')
    return render(request, 'core/booking_success.html', {'appointment': appointment})


@login_required
def appointment_detail(request, pk):
    """Patient/Doctor view a single appointment."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user = request.user
    is_patient = hasattr(user, 'patient_profile') and appointment.patient.user == user
    is_doctor  = hasattr(user, 'doctor_profile')  and appointment.slot.doctor.user == user
    if not (is_patient or is_doctor):
        messages.error(request, 'Access denied.')
        return redirect('home')
    return render(request, 'core/appointment_detail.html', {
        'appointment': appointment, 'is_patient': is_patient, 'is_doctor': is_doctor,
    })


@login_required
def cancel_appointment(request, pk):
    """Patient cancels an appointment (only if not yet accepted)."""
    appointment = get_object_or_404(Appointment, pk=pk)

    if appointment.patient.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('patient_dashboard')

    if appointment.status in ('completed', 'rejected', 'cancelled'):
        messages.error(request,
            'This appointment cannot be cancelled.')
        return redirect('appointment_detail', pk=pk)

    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal

    now = timezone.now()
    appointment_dt = timezone.make_aware(datetime.combine(appointment.slot.date, appointment.slot.start_time))
    hours_until = (appointment_dt - now).total_seconds() / 3600

    fee = appointment.slot.doctor.video_consult_fee if appointment.appointment_type == 'video' else appointment.slot.doctor.fee
    fee = fee or 0

    appointment.status       = 'cancelled'
    appointment.cancellation_time = now

    if appointment.payment_status == 'paid' and fee > 0:
        if hours_until > 1:
            refund_amt = Decimal(str(fee)) * Decimal('0.40')
            appointment.refund_eligible = True
            appointment.refund_amount  = refund_amt
            appointment.payment_status = 'refund_pending'
            messages.success(request,
                f'Appointment cancelled. A 40% refund of '
                f'₹{refund_amt:.2f} will be processed to your '
                f'UPI by the doctor.')
        else:
            appointment.refund_eligible = False
            appointment.refund_amount = Decimal('0.00')
            appointment.payment_status = 'no_refund'
            messages.success(request, 'Appointment cancelled. No refund (cancelled within 1 hour).')
    else:
        messages.success(request, 'Appointment cancelled.')

    appointment.save()

    # CRITICAL: Free the slot so it can be rebooked
    slot = appointment.slot
    
    active_count = Appointment.objects.filter(
        slot=slot,
        status__in=['pending_payment', 'payment_done', 'confirmed']
    ).count()
    if active_count < 6:
        slot.is_booked = False
        slot.save(update_fields=['is_booked'])

    return redirect('patient_dashboard')


@login_required
def doctor_appointments(request):
    """Doctor sees all their appointments with accept/reject actions."""
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, 'Only doctors can access this page.')
        return redirect('home')

    doctor = request.user.doctor_profile
    confirmed = Appointment.objects.filter(slot__doctor=doctor, status='confirmed').order_by('slot__date', 'slot__start_time')
    completed = Appointment.objects.filter(slot__doctor=doctor, status='completed').order_by('-slot__date')
    rejected  = Appointment.objects.filter(slot__doctor=doctor, status='rejected').order_by('-slot__date')
    refunds   = Appointment.objects.filter(slot__doctor=doctor, payment_status='refund_pending').order_by('-slot__date')

    return render(request, 'core/doctor_appointments.html', {
        'confirmed': confirmed, 'completed': completed,
        'rejected': rejected, 'refunds': refunds, 'doctor': doctor,
    })


@login_required
@require_POST
def appointment_action(request, pk):
    """Doctor accepts or rejects an appointment."""
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, 'Only doctors can perform this action.')
        return redirect('home')

    appointment = get_object_or_404(Appointment, pk=pk, slot__doctor=request.user.doctor_profile)
    action = request.POST.get('action')
    reason = request.POST.get('reason', '').strip()

    if action == 'reject':
        appointment.status           = 'rejected'
        appointment.rejection_reason = reason
        if appointment.payment_status == 'paid':
            appointment.payment_status = 'refund_pending'
            appointment.refund_eligible = True
            appointment.refund_amount = appointment.slot.doctor.video_consult_fee if appointment.appointment_type == 'video' else appointment.slot.doctor.fee
        
        appointment.save(update_fields=['status', 'rejection_reason', 'payment_status', 'refund_eligible', 'refund_amount'])
        
        # Free slot capacity
        active_count = Appointment.objects.filter(
            slot=appointment.slot,
            status__in=['pending_payment', 'payment_done', 'confirmed']
        ).count()
        if active_count < 6:
            appointment.slot.is_booked = False
            appointment.slot.save(update_fields=['is_booked'])

        from accounts.email_utils import send_appointment_status_email
        send_appointment_status_email(
            appointment.patient.email, appointment.patient.name,
            appointment.slot.doctor.name, 'rejected',
            appointment.slot.date, appointment.slot.start_time,
            reason=reason
        )
        messages.success(request, f'Appointment #{pk} rejected. Patient has been notified.')

    elif action == 'mark_refunded':
        appointment.payment_status = 'refunded'
        appointment.save(update_fields=['payment_status'])
        messages.success(request, f'Refund for Appointment #{pk} marked as completed.')

    return redirect('doctor_appointments')



@login_required
@csrf_exempt
def razorpay_verify(request):
    import hmac, hashlib
    if request.method != 'POST':
        return redirect('patient_dashboard')

    order_id   = request.POST.get('razorpay_order_id', '')
    payment_id = request.POST.get('razorpay_payment_id', '')
    signature  = request.POST.get('razorpay_signature', '')
    appt_id    = request.POST.get('appointment_id')

    appointment = get_object_or_404(
        Appointment, pk=appt_id,
        patient=request.user.patient_profile
    )

    generated = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if generated == signature:
        # Signature valid — mark paid
        appointment.razorpay_payment_id = payment_id
        appointment.payment_status      = 'paid'
        appointment.status              = 'pending_approval'
        appointment.save()
        messages.success(request,
            'Payment successful! Awaiting doctor confirmation.')
        return redirect('appointment_detail', pk=appt_id)
    else:
        appointment.payment_status = 'failed'
        appointment.save()
        messages.error(request,
            'Payment verification failed. Please try again.')
        return redirect('appointment_detail', pk=appt_id)


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
        appointments  = Appointment.objects.filter(
            patient=user.patient_profile
        ).select_related('slot__doctor').order_by('-created_at')
        role = 'patient'
    elif hasattr(user, 'doctor_profile'):
        consultations = user.doctor_profile.consultations.select_related('patient').order_by('-created_at')
        appointments  = Appointment.objects.filter(
            slot__doctor=user.doctor_profile
        ).select_related('patient').order_by('-created_at')
        role = 'doctor'
    else:
        return redirect('home')

    return render(request, 'core/consultation_history.html', {
        'consultations': consultations,
        'appointments':  appointments,
        'role': role,
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


def contact_us(request):
    """Handle Contact Us form submissions."""
    from .models import ContactMessage
    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        topic   = request.POST.get('topic', 'other')
        message = request.POST.get('message', '').strip()
        if name and message:
            ContactMessage.objects.create(name=name, email=email, topic=topic, message=message)
            messages.success(request, 'Your message has been sent! We will get back to you within 24 hours.')
        else:
            messages.error(request, 'Please fill in your name and message.')
    return redirect('home')


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

import io, base64

@login_required
def upi_payment(request, appointment_id):
    """Show UPI QR code for patient to pay doctor directly."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Only patients can make payments.')
        return redirect('home')

    appointment = get_object_or_404(Appointment, pk=appointment_id)

    # Security: only the appointment's patient can pay
    if appointment.patient.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('patient_dashboard')

    # Already paid
    if appointment.status == 'pending_approval':
        messages.info(request, 'Payment already recorded. Awaiting doctor confirmation.')
        return redirect('appointment_detail', pk=appointment.pk)

    doctor = appointment.slot.doctor
    fee = appointment.fee

    # Generate UPI QR code
    upi_url = (
        f"upi://pay?pa={doctor.upi_id}"
        f"&pn={doctor.name.replace(' ', '%20')}"
        f"&am={fee}"
        f"&cu=INR"
        f"&tn=MediCate%20Appointment%20%23{appointment.id}"
    )

    try:
        import qrcode
        from io import BytesIO
        import base64
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(upi_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        qr_b64 = base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        qr_b64 = ''

    return render(request, 'core/upi_payment.html', {
        'appointment': appointment,
        'doctor': doctor,
        'fee': fee,
        'upi_url': upi_url,
        'qr_b64': qr_b64,
    })


@login_required
@require_POST
def mark_upi_paid(request, appointment_id):
    """Patient marks UPI payment as done → status becomes pending_approval."""
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    appointment = get_object_or_404(Appointment, pk=appointment_id)

    if appointment.patient.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('patient_dashboard')

    if appointment.status != 'pending_payment':
        messages.warning(request, 'This appointment is already processed.')
        return redirect('appointment_detail', pk=appointment.pk)

    appointment.status = 'confirmed'
    appointment.payment_status = 'paid'
    
    queue_pos = Appointment.objects.filter(slot=appointment.slot, status='confirmed').count() + 1
    appointment.queue_position = queue_pos

    if appointment.appointment_type == 'video':
        from core.video_utils import create_daily_room
        room_name = f"appt-{appointment.id}-{appointment.slot.date}-{appointment.slot.start_time.strftime('%H%M')}"
        url, name = create_daily_room(room_name)
        appointment.video_room_url = url
        appointment.video_room_name = name

    appointment.save(update_fields=['status', 'payment_status', 'queue_position', 'video_room_url', 'video_room_name'])

    # Notify doctor by email
    doctor = appointment.slot.doctor
    patient = appointment.patient
    try:
        from accounts.email_utils import send_appointment_email_to_doctor
        send_appointment_email_to_doctor(
            doctor.email, doctor.name, patient.name,
            appointment.slot.date, appointment.slot.start_time,
            appointment.id
        )
    except Exception:
        pass

    messages.success(
        request,
        f'✅ Payment marked as done! Dr. {doctor.name} is confirmed.'
    )
    return redirect('booking_success', pk=appointment.pk)


@login_required
def no_upi_fallback(request, appointment_id):
    """Shown when doctor has no UPI ID set up yet."""
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    if appointment.patient.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('patient_dashboard')
    doctor = appointment.slot.doctor
    return render(request, 'core/no_upi_fallback.html', {
        'appointment': appointment,
        'doctor': doctor,
    })

