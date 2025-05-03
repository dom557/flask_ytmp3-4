from flask import Flask, render_template, request, send_file, Response, jsonify, abort
from yt_dlp import YoutubeDL
from io import BytesIO
import os
import tempfile
import logging
import re
import subprocess
import time
import json
import uuid
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
MAX_DOWNLOAD_SIZE_MB = 500  # Maximum download size in MB
ALLOWED_DOMAINS = [
    'youtube.com', 
    'youtu.be', 
    'www.youtube.com',
    'soundcloud.com',
    'www.soundcloud.com',
    'vimeo.com',
    'www.vimeo.com'
]

def is_valid_url(url):
    """
    Validate if URL is from an allowed domain
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        return any(domain.endswith(allowed_domain) for allowed_domain in ALLOWED_DOMAINS)
    except:
        return False

def sanitize_filename(filename):
    """
    Create a safe filename from video title
    """
    # Remove invalid characters and limit length
    safe_name = "".join(c for c in filename if c.isalnum() or c in ' -_').strip()
    # Limit filename length
    return safe_name[:100] if safe_name else "download"

def probe_media_info(file_path):
    """
    Use ffprobe to get information about the media file
    """
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'stream=codec_type,width,height', 
            '-show_entries', 'format=duration',
            '-of', 'json', 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.warning(f"ffprobe error: {result.stderr}")
            return None
            
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Error probing media: {str(e)}")
        return None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
def check_url():
    """
    API endpoint to validate URL before download
    """
    url = request.form.get("url", "")
    
    if not url or not is_valid_url(url):
        return jsonify({
            "status": "error",
            "message": "Invalid or unsupported URL. Please provide a valid YouTube, SoundCloud, or Vimeo URL."
        }), 400
        
    try:
        # Just extract info without downloading
        with YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
        if not info_dict:
            return jsonify({
                "status": "error",
                "message": "Could not fetch video information. The content may be private or unavailable."
            }), 400
            
        # Return video title and duration
        return jsonify({
            "status": "success",
            "title": info_dict.get('title', 'Unknown Title'),
            "duration": info_dict.get('duration', 0),
            "thumbnail": info_dict.get('thumbnail', '')
        })
    except Exception as e:
        logger.error(f"Error checking URL: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error processing URL: {str(e)}"
        }), 500

@app.route("/download", methods=["POST"])
def download():
    """
    Process download request
    """
    url = request.form.get("url", "")
    file_format = request.form.get("format", "audio")
    quality = request.form.get("quality", "high")
    
    # Validate input
    if not url:
        return "URL is required", 400
        
    if not is_valid_url(url):
        return "Invalid or unsupported URL", 400
        
    if file_format not in ["audio", "video"]:
        return "Invalid format", 400
        
    # Generate a unique download ID
    download_id = str(uuid.uuid4())
    logger.info(f"Starting download {download_id} for {url}")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define output template
        output_template = os.path.join(temp_dir, "download")
        
        try:
            # First, get the video info without downloading
            with YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                
                if info_dict is None:
                    return "Could not get video information. The URL may be invalid.", 400
                
                # Get clean title
                title = sanitize_filename(info_dict.get('title', 'download'))
                
                # Check file size limitation
                filesize_approx = info_dict.get('filesize_approx', 0)
                if filesize_approx and filesize_approx > MAX_DOWNLOAD_SIZE_MB * 1024 * 1024:
                    return f"The requested media exceeds the maximum download size of {MAX_DOWNLOAD_SIZE_MB}MB", 400
                
                if file_format == 'audio':
                    # Audio download configuration
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': output_template,
                        'quiet': True,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '320',
                        }],
                        'ignoreerrors': True,
                        'no_warnings': True,
                    }
                    expected_extension = '.mp3'
                    mimetype = "audio/mpeg"
                    download_name = f"{title}.mp3"
                    
                else:  # Video format
                    # Configure video quality based on user selection
                    if quality == "high":
                        format_spec = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<=1080]'
                    else:  # balanced
                        # Format 22 (720p) or 18 (360p) with audio included
                        format_spec = '22/18/best[ext=mp4]'
                    
                    ydl_opts = {
                        'format': format_spec,
                        'outtmpl': output_template,
                        'quiet': True,
                        'ignoreerrors': True,
                        'no_warnings': True,
                        'merge_output_format': 'mp4',
                    }
                    expected_extension = '.mp4'
                    mimetype = "video/mp4"
                    download_name = f"{title}.mp4"
            
            # Download the file
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            downloaded_file = None
            possible_extensions = [expected_extension, '', '.webm', '.mkv', '.part']
            
            for ext in possible_extensions:
                test_path = output_template + ext
                if os.path.exists(test_path):
                    downloaded_file = test_path
                    break
            
            if not downloaded_file:
                files = os.listdir(temp_dir)
                if files:
                    # Sort by modification time (newest first)
                    files.sort(key=lambda f: os.path.getmtime(os.path.join(temp_dir, f)), reverse=True)
                    downloaded_file = os.path.join(temp_dir, files[0])
                else:
                    return "Download failed. No output files were created.", 500
            
            # For videos, verify media information
            if file_format == 'video':
                media_info = probe_media_info(downloaded_file)
                if media_info:
                    streams = media_info.get('streams', [])
                    
                    # Check if file has both video and audio
                    has_video = any(s.get('codec_type') == 'video' for s in streams)
                    has_audio = any(s.get('codec_type') == 'audio' for s in streams)
                    
                    if not has_video:
                        return "Downloaded file doesn't contain video stream", 500
                    
                    if not has_audio and quality == "high":
                        logger.warning(f"Download {download_id}: Video has no audio. Trying alternative.")
                        # Try again with a more compatible format
                        alt_opts = {
                            'format': '18/best',  # Format 18 is 360p MP4 with audio
                            'outtmpl': output_template + "_alt",
                            'quiet': True,
                            'ignoreerrors': True,
                            'no_warnings': True,
                        }
                        
                        with YoutubeDL(alt_opts) as ydl:
                            ydl.download([url])
                        
                        # Check for alternative file
                        alt_file = output_template + "_alt.mp4"
                        if os.path.exists(alt_file):
                            downloaded_file = alt_file
            
            # Read file content into memory
            with open(downloaded_file, 'rb') as f:
                media_data = BytesIO(f.read())
            media_data.seek(0)
            
            # Log successful download
            file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
            logger.info(f"Download {download_id} complete: {file_size_mb:.2f} MB")
            
            return send_file(
                media_data,
                as_attachment=True,
                download_name=download_name,
                mimetype=mimetype
            )
                
        except Exception as e:
            logger.error(f"Download {download_id} error: {str(e)}")
            return f"Error processing download: {str(e)}", 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error="Server error occurred"), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)