from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import json
import re
import os
import tempfile

app = Flask(__name__)
CORS(app)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def format_timestamp(seconds):
    """Convert seconds to (MM:SS) format"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"({minutes:02d}:{secs:02d})"

def get_transcript(video_id):
    """Get transcript using yt-dlp Python library"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "sub")
        
        ydl_opts = {
            'skip_download': True,
            'writeautomaticsub': True,
            'writesubtitles': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB', 'en-orig'],
            'subtitlesformat': 'json3',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            # Even if download "fails", subtitle files might still be created
            pass
        
        # Find subtitle file
        sub_file = None
        for f in os.listdir(tmpdir):
            if f.endswith('.json3'):
                sub_file = os.path.join(tmpdir, f)
                break
        
        if not sub_file:
            # Try without specifying language
            ydl_opts['subtitleslangs'] = ['all']
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except:
                pass
            
            for f in os.listdir(tmpdir):
                if f.endswith('.json3'):
                    sub_file = os.path.join(tmpdir, f)
                    break
        
        if not sub_file:
            return None
        
        # Parse JSON3 subtitle format
        with open(sub_file, 'r', encoding='utf-8') as f:
            sub_data = json.load(f)
        
        # Extract text with timestamps
        formatted_parts = []
        events = sub_data.get('events', [])
        
        for event in events:
            if 'segs' not in event:
                continue
            
            start_ms = event.get('tStartMs', 0)
            start_sec = start_ms / 1000.0
            timestamp = format_timestamp(start_sec)
            
            text_parts = []
            for seg in event.get('segs', []):
                text = seg.get('utf8', '').strip()
                if text and text != '\n':
                    text_parts.append(text)
            
            combined_text = ' '.join(text_parts).strip()
            if combined_text:
                formatted_parts.append(f"{timestamp} {combined_text}")
        
        return '\n'.join(formatted_parts)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/transcript', methods=['GET'])
def get_transcript_endpoint():
    try:
        video_url = request.args.get('videoId') or request.args.get('url')
        
        if not video_url:
            return jsonify({"error": "Missing videoId parameter"}), 400
        
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL or video ID"}), 400
        
        transcript = get_transcript(video_id)
        
        if not transcript:
            return jsonify({
                "error": "No transcript available for this video"
            }), 404
        
        return jsonify({
            "success": True,
            "videoId": video_id,
            "transcript": transcript
        })
    
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "YouTube Transcript API",
        "version": "2.1.0",
        "endpoints": {
            "/health": "Health check",
            "/api/transcript?videoId={VIDEO_ID}": "Get transcript"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
