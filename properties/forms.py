import requests

from django import forms

from .models import Property


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ('url',)

    def clean_url(self):
        url = self.cleaned_data['url']
        if not url.startswith('http'):
            url = 'http://' + url
        try:
            r = requests.get(url)
            r.raise_for_status()
        except requests.exceptions.RequestException:
            raise forms.ValidationError('Invalid URL')
        return r.url  # NOTE: requests' "Final URL location of Response."
