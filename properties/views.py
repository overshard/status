import uuid

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from status.chromium import generate_pdf_from_html

from .forms import PropertyForm
from .models import Property


def properties(request):
    if not request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            new_property = form.save(commit=False)
            new_property.user = request.user
            new_property.save()
            messages.success(request, "Property added successfully.")
            return redirect("properties")
    else:
        form = PropertyForm()

    properties = request.user.properties.order_by('-url')
    properties = sorted(properties, key=lambda x: x.current_status)
    properties = reversed(properties)

    return render(
        request,
        "properties/properties.html",
        {"form": form, "title": "Properties", "description": "Manage your properties.", "properties": properties},
    )


def property_delete(request, property_id):
    if not request.user.is_authenticated:
        return redirect("/")

    try:
        property_obj = request.user.properties.get(pk=property_id)
    except Property.DoesNotExist:
        return redirect("properties")

    property_obj.delete()
    messages.success(request, "Property deleted successfully.")
    return redirect("properties")


def adjust_is_public_property(request, property_id):
    """
    Sets the property to public or private
    """
    if not request.user.is_authenticated:
        return redirect("/")

    try:
        property_obj = request.user.properties.get(pk=property_id)
    except Property.DoesNotExist:
        return redirect("properties")

    if request.method == "POST":
        property_obj.is_public = property_obj.is_public is False
        property_obj.save()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False})


def property(request, property_id):
    context = {}

    try:
        property_obj = Property.objects.get(pk=property_id)
        context["property"] = property_obj
    except Property.DoesNotExist:
        return redirect("properties")

    if not property_obj.is_public and property_obj.user != request.user:
        return redirect("properties")

    # Set some basic page context variables
    context["title"] = property_obj.name
    context["description"] = "Status for " + property_obj.name
    context["BASE_URL"] = settings.BASE_URL

    status_response_times = []
    for status in property_obj.statuses.order_by('created_at')[:31]:
        status_response_times.append(
            {"label": status.created_at, "count": status.response_time}
        )
    context["status_response_times_graph"] = status_response_times

    status_codes = property_obj.statuses.values("status_code").annotate(
        count=models.Count("status_code")
    )
    context["status_codes_graph"] = [
        {"label": x["status_code"], "count": x["count"]} for x in status_codes
    ]

    uptime = property_obj.statuses.filter(status_code=200).count()
    downtime = property_obj.statuses.exclude(status_code=200).count()
    total = uptime + downtime
    uptime_pct = round(uptime / total * 100, 2)
    downtime_pct = round(downtime / total * 100, 2)
    context["uptime_graph"] = [
        {"label": "Uptime", "count": uptime_pct},
        {"label": "Downtime", "count": downtime_pct},
    ]

    if request.GET.get("report") == "":
        context["print"] = True
        html = render_to_string("properties/property.html", context)
        filename = f"reports/{uuid.uuid4()}.pdf"
        generate_pdf_from_html(html, filename)
        with open(default_storage.path(filename), "rb") as pdf:
            response = HttpResponse(pdf.read(), content_type="application/pdf")
            response["Content-Disposition"] = "inline; filename=report.pdf"
            return response

    return render(request, "properties/property.html", context)
