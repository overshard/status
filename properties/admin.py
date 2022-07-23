from django.contrib import admin

from .models import Property, Check


class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "url",
        "user",
        "total_checks",
        "last_run_at",
        "next_run_at",
        "should_check",
    )
    list_filter = ("user__username",)
    search_fields = (
        "url",
        "user__username",
    )
    ordering = ("user",)


admin.site.register(Property, PropertyAdmin)


class CheckAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "status_code",
        "response_time",
        "created_at",
    )
    list_filter = ("property__url", "created_at")


admin.site.register(Check, CheckAdmin)
