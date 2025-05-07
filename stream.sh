#!/bin/bash
# Camera streaming script for Raspberry Pi in Docker

# Default values if environment variables are not set
NGINX_RTMP_HOST=${NGINX_RTMP_HOST:-localhost}
STREAM_WIDTH=${STREAM_WIDTH:-1280}
STREAM_HEIGHT=${STREAM_HEIGHT:-720}
STREAM_FRAMERATE=${STREAM_FRAMERATE:-30}
STREAM_PATH=${STREAM_PATH:-live/stream}

echo "[INFO] Starting camera streaming service (${STREAM_WIDTH}x${STREAM_HEIGHT}@${STREAM_FRAMERATE}fps)"

# Wait for NGINX RTMP server to be ready, with less frequent messages
echo "[INFO] Checking NGINX RTMP server at $NGINX_RTMP_HOST:1935..."
retry_count=0
max_retries=120
until nc -z $NGINX_RTMP_HOST 1935; do
    retry_count=$((retry_count+1))
    if [ $((retry_count % 5)) -eq 0 ]; then
        echo "[INFO] Waiting for NGINX RTMP server at $NGINX_RTMP_HOST:1935... (attempt $retry_count/$max_retries)"
    fi
    
    if [ $retry_count -ge $max_retries ]; then
        echo "[ERROR] NGINX RTMP server at $NGINX_RTMP_HOST:1935 did not respond after $max_retries attempts"
        exit 1
    fi
    
    sleep 2
done
echo "[INFO] NGINX RTMP server at $NGINX_RTMP_HOST:1935 ready"

# Function to detect camera system
detect_camera_system() {
    if command -v rpicam-vid > /dev/null 2>&1; then
        CAMERA_SYSTEM="rpicam"
        echo "[INFO] Using rpicam camera system"
    else
        echo "[ERROR] rpicam-vid not found. Please install Raspberry Pi Camera Stack."
        exit 1
    fi
}

# Start streaming with rpicam
start_streaming() {
    RTMP_URL="rtmp://$NGINX_RTMP_HOST:1935/$STREAM_PATH"
    echo "[INFO] Streaming to: $RTMP_URL"
    
    rpicam-vid -t 0 --width $STREAM_WIDTH --height $STREAM_HEIGHT --framerate $STREAM_FRAMERATE --codec h264 --inline --output - 2>/dev/null | \
        ffmpeg -hide_banner -loglevel error -i - -c:v copy -f flv $RTMP_URL
}

# Handle graceful shutdown
handle_shutdown() {
    echo "[INFO] Shutting down camera streaming service..."
    pkill -TERM -f "ffmpeg|rpicam-vid"
    exit 0
}

# Register signal handlers
trap handle_shutdown SIGTERM SIGINT

# Main execution
detect_camera_system
echo "[INFO] Camera streaming started"
start_streaming

# This line should not be reached under normal operation
echo "[ERROR] Streaming stopped unexpectedly. Exiting..."
exit 1