from django.contrib import admin
from .models import DownloadHistory


@admin.register(DownloadHistory)
class DownloadHistoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'platform', 'quality', 'status', 'created_at', 'ip_address']
    list_filter = ['platform', 'status', 'quality', 'created_at']
    search_fields = ['title', 'original_url', 'ip_address']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Video Information', {
            'fields': ('title', 'original_url', 'platform', 'thumbnail_url')
        }),
        ('Download Details', {
            'fields': ('quality', 'status', 'file_path', 'file_size', 'duration')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

