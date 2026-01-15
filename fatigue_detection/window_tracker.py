"""
Gate 1: Context Gate - Active Window Tracking
Detects which application window is active and assigns context multiplier.
"""

import ctypes
from ctypes import wintypes
import time
from typing import Tuple, Optional


class WindowTracker:
    """
    Tracks active window and determines if user is in a valid work context.
    
    Uses Windows API to detect foreground window title.
    Assigns multipliers based on whitelist:
    - 1.0: Full work apps (IDEs, terminals, etc.)
    - 0.5: Hybrid apps (browsers - could be work or leisure)
    - 0.0: Blocked apps (games, streaming services)
    
    For browsers, uses KEYWORD SCANNING to distinguish work from entertainment:
    - Work keywords (docs, localhost, stack overflow) → 1.0
    - Entertainment keywords (netflix, youtube, reddit) → 0.0
    - Unknown → 0.5
    """
    
    # Windows API functions
    _GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
    _GetWindowTextW = ctypes.windll.user32.GetWindowTextW
    _GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
    
    # Browser identification (case-insensitive)
    BROWSERS = ['chrome', 'firefox', 'edge', 'safari', 'brave', 'opera']
    
    # Work-related keywords for browser titles (case-insensitive)
    WORK_KEYWORDS = [
        'localhost', '127.0.0.1', 'github', 'gitlab', 'stackoverflow', 'stack overflow',
        'documentation', 'docs', 'api reference', 'mdn', 'w3schools', 'devdocs',
        'jira', 'confluence', 'notion', 'linear', 'asana', 'monday.com',
        'google drive', 'google docs', 'google sheets', 'google slides',
        'figma', 'canva', 'jupyter', 'colab', 'aws console', 'azure portal',
        'vercel', 'netlify', 'heroku', 'railway',
        'developer', 'developers',  # Catches "Facebook for Developers", "Twitter API Developers"
    ]
    
    # Entertainment keywords for browser titles (case-insensitive)
    ENTERTAINMENT_KEYWORDS = [
        'youtube', 'netflix', 'twitch', 'tiktok', 'instagram', 'facebook',
        'twitter', 'reddit', 'discord', 'spotify', 'soundcloud',
        'hulu', 'disney+', 'amazon prime video', 'hbo max',
        'gaming', 'game', 'chess.com', 'lichess',
    ]
    
    # Application whitelist with multipliers
    WHITELIST = {
        # Full work context (1.0)
        'Visual Studio Code': 1.0,
        'VSCode': 1.0,
        'Code': 1.0,
        'PyCharm': 1.0,
        'IntelliJ': 1.0,
        'Sublime Text': 1.0,
        'Atom': 1.0,
        'vim': 1.0,
        'emacs': 1.0,
        'Eclipse': 1.0,
        'Visual Studio': 1.0,
        'Terminal': 1.0,
        'PowerShell': 1.0,
        'Command Prompt': 1.0,
        'cmd.exe': 1.0,
        'Figma': 1.0,
        'Photoshop': 1.0,
        'Blender': 1.0,
        'Unity': 1.0,
        
        # Communication (work-adjacent, 0.7)
        'Slack': 0.7,
        'Microsoft Teams': 0.7,
        'Discord': 0.7,
        'Zoom': 0.7,
        
        # Browsers - trigger keyword scanning (None = check title)
        'Chrome': None,
        'Firefox': None,
        'Edge': None,
        'Safari': None,
        'Brave': None,
        'Opera': None,
        
        # Blocked context (0.0 - entertainment/gaming)
        'Steam': 0.0,
        'Netflix': 0.0,
        'YouTube': 0.0,  # If dedicated app
        'Twitch': 0.0,
        'Spotify': 0.0,
        'League of Legends': 0.0,
        'Valorant': 0.0,
        'Counter-Strike': 0.0,
        'Dota': 0.0,
        'Fortnite': 0.0,
        'Minecraft': 0.0,
        'Epic Games': 0.0,
        'Origin': 0.0,
        'Battle.net': 0.0,
    }
    
    def __init__(self, poll_interval: float = 2.0):
        """
        Initialize window tracker.
        
        Args:
            poll_interval: How often to poll active window (seconds)
        """
        self.poll_interval = poll_interval
        self.last_poll_time = 0
        self.cached_window = ""
        self.cached_multiplier = 1.0
        
    def get_active_window(self, force_update: bool = False) -> Tuple[str, float]:
        """
        Get active window title and context multiplier.
        
        Args:
            force_update: If True, bypass cache and poll immediately
            
        Returns:
            Tuple of (window_title, context_multiplier)
            
        Example:
            >>> tracker = WindowTracker()
            >>> title, mult = tracker.get_active_window()
            >>> print(f"{title}: {mult}")
            'Visual Studio Code - main.py': 1.0
        """
        current_time = time.time()
        
        # Use cache if within poll interval
        if not force_update and (current_time - self.last_poll_time) < self.poll_interval:
            return self.cached_window, self.cached_multiplier
        
        try:
            # Get foreground window handle
            hwnd = self._GetForegroundWindow()
            
            # Get window title
            length = self._GetWindowTextLengthW(hwnd)
            if length == 0:
                return "Unknown", 0.5
                
            buf = ctypes.create_unicode_buffer(length + 1)
            self._GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            
            # Match against whitelist
            multiplier = self._get_multiplier_for_window(title)
            
            # Update cache
            self.cached_window = title
            self.cached_multiplier = multiplier
            self.last_poll_time = current_time
            
            return title, multiplier
            
        except Exception as e:
            print(f"[WindowTracker] Error getting active window: {e}")
            return "Error", 0.5
    
    def _get_multiplier_for_window(self, title: str) -> float:
        """
        Determine multiplier based on window title.
        
        For browsers, uses keyword scanning:
        - Work keywords → 1.0 (localhost, docs, github)
        - Entertainment keywords → 0.0 (youtube, netflix)
        - Unknown → 0.5 (truly ambiguous)
        
        Args:
            title: Window title string
            
        Returns:
            Multiplier value (0.0, 0.5, 0.7, or 1.0)
        """
        if not title:
            return 0.5  # Unknown = hybrid
        
        title_lower = title.lower()
        
        # Check whitelist (case-insensitive substring match)
        for app_name, multiplier in self.WHITELIST.items():
            if app_name.lower() in title_lower:
                # If browser (multiplier = None), scan title keywords
                if multiplier is None:
                    return self._scan_browser_keywords(title_lower)
                return multiplier
        
        # Default: Unknown app = hybrid context
        return 0.5
    
    def _scan_browser_keywords(self, title_lower: str) -> float:
        """
        Scan browser title for work/entertainment keywords.
        
        PRIORITY ORDER (give user benefit of the doubt):
        1. Check WORK keywords first → return 1.0 (productivity wins ties)
        2. Check entertainment keywords → return 0.0 (distraction)
        3. No match → return 0.5 (truly ambiguous)
        
        This ensures:
        - "Twitter API Docs" → 1.0 (work keyword "docs" found first)
        - "Facebook for Developers" → 1.0 (work keyword "developer" implied)
        - "Facebook" alone → 0.0 (entertainment keyword)
        
        Args:
            title_lower: Lowercase window title
            
        Returns:
            1.0 if work-related, 0.0 if entertainment, 0.5 if ambiguous
        """
        # === STEP 1: Check WORK keywords FIRST (benefit of the doubt) ===
        # If user has ANY work indicator, we assume they're being productive
        for keyword in self.WORK_KEYWORDS:
            if keyword in title_lower:
                return 1.0  # WORK CONTEXT - user gets credit
        
        # === STEP 2: Check entertainment keywords ===
        # Only flag as distraction if NO work indicators found
        for keyword in self.ENTERTAINMENT_KEYWORDS:
            if keyword in title_lower:
                return 0.0  # DISTRACTION
        
        # === STEP 3: Truly ambiguous (no keywords) ===
        # Give benefit of the doubt: could be legitimate work
        return 0.5
    
    def add_custom_app(self, app_name: str, multiplier: float):
        """
        Add custom application to whitelist.
        
        Args:
            app_name: Application name to match in window title
            multiplier: Context multiplier (0.0-1.0)
            
        Example:
            >>> tracker.add_custom_app("MyCustomIDE", 1.0)
        """
        if not 0.0 <= multiplier <= 1.0:
            raise ValueError("Multiplier must be between 0.0 and 1.0")
        self.WHITELIST[app_name] = multiplier
    
    def is_gate_open(self) -> bool:
        """
        Check if context gate is open (multiplier > 0).
        
        Returns:
            True if user is in valid work/hybrid context
        """
        _, multiplier = self.get_active_window()
        return multiplier > 0.0


# Example usage / testing
if __name__ == "__main__":
    tracker = WindowTracker()
    
    print("Active Window Tracker - Gate 1")
    print("=" * 60)
    print("Monitoring active window for 30 seconds...")
    print("Switch between different applications to test.")
    print()
    
    start_time = time.time()
    last_window = ""
    
    while time.time() - start_time < 30:
        title, multiplier = tracker.get_active_window()
        
        if title != last_window:
            status = "🟢 OPEN" if multiplier == 1.0 else \
                    "🟡 HYBRID" if multiplier == 0.5 else \
                    "🟠 PARTIAL" if multiplier == 0.7 else \
                    "🔴 BLOCKED"
            
            print(f"{status} | {title[:50]:50s} | Multiplier: {multiplier:.1f}")
            last_window = title
        
        time.sleep(0.5)
    
    print("\nTest complete!")
