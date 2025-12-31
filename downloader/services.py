"""
Video Downloader Service Module

This module provides the core functionality for downloading videos from various platforms
using yt-dlp library. It supports YouTube, Facebook, TikTok, Instagram, Twitter, and many
other video sharing platforms.
"""

import os
import re
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlparse
from dataclasses import dataclass

import yt_dlp
from django.conf import settings

# Get FFmpeg path from imageio-ffmpeg (bundled with venv)
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = None

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Data class to hold video information."""
    title: str
    url: str
    platform: str
    thumbnail: str
    duration: int
    formats: list
    description: str = ""
    uploader: str = ""
    view_count: int = 0
    like_count: int = 0


@dataclass
class DownloadResult:
    """Data class to hold download result."""
    success: bool
    file_path: str = ""
    file_size: int = 0
    title: str = ""
    error_message: str = ""
    thumbnail: str = ""
    duration: int = 0
    platform: str = ""


class VideoDownloaderError(Exception):
    """Base exception for video downloader errors."""
    pass


class InvalidURLError(VideoDownloaderError):
    """Raised when the URL is invalid or malformed."""
    pass


class UnsupportedPlatformError(VideoDownloaderError):
    """Raised when the platform is not supported."""
    pass


class DownloadFailedError(VideoDownloaderError):
    """Raised when download fails."""
    pass


class VideoDownloader:
    """
    Video Downloader class that handles video extraction and downloading
    from various platforms using yt-dlp.
    """
    
    # Platform detection patterns
    PLATFORM_PATTERNS = {
        'youtube': [
            r'(youtube\.com|youtu\.be)',
            r'youtube\.com/watch',
            r'youtube\.com/shorts',
            r'youtube\.com/embed',
        ],
        'facebook': [
            r'facebook\.com',
            r'fb\.watch',
            r'fb\.com',
        ],
        'tiktok': [
            r'tiktok\.com',
            r'vm\.tiktok\.com',
        ],
        'instagram': [
            r'instagram\.com',
            r'instagr\.am',
        ],
        'twitter': [
            r'twitter\.com',
            r'x\.com',
        ],
        'vimeo': [
            r'vimeo\.com',
        ],
        'dailymotion': [
            r'dailymotion\.com',
            r'dai\.ly',
        ],
        'reddit': [
            r'reddit\.com',
            r'v\.redd\.it',
        ],
        'twitch': [
            r'twitch\.tv',
            r'clips\.twitch\.tv',
        ],
    }
    
    # Quality format mapping - use best video+audio with FFmpeg merging
    QUALITY_FORMATS = {
        'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
        '2160': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]',
        '1440': 'bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1440]+bestaudio/best[height<=1440]',
        '1080': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '720': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]',
        '480': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]',
        '360': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]',
        '240': 'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=240]+bestaudio/best[height<=240]',
        'audio': 'bestaudio[ext=m4a]/bestaudio/best',
    }
    
    def __init__(self, download_dir: Optional[Path] = None):
        """
        Initialize the VideoDownloader.
        
        Args:
            download_dir: Directory to save downloaded videos. Defaults to settings.DOWNLOAD_DIR
        """
        self.download_dir = download_dir or settings.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is properly formatted.
        
        Args:
            url: The URL to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not url:
            return False
            
        try:
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False
    
    def detect_platform(self, url: str) -> str:
        """
        Detect the video platform from the URL.
        
        Args:
            url: The video URL
            
        Returns:
            str: Platform name or 'other' if not recognized
        """
        url_lower = url.lower()
        
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return platform
        
        return 'other'
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Remove invalid characters for Windows/Linux
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(invalid_chars, '_', filename)
        
        # Limit length
        max_length = 200
        if len(sanitized) > max_length:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:max_length - len(ext)] + ext
        
        return sanitized.strip()
    
    def generate_unique_filename(self, title: str, extension: str = 'mp4') -> str:
        """
        Generate a unique filename using title and timestamp.
        
        Args:
            title: Video title
            extension: File extension
            
        Returns:
            str: Unique filename
        """
        timestamp = int(time.time())
        hash_suffix = hashlib.md5(f"{title}{timestamp}".encode()).hexdigest()[:8]
        sanitized_title = self.sanitize_filename(title)
        
        return f"{sanitized_title}_{hash_suffix}.{extension}"
    
    def get_ydl_options(self, quality: str = 'best', output_template: Optional[str] = None) -> Dict[str, Any]:
        """
        Get yt-dlp options based on quality setting.
        
        Args:
            quality: Quality setting (best, 1080, 720, etc.)
            output_template: Custom output template
            
        Returns:
            dict: yt-dlp options
        """
        format_string = self.QUALITY_FORMATS.get(quality, self.QUALITY_FORMATS['best'])
        
        # For audio-only, use different format and extension
        is_audio = quality == 'audio'
        
        options = {
            'format': format_string,
            'outtmpl': output_template or str(self.download_dir / '%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'noplaylist': True,  # Only download single video
            'no_warnings': False,
            'ignoreerrors': False,
            'quiet': False,
            'no_color': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'merge_output_format': 'mp4',  # Merge to mp4
            # HTTP headers to avoid blocks
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
        }
        
        # Add FFmpeg path if available - REQUIRED for merging video+audio
        if FFMPEG_PATH:
            options['ffmpeg_location'] = FFMPEG_PATH
            # Add postprocessors to ensure proper video+audio merging
            if not is_audio:
                options['postprocessors'] = [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }]
            else:
                options['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
        else:
            # Fallback: prefer formats that already have audio combined
            if not is_audio:
                options['format'] = 'best[ext=mp4]/best'
            logger.warning("FFmpeg not found - using fallback format (may have quality limitations)")
        
        return options
    
    def get_video_info(self, url: str) -> VideoInfo:
        """
        Extract video information without downloading.
        
        Args:
            url: Video URL
            
        Returns:
            VideoInfo: Video information object
            
        Raises:
            InvalidURLError: If URL is invalid
            UnsupportedPlatformError: If platform is not supported
            VideoDownloaderError: If extraction fails
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid URL: {url}")
        
        platform = self.detect_platform(url)
        
        options = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    raise VideoDownloaderError("Could not extract video information")
                
                # Extract available formats with quality info
                formats = []
                if 'formats' in info:
                    seen_heights = set()
                    for fmt in info['formats']:
                        height = fmt.get('height')
                        if height and height not in seen_heights:
                            seen_heights.add(height)
                            formats.append({
                                'quality': f"{height}p",
                                'height': height,
                                'ext': fmt.get('ext', 'mp4'),
                                'filesize': fmt.get('filesize') or fmt.get('filesize_approx'),
                            })
                    formats.sort(key=lambda x: x['height'], reverse=True)
                
                return VideoInfo(
                    title=info.get('title', 'Unknown Title'),
                    url=url,
                    platform=platform,
                    thumbnail=info.get('thumbnail', ''),
                    duration=info.get('duration', 0) or 0,
                    formats=formats,
                    description=info.get('description', ''),
                    uploader=info.get('uploader', ''),
                    view_count=info.get('view_count', 0) or 0,
                    like_count=info.get('like_count', 0) or 0,
                )
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if 'Unsupported URL' in error_msg:
                raise UnsupportedPlatformError(f"Unsupported platform or URL: {url}")
            elif 'Video unavailable' in error_msg or 'Private video' in error_msg:
                raise VideoDownloaderError("Video is unavailable or private")
            elif 'age-restricted' in error_msg.lower():
                raise VideoDownloaderError("Video is age-restricted and cannot be downloaded")
            else:
                raise VideoDownloaderError(f"Failed to extract video info: {error_msg}")
        except Exception as e:
            logger.exception(f"Unexpected error extracting video info from {url}")
            raise VideoDownloaderError(f"An unexpected error occurred: {str(e)}")
    
    def download_video(self, url: str, quality: str = 'best', 
                       custom_filename: Optional[str] = None) -> DownloadResult:
        """
        Download video from the given URL.
        
        Args:
            url: Video URL
            quality: Quality setting (best, 1080, 720, etc.)
            custom_filename: Custom filename for the downloaded file
            
        Returns:
            DownloadResult: Download result object
            
        Raises:
            InvalidURLError: If URL is invalid
            DownloadFailedError: If download fails
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid URL: {url}")
        
        platform = self.detect_platform(url)
        is_audio = quality == 'audio'
        extension = 'mp3' if is_audio else 'mp4'
        
        # Progress tracking
        progress_info = {'downloaded_bytes': 0, 'total_bytes': 0}
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                progress_info['downloaded_bytes'] = d.get('downloaded_bytes', 0)
                progress_info['total_bytes'] = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            elif d['status'] == 'finished':
                logger.info(f"Download finished: {d.get('filename', 'unknown')}")
        
        try:
            # First, get video info to generate filename
            info_options = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(info_options) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise DownloadFailedError("Could not extract video information")
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0) or 0
                thumbnail = info.get('thumbnail', '')
            
            # Generate filename
            if custom_filename:
                filename = self.sanitize_filename(custom_filename)
                if not filename.endswith(f'.{extension}'):
                    filename = f"{filename}.{extension}"
            else:
                filename = self.generate_unique_filename(title, extension)
            
            output_path = self.download_dir / filename
            output_template = str(output_path.with_suffix(''))  # yt-dlp adds extension
            
            # Set up download options
            options = self.get_ydl_options(quality, output_template + '.%(ext)s')
            options['progress_hooks'] = [progress_hook]
            
            # Download the video
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
            
            # Find the downloaded file (extension might differ)
            downloaded_file = None
            for ext in [extension, 'mp4', 'mkv', 'webm', 'mp3', 'm4a']:
                potential_file = output_path.with_suffix(f'.{ext}')
                if potential_file.exists():
                    downloaded_file = potential_file
                    break
            
            # Also check for files with the base name
            if not downloaded_file:
                for file in self.download_dir.glob(f"{output_path.stem}*"):
                    if file.is_file():
                        downloaded_file = file
                        break
            
            if not downloaded_file or not downloaded_file.exists():
                raise DownloadFailedError("Download completed but file not found")
            
            file_size = downloaded_file.stat().st_size
            
            logger.info(f"Successfully downloaded: {downloaded_file} ({file_size} bytes)")
            
            return DownloadResult(
                success=True,
                file_path=str(downloaded_file),
                file_size=file_size,
                title=title,
                thumbnail=thumbnail,
                duration=duration,
                platform=platform,
            )
            
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Download error for {url}: {error_msg}")
            
            if 'Unsupported URL' in error_msg:
                raise UnsupportedPlatformError(f"Unsupported platform or URL")
            elif 'Video unavailable' in error_msg:
                raise DownloadFailedError("Video is unavailable or has been removed")
            elif 'Private video' in error_msg:
                raise DownloadFailedError("Video is private and cannot be downloaded")
            elif 'Sign in' in error_msg or 'login' in error_msg.lower():
                raise DownloadFailedError("Video requires authentication to download")
            elif 'age-restricted' in error_msg.lower():
                raise DownloadFailedError("Video is age-restricted")
            else:
                raise DownloadFailedError(f"Download failed: {error_msg}")
                
        except Exception as e:
            logger.exception(f"Unexpected error downloading {url}")
            raise DownloadFailedError(f"An unexpected error occurred: {str(e)}")
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Remove downloaded files older than specified hours.
        
        Args:
            max_age_hours: Maximum age of files in hours
            
        Returns:
            int: Number of files deleted
        """
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for file_path in self.download_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old file: {file_path}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        return deleted_count

    def get_direct_url(self, url: str, quality: str = 'best') -> dict:
        """
        Get direct download URL for the video - streams directly to user.
        Prioritizes formats with both video+audio that can be directly streamed.
        
        Args:
            url: Video URL
            quality: Quality setting (best, 1080, 720, etc.)
            
        Returns:
            dict: Contains direct_url, title, ext, filesize, etc.
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid URL: {url}")
        
        platform = self.detect_platform(url)
        
        # Quality to height mapping
        quality_heights = {
            'best': 9999,
            '2160': 2160,
            '1440': 1440,
            '1080': 1080,
            '720': 720,
            '480': 480,
            '360': 360,
            '240': 240,
        }
        target_height = quality_heights.get(quality, 720)
        
        options = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }
        
        # Add FFmpeg path if available for format selection
        if FFMPEG_PATH:
            options['ffmpeg_location'] = FFMPEG_PATH
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    raise VideoDownloaderError("Could not extract video information")
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0) or 0
                thumbnail = info.get('thumbnail', '')
                
                direct_url = None
                ext = 'mp4'
                filesize = 0
                selected_height = 0
                best_format = None
                
                if 'formats' in info:
                    # First pass: Look for formats with BOTH video and audio (pre-merged)
                    for fmt in reversed(info['formats']):
                        fmt_url = fmt.get('url', '')
                        fmt_ext = fmt.get('ext', '')
                        fmt_protocol = fmt.get('protocol', '')
                        fmt_height = fmt.get('height') or 0
                        fmt_vcodec = fmt.get('vcodec', 'none')
                        fmt_acodec = fmt.get('acodec', 'none')
                        
                        # Skip HLS/DASH streams
                        if not fmt_url:
                            continue
                        if 'm3u8' in fmt_url or fmt_protocol in ['m3u8', 'm3u8_native', 'http_dash_segments']:
                            continue
                        
                        # Must have BOTH video and audio
                        if fmt_vcodec == 'none' or fmt_acodec == 'none':
                            continue
                        
                        # Prefer mp4
                        if fmt_ext not in ['mp4', 'webm', 'mov', '3gp']:
                            continue
                        
                        # Check quality match
                        if fmt_height <= target_height or target_height == 9999:
                            if best_format is None or fmt_height > selected_height:
                                best_format = fmt
                                selected_height = fmt_height
                    
                    # Second pass: If no pre-merged format, look for any direct video
                    if best_format is None:
                        for fmt in reversed(info['formats']):
                            fmt_url = fmt.get('url', '')
                            fmt_protocol = fmt.get('protocol', '')
                            fmt_ext = fmt.get('ext', '')
                            
                            if not fmt_url:
                                continue
                            if 'm3u8' in fmt_url or fmt_protocol in ['m3u8', 'm3u8_native', 'http_dash_segments']:
                                continue
                            if fmt_ext not in ['mp4', 'webm', 'mov', '3gp', 'mkv']:
                                continue
                            
                            best_format = fmt
                            break
                    
                    if best_format:
                        direct_url = best_format.get('url')
                        ext = best_format.get('ext', 'mp4')
                        filesize = best_format.get('filesize') or best_format.get('filesize_approx') or 0
                
                # Fallback to main URL
                if not direct_url:
                    direct_url = info.get('url')
                    ext = info.get('ext', 'mp4')
                    filesize = info.get('filesize') or info.get('filesize_approx') or 0
                
                if not direct_url:
                    raise DownloadFailedError("No downloadable format found. Try a lower quality or different video.")
                if 'm3u8' in direct_url.lower():
                    raise DownloadFailedError("This video uses HLS streaming and requires FFmpeg to download. Please install FFmpeg for full functionality.")
                
                # Sanitize filename
                safe_title = self.sanitize_filename(title)
                
                return {
                    'direct_url': direct_url,
                    'title': title,
                    'safe_title': safe_title,
                    'ext': ext,
                    'filesize': filesize,
                    'duration': duration,
                    'thumbnail': thumbnail,
                    'platform': platform,
                }
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Error getting direct URL for {url}: {error_msg}")
            
            if 'Unsupported URL' in error_msg:
                raise UnsupportedPlatformError(f"Unsupported platform or URL")
            elif 'Video unavailable' in error_msg:
                raise DownloadFailedError("Video is unavailable or has been removed")
            elif 'Private video' in error_msg:
                raise DownloadFailedError("Video is private and cannot be downloaded")
            else:
                raise DownloadFailedError(f"Failed to get download URL: {error_msg}")
                
        except Exception as e:
            logger.exception(f"Unexpected error getting direct URL from {url}")
            raise DownloadFailedError(f"An unexpected error occurred: {str(e)}")

    def get_direct_url_with_audio(self, url: str, quality: str = 'best') -> dict:
        """
        Get direct download URL for a format that has BOTH video and audio.
        Only returns formats that can be streamed directly with audio.
        Returns None if no suitable format found (caller should use FFmpeg fallback).
        
        Args:
            url: Video URL
            quality: Quality setting (best, 1080, 720, etc.)
            
        Returns:
            dict: Contains direct_url, title, ext, filesize, has_audio flag, etc.
                  Returns None if no pre-merged format available
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid URL: {url}")
        
        platform = self.detect_platform(url)
        
        # Quality to height mapping
        quality_heights = {
            'best': 9999,
            '2160': 2160,
            '1440': 1440,
            '1080': 1080,
            '720': 720,
            '480': 480,
            '360': 360,
            '240': 240,
        }
        target_height = quality_heights.get(quality, 720)
        
        options = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    return None
                
                title = info.get('title', 'video')
                duration = info.get('duration', 0) or 0
                thumbnail = info.get('thumbnail', '')
                
                best_format = None
                selected_height = 0
                
                if 'formats' in info:
                    # ONLY look for formats with BOTH video AND audio (pre-merged)
                    for fmt in info['formats']:
                        fmt_url = fmt.get('url', '')
                        fmt_ext = fmt.get('ext', '')
                        fmt_protocol = fmt.get('protocol', '')
                        fmt_height = fmt.get('height') or 0
                        fmt_vcodec = fmt.get('vcodec', 'none')
                        fmt_acodec = fmt.get('acodec', 'none')
                        
                        # Skip if no URL
                        if not fmt_url:
                            continue
                        
                        # Skip HLS/DASH streams (need FFmpeg)
                        if 'm3u8' in fmt_url or fmt_protocol in ['m3u8', 'm3u8_native', 'http_dash_segments']:
                            continue
                        
                        # MUST have BOTH video AND audio
                        if fmt_vcodec == 'none' or fmt_acodec == 'none':
                            continue
                        
                        # Prefer common formats
                        if fmt_ext not in ['mp4', 'webm', 'mov', '3gp']:
                            continue
                        
                        # Check quality - find best match at or below target
                        if fmt_height <= target_height or target_height == 9999:
                            # Prefer higher quality within the limit
                            if best_format is None or fmt_height > selected_height:
                                best_format = fmt
                                selected_height = fmt_height
                
                # Return None if no pre-merged format found
                if best_format is None:
                    logger.info(f"No pre-merged format found for {url} at quality {quality}")
                    return None
                
                direct_url = best_format.get('url')
                ext = best_format.get('ext', 'mp4')
                filesize = best_format.get('filesize') or best_format.get('filesize_approx') or 0
                
                # Validate URL is usable
                if not direct_url or 'm3u8' in direct_url.lower():
                    return None
                
                safe_title = self.sanitize_filename(title)
                
                logger.info(f"Found pre-merged format: {selected_height}p {ext} for {url}")
                
                return {
                    'direct_url': direct_url,
                    'title': title,
                    'safe_title': safe_title,
                    'ext': ext,
                    'filesize': filesize,
                    'duration': duration,
                    'thumbnail': thumbnail,
                    'platform': platform,
                    'has_audio': True,  # Confirmed this format has audio
                    'height': selected_height,
                }
                
        except Exception as e:
            logger.warning(f"Error finding pre-merged format for {url}: {e}")
            return None

    def get_direct_audio_url(self, url: str) -> dict:
        """
        Get direct download URL for audio-only stream.
        Looks for the best quality audio stream that can be directly downloaded.
        
        Args:
            url: Video URL
            
        Returns:
            dict: Contains direct_url, title, ext, filesize, etc.
                  Returns None if no suitable audio format found
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid URL: {url}")
        
        platform = self.detect_platform(url)
        
        options = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    return None
                
                title = info.get('title', 'audio')
                duration = info.get('duration', 0) or 0
                thumbnail = info.get('thumbnail', '')
                
                best_audio = None
                best_bitrate = 0
                
                if 'formats' in info:
                    for fmt in info['formats']:
                        fmt_url = fmt.get('url', '')
                        fmt_ext = fmt.get('ext', '')
                        fmt_protocol = fmt.get('protocol', '')
                        fmt_vcodec = fmt.get('vcodec', 'none')
                        fmt_acodec = fmt.get('acodec', 'none')
                        fmt_abr = fmt.get('abr') or fmt.get('tbr') or 0  # Audio bitrate
                        
                        # Skip if no URL
                        if not fmt_url:
                            continue
                        
                        # Skip HLS/DASH streams
                        if 'm3u8' in fmt_url or fmt_protocol in ['m3u8', 'm3u8_native', 'http_dash_segments']:
                            continue
                        
                        # Must be audio-only (no video) or have audio codec
                        if fmt_acodec == 'none':
                            continue
                        
                        # Prefer audio-only formats
                        is_audio_only = fmt_vcodec == 'none'
                        
                        # Prefer common audio formats
                        if fmt_ext not in ['m4a', 'mp3', 'webm', 'ogg', 'opus', 'aac']:
                            if not is_audio_only:
                                continue
                        
                        # Select best quality audio
                        if is_audio_only:
                            if best_audio is None or fmt_abr > best_bitrate:
                                best_audio = fmt
                                best_bitrate = fmt_abr
                
                if best_audio is None:
                    logger.info(f"No direct audio format found for {url}")
                    return None
                
                direct_url = best_audio.get('url')
                ext = best_audio.get('ext', 'm4a')
                
                # Normalize extension for user-friendly display
                if ext in ['webm', 'opus', 'ogg']:
                    ext = 'webm'  # Keep as webm, most players support it
                elif ext not in ['mp3']:
                    ext = 'm4a'  # Default to m4a
                
                filesize = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0
                
                if not direct_url or 'm3u8' in direct_url.lower():
                    return None
                
                safe_title = self.sanitize_filename(title)
                
                logger.info(f"Found direct audio format: {ext} {best_bitrate}kbps for {url}")
                
                return {
                    'direct_url': direct_url,
                    'title': title,
                    'safe_title': safe_title,
                    'ext': ext,
                    'filesize': filesize,
                    'duration': duration,
                    'thumbnail': thumbnail,
                    'platform': platform,
                    'bitrate': best_bitrate,
                }
                
        except Exception as e:
            logger.warning(f"Error finding direct audio format for {url}: {e}")
            return None


# Singleton instance for convenience
_downloader_instance: Optional[VideoDownloader] = None


def get_downloader() -> VideoDownloader:
    """Get or create the singleton VideoDownloader instance."""
    global _downloader_instance
    if _downloader_instance is None:
        _downloader_instance = VideoDownloader()
    return _downloader_instance

