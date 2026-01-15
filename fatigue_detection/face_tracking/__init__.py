"""
MediaPipe-based Face Tracking System
Replaces Dlib/YuNet C++ code with Google MediaPipe for better stability with glasses and rotation.
"""

from .vision_system import VisionSystem

__all__ = ['VisionSystem']
