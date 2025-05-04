"""
Camera module for streaming Raspberry Pi camera to RTMP.
"""

import os
import time
import subprocess
import signal
import logging
from threading import Thread, Event

import numpy as np
from picamera2 import Picamera2
import ffmpeg

logger = logging.getLogger(__name__)

class RTMPStreamer:
    """
    Class to stream Raspberry Pi camera to RTMP server.
    """
    def __init__(
        self,
        rtmp_url="rtmp://localhost/live/stream",
        width=1280,
        height=720,
        fps=30,
        bitrate="2M",
        format="yuv420p",
    ):
        """
        Initialize the RTMP streamer.

        Args:
            rtmp_url (str): RTMP URL to stream to
            width (int): Width of the video stream
            height (int): Height of the video stream
            fps (int): Frames per second
            bitrate (str): Video bitrate
            format (str): Video format
        """
        self.rtmp_url = rtmp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.format = format
        
        self.camera = None
        self.ffmpeg_process = None
        self._stop_event = Event()
        self._thread = None

    def _setup_camera(self):
        """Set up the Raspberry Pi camera."""
        self.camera = Picamera2()
        config = self.camera.create_video_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        self.camera.configure(config)
        self.camera.start()
        # Allow camera to warm up
        time.sleep(2)
        
    def _streaming_thread(self):
        """Thread that handles streaming from camera to RTMP."""
        try:
            # Setup ffmpeg command
            ffmpeg_cmd = (
                ffmpeg
                .input('pipe:', format='rawvideo', pix_fmt='rgb24', 
                       s=f'{self.width}x{self.height}', r=self.fps)
                .output(
                    self.rtmp_url,
                    codec='libx264',
                    pix_fmt=self.format,
                    preset='ultrafast',
                    tune='zerolatency',
                    b=self.bitrate,
                    maxrate=self.bitrate,
                    bufsize=f"{int(self.bitrate[:-1])/2}M",
                    g=str(self.fps*2),
                    format='flv',
                )
                .global_args('-y')  # Overwrite output file
                .compile()
            )
            
            logger.info(f"Starting FFmpeg with command: {' '.join(ffmpeg_cmd)}")
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, 
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Stream frames
            while not self._stop_event.is_set():
                frame = self.camera.capture_array()
                # FFmpeg expects RGB frames
                self.ffmpeg_process.stdin.write(frame.tobytes())
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources."""
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            logger.info("Terminating FFmpeg process")
            self.ffmpeg_process.stdin.close()
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            
        if self.camera:
            logger.info("Stopping camera")
            self.camera.stop()
    
    def start(self):
        """Start the RTMP stream."""
        if self._thread and self._thread.is_alive():
            logger.warning("Stream is already running")
            return
            
        logger.info(f"Starting RTMP stream to {self.rtmp_url}")
        self._stop_event.clear()
        self._setup_camera()
        
        self._thread = Thread(target=self._streaming_thread)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """Stop the RTMP stream."""
        if not self._thread or not self._thread.is_alive():
            logger.warning("No stream is running")
            return
            
        logger.info("Stopping RTMP stream")
        self._stop_event.set()
        self._thread.join(timeout=10)
        self._cleanup()
        
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()