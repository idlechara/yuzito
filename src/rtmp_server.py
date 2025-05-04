"""
Self-hosted RTMP server module.
"""

import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

NGINX_CONFIG_TEMPLATE = """
worker_processes auto;
daemon off;
error_log logs/error.log info;

events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;
    server {
        listen 8080;
        
        location /live {
            root html;
            add_header 'Access-Control-Allow-Origin' '*';
        }
    }
}

rtmp {
    server {
        listen 1935;
        chunk_size 4096;
        
        application live {
            live on;
            record off;
            
            # Enable HLS streaming
            hls on;
            hls_path html/live/hls;
            hls_fragment 3;
            hls_playlist_length 60;
            
            # Enable DASH streaming
            dash on;
            dash_path html/live/dash;
        }
    }
}
"""

class RTMPServer:
    """
    Self-hosted RTMP server using NGINX with RTMP module.
    """
    def __init__(self, host="0.0.0.0", rtmp_port=1935, http_port=8080):
        """
        Initialize the RTMP server.
        
        Args:
            host (str): Host to bind to
            rtmp_port (int): Port for RTMP streaming
            http_port (int): Port for HTTP server (HLS/DASH/stats)
        """
        self.host = host
        self.rtmp_port = rtmp_port
        self.http_port = http_port
        self.nginx_process = None
        self.nginx_dir = None
        self.rtmp_url = f"rtmp://{host}:{rtmp_port}/live/stream"
        
    def _check_nginx_rtmp_installed(self):
        """Check if NGINX with RTMP module is installed."""
        try:
            # Try to find nginx-rtmp in the system
            nginx_path = shutil.which("nginx")
            if not nginx_path:
                logger.error("NGINX not found. Please install NGINX with RTMP module.")
                return False
                
            # Check if NGINX has RTMP module
            result = subprocess.run([nginx_path, "-V"], 
                                    capture_output=True, 
                                    text=True)
            if "rtmp" not in result.stderr:
                logger.error("NGINX found but RTMP module is not installed.")
                return False
                
            logger.info(f"Found NGINX with RTMP module at {nginx_path}")
            return True
        except Exception as e:
            logger.error(f"Error checking NGINX installation: {e}")
            return False
            
    def _setup_nginx_config(self):
        """Set up the NGINX configuration."""
        try:
            # Create temporary directory for NGINX
            self.nginx_dir = tempfile.mkdtemp(prefix="yuzito_nginx_")
            nginx_conf_path = os.path.join(self.nginx_dir, "nginx.conf")
            
            # Create necessary directories
            os.makedirs(os.path.join(self.nginx_dir, "logs"), exist_ok=True)
            os.makedirs(os.path.join(self.nginx_dir, "html", "live", "hls"), exist_ok=True)
            os.makedirs(os.path.join(self.nginx_dir, "html", "live", "dash"), exist_ok=True)
            
            # Write NGINX configuration
            with open(nginx_conf_path, "w") as f:
                f.write(NGINX_CONFIG_TEMPLATE)
                
            logger.info(f"NGINX configuration written to {nginx_conf_path}")
            return nginx_conf_path
        except Exception as e:
            logger.error(f"Error setting up NGINX configuration: {e}")
            return None
            
    def start(self):
        """Start the RTMP server."""
        if self.nginx_process and self.nginx_process.poll() is None:
            logger.warning("RTMP server is already running")
            return
            
        if not self._check_nginx_rtmp_installed():
            logger.error("Cannot start RTMP server without NGINX with RTMP module")
            raise RuntimeError("NGINX with RTMP module not installed")
            
        nginx_conf_path = self._setup_nginx_config()
        if not nginx_conf_path:
            logger.error("Failed to set up NGINX configuration")
            raise RuntimeError("Failed to set up NGINX configuration")
            
        try:
            # Start NGINX with our configuration
            nginx_path = shutil.which("nginx")
            self.nginx_process = subprocess.Popen(
                [nginx_path, "-c", nginx_conf_path, "-p", self.nginx_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give NGINX some time to start
            time.sleep(2)
            
            if self.nginx_process.poll() is not None:
                stdout, stderr = self.nginx_process.communicate()
                logger.error(f"NGINX failed to start: {stderr.decode()}")
                raise RuntimeError(f"NGINX failed to start: {stderr.decode()}")
                
            logger.info(f"RTMP server started on {self.rtmp_url}")
            logger.info(f"HTTP server started on http://{self.host}:{self.http_port}")
            logger.info(f"HLS endpoint: http://{self.host}:{self.http_port}/live/hls/stream.m3u8")
            logger.info(f"DASH endpoint: http://{self.host}:{self.http_port}/live/dash/stream.mpd")
            
            return self.rtmp_url
        except Exception as e:
            logger.error(f"Error starting RTMP server: {e}")
            self._cleanup()
            raise
            
    def _cleanup(self):
        """Clean up resources."""
        if self.nginx_dir and os.path.exists(self.nginx_dir):
            try:
                shutil.rmtree(self.nginx_dir)
                logger.info(f"Removed temporary NGINX directory: {self.nginx_dir}")
            except Exception as e:
                logger.error(f"Error removing NGINX directory: {e}")
                
    def stop(self):
        """Stop the RTMP server."""
        if not self.nginx_process or self.nginx_process.poll() is not None:
            logger.warning("No RTMP server is running")
            return
            
        try:
            logger.info("Stopping RTMP server")
            self.nginx_process.terminate()
            
            # Give NGINX some time to stop gracefully
            try:
                self.nginx_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("NGINX didn't stop gracefully, killing it")
                self.nginx_process.kill()
                
            self._cleanup()
        except Exception as e:
            logger.error(f"Error stopping RTMP server: {e}")
            
    def __del__(self):
        """Cleanup when the object is deleted."""
        self.stop()