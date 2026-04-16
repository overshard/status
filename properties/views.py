import csv
import io
import threading
import uuid

import requests
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

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

    properties = request.user.properties.order_by("url")

    q = request.GET.get("q")
    if q:
        properties = properties.filter(url__icontains=q)

    page = request.GET.get("page")
    properties = Paginator(properties, 25)
    properties = properties.get_page(page)

    return render(
        request,
        "properties/properties.html",
        {
            "form": form,
            "title": "Properties",
            "description": "Manage your properties.",
            "q": q,
            "properties": properties,
        },
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
    for status in reversed(property_obj.statuses.order_by("-created_at")[:31]):
        status_response_times.append(
            {"label": status.created_at.isoformat(), "count": status.response_time}
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
    try:
        uptime_pct = round(uptime / total * 100, 2)
    except ZeroDivisionError:
        uptime_pct = 0
    try:
        downtime_pct = round(downtime / total * 100, 2)
    except ZeroDivisionError:
        downtime_pct = 0
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


def _crawl_progress(property_obj):
    """Return the fraction (0-1) of the discovered work that's complete."""
    from crawler.fetcher import PAGE_CAP

    pages = property_obj.last_crawl_pages_count or 0
    if pages <= 0:
        return 0.05  # show *some* movement once we start
    # We don't know the total ahead of time, so use a log-ish ratio capped at
    # ~90% — the last 10% is reserved for post-crawl check processing.
    return min(pages / PAGE_CAP, 0.9)


def _serialize_status(property_obj):
    now = timezone.now()

    crawl_next = property_obj.next_run_at_crawler
    lh_next = property_obj.next_lighthouse_run_at

    insights = property_obj.crawler_insights or []
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for insight in insights:
        sev = insight.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    return {
        "crawler": {
            "state": property_obj.crawl_state,
            "started_at": property_obj.crawl_started_at.isoformat()
            if property_obj.crawl_started_at
            else None,
            "last_attempt_at": property_obj.last_run_at_crawler.isoformat()
            if property_obj.last_run_at_crawler
            else None,
            "last_success_at": property_obj.last_crawl_success_at.isoformat()
            if property_obj.last_crawl_success_at
            else None,
            "last_error": property_obj.last_crawl_error,
            "last_duration_ms": property_obj.last_crawl_duration_ms,
            "pages_count": property_obj.last_crawl_pages_count,
            "next_run_at": crawl_next.isoformat() if crawl_next else None,
            "is_overdue": bool(crawl_next and crawl_next <= now),
            "insights_total": len(insights),
            "insights_by_severity": severity_counts,
            "progress": _crawl_progress(property_obj)
            if property_obj.crawl_state == "running"
            else None,
        },
        "lighthouse": {
            "state": property_obj.lighthouse_state,
            "started_at": property_obj.lighthouse_started_at.isoformat()
            if property_obj.lighthouse_started_at
            else None,
            "last_attempt_at": property_obj.last_lighthouse_run_at.isoformat()
            if property_obj.last_lighthouse_run_at
            else None,
            "last_success_at": property_obj.last_lighthouse_success_at.isoformat()
            if property_obj.last_lighthouse_success_at
            else None,
            "last_error": property_obj.last_lighthouse_error,
            "last_duration_ms": property_obj.last_lighthouse_duration_ms,
            "next_run_at": lh_next.isoformat() if lh_next else None,
            "is_overdue": bool(lh_next and lh_next <= now),
            "scores": property_obj.lighthouse_scores,
        },
        "server_time": now.isoformat(),
    }


def property_status(request, property_id):
    try:
        property_obj = Property.objects.get(pk=property_id)
    except Property.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    if not property_obj.is_public and property_obj.user != request.user:
        return JsonResponse({"error": "forbidden"}, status=403)

    return JsonResponse(_serialize_status(property_obj))


def property_recrawl(request, property_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "forbidden"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    try:
        property_obj = request.user.properties.get(pk=property_id)
    except Property.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    if property_obj.crawl_state in ("queued", "running"):
        return JsonResponse(
            {
                "ok": False,
                "reason": "already_running",
                **_serialize_status(property_obj),
            }
        )

    property_obj.next_run_at_crawler = timezone.now()
    property_obj.save(update_fields=["next_run_at_crawler"])
    return JsonResponse({"ok": True, **_serialize_status(property_obj)})


def property_rerun_lighthouse(request, property_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "forbidden"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    try:
        property_obj = request.user.properties.get(pk=property_id)
    except Property.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    if property_obj.lighthouse_state in ("queued", "running"):
        return JsonResponse(
            {
                "ok": False,
                "reason": "already_running",
                **_serialize_status(property_obj),
            }
        )

    property_obj.next_lighthouse_run_at = timezone.now()
    property_obj.save(update_fields=["next_lighthouse_run_at"])
    return JsonResponse({"ok": True, **_serialize_status(property_obj)})


def import_property(request, url):
    url = url.lower().strip()
    if not url.startswith("http"):
        url = "http://" + url
    try:
        r = requests.get(url)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return
    if not Property.objects.filter(url=r.url).exists():
        property_obj = Property(
            url=r.url,
            user=request.user,
        )
        property_obj.save()


def import_properties(request):
    if not request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        file = request.FILES["csv_file"]
        reader = csv.reader(io.TextIOWrapper(file.file, encoding="utf-8"))
        for row in reader:
            try:
                url = row[0]
                threading.Thread(target=import_property, args=(request, url)).start()
            except IndexError:
                continue
        messages.success(request, "Properties imported successfully.")
        return redirect("properties")

    return redirect("properties")
