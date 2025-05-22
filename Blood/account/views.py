from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import random
from .forms import UserRegistrationForm, OTPVerificationForm, LoginForm, ScheduleDonationForm, EditProfileForm, ChangePasswordWithOTPForm, DonationCenterForm, BloodRequestForm, ForgotPasswordForm, ResetPasswordForm
from .models import User, OTP, UserProfile, DonationCenter, DonationAppointment, Notification, BloodStock, BloodRequest
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import timedelta

def home(request):
    return render(request, 'account/home.html')

@login_required
def dashboard(request):
    user = request.user
    if user.role == 'ADMIN':
        return redirect('admin_dashboard')
    user_profile = getattr(user, 'userprofile', None)
    blood_group = user_profile.blood_group if user_profile else None
    context = {}

    if user.role == 'DONOR':
        donor = user
        # Use real queries for donor dashboard context
        from .models import DonationAppointment
        from django.utils import timezone
        from datetime import timedelta

        # Total confirmed donations
        total_donations = DonationAppointment.objects.filter(donor=donor, status='CONFIRMED').count()

        # Last confirmed donation date
        last_appointment = DonationAppointment.objects.filter(donor=donor, status='CONFIRMED').order_by('-date').first()
        last_donation = last_appointment.date if last_appointment else None

        # Next eligible date (90 days after last donation or today if never donated)
        if last_donation:
            next_eligible_date = last_donation + timedelta(days=90)
        else:
            next_eligible_date = timezone.now().date()

        # Eligibility check
        is_eligible = timezone.now().date() >= next_eligible_date

        # Upcoming appointment (next pending or confirmed in the future)
        upcoming_appointment = DonationAppointment.objects.filter(
            donor=donor,
            date__gte=timezone.now().date(),
            status__in=['PENDING', 'CONFIRMED']
        ).order_by('date').first()

        # Lives saved estimate
        lives_saved = total_donations * 3

        # Recent donations (last 5)
        recent_donations = DonationAppointment.objects.filter(donor=donor).order_by('-date')[:5]

        context.update({
            'donor': donor,
            'total_donations': total_donations,
            'last_donation': last_donation,
            'next_eligible_date': next_eligible_date,
            'is_eligible': is_eligible,
            'upcoming_appointment': upcoming_appointment,
            'lives_saved': lives_saved,
            'recent_donations': recent_donations,
            'blood_group': blood_group,
        })
    elif user.role == 'PATIENT':
        from .models import BloodRequest
        patient = user
        all_requests = BloodRequest.objects.filter(patient=patient)
        total_requests = all_requests.count()
        approved_requests = all_requests.filter(status='APPROVED').count()
        rejected_requests = all_requests.filter(status='REJECTED').count()
        latest_request = all_requests.order_by('-created_at').first()
        next_appointment = all_requests.filter(status='APPROVED').order_by('-created_at').first()
        lives_saved = approved_requests * 3  # Optional motivational card
        context.update({
            'patient': patient,
            'blood_group': blood_group,
            'total_requests': total_requests,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests,
            'latest_request': latest_request,
            'next_appointment': next_appointment,
            'lives_saved': lives_saved,
        })

    return render(request, 'account/dashboard.html', context)

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_email(email, otp):
    subject = 'Your OTP for Blood Bank Registration'
    message = f'Your OTP for registration is: {otp}'
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]
    send_mail(subject, message, from_email, recipient_list)

def register_donor(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES, role='DONOR')
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            
            # Generate and save OTP
            otp = generate_otp()
            OTP.objects.create(user=user, otp=otp)
            
            # Send OTP email
            send_otp_email(user.email, otp)
            
            return redirect('verify_otp', user_id=user.id)
    else:
        form = UserRegistrationForm(role='DONOR')
    return render(request, 'account/register_donor.html', {'form': form})

def register_patient(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES, role='PATIENT')
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            
            # Generate and save OTP
            otp = generate_otp()
            OTP.objects.create(user=user, otp=otp)
            
            # Send OTP email
            send_otp_email(user.email, otp)
            
            return redirect('verify_otp', user_id=user.id)
    else:
        form = UserRegistrationForm(role='PATIENT')
    return render(request, 'account/register_patient.html', {'form': form})

def verify_otp(request, user_id):
    user = User.objects.get(id=user_id)
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            otp_obj = OTP.objects.filter(user=user, otp=otp, is_verified=False).first()
            
            if otp_obj:
                user.is_active = True
                user.is_email_verified = True
                user.save()
                otp_obj.is_verified = True
                otp_obj.save()
                
                login(request, user)
                messages.success(request, 'Registration successful!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid OTP')
    else:
        form = OTPVerificationForm()
    return render(request, 'account/verify_otp.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()
    return render(request, 'account/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def schedule_donation(request):
    user = request.user
    if user.role != 'DONOR':
        messages.error(request, 'Only donors can schedule donations.')
        return redirect('dashboard')

    # Example logic for eligibility and last donation
    user_profile = getattr(user, 'userprofile', None)
    total_donations = DonationAppointment.objects.filter(donor=user, status='CONFIRMED').count()
    last_appointment = DonationAppointment.objects.filter(donor=user, status='CONFIRMED').order_by('-date').first()
    last_donation = last_appointment.date if last_appointment else None
    # Assume 3 months (90 days) between donations
    next_eligible_date = (last_donation + timezone.timedelta(days=90)) if last_donation else timezone.now().date()
    is_eligible = timezone.now().date() >= next_eligible_date
    existing_appointments = DonationAppointment.objects.filter(donor=user, date__gte=timezone.now().date(), status__in=['PENDING', 'CONFIRMED'])

    if request.method == 'POST':
        form = ScheduleDonationForm(request.POST, donor=user, next_eligible_date=next_eligible_date)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.donor = user
            appointment.status = 'PENDING'
            appointment.save()
            # Notify all admins
            from .models import User, Notification
            admins = User.objects.filter(role='ADMIN')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title='New Donation Appointment',
                    message=f'Donor {request.user.get_full_name()} scheduled a donation on {appointment.date} at {appointment.center.name}.',
                    type='donation'
                )
            messages.success(request, 'Donation appointment scheduled successfully!')
            return redirect('dashboard')
    else:
        form = ScheduleDonationForm(donor=user, next_eligible_date=next_eligible_date)

    context = {
        'form': form,
        'donation_centers': DonationCenter.objects.all(),
        'next_eligible_date': next_eligible_date,
        'is_eligible': is_eligible,
        'existing_appointments': existing_appointments,
        'last_donation': last_donation,
        'total_donations': total_donations,
    }
    return render(request, 'account/schedule_donation.html', context)

@login_required
def donation_history(request):
    user = request.user
    if user.role != 'DONOR':
        messages.error(request, 'Only donors can view donation history.')
        return redirect('dashboard')

    appointments = DonationAppointment.objects.filter(donor=user).order_by('-date')
    paginator = Paginator(appointments, 8)  # 8 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    donation_history = []
    for appt in page_obj:
        donation_history.append({
            'date': appt.date,
            'center_name': appt.center.name,
            'location': appt.center.address,
            'status': appt.status.lower(),
            'remarks': appt.notes,
        })

    context = {
        'donation_history': donation_history,
        'page_obj': page_obj,
        'total_approved': appointments.filter(status='CONFIRMED').count(),
    }
    return render(request, 'account/donation_history.html', context)

@login_required
def notifications(request):
    user = request.user
    notif_type = request.GET.get('type', 'all')
    show_unread = request.GET.get('unread', '0') == '1'

    notifs = Notification.objects.filter(user=user)
    if notif_type != 'all':
        notifs = notifs.filter(type=notif_type)
    if show_unread:
        notifs = notifs.filter(read=False)
    notifs = notifs.order_by('-timestamp')

    if request.method == 'POST' and 'mark_all_read' in request.POST:
        notifs.update(read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('notifications')

    context = {
        'notifications': notifs,
        'notif_type': notif_type,
        'show_unread': show_unread,
    }
    return render(request, 'account/notifications.html', context)

@login_required
def profile_settings(request):
    user = request.user
    user_profile = getattr(user, 'userprofile', None)
    success_message = ''
    error_message = ''

    if request.method == 'POST' and 'update_profile' in request.POST:
        form = EditProfileForm(request.POST, request.FILES, instance=user, user_profile=user_profile)
        if form.is_valid():
            form.save()
            success_message = 'Profile updated successfully.'
        else:
            error_message = 'Please correct the errors below.'
        password_form = ChangePasswordWithOTPForm(user)
    elif request.method == 'POST' and 'change_password' in request.POST:
        password_form = ChangePasswordWithOTPForm(user, request.POST)
        form = EditProfileForm(instance=user, user_profile=user_profile)
        if password_form.is_valid():
            user.set_password(password_form.cleaned_data['new_password1'])
            user.save()
            success_message = 'Password changed successfully.'
        else:
            error_message = 'Please correct the errors below.'
    else:
        form = EditProfileForm(instance=user, user_profile=user_profile)
        password_form = ChangePasswordWithOTPForm(user)

    context = {
        'form': form,
        'password_form': password_form,
        'success_message': success_message,
        'error_message': error_message,
    }
    return render(request, 'account/profile_settings.html', context)

def admin_login(request):
    if request.user.is_authenticated and request.user.role == 'ADMIN':
        return redirect('admin_dashboard')
    error_message = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None and user.role == 'ADMIN':
            login(request, user)
            return redirect('admin_dashboard')
        else:
            error_message = 'Invalid credentials or not an admin.'
    return render(request, 'account/admin_login.html', {'error_message': error_message})

@login_required
def admin_dashboard(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')

    # Blood stock overview
    blood_types = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    blood_stock = []
    low_stock_alerts = []
    for btype in blood_types:
        stock = BloodStock.objects.filter(type=btype).first()
        units = stock.units if stock else 0
        last_updated = stock.last_updated if stock else None
        blood_stock.append({'type': btype, 'units': units, 'last_updated': last_updated})
        if units < 5:
            low_stock_alerts.append(btype)

    # User stats
    total_donors = User.objects.filter(role='DONOR').count()
    total_patients = User.objects.filter(role='PATIENT').count()
    total_admins = User.objects.filter(role='ADMIN').count()

    # Pending donations (appointments)
    pending_donations = DonationAppointment.objects.filter(status='PENDING').count()
    # (Optional) Add pending blood requests if you have such a model

    context = {
        'blood_stock': blood_stock,
        'total_donors': total_donors,
        'total_patients': total_patients,
        'total_admins': total_admins,
        'pending_donations': pending_donations,
        'low_stock_alerts': low_stock_alerts,
    }
    return render(request, 'account/admin_dashboard.html', context)

@login_required
def admin_users(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import User, UserProfile, DonationAppointment
    from django.db.models import Q

    # Filters
    role = request.GET.get('role', '')
    blood_group = request.GET.get('blood_group', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')

    users = User.objects.all().select_related('userprofile').order_by('-date_joined')
    if role:
        users = users.filter(role=role)
    if blood_group:
        users = users.filter(userprofile__blood_group=blood_group)
    if status:
        users = users.filter(is_active=(status == 'active'))
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_number__icontains=search)
        )

    # Pagination
    paginator = Paginator(users, 10)  # Show 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Count badges
    total_donors = User.objects.filter(role='DONOR').count()
    total_patients = User.objects.filter(role='PATIENT').count()
    total_admins = User.objects.filter(role='ADMIN').count()

    context = {
        'users': page_obj,
        'role': role,
        'blood_group': blood_group,
        'status': status,
        'search': search,
        'total_donors': total_donors,
        'total_patients': total_patients,
        'total_admins': total_admins,
        'blood_groups': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    }
    return render(request, 'account/admin_user_management.html', context)

@login_required
def admin_user_detail(request, user_id):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import User, UserProfile, DonationAppointment
    user_obj = User.objects.get(id=user_id)
    user_profile = getattr(user_obj, 'userprofile', None)
    donation_history = DonationAppointment.objects.filter(donor=user_obj).order_by('-date')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'activate':
            user_obj.is_active = True
            user_obj.save()
        elif action == 'deactivate':
            user_obj.is_active = False
            user_obj.save()
        elif action == 'delete':
            user_obj.delete()
            return redirect('admin_users')
        # Add more actions as needed
    context = {
        'user_obj': user_obj,
        'user_profile': user_profile,
        'donation_history': donation_history,
    }
    return render(request, 'account/admin_user_detail.html', context)

@login_required
def admin_donation_blood_request(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    tab = request.GET.get('tab', 'donation')
    status_filter = request.GET.get('status', '')
    history = request.GET.get('history', '0') == '1'

    # Donation Requests
    donation_requests = DonationAppointment.objects.select_related('donor', 'center').all().order_by('-date')  # Added ordering by date
    if not history:
        if status_filter:
            donation_requests = donation_requests.filter(status=status_filter)
        else:
            donation_requests = donation_requests.filter(status='PENDING')
    else:
        donation_requests = donation_requests.exclude(status='PENDING')

    # Blood Requests
    blood_requests = BloodRequest.objects.select_related('patient').all().order_by('-request_date')  # Added ordering by request_date
    if not history:
        if status_filter:
            blood_requests = blood_requests.filter(status=status_filter)
        else:
            blood_requests = blood_requests.filter(status='PENDING')
    else:
        blood_requests = blood_requests.exclude(status='PENDING')

    # Pagination
    donation_page = Paginator(donation_requests, 10).get_page(request.GET.get('donation_page'))
    blood_page = Paginator(blood_requests, 10).get_page(request.GET.get('blood_page'))
    context = {
        'tab': tab,
        'status_filter': status_filter,
        'donation_requests': donation_page,
        'blood_requests': blood_page,
        'history': history,
    }
    return render(request, 'account/admin_donation_blood_request.html', context)

@login_required
def add_donation_center(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    if request.method == 'POST':
        form = DonationCenterForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Donation center added successfully.'})
            messages.success(request, 'Donation center added successfully!')
            return redirect('admin_dashboard')
    else:
        form = DonationCenterForm()
    return render(request, 'account/add_donation_center_form.html', {'form': form})

@login_required
def approve_donation(request, pk):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import DonationAppointment, Notification, BloodStock
    appt = DonationAppointment.objects.get(pk=pk)
    appt.status = 'CONFIRMED'
    appt.save()
    # Update blood stock
    blood_group = appt.donor.userprofile.blood_group if hasattr(appt.donor, 'userprofile') else None
    if blood_group:
        stock, created = BloodStock.objects.get_or_create(type=blood_group)
        stock.units += 1  # Minimum donation amount
        stock.save()
    Notification.objects.create(
        user=appt.donor,
        title='Donation Approved',
        message=f'Your donation scheduled for {appt.date} at {appt.center.name} has been approved.',
        type='donation'
    )

    # --- Generate Certificate PDF ---
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width/2, height-100, "Certificate of Appreciation")
    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height-150, f"This is to certify that")
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-180, f"{appt.donor.get_full_name()}")
    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height-210, f"donated blood on {appt.date} at {appt.center.name}.")
    p.drawCentredString(width/2, height-240, "Thank you for your valuable contribution!")
    p.setFont("Helvetica-Oblique", 12)
    p.drawCentredString(width/2, height-270, "Blood Bank Management System")
    p.showPage()
    p.save()
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    # --- Send Email with Certificate ---
    subject = "Your Blood Donation Certificate"
    message = (
        f"Dear {appt.donor.get_full_name()},\n\n"
        f"Thank you for your blood donation on {appt.date} at {appt.center.name}.\n"
        f"Please find your certificate of appreciation attached.\n\n"
        f"Best regards,\nBlood Bank Team"
    )
    email = EmailMessage(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [appt.donor.email],
    )
    email.attach('Donation_Certificate.pdf', pdf_data, 'application/pdf')
    email.send(fail_silently=True)

    return redirect('admin_donation_blood_request')

@login_required
def reject_donation(request, pk):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import DonationAppointment, Notification
    appt = DonationAppointment.objects.get(pk=pk)
    appt.status = 'REJECTED'
    appt.save()
    Notification.objects.create(
        user=appt.donor,
        title='Donation Rejected',
        message=f'Your donation scheduled for {appt.date} at {appt.center.name} has been rejected.',
        type='donation'
    )
    return redirect('admin_donation_blood_request')

@login_required
def approve_blood_request(request, pk):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import BloodRequest, Notification, BloodStock
    req = BloodRequest.objects.get(pk=pk)
    stock = BloodStock.objects.filter(type=req.blood_group).first()

    # Check if there is sufficient stock
    if not stock or stock.units < req.quantity:
        # Auto-reject the request due to insufficient stock
        req.status = 'REJECTED'
        req.save()
        Notification.objects.create(
            user=req.patient,
            title='Blood Request Rejected',
            message=f'Your blood request for {req.blood_group} ({req.quantity} units) was rejected due to insufficient stock. Current stock: {stock.units if stock else 0} units.',
            type='blood_request'
        )
        messages.error(request, f"Blood request for {req.blood_group} ({req.quantity} units) was auto-rejected due to insufficient stock.")
        return redirect('admin_donation_blood_request')

    # Approve and deduct stock
    req.status = 'APPROVED'
    req.save()
    stock.units -= req.quantity
    stock.save()
    Notification.objects.create(
        user=req.patient,
        title='Blood Request Approved',
        message=f'Your blood request for {req.blood_group} ({req.quantity} units) has been approved.',
        type='blood_request'
    )
    messages.success(request, f"Blood request for {req.blood_group} ({req.quantity} units) has been approved.")
    return redirect('admin_donation_blood_request')

@login_required
def reject_blood_request(request, pk):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    from .models import BloodRequest, Notification
    req = BloodRequest.objects.get(pk=pk)
    req.status = 'REJECTED'
    req.save()
    Notification.objects.create(
        user=req.patient,
        title='Blood Request Rejected',
        message=f'Your blood request for {req.blood_group} ({req.quantity} units) has been rejected.',
        type='blood_request'
    )
    return redirect('admin_donation_blood_request')

@login_required
def add_blood_stock(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')
    if request.method == 'POST':
        blood_type = request.POST.get('type')
        units = int(request.POST.get('units', 1))
        from .models import BloodStock
        stock, created = BloodStock.objects.get_or_create(type=blood_type)
        stock.units += units
        stock.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'{units} units added to {blood_type} stock.'})
        messages.success(request, f'{units} units added to {blood_type} stock.')
        return redirect('admin_dashboard')
    return JsonResponse({'success': False, 'message': 'Invalid request.'})

@login_required
def generate_report_pdf(request):
    if request.user.role != 'ADMIN':
        return redirect('admin_login')

    from .models import DonationAppointment, BloodRequest

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "Blood Bank Report")
    y -= 30

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Donations:")
    y -= 20
    p.setFont("Helvetica", 10)
    donations = DonationAppointment.objects.all().order_by('-date')[:20]
    for d in donations:
        donor_name = d.donor.get_full_name() if hasattr(d.donor, 'get_full_name') else str(d.donor)
        center_name = d.center.name if hasattr(d.center, 'name') else str(d.center)
        p.drawString(60, y, f"{donor_name} | {d.date} | {center_name} | {d.status}")
        y -= 15
        if y < 50:
            p.showPage()
            y = height - 50

    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Blood Requests:")
    y -= 20
    p.setFont("Helvetica", 10)
    requests = BloodRequest.objects.all().order_by('-request_date')[:20]
    for r in requests:
        patient_name = r.patient.get_full_name() if hasattr(r.patient, 'get_full_name') else str(r.patient)
        p.drawString(60, y, f"{patient_name} | {r.blood_group} | {r.quantity} | {r.status}")
        y -= 15
        if y < 50:
            p.showPage()
            y = height - 50

    p.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="blood_bank_report.pdf"'})

@login_required
def request_blood(request):
    if request.user.role != 'PATIENT':
        return redirect('dashboard')
    if request.method == 'POST':
        form = BloodRequestForm(request.POST, request.FILES)
        if form.is_valid():
            blood_request = form.save(commit=False)
            blood_request.patient = request.user
            blood_request.status = 'PENDING'
            blood_request.save()
            # Notify all admins
            from .models import User, Notification
            admins = User.objects.filter(role='ADMIN')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title='New Blood Request',
                    message=f'Patient {request.user.get_full_name()} requested {form.cleaned_data["quantity"]} units of {form.cleaned_data["blood_group"]}.',
                    type='blood_request'
                )
            messages.success(request, 'Blood request submitted successfully!')
            return redirect('blood_request_history')
    else:
        form = BloodRequestForm()
    return render(request, 'account/request_blood.html', {'form': form})

@login_required
def blood_request_history(request):
    if request.user.role != 'PATIENT':
        return redirect('dashboard')
    from .models import BloodRequest
    requests = BloodRequest.objects.filter(patient=request.user).order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests = requests.filter(status=status_filter)
    return render(request, 'account/blood_request_history.html', {'requests': requests, 'status_filter': status_filter})

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            user = User.objects.filter(username=username).first()
            if user and user.email:
                otp = generate_otp()
                OTP.objects.create(user=user, otp=otp)
                send_otp_email(user.email, otp)
                request.session['reset_user_id'] = user.id
                messages.success(request, 'OTP sent to your registered email.')
                return redirect('reset_password', user_id=user.id)
            else:
                messages.error(request, 'Invalid username or no email found.')
    else:
        form = ForgotPasswordForm()
    return render(request, 'account/forgot_password.html', {'form': form})

def reset_password(request, user_id):
    user = User.objects.get(id=user_id)
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            otp_obj = OTP.objects.filter(user=user, otp=otp, is_verified=False).first()
            if otp_obj:
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                otp_obj.is_verified = True
                otp_obj.save()
                messages.success(request, 'Password reset successful. Please login.')
                return redirect('login')
            else:
                messages.error(request, 'Invalid OTP.')
    else:
        form = ResetPasswordForm()
    return render(request, 'account/reset_password.html', {'form': form, 'user': user})
