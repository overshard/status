from django.shortcuts import render
from django.contrib import messages

from .forms import UserForm


def profile(request):
    if request.method == "POST":
        form = UserForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was successfully updated!")
            return render(request, "accounts/profile.html", {"form": form})
    else:
        form = UserForm(instance=request.user)
    return render(
        request,
        "accounts/profile.html",
        {"form": form, "title": "Profile", "description": "Update your profile."},
    )
