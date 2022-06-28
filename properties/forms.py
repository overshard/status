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


class PropertyImportForm(forms.Form):
    csv_file = forms.FileField()

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError('Invalid file type')
        return csv_file
