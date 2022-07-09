from django.shortcuts import render, redirect
from django.http import HttpResponse

from properties.models import Check, Property
from accounts.models import User


def home(request):
    if request.user.is_authenticated:
        return redirect('properties')

    context = {}
    context['title'] = 'Home'
    context['description'] = 'Made by Isaac Bythewood, simple status for people who want to host their own and hack on it a bit.'

    total_statuses = Check.objects.all().count()
    context['total_statuses'] = total_statuses

    total_properties = Property.objects.all().count()
    context['total_properties'] = total_properties

    total_users = User.objects.all().count()
    context['total_users'] = total_users

    try:
        first_status_created_at = Check.objects.all().order_by('created_at').first().created_at
        context['first_status_created_at'] = first_status_created_at
    except AttributeError:
        context['first_status_created_at'] = None

    return render(request, 'pages/home.html', context)


def changelog(request):
    context = {}
    context['title'] = 'Changelog'
    context['description'] = 'An ongoing changelog and upcoming list of features for Status.'
    return render(request, 'pages/changelog.html', context)


def favicon(request):
    icon = "🚀"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="80" font-size="80">{icon}</text></svg>'
    return HttpResponse(svg, content_type="image/svg+xml")


def robots(request):
    return render(request, 'robots.txt', content_type='text/plain')


def sitemap(request):
    return render(request, 'sitemap.xml', content_type='text/xml')
