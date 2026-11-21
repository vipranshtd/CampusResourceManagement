from django.shortcuts import render, redirect
from django.contrib.auth import login,logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegistrationForm
from .models import Profile

from django.views.decorators.http import require_POST

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            Profile.objects.create(
                user=user,
                role='STUDENT',
                enrollment_number=form.cleaned_data['enrollment_number']
            )
            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html')

@require_POST
@login_required
def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')