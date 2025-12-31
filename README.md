# AnyDownloader - Universal Video Downloader

A Django-based web application that allows users to download videos from YouTube, Facebook, TikTok, Instagram, Twitter, and 1000+ more video sharing platforms.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Django](https://img.shields.io/badge/Django-6.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- 🎬 **Universal Support**: Download videos from YouTube, Facebook, TikTok, Instagram, Twitter, Vimeo, and 1000+ more platforms
- 🎯 **Quality Selection**: Choose your preferred video quality (4K, 1080p, 720p, 480p, etc.)
- 🎵 **Audio Extraction**: Download audio-only in MP3 format
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile devices
- 🔒 **Secure**: Built with Django's security best practices
- ⚡ **Fast**: High-speed downloads with progress tracking
- 🆓 **Free**: No registration required

## Prerequisites

- Python 3.11 or higher (Python 3.13 recommended)
- FFmpeg (required for video/audio merging and conversion)

### Installing FFmpeg

**Windows:**
```bash
# Using winget
winget install FFmpeg

# Or using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/anydownloader.git
cd anydownloader
```

2. **Create a virtual environment:**
```bash
# Windows
py -3.13 -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3.13 -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run database migrations:**
```bash
python manage.py migrate
```

5. **Create a superuser (optional, for admin access):**
```bash
python manage.py createsuperuser
```

6. **Collect static files:**
```bash
python manage.py collectstatic
```

7. **Run the development server:**
```bash
python manage.py runserver
```

8. **Open your browser and visit:**
```
http://127.0.0.1:8000
```

## Project Structure

```
AnyDownloader/
├── anydownloader/          # Django project settings
│   ├── __init__.py
│   ├── settings.py         # Project settings
│   ├── urls.py             # Main URL configuration
│   ├── asgi.py
│   └── wsgi.py
├── downloader/             # Main application
│   ├── __init__.py
│   ├── admin.py            # Admin configuration
│   ├── apps.py
│   ├── forms.py            # Form definitions
│   ├── models.py           # Database models
│   ├── services.py         # Video download service
│   ├── urls.py             # App URL configuration
│   └── views.py            # View functions
├── templates/              # HTML templates
│   ├── base.html
│   └── downloader/
│       └── home.html
├── static/                 # Static files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── downloads/              # Downloaded videos (auto-created)
├── media/                  # Media files (auto-created)
├── venv/                   # Virtual environment
├── manage.py
├── requirements.txt
└── README.md
```

## Usage

1. **Paste Video URL**: Copy the video URL from any supported platform and paste it into the input field.

2. **Select Quality**: Choose your preferred video quality from the dropdown menu.

3. **Get Info (Optional)**: Click "Get Info" to preview video details before downloading.

4. **Download**: Click "Download" to start the download process.

5. **Save**: Once complete, click "Save Video" to download the file to your device.

## Supported Platforms

AnyDownloader supports 1000+ video platforms including:

- YouTube (videos, shorts, playlists)
- Facebook (videos, reels, stories)
- TikTok
- Instagram (posts, reels, stories)
- Twitter/X
- Vimeo
- Dailymotion
- Reddit
- Twitch (clips, VODs)
- SoundCloud
- And many more...

For a complete list, visit [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Configuration

### Environment Variables

Create a `.env` file in the project root for custom configuration:

```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
MAX_DOWNLOAD_SIZE=2147483648
DOWNLOAD_TIMEOUT=600
```

### Settings

Key settings in `anydownloader/settings.py`:

- `DOWNLOAD_DIR`: Directory for downloaded videos (default: `downloads/`)
- `MAX_DOWNLOAD_SIZE`: Maximum file size in bytes (default: 2GB)
- `DOWNLOAD_TIMEOUT`: Download timeout in seconds (default: 600)
- `QUALITY_OPTIONS`: Available quality options

## Security Considerations

- CSRF protection enabled on all forms
- Input validation and sanitization
- Secure file handling
- No user data collection
- Respects rate limiting

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in settings
2. Set a strong `SECRET_KEY`
3. Configure `ALLOWED_HOSTS`
4. Use a production-grade server (gunicorn + nginx)
5. Enable HTTPS
6. Configure proper logging

Example with Gunicorn:
```bash
gunicorn anydownloader.wsgi:application --bind 0.0.0.0:8000
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Make sure FFmpeg is installed and in your PATH.

2. **Video unavailable**: Some videos may be private, age-restricted, or region-locked.

3. **Download fails**: Try updating yt-dlp: `pip install --upgrade yt-dlp`

4. **Slow downloads**: This depends on your internet connection and the source server.

## Legal Disclaimer

This tool is for personal use only. Please respect copyright laws and terms of service of the platforms you download from. Only download content you have the right to download.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The powerful video downloading library
- [Django](https://www.djangoproject.com/) - The web framework
- [Bootstrap](https://getbootstrap.com/) - CSS framework
