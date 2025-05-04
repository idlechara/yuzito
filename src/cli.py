"""
Command line interface for Yuzito RTMP streamer.
"""

import argparse
import logging
import signal
import socket
import sys
import time

from .camera import RTMPStreamer
from .rtmp_server import RTMPServer
from .server import StatsServer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Raspberry Pi Camera RTMP Streamer")
    parser.add_argument(
        "--rtmp-url",
        default="rtmp://localhost/live/stream",
        help="RTMP URL to stream to (default: rtmp://localhost/live/stream)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Video width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Video height (default: 720)"
    )
    parser.add_argument(
        "--fps", type=int, default=30, help="Frames per second (default: 30)"
    )
    parser.add_argument(
        "--bitrate", default="2M", help="Video bitrate (default: 2M)"
    )
    parser.add_argument(
        "--format", default="yuv420p", help="Video pixel format (default: yuv420p)"
    )
    parser.add_argument(
        "--self-hosted", action="store_true", 
        help="Run in self-hosted mode with local RTMP server and stats endpoint"
    )
    parser.add_argument(
        "--rtmp-port", type=int, default=1935, 
        help="RTMP server port (default: 1935, only used with --self-hosted)"
    )
    parser.add_argument(
        "--http-port", type=int, default=8080, 
        help="HTTP server port for stats and HLS/DASH (default: 8080, only used with --self-hosted)"
    )
    parser.add_argument(
        "--stats-port", type=int, default=8081, 
        help="Stats HTTP server port (default: 8081, only used with --self-hosted)"
    )
    return parser.parse_args()

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Create a socket to connect to an external server (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    """Main entry point for the application."""
    args = parse_args()
    
    # Initialize RTMP server if in self-hosted mode
    rtmp_server = None
    stats_server = None
    
    if args.self_hosted:
        logger.info("Starting in self-hosted mode")
        host_ip = get_local_ip()
        
        # Start RTMP server
        rtmp_server = RTMPServer(
            host=host_ip,
            rtmp_port=args.rtmp_port,
            http_port=args.http_port
        )
        try:
            rtmp_url = rtmp_server.start()
            # Override RTMP URL to use our local server
            args.rtmp_url = rtmp_url
            logger.info(f"Self-hosted RTMP server running at {rtmp_url}")
        except Exception as e:
            logger.error(f"Failed to start RTMP server: {e}")
            logger.warning("Continuing without self-hosted RTMP server")
    
    # Initialize streamer
    streamer = RTMPStreamer(
        rtmp_url=args.rtmp_url,
        width=args.width,
        height=args.height,
        fps=args.fps,
        bitrate=args.bitrate,
        format=args.format,
    )
    
    # Start stats server if in self-hosted mode
    if args.self_hosted:
        stats_server = StatsServer(
            host="0.0.0.0",  # Bind to all interfaces
            port=args.stats_port,
            streamer=streamer
        )
        stats_server.start()
        logger.info(f"Stats server running at http://0.0.0.0:{args.stats_port}/live/stats")
        logger.info(f"  - Access from other devices: http://{get_local_ip()}:{args.stats_port}/live/stats")
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received interrupt signal, shutting down...")
        streamer.stop()
        if stats_server:
            stats_server.stop()
        if rtmp_server:
            rtmp_server.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info(f"Starting RTMP stream to {args.rtmp_url}")
        logger.info(f"Resolution: {args.width}x{args.height}, FPS: {args.fps}")
        logger.info(f"Press Ctrl+C to stop streaming")
        
        streamer.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        logger.info("Shutting down all services...")
        streamer.stop()
        if stats_server:
            stats_server.stop()
        if rtmp_server:
            rtmp_server.stop()
        
if __name__ == "__main__":
    main()