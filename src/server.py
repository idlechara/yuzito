"""
Web server module for exposing camera statistics.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
import psutil

from flask import Flask, jsonify

logger = logging.getLogger(__name__)

class StatsServer:
    """
    Web server to expose camera statistics.
    """
    def __init__(self, host="0.0.0.0", port=8080, streamer=None):
        """
        Initialize the stats server.
        
        Args:
            host (str): Host to bind to
            port (int): Port to listen on
            streamer (RTMPStreamer): Reference to the RTMP streamer
        """
        self.host = host
        self.port = port
        self.streamer = streamer
        self.app = Flask(__name__)
        self.server_thread = None
        self.start_time = datetime.now()
        self._register_routes()
        
    def _register_routes(self):
        """Register the Flask routes."""
        
        @self.app.route('/live/stats', methods=['GET'])
        def get_stats():
            """Endpoint to get camera and stream statistics."""
            if not self.streamer:
                return jsonify({
                    "error": "Streamer not initialized",
                    "status": "error"
                }), 500
                
            # Basic statistics
            stats = {
                "status": "active" if self.streamer._thread and self.streamer._thread.is_alive() else "inactive",
                "uptime": str(datetime.now() - self.start_time),
                "started_at": self.start_time.isoformat(),
                "stream": {
                    "url": self.streamer.rtmp_url,
                    "resolution": f"{self.streamer.width}x{self.streamer.height}",
                    "fps": self.streamer.fps,
                    "bitrate": self.streamer.bitrate,
                    "format": self.streamer.format,
                },
                "system": {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "temperature": self._get_cpu_temperature(),
                    "disk_usage": psutil.disk_usage('/').percent,
                }
            }
            
            # Get camera properties if available
            if self.streamer.camera:
                try:
                    camera_info = self.streamer.camera.camera_properties
                    stats["camera"] = {
                        "model": camera_info.get("Model", "Unknown"),
                        "focal_length": camera_info.get("FocalLength", "Unknown"),
                        "sensor_mode": camera_info.get("SensorMode", "Unknown"),
                    }
                except Exception as e:
                    logger.error(f"Error getting camera properties: {e}")
                    stats["camera"] = {"error": str(e)}
            
            return jsonify(stats)
            
    def _get_cpu_temperature(self):
        """Get the CPU temperature on Raspberry Pi."""
        try:
            # Try to get temperature from thermal zone
            if os.path.isfile('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    temp = float(f.read()) / 1000.0
                return f"{temp:.1f}°C"
        except Exception as e:
            logger.error(f"Error reading CPU temperature: {e}")
        return "Unknown"
            
    def start(self):
        """Start the stats server in a separate thread."""
        if self.server_thread and self.server_thread.is_alive():
            logger.warning("Stats server is already running")
            return
            
        logger.info(f"Starting stats server on http://{self.host}:{self.port}")
        
        def run_server():
            self.app.run(host=self.host, port=self.port)
            
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
    def stop(self):
        """Stop the stats server."""
        # Flask doesn't provide a clean way to stop the server in a separate thread
        # This is a simple implementation that will work for our purposes
        if not self.server_thread or not self.server_thread.is_alive():
            logger.warning("No stats server is running")
            return
            
        logger.info("Stopping stats server")
        # We'll rely on the daemon flag to terminate the thread when the main process ends