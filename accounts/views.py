from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import PatientSignupForm, DoctorSignupForm, PatientProfileForm, DoctorProfileForm
from .models import PatientProfile, DoctorProfile
from core.utils import geocode_address


def signup_patient(request):
    form = PatientSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=d['password'])
        addr = f"{d.get('address','')}, {d.get('city','')}, {d.get('state','')}, {d.get('country','India')}"
        lat, lon = geocode_address(addr)
        PatientProfile.objects.create(
            user=user, name=d['name'], email=d['email'],
            dob=d.get('dob'), gender=d.get('gender',''),
            mobile_no=d.get('mobile_no',''), address=d.get('address',''),
            city=d.get('city',''), state=d.get('state',''),
            pincode=d.get('pincode',''), country=d.get('country','India'),
            blood_group=d.get('blood_group',''),
            latitude=lat, longitude=lon,
        )
        login(request, user)
        messages.success(request, f'Welcome, {user.username}! Account created.')
        return redirect('patient_dashboard')
    return render(request, 'accounts/signup_patient.html', {'form': form})


def signup_doctor(request):
    form = DoctorSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=d['password'])
        addr = f"{d.get('address','')}, {d.get('city','')}, {d.get('state','')}, {d.get('country','India')}"
        lat, lon = geocode_address(addr)
        DoctorProfile.objects.create(
            user=user, name=d['name'], email=d['email'],
            specialization=d.get('specialization',''),
            qualification=d.get('qualification',''),
            experience_yrs=d.get('experience_yrs') or 0,
            hospital_name=d.get('hospital_name',''),
            fee=d.get('fee') or 0,
            bio=d.get('bio',''),
            mobile_no=d.get('mobile_no',''),
            address=d.get('address',''),
            city=d.get('city',''), state=d.get('state',''),
            pincode=d.get('pincode',''), country=d.get('country','India'),
            video_consult=d.get('video_consult', True),
            chat_consult=d.get('chat_consult', True),
            latitude=lat, longitude=lon,
        )
        login(request, user)
        messages.success(request, f'Welcome Dr. {d["name"]}! Account created.')
        return redirect('doctor_dashboard')
    return render(request, 'accounts/signup_doctor.html', {'form': form})


def login_patient(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and hasattr(user, 'patient_profile'):
            login(request, user)
            return redirect('patient_dashboard')
        messages.error(request, 'Invalid credentials or not a patient account.')
    return render(request, 'accounts/login_patient.html')


def login_doctor(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and hasattr(user, 'doctor_profile'):
            login(request, user)
            return redirect('doctor_dashboard')
        messages.error(request, 'Invalid credentials or not a doctor account.')
    return render(request, 'accounts/login_doctor.html')


def login_admin(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and user.is_staff:
            login(request, user)
            return redirect('/admin/')
        messages.error(request, 'Invalid admin credentials.')
    return render(request, 'accounts/login_admin.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def patient_profile(request, username):
    profile = get_object_or_404(PatientProfile, user__username=username)
    is_owner = request.user == profile.user
    form = None
    if is_owner and request.method == 'POST':
        form = PatientProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            prof = form.save(commit=False)
            addr = f"{prof.address}, {prof.city}, {prof.state}, {prof.country}"
            lat, lon = geocode_address(addr)
            if lat:
                prof.latitude, prof.longitude = lat, lon
            prof.save()
            messages.success(request, 'Profile updated.')
            return redirect('patient_profile', username=username)
    elif is_owner:
        form = PatientProfileForm(instance=profile)
    return render(request, 'accounts/patient_profile.html', {'profile': profile, 'form': form, 'is_owner': is_owner})


@login_required
def doctor_profile(request, username):
    profile = get_object_or_404(DoctorProfile, user__username=username)
    is_owner = request.user == profile.user
    form = None
    if is_owner and request.method == 'POST':
        form = DoctorProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            prof = form.save(commit=False)
            addr = f"{prof.address}, {prof.city}, {prof.state}, {prof.country}"
            lat, lon = geocode_address(addr)
            if lat:
                prof.latitude, prof.longitude = lat, lon
            prof.save()
            messages.success(request, 'Profile updated.')
            return redirect('doctor_profile', username=username)
    elif is_owner:
        form = DoctorProfileForm(instance=profile)
    return render(request, 'accounts/doctor_profile.html', {'profile': profile, 'form': form, 'is_owner': is_owner})
