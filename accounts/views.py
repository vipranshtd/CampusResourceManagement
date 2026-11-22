
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
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

                Profile.objects.create(
                    user=user,
                    role='STUDENT',
                    enrollment_number=form.cleaned_data['enrollment_number']
                )

            messages.success(
                request,
                "Registration successful. Please log in."
            )
            return redirect('login')

    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={'role': 'STUDENT'}
    )

    context = {
        'profile': profile,
        'user_role': profile.role,
        'role_display': profile.get_role_display(),
        'is_student': profile.role == 'STUDENT',
        'is_faculty': profile.role == 'FACULTY',
        'is_staff_member': profile.role == 'STAFF',
        'is_admin_role': profile.role == 'ADMIN' or request.user.is_superuser,
        'can_manage': (
            profile.role in ['STAFF', 'ADMIN']
            or request.user.is_superuser
        ),
    }

    return render(request, 'accounts/dashboard.html', context)


@require_POST
@login_required
def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')
