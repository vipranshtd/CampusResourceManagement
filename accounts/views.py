
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction

from .forms import RegistrationForm
from .models import Profile


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                requested_role = form.cleaned_data['requested_role']

                Profile.objects.create(
                    user=user,
                    role=(
                        'STUDENT'
                        if requested_role == 'STUDENT'
                        else 'PENDING'
                    ),
                    requested_role=(
                        ''
                        if requested_role == 'STUDENT'
                        else requested_role
                    ),
                    institutional_id=form.cleaned_data['institutional_id']
                )

            if requested_role == 'STUDENT':
                messages.success(
                    request,
                    "Registration successful. You can now log in."
                )
            else:
                messages.success(
                    request,
                    "Registration submitted successfully! "
                    "Your account will be activated after administrator approval."
                )

            return redirect('login')

    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form
    })



@login_required
def dashboard(request):
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'ADMIN' if request.user.is_superuser else 'STUDENT'
        }
    )

    if request.user.is_superuser:
        effective_role = 'ADMIN'
        role_display = 'Administrator'
    else:
        effective_role = profile.role
        role_display = profile.get_role_display()

    context = {
        'profile': profile,
        'user_role': effective_role,
        'role_display': role_display,

        'is_student': effective_role == 'STUDENT',
        'is_faculty': effective_role == 'FACULTY',
        'is_staff_member': effective_role == 'STAFF',

        'is_admin_role': effective_role == 'ADMIN',

        'can_manage': effective_role in ['STAFF', 'ADMIN'],
    }

    return render(request, 'accounts/dashboard.html', context)


@require_POST
@login_required
def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')
