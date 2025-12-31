/**
 * AnyDownloader - Main JavaScript
 * Handles video information fetching and download functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const downloadForm = document.getElementById('download-form');
    const videoUrlInput = document.getElementById('video-url');
    const qualitySelect = document.getElementById('quality-select');
    const downloadBtn = document.getElementById('download-btn');
    const pasteBtn = document.getElementById('paste-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingText = document.getElementById('loading-text');
    const errorAlert = document.getElementById('error-alert');
    const errorMessage = document.getElementById('error-message');
    const videoInfoSection = document.getElementById('video-info-section');

    // Get CSRF token from the form
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Store current video URL for downloads
    let currentVideoUrl = '';

    /**
     * Show loading state
     */
    function showLoading(message = 'Processing your request...') {
        loadingSpinner.classList.remove('d-none');
        loadingText.textContent = message;
        downloadBtn.disabled = true;
        hideError();
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        loadingSpinner.classList.add('d-none');
        downloadBtn.disabled = false;
    }

    /**
     * Show error message
     */
    function showError(message) {
        errorAlert.classList.remove('d-none');
        errorMessage.textContent = message;
    }

    /**
     * Hide error message
     */
    function hideError() {
        errorAlert.classList.add('d-none');
    }

    /**
     * Format view count
     */
    function formatViewCount(count) {
        if (!count) return 'N/A';
        if (count >= 1000000) {
            return (count / 1000000).toFixed(1) + 'M views';
        } else if (count >= 1000) {
            return (count / 1000).toFixed(1) + 'K views';
        }
        return count + ' views';
    }

    /**
     * Fetch video information and show quality options
     */
    async function fetchVideoInfo(event) {
        event.preventDefault();
        
        const url = videoUrlInput.value.trim();
        
        if (!url) {
            showError('Please enter a video URL.');
            return;
        }

        currentVideoUrl = url;
        showLoading('Fetching video information...');
        hideError();
        videoInfoSection.classList.add('d-none');

        try {
            const response = await fetch('/api/video-info/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (data.success) {
                displayVideoInfo(data.data);
            } else {
                showError(data.error || 'Failed to fetch video information.');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('An error occurred while fetching video information.');
        } finally {
            hideLoading();
        }
    }

    /**
     * Display video information with download buttons
     */
    function displayVideoInfo(info) {
        // Set thumbnail
        const thumbnail = document.getElementById('video-thumbnail');
        if (info.thumbnail) {
            thumbnail.src = info.thumbnail;
            thumbnail.alt = info.title;
        } else {
            thumbnail.src = 'https://via.placeholder.com/320x180?text=No+Thumbnail';
        }

        // Set title
        document.getElementById('video-title').textContent = info.title;

        // Set platform
        const platformBadge = document.getElementById('video-platform');
        platformBadge.querySelector('span').textContent = info.platform.charAt(0).toUpperCase() + info.platform.slice(1);

        // Set duration
        const durationBadge = document.getElementById('video-duration');
        durationBadge.querySelector('span').textContent = info.duration_formatted;
        document.getElementById('video-duration-badge').textContent = info.duration_formatted;

        // Set views
        const viewsBadge = document.getElementById('video-views');
        viewsBadge.querySelector('span').textContent = formatViewCount(info.view_count);

        // Set uploader
        const uploaderEl = document.getElementById('video-uploader');
        if (info.uploader) {
            uploaderEl.textContent = 'By: ' + info.uploader;
        } else {
            uploaderEl.textContent = '';
        }

        // Create download buttons for each quality option
        const formatsList = document.getElementById('formats-list');
        formatsList.innerHTML = '';
        
        // Quality options to show as download buttons
        const qualityOptions = [
            { value: 'best', label: 'Best Quality', icon: 'bi-star-fill', color: 'success' },
            { value: '1080', label: '1080p HD', icon: 'bi-badge-hd-fill', color: 'primary' },
            { value: '720', label: '720p HD', icon: 'bi-badge-hd', color: 'info' },
            { value: '480', label: '480p', icon: 'bi-file-play', color: 'secondary' },
            { value: '360', label: '360p', icon: 'bi-file-play', color: 'secondary' },
            { value: 'audio', label: 'MP3 Audio', icon: 'bi-music-note-beamed', color: 'warning' },
        ];
        
        qualityOptions.forEach(quality => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `btn btn-${quality.color} btn-sm me-2 mb-2 download-quality-btn`;
            btn.innerHTML = `<i class="bi ${quality.icon} me-1"></i><i class="bi bi-download me-1"></i>${quality.label}`;
            btn.dataset.quality = quality.value;
            btn.addEventListener('click', () => startDownload(quality.value, quality.label));
            formatsList.appendChild(btn);
        });

        // Show the info section
        videoInfoSection.classList.remove('d-none');
        
        // Scroll to info section
        videoInfoSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    /**
     * Start download with selected quality
     * Uses direct streaming if pre-merged format available, FFmpeg fallback otherwise
     */
    async function startDownload(quality, qualityLabel) {
        if (!currentVideoUrl) {
            showError('Please enter a video URL first.');
            return;
        }

        // Disable all download buttons and show loading state
        const allBtns = document.querySelectorAll('.download-quality-btn');
        const clickedBtn = document.querySelector(`[data-quality="${quality}"]`);
        
        allBtns.forEach(btn => btn.disabled = true);
        if (clickedBtn) {
            clickedBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Processing...`;
        }

        // Show progress section
        const progressSection = document.getElementById('download-progress-section');
        const progressBar = document.getElementById('download-progress-bar');
        const progressText = document.getElementById('download-progress-text');
        const statusText = document.getElementById('download-status-text');
        
        progressSection.classList.remove('d-none');
        progressBar.style.width = '50%';
        progressText.textContent = 'Processing...';
        statusText.textContent = `Preparing ${qualityLabel}...`;

        try {
            // Request download (server will try direct stream first, fallback to FFmpeg)
            const response = await fetch('/api/download/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    url: currentVideoUrl, 
                    quality: quality 
                })
            });

            const data = await response.json();

            if (data.success) {
                // Start download!
                progressBar.style.width = '100%';
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-success');
                
                // Show mode info
                const mode = data.data.mode || 'direct';
                if (mode === 'direct') {
                    progressText.textContent = 'Download starting!';
                } else {
                    progressText.textContent = 'Download ready!';
                }
                statusText.textContent = `${data.data.title}`;

                // Trigger download using anchor click (most reliable method)
                const downloadUrl = '/api/download-file/' + data.data.download_id + '/';
                
                // Create a temporary link and click it
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // Reset UI quickly
                setTimeout(() => {
                    progressSection.classList.add('d-none');
                    progressBar.style.width = '0%';
                    progressBar.classList.add('progress-bar-animated');
                    progressBar.classList.remove('bg-success');
                    
                    // Restore button text
                    allBtns.forEach(btn => {
                        btn.disabled = false;
                        const q = btn.dataset.quality;
                        const qInfo = [
                            { value: 'best', label: 'Best Quality', icon: 'bi-star-fill' },
                            { value: '1080', label: '1080p HD', icon: 'bi-badge-hd-fill' },
                            { value: '720', label: '720p HD', icon: 'bi-badge-hd' },
                            { value: '480', label: '480p', icon: 'bi-file-play' },
                            { value: '360', label: '360p', icon: 'bi-file-play' },
                            { value: 'audio', label: 'MP3 Audio', icon: 'bi-music-note-beamed' },
                        ].find(x => x.value === q);
                        if (qInfo) {
                            btn.innerHTML = `<i class="bi ${qInfo.icon} me-1"></i><i class="bi bi-download me-1"></i>${qInfo.label}`;
                        }
                    });
                }, 500);

            } else {
                throw new Error(data.error || 'Download failed');
            }
        } catch (error) {
            console.error('Error:', error);
            showError(error.message || 'An error occurred while getting download link.');
            progressSection.classList.add('d-none');
            
            // Restore buttons
            allBtns.forEach(btn => {
                btn.disabled = false;
                const q = btn.dataset.quality;
                const qInfo = [
                    { value: 'best', label: 'Best Quality', icon: 'bi-star-fill' },
                    { value: '1080', label: '1080p HD', icon: 'bi-badge-hd-fill' },
                    { value: '720', label: '720p HD', icon: 'bi-badge-hd' },
                    { value: '480', label: '480p', icon: 'bi-file-play' },
                    { value: '360', label: '360p', icon: 'bi-file-play' },
                    { value: 'audio', label: 'MP3 Audio', icon: 'bi-music-note-beamed' },
                ].find(x => x.value === q);
                if (qInfo) {
                    btn.innerHTML = `<i class="bi ${qInfo.icon} me-1"></i><i class="bi bi-download me-1"></i>${qInfo.label}`;
                }
            });
        }
    }

    /**
     * Paste from clipboard
     */
    async function pasteFromClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                videoUrlInput.value = text;
                videoUrlInput.focus();
            }
        } catch (error) {
            console.error('Failed to read clipboard:', error);
            videoUrlInput.focus();
        }
    }

    // Event Listeners
    downloadForm.addEventListener('submit', fetchVideoInfo);
    pasteBtn.addEventListener('click', pasteFromClipboard);

    // Clear error when user starts typing
    videoUrlInput.addEventListener('input', function() {
        hideError();
    });

    // Auto-focus the URL input
    videoUrlInput.focus();
});