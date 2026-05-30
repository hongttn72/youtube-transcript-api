from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "YouTube Transcript API is running"})

@app.route('/api/transcript', methods=['GET'])
def get_transcript():
    """Get transcript for a YouTube video"""
    try:
        # Get video URL or ID from query params
        video_url = request.args.get('videoId') or request.args.get('url')
        
        if not video_url:
            return jsonify({"error": "Missing videoId parameter"}), 400
        
        # Extract video ID
        video_id = extract_video_id(video_url)
        
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL or video ID"}), 400
        
        # Try to get transcript
        try:
            # Try to get transcript in English first, then any available language
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try English first
            try:
                transcript = transcript_list.find_transcript(['en'])
                transcript_data = transcript.fetch()
            except:
                # If English not available, get any available transcript
                transcript = transcript_list.find_generated_transcript(['en'])
                transcript_data = transcript.fetch()
            
            # Format transcript with timestamps
            formatted_transcript = ""
            for entry in transcript_data:
                timestamp = format_timestamp(entry['start'])
                text = entry['text'].strip()
                formatted_transcript += f"{timestamp} {text} "
            
            # Clean up extra spaces
            formatted_transcript = re.sub(r'\s+', ' ', formatted_transcript).strip()
            
            return jsonify({
                "success": True,
                "videoId": video_id,
                "transcript": formatted_transcript,
                "length": len(transcript_data)
            })
            
        except TranscriptsDisabled:
            return jsonify({
                "error": "Transcripts are disabled for this video"
            }), 404
            
        except NoTranscriptFound:
            return jsonify({
                "error": "No transcript found for this video"
            }), 404
            
        except Exception as e:
            return jsonify({
                "error": f"Error fetching transcript: {str(e)}"
            }), 500
    
    except Exception as e:
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API documentation"""
    return jsonify({
        "name": "YouTube Transcript API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/api/transcript?videoId={VIDEO_ID}": "Get transcript for a video"
        },
        "example": "/api/transcript?videoId=dQw4w9WgXcQ"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
