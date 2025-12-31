import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.conf import settings

from .forms import VideoDownloadForm
from .services import (
    get_downloader,
    VideoDownloaderError,
    InvalidURLError,
    UnsupportedPlatformError,
    DownloadFailedError,
)
from .models import DownloadHistory

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def home(request):
    """Render the home page with the download form."""
    form = VideoDownloadForm()
    context = {
        'form': form,
        'supported_platforms': settings.SUPPORTED_PLATFORMS,
        'quality_options': settings.QUALITY_OPTIONS,
    }
    return render(request, 'downloader/home.html', context)


@csrf_protect
@require_http_methods(["POST"])
def get_video_info(request):
    """
    API endpoint to fetch video information without downloading.
    Returns video title, thumbnail, duration, and available formats.
    """
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        
        if not url:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a video URL.'
            }, status=400)
        
        downloader = get_downloader()
        video_info = downloader.get_video_info(url)
        
        return JsonResponse({
            'success': True,
            'data': {
                'title': video_info.title,
                'platform': video_info.platform,
                'thumbnail': video_info.thumbnail,
                'duration': video_info.duration,
                'duration_formatted': format_duration(video_info.duration),
                'formats': video_info.formats,
                'uploader': video_info.uploader,
                'view_count': video_info.view_count,
            }
        })
        
    except InvalidURLError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid URL. Please enter a valid video link.'
        }, status=400)
        
    except UnsupportedPlatformError:
        return JsonResponse({
            'success': False,
            'error': 'This platform is not supported or the URL is invalid.'
        }, status=400)
        
    except VideoDownloaderError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format.'
        }, status=400)
        
    except Exception as e:
        logger.exception("Unexpected error in get_video_info")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)


@csrf_protect
@require_http_methods(["POST"])
def download_video(request):
    """
    API endpoint to get video download.
    Strategy:
    1. For audio-only: try direct audio stream, fallback to FFmpeg extraction
    2. For video: try pre-merged format (has both video+audio), fallback to FFmpeg download
    """
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        quality = data.get('quality', 'best')
        
        if not url:
            return JsonResponse({
                'success': False,
                'error': 'Please provide a video URL.'
            }, status=400)
        
        # Validate quality option
        valid_qualities = [q[0] for q in settings.QUALITY_OPTIONS]
        if quality not in valid_qualities:
            quality = 'best'
        
        downloader = get_downloader()
        is_audio_only = quality == 'audio'
        
        # AUDIO-ONLY: Try direct audio stream first
        if is_audio_only:
            try:
                audio_info = downloader.get_direct_audio_url(url)
                
                if audio_info and audio_info.get('direct_url'):
                    # Found direct audio stream - instant!
                    download_record = DownloadHistory.objects.create(
                        original_url=url,
                        platform=audio_info['platform'],
                        quality='audio',
                        status='completed',
                        title=f"{audio_info['safe_title']}|{audio_info['ext']}",
                        file_size=audio_info['filesize'],
                        duration=audio_info['duration'],
                        thumbnail_url=audio_info['thumbnail'],
                        ip_address=get_client_ip(request),
                        user_agent='DIRECT_STREAM',
                        file_path=audio_info['direct_url'],
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'data': {
                            'download_id': str(download_record.id),
                            'title': audio_info['title'],
                            'file_size': audio_info['filesize'],
                            'file_size_formatted': format_file_size(audio_info['filesize']),
                            'duration': audio_info['duration'],
                            'duration_formatted': format_duration(audio_info['duration']),
                            'platform': audio_info['platform'],
                            'thumbnail': audio_info['thumbnail'],
                            'ext': audio_info['ext'],
                            'mode': 'direct',
                        }
                    })
            except Exception as e:
                logger.warning(f"Direct audio streaming not available: {e}")
            
            # Fallback: Extract audio with FFmpeg
            result = downloader.download_video(url, 'audio')
            
            if not result.success:
                raise DownloadFailedError(result.error_message or "Audio extraction failed")
            
            download_record = DownloadHistory.objects.create(
                original_url=url,
                platform=result.platform,
                quality='audio',
                status='completed',
                title=result.title,
                file_size=result.file_size,
                duration=result.duration,
                thumbnail_url=result.thumbnail,
                ip_address=get_client_ip(request),
                user_agent='FFMPEG_MERGED',
                file_path=result.file_path,
            )
            
            return JsonResponse({
                'success': True,
                'data': {
                    'download_id': str(download_record.id),
                    'title': result.title,
                    'file_size': result.file_size,
                    'file_size_formatted': format_file_size(result.file_size),
                    'duration': result.duration,
                    'duration_formatted': format_duration(result.duration),
                    'platform': result.platform,
                    'thumbnail': result.thumbnail,
                    'ext': Path(result.file_path).suffix.lstrip('.') or 'mp3',
                    'mode': 'merged',
                }
            })
        
        # VIDEO: Try to get a pre-merged format (instant streaming with audio)
        try:
            direct_info = downloader.get_direct_url_with_audio(url, quality)
            
            if direct_info and direct_info.get('has_audio'):
                # Found pre-merged format - use direct streaming (fast!)
                download_record = DownloadHistory.objects.create(
                    original_url=url,
                    platform=direct_info['platform'],
                    quality=quality,
                    status='completed',
                    title=f"{direct_info['safe_title']}|{direct_info['ext']}",
                    file_size=direct_info['filesize'],
                    duration=direct_info['duration'],
                    thumbnail_url=direct_info['thumbnail'],
                    ip_address=get_client_ip(request),
                    user_agent='DIRECT_STREAM',  # Marker for direct streaming
                    file_path=direct_info['direct_url'],
                )
                
                return JsonResponse({
                    'success': True,
                    'data': {
                        'download_id': str(download_record.id),
                        'title': direct_info['title'],
                        'file_size': direct_info['filesize'],
                        'file_size_formatted': format_file_size(direct_info['filesize']),
                        'duration': direct_info['duration'],
                        'duration_formatted': format_duration(direct_info['duration']),
                        'platform': direct_info['platform'],
                        'thumbnail': direct_info['thumbnail'],
                        'ext': direct_info['ext'],
                        'mode': 'direct',  # Tell frontend it's instant
                    }
                })
        except Exception as e:
            logger.warning(f"Direct streaming not available: {e}")
        
        # Fallback: Download with FFmpeg merging (slower but ensures audio)
        result = downloader.download_video(url, quality)
        
        if not result.success:
            raise DownloadFailedError(result.error_message or "Download failed")
        
        # Create download history record
        download_record = DownloadHistory.objects.create(
            original_url=url,
            platform=result.platform,
            quality=quality,
            status='completed',
            title=result.title,
            file_size=result.file_size,
            duration=result.duration,
            thumbnail_url=result.thumbnail,
            ip_address=get_client_ip(request),
            user_agent='FFMPEG_MERGED',  # Marker for FFmpeg merged file
            file_path=result.file_path,
        )
        
        return JsonResponse({
            'success': True,
            'data': {
                'download_id': str(download_record.id),
                'title': result.title,
                'file_size': result.file_size,
                'file_size_formatted': format_file_size(result.file_size),
                'duration': result.duration,
                'duration_formatted': format_duration(result.duration),
                'platform': result.platform,
                'thumbnail': result.thumbnail,
                'ext': Path(result.file_path).suffix.lstrip('.') or 'mp4',
                'mode': 'merged',  # Tell frontend it was FFmpeg merged
            }
        })
            
    except InvalidURLError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid URL. Please enter a valid video link.'
        }, status=400)
        
    except UnsupportedPlatformError:
        return JsonResponse({
            'success': False,
            'error': 'This platform is not supported or the URL is invalid.'
        }, status=400)
        
    except DownloadFailedError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
    except VideoDownloaderError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format.'
        }, status=400)
        
    except Exception as e:
        logger.exception("Unexpected error in download_video")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)


@require_http_methods(["GET"])
def serve_download(request, download_id):
    """
    Serve video to user's browser.
    Handles both: direct streaming (from source URL) and file serving (FFmpeg merged).
    """
    import requests
    
    try:
        download_record = DownloadHistory.objects.get(id=download_id)
        
        if download_record.status != 'completed':
            raise Http404("Download not ready")
        
        # Check if this is direct streaming or file serving
        is_direct_stream = download_record.user_agent == 'DIRECT_STREAM'
        
        # Determine content type helper
        content_types = {
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'mkv': 'video/x-matroska',
            'mp3': 'audio/mpeg',
            'm4a': 'audio/mp4',
            'mov': 'video/quicktime',
            '3gp': 'video/3gpp',
        }
        
        if is_direct_stream:
            # DIRECT REDIRECT - send user directly to source URL (instant!)
            from django.http import HttpResponseRedirect
            
            direct_url = download_record.file_path
            
            # Redirect user's browser directly to the source URL
            # This is instant - no server proxying needed
            return HttpResponseRedirect(direct_url)
        
        else:
            # FILE SERVING - serve FFmpeg merged file from disk
            file_path = Path(download_record.file_path)
            
            if not file_path.exists():
                raise Http404("File not found - it may have been cleaned up")
            
            title = download_record.title or 'video'
            ext = file_path.suffix.lstrip('.') or 'mp4'
            filesize = file_path.stat().st_size
            content_type = content_types.get(ext.lower(), 'application/octet-stream')
            
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            
            # Set filename
            safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)[:200].strip()
            filename = f"{safe_title}.{ext}"
            ascii_filename = filename.encode('ascii', 'ignore').decode('ascii') or f'video.{ext}'
            encoded_filename = quote(filename)
            
            response['Content-Disposition'] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            response['Content-Length'] = filesize
            
            return response
        
    except DownloadHistory.DoesNotExist:
        raise Http404("Download not found")
    except Exception as e:
        logger.exception(f"Error serving download {download_id}")
        raise Http404("Error serving video")


@require_http_methods(["GET"])
def check_status(request, download_id):
    """
    Check the status of a download.
    """
    try:
        download_record = DownloadHistory.objects.get(id=download_id)
        
        response_data = {
            'success': True,
            'status': download_record.status,
            'title': download_record.title,
        }
        
        if download_record.status == 'completed':
            response_data['file_size'] = download_record.file_size
            response_data['file_size_formatted'] = format_file_size(download_record.file_size)
            
        elif download_record.status == 'failed':
            response_data['error'] = download_record.error_message
            
        return JsonResponse(response_data)
        
    except DownloadHistory.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Download not found'
        }, status=404)


def format_duration(seconds):
    """Format duration in seconds to human-readable string."""
    if not seconds:
        return 'Unknown'
    
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_file_size(size_bytes):
    """Format file size in bytes to human-readable string."""
    if not size_bytes:
        return 'Unknown'
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

