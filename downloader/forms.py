from django import forms
from django.conf import settings


class VideoDownloadForm(forms.Form):
    """Form for video download input."""
    
    url = forms.URLField(
        label='Video URL',
        max_length=2048,
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Paste your video link here...',
            'id': 'video-url',
            'autocomplete': 'off',
            'autofocus': True,
        }),
        error_messages={
            'required': 'Please enter a video URL.',
            'invalid': 'Please enter a valid URL.',
        }
    )
    
    quality = forms.ChoiceField(
        label='Quality',
        choices=settings.QUALITY_OPTIONS,
        initial='1080',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'quality-select',
        })
    )
    
    def clean_url(self):
        """Validate and clean the URL."""
        url = self.cleaned_data.get('url', '').strip()
        
        if not url:
            raise forms.ValidationError('Please enter a video URL.')
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError('URL must start with http:// or https://')
        
        # Check for potentially dangerous URLs
        dangerous_patterns = ['javascript:', 'data:', 'file://']
        for pattern in dangerous_patterns:
            if pattern in url.lower():
                raise forms.ValidationError('Invalid URL format.')
        
        return url
