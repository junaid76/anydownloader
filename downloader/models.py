from django.db import models
import uuid


class DownloadHistory(models.Model):
    """Model to track download history and statistics."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('facebook', 'Facebook'),
        ('tiktok', 'TikTok'),
        ('instagram', 'Instagram'),
        ('twitter', 'Twitter/X'),
        ('vimeo', 'Vimeo'),
        ('dailymotion', 'Dailymotion'),
        ('reddit', 'Reddit'),
        ('twitch', 'Twitch'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_url = models.URLField(max_length=2048)
    title = models.CharField(max_length=500, blank=True)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES, default='other')
    quality = models.CharField(max_length=20, default='best')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File information
    file_path = models.CharField(max_length=1024, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # in bytes
    duration = models.IntegerField(null=True, blank=True)  # in seconds
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Download History'
        verbose_name_plural = 'Download Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['platform']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title or 'Unknown'} - {self.platform} - {self.status}"
    
    @property
    def file_size_formatted(self):
        """Return human-readable file size."""
        if not self.file_size:
            return 'Unknown'
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    
    @property
    def duration_formatted(self):
        """Return human-readable duration."""
        if not self.duration:
            return 'Unknown'
        
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

