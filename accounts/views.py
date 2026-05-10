import random
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from accounts.models import UserProfile
from accounts.services.profile_service import ProfileService
from accounts.tokens import latest_password_reset_token_generator
from equipment.models import Equipment
from equipment.services.equipment_service import EquipmentService
from lending.models import LendingRequest, Penalty
from lending.services.lending_service import LendingService


profile_service = ProfileService()
equipment_service = EquipmentService()
lending_service = LendingService()

EMAIL_OTP_SESSION_KEY = 'profile_email_otp'
EMAIL_OTP_COOLDOWN_SECONDS = 60
EMAIL_OTP_EXPIRY_MINUTES = 10
PASSWORD_RESET_EXPIRY_MINUTES = 5
PASSWORD_RULE_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')


def _render_login(request, auth_mode='login', next_url=''):
    return render(request, 'accounts/login.html', {
        'auth_mode': auth_mode,
        'next': next_url,
    })


def username_availability(request):
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({
            'available': False,
            'message': 'Please fill in username.',
        })

    is_available = not User.objects.filter(username__iexact=username).exists()
    return JsonResponse({
        'available': is_available,
        'message': 'Username is available.' if is_available else 'Username is already taken.',
    })


def _password_meets_registration_rules(password):
    return bool(PASSWORD_RULE_PATTERN.match(password))


def _get_email_otp_state(request):
    state = request.session.get(EMAIL_OTP_SESSION_KEY)
    if not state:
        return None

    sent_at_value = state.get('sent_at')
    if not sent_at_value:
        return None

    try:
        sent_at = timezone.datetime.fromisoformat(sent_at_value)
    except ValueError:
        request.session.pop(EMAIL_OTP_SESSION_KEY, None)
        return None

    if timezone.is_naive(sent_at):
        sent_at = timezone.make_aware(sent_at, timezone.get_current_timezone())

    state['sent_at_datetime'] = sent_at
    return state


def _email_otp_cooldown_remaining(request):
    state = _get_email_otp_state(request)
    if not state:
        return 0

    elapsed = (timezone.now() - state['sent_at_datetime']).total_seconds()
    return max(0, EMAIL_OTP_COOLDOWN_SECONDS - int(elapsed))


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'Unavailable')


def _send_email_change_otp(request, user, new_email, otp_code):
    display_name = user.get_full_name() or user.username
    requested_at = timezone.localtime(timezone.now()).strftime('%d %b %Y, %I:%M %p')
    context = {
        'display_name': display_name,
        'username': user.username,
        'otp_code': otp_code,
        'new_email': new_email,
        'expiry_minutes': EMAIL_OTP_EXPIRY_MINUTES,
        'requested_at': requested_at,
        'ip_address': _get_client_ip(request),
    }
    subject = f'Your lendr+ Email Verification OTP is {otp_code}'
    message = render_to_string('accounts/emails/email_change_otp.txt', context)
    html_message = render_to_string('accounts/emails/email_change_otp.html', context)
    sent_count = send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [new_email],
        fail_silently=False,
        html_message=html_message,
    )
    if sent_count < 1:
        raise RuntimeError('Email backend did not report a sent OTP email.')


def _send_password_reset_email(request, user):
    profile = profile_service.get_or_create_profile(user)
    profile.reset_password_requested_at = timezone.now()
    profile.save(update_fields=['reset_password_requested_at'])

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = latest_password_reset_token_generator.make_token(user)
    reset_url = request.build_absolute_uri(
        f'/reset-password/{uid}/{token}/'
    )
    context = {
        'display_name': user.get_full_name() or user.username,
        'username': user.username,
        'reset_url': reset_url,
        'expiry_minutes': PASSWORD_RESET_EXPIRY_MINUTES,
        'requested_at': timezone.localtime(timezone.now()).strftime('%d %b %Y, %I:%M %p'),
        'ip_address': _get_client_ip(request),
    }
    subject = 'Reset Your lendr+ Password'
    message = render_to_string('accounts/emails/password_reset.txt', context)
    html_message = render_to_string('accounts/emails/password_reset.html', context)
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
        html_message=html_message,
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action', 'login')
        next_url = request.POST.get('next') or 'accounts:dashboard'

        if action == 'login':
            identifier = request.POST.get('identifier', '').strip()
            password = request.POST.get('password', '')
            username = identifier
            if '@' in identifier:
                email_user = User.objects.filter(email__iexact=identifier).first()
                username = email_user.username if email_user else identifier

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                profile_service.get_or_create_profile(user)
                return redirect(next_url)
            messages.error(request, 'Invalid username or password.')

        elif action == 'register':
            username = request.POST.get('username', '').strip()
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            password = request.POST.get('password', '')

            if not username or not name or not email or not password:
                messages.error(request, 'Please fill in all registration fields.')
                return _render_login(request, 'register', next_url)

            try:
                validate_email(email)
                validate_password(password)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
                return _render_login(request, 'register', next_url)

            if not _password_meets_registration_rules(password):
                messages.error(request, 'Password must be at least 8 characters and include 1 uppercase letter, 1 lowercase letter, 1 number, and 1 special character.')
                return _render_login(request, 'register', next_url)

            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, 'This username is already taken.')
                return _render_login(request, 'register', next_url)

            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'This email address is already registered.')
                return _render_login(request, 'register', next_url)

            user = User.objects.create_user(username=username, email=email, password=password, first_name=name)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.ROLE_USER
            profile.is_active = True
            profile.save(update_fields=['role', 'is_active'])
            messages.success(request, 'Registration successful. You can now log in.')
            return _render_login(request, 'login', next_url)

        elif action == 'reset':
            email = request.POST.get('email', '').strip().lower()
            if not email:
                messages.error(request, 'Please enter your email address.')
                return _render_login(request, 'forgot', next_url)

            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, 'Please enter a valid email address.')
                return _render_login(request, 'forgot', next_url)

            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                try:
                    _send_password_reset_email(request, user)
                except Exception:
                    messages.error(request, 'Unable to send reset email. Please check the email settings and try again.')
                    return _render_login(request, 'forgot', next_url)
            messages.success(request, 'If the email exists, a reset link has been sent.')
            return _render_login(request, 'login', next_url)

    return _render_login(request, 'login', request.GET.get('next', ''))


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_is_valid = user is not None and latest_password_reset_token_generator.check_token(user, token)
    if not token_is_valid:
        messages.error(request, 'Password reset link is invalid or has expired.')
        return redirect('accounts:login')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not new_password or not confirm_password:
            messages.error(request, 'Please fill in all password fields.')
            return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})

        if new_password != confirm_password:
            messages.error(request, 'New password and confirm password do not match.')
            return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})

        try:
            validate_password(new_password, user)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})

        user.set_password(new_password)
        user.save()
        messages.success(request, 'Password reset successfully. You can now log in.')
        return redirect('accounts:login')

    return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def dashboard(request):
    profile = profile_service.get_or_create_profile(request.user)
    if profile_service.is_admin(request.user):
        active_equipment = equipment_service.list_active_equipment()
        total_equipment = active_equipment.count()
        available_equipment = equipment_service.list_available_equipment().count()
        pending_requests = lending_service.list_pending_requests().count()
        overdue_requests = lending_service.list_overdue_requests().count()
        request_total = LendingRequest.objects.count()
        penalty_total = Penalty.objects.count()
        unpaid_penalty_total = Penalty.objects.filter(status=Penalty.STATUS_UNPAID).aggregate(total=Sum('amount'))['total'] or 0

        equipment_status_counts = []
        for status, label in Equipment.STATUS_CHOICES:
            count = active_equipment.filter(status=status).count()
            equipment_status_counts.append({
                'status': status,
                'label': label,
                'total': count,
                'percent': int((count / total_equipment) * 100) if total_equipment else 0,
            })

        request_status_counts = []
        for status, label in LendingRequest.STATUS_CHOICES:
            count = LendingRequest.objects.filter(status=status).count()
            request_status_counts.append({
                'status': status,
                'label': label,
                'total': count,
                'percent': int((count / request_total) * 100) if request_total else 0,
            })

        penalty_status_counts = []
        for status, label in Penalty.STATUS_CHOICES:
            count = Penalty.objects.filter(status=status).count()
            penalty_status_counts.append({
                'status': status,
                'label': label,
                'total': count,
                'percent': int((count / penalty_total) * 100) if penalty_total else 0,
            })

        context = {
            'total_equipment': total_equipment,
            'available_equipment': available_equipment,
            'pending_requests': pending_requests,
            'overdue_requests': overdue_requests,
            'request_total': request_total,
            'penalty_total': penalty_total,
            'unpaid_penalty_total': unpaid_penalty_total,
            'availability_percent': int((available_equipment / total_equipment) * 100) if total_equipment else 0,
            'equipment_status_counts': equipment_status_counts,
            'request_status_counts': request_status_counts,
            'penalty_status_counts': penalty_status_counts,
            'recent_requests': lending_service.list_all_requests()[:6],
        }
        return render(request, 'accounts/admin_dashboard.html', context)

    active_equipment = equipment_service.list_active_equipment()
    total_equipment = active_equipment.count()
    available_equipment = equipment_service.list_available_equipment().count()
    user_requests = lending_service.list_user_requests(request.user)
    penalty_queryset = lending_service.list_penalties_for_user(request.user)
    request_total = user_requests.count()
    penalty_total = penalty_queryset.count()
    unpaid_penalty_total = penalty_queryset.filter(status=Penalty.STATUS_UNPAID).aggregate(total=Sum('amount'))['total'] or 0

    request_status_counts = []
    for status, label in LendingRequest.STATUS_CHOICES:
        count = user_requests.filter(status=status).count()
        request_status_counts.append({
            'status': status,
            'label': label,
            'total': count,
            'percent': int((count / request_total) * 100) if request_total else 0,
        })

    context = {
        'profile': profile,
        'total_equipment': total_equipment,
        'available_equipment': available_equipment,
        'availability_percent': int((available_equipment / total_equipment) * 100) if total_equipment else 0,
        'active_requests': user_requests.exclude(status__in=[
            LendingRequest.STATUS_RETURNED,
            LendingRequest.STATUS_DENIED,
        ]).count(),
        'pending_requests': user_requests.filter(status=LendingRequest.STATUS_PENDING).count(),
        'borrowed_requests': user_requests.filter(status=LendingRequest.STATUS_BORROWED).count(),
        'overdue_requests': user_requests.filter(status=LendingRequest.STATUS_OVERDUE).count(),
        'request_total': request_total,
        'penalty_total': penalty_total,
        'unpaid_penalty_total': unpaid_penalty_total,
        'request_status_counts': request_status_counts,
        'penalties': penalty_queryset,
        'recent_requests': user_requests[:5],
    }
    return render(request, 'accounts/user_dashboard.html', context)


@login_required
def profile_view(request):
    profile = profile_service.get_or_create_profile(request.user)
    if request.method == 'POST':
        user = request.user
        action = request.POST.get('action')

        if action == 'name':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Name cannot be empty.')
                return redirect('accounts:profile')

            user.first_name = name
            user.last_name = ''
            user.save(update_fields=['first_name', 'last_name'])
            messages.success(request, 'Name updated successfully.')
        elif action == 'email_request_otp':
            new_email = request.POST.get('email', '').strip().lower()
            if not new_email:
                messages.error(request, 'Please enter a new email address.')
                return redirect('accounts:profile')

            try:
                validate_email(new_email)
            except ValidationError:
                messages.error(request, 'Please enter a valid email address.')
                return redirect('accounts:profile')

            if new_email == (user.email or '').lower():
                messages.error(request, 'New email must be different from your current email.')
                return redirect('accounts:profile')

            if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                messages.error(request, 'This email address is already linked to another account.')
                return redirect('accounts:profile')

            cooldown_remaining = _email_otp_cooldown_remaining(request)
            if cooldown_remaining > 0:
                messages.error(request, f'Please wait {cooldown_remaining} seconds before requesting a new OTP.')
                return redirect('accounts:profile')

            otp_code = f'{random.SystemRandom().randint(0, 999999):06d}'
            try:
                _send_email_change_otp(request, user, new_email, otp_code)
            except Exception:
                messages.error(request, 'Unable to send OTP email. Please check the email settings and try again.')
                return redirect('accounts:profile')

            request.session[EMAIL_OTP_SESSION_KEY] = {
                'email': new_email,
                'code': otp_code,
                'sent_at': timezone.now().isoformat(),
            }
            request.session.modified = True
            messages.success(request, f'OTP sent to {new_email}.')
        elif action == 'email_verify_otp':
            state = _get_email_otp_state(request)
            otp_code = request.POST.get('otp_code', '').strip()

            if not state:
                messages.error(request, 'Please request an OTP before updating your email.')
                return redirect('accounts:profile')

            if timezone.now() - state['sent_at_datetime'] > timedelta(minutes=EMAIL_OTP_EXPIRY_MINUTES):
                request.session.pop(EMAIL_OTP_SESSION_KEY, None)
                messages.error(request, 'OTP expired. Please request a new code.')
                return redirect('accounts:profile')

            if otp_code != state.get('code'):
                messages.error(request, 'Invalid OTP code. Email was not changed.')
                return redirect('accounts:profile')

            user.email = state['email']
            user.save(update_fields=['email'])
            request.session.pop(EMAIL_OTP_SESSION_KEY, None)
            logout(request)
            messages.success(request, 'Email updated successfully. Please log in again.')
            return redirect('accounts:login')
        elif action == 'password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not current_password or not new_password or not confirm_password:
                messages.error(request, 'Please fill in all password fields.')
                return redirect('accounts:profile')

            if not user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('accounts:profile')

            if current_password == new_password:
                messages.error(request, 'New password must be different from your current password.')
                return redirect('accounts:profile')

            if new_password != confirm_password:
                messages.error(request, 'New password and confirm password do not match.')
                return redirect('accounts:profile')

            try:
                validate_password(new_password, user)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
                return redirect('accounts:profile')

            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated successfully.')
        else:
            messages.error(request, 'No profile action selected.')
        return redirect('accounts:profile')

    email_otp_state = _get_email_otp_state(request)
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'display_name': request.user.get_full_name() or request.user.first_name,
        'email_otp_pending': bool(email_otp_state),
        'email_otp_target': email_otp_state.get('email', '') if email_otp_state else '',
        'email_otp_cooldown_remaining': _email_otp_cooldown_remaining(request),
    })

# Create your views here.
