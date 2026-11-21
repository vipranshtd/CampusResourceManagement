from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from .models import Resource
from .forms import ResourceForm

def can_manage_resources(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )

@login_required
@user_passes_test(can_manage_resources)
def resource_list(request):
    resources = Resource.objects.select_related(
        'category', 'location'
    ).all()

    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')

    if query:
        resources = resources.filter(
            Q(name__icontains=query) |
            Q(asset_tag__icontains=query)
        )

    if category:
        resources = resources.filter(category_id=category)

    if status:
        resources = resources.filter(status=status)

    from .models import Category

    return render(request, 'resources/resource_list.html', {
        'resources': resources,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category,
        'selected_status': status
    })


@login_required
@user_passes_test(can_manage_resources)
def resource_create(request):
    form = ResourceForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('resource_list')

    return render(request, 'resources/resource_form.html', {
        'form': form,
        'title': 'Add Resource'
    })


@login_required
@user_passes_test(can_manage_resources)
def resource_update(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    form = ResourceForm(request.POST or None, instance=resource)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('resource_list')

    return render(request, 'resources/resource_form.html', {
        'form': form,
        'title': 'Update Resource'
    })


@login_required
@user_passes_test(can_manage_resources)
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)

    if request.method == 'POST':
        resource.delete()
        return redirect('resource_list')

    return render(request, 'resources/resource_confirm_delete.html', {
        'resource': resource
    })