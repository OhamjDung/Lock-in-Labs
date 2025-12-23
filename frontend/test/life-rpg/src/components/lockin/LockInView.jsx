import React, { useRef, useState, useEffect, useMemo } from 'react';
import { RotateCcw, Download, Radio, Send, Power, Video, VideoOff, Check, Play, ClipboardList, Clock, ArrowRight, Plus, Minus, Lock } from 'lucide-react';
import GeminiMapView from './GeminiMapView';

export default function LockInView({ availableQuests = [], sendFile, selectedAlgorithm, setSelectedAlgorithm, ditheredPreviewUrl, setDitheredPreviewUrl, fileInputRef, takePhotoRef }) {
  const [showSetup, setShowSetup] = useState(true);
  const [lockdownDuration, setLockdownDuration] = useState(60 * 60); // Default 1 hour in seconds
  const [lockdownTimeLeft, setLockdownTimeLeft] = useState(60 * 60);
  const [lockdownRunning, setLockdownRunning] = useState(false);
  
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const canvasRef = useRef(null);
  const pendingStreamRef = useRef(null);
  const detectionWsRef = useRef(null);
  const detectionIntervalRef = useRef(null);
  const [detectionState, setDetectionState] = useState({ detections: [] });
  const [videoReady, setVideoReady] = useState(false);
  const [lastSentFrameTs, setLastSentFrameTs] = useState(0);

  const DETECTOR_WS_URL = useMemo(() => {
    try {
      const hostname = window.location?.hostname || '127.0.0.1';
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '';
      
      if (isLocalhost) {
        return 'ws://127.0.0.1:8000/ws/phone-detect';
      }
      
      // In production, construct from current origin
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      return `${proto}://${hostname}/ws/phone-detect`;
    } catch (e) {
      console.warn('Failed to construct WebSocket URL, using default:', e);
      return 'ws://127.0.0.1:8000/ws/phone-detect';
    }
  }, []);

  const [detectionConnState, setDetectionConnState] = useState('idle');
  const backoffRef = useRef(1000);
  const reconnectTimerRef = useRef(null);
  const MAX_BACKOFF = 16000;
  const [cameraActive, setCameraActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerMode, setTimerMode] = useState('WORK');
  const [tasks, setTasks] = useState([{ id: 101, text: 'Review mission parameters', completed: false }]);
  const [chatLog, setChatLog] = useState([{ sender: 'HANDLER', text: 'Comms link established. Ready for tasking.' }]);
  const [chatInput, setChatInput] = useState('');
  const [powerOn, setPowerOn] = useState(true);
  const [pomodoroCount, setPomodoroCount] = useState(0);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editingTaskText, setEditingTaskText] = useState('');
  const [phoneDetectionCount, setPhoneDetectionCount] = useState(0);
  const [showPhoneNotification, setShowPhoneNotification] = useState(false);
  const lastPhoneDetectionRef = useRef(null);
  const tabs = ['lockin', 'gemini-map', 'placeholder2']; // Array of tab identifiers
  const [activeTabIndex, setActiveTabIndex] = useState(0); // Index of current tab

  const toggleCamera = async () => {
    if (cameraActive) {
      if (videoRef.current && videoRef.current.srcObject) {
        const tracks = videoRef.current.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        videoRef.current.srcObject = null;
      }
      if (pendingStreamRef.current) {
        pendingStreamRef.current.getTracks().forEach(t => t.stop());
        pendingStreamRef.current = null;
      }
      setCameraActive(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        pendingStreamRef.current = stream;
        setCameraActive(true);
      } catch (err) { /* camera denied */ }
    }
  };

  const sendFrame = async () => {
    try {
      const ws = detectionWsRef.current;
      const video = videoRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (!video || !video.videoWidth || !video.videoHeight) return;

      const targetW = 320;
      const scale = targetW / video.videoWidth;
      const cw = targetW;
      const ch = Math.round(video.videoHeight * scale);

      let canvas = canvasRef.current;
      if (!canvas) {
        canvas = document.createElement('canvas');
        canvasRef.current = canvas;
      }
      canvas.width = cw;
      canvas.height = ch;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, cw, ch);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
      const frameId = `${Date.now()}`;
      const payload = { type: 'frame', frame_id: frameId, image: dataUrl };
      setLastSentFrameTs(Date.now());
      try { ws.send(JSON.stringify(payload)); } catch (e) { /* ignore send errors */ }
    } catch (e) { /* sendFrame error */ }
  };

  const takePhotoAndDither = async () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const c = document.createElement('canvas');
    c.width = video.videoWidth;
    c.height = video.videoHeight;
    const ctx = c.getContext('2d');
    ctx.drawImage(video, 0, 0, c.width, c.height);
    return new Promise((resolve) => {
      c.toBlob(async (blob) => {
        if (!blob) return resolve();
        const file = new File([blob], 'capture.png', { type: blob.type });
        if (typeof sendFile === 'function') await sendFile(file, selectedAlgorithm);
        resolve();
      }, 'image/png');
    });
  };

  const scheduleReconnect = () => {
    if (reconnectTimerRef.current) return;
    const delay = backoffRef.current;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      if (cameraActive) connectWS();
    }, delay);
    backoffRef.current = Math.min(MAX_BACKOFF, backoffRef.current * 2);
  };

  const connectWS = () => {
    // Don't connect if camera is not active or if already connected
    if (!cameraActive || detectionWsRef.current) return;
    
    // Don't connect if WebSocket is already in connecting state
    if (detectionConnState === 'connecting') return;
    
    setDetectionConnState('connecting');
    try {
      const ws = new WebSocket(DETECTOR_WS_URL);
      detectionWsRef.current = ws;
      
      ws.onopen = () => {
        setDetectionConnState('connected');
        backoffRef.current = 1000;
        if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
        detectionIntervalRef.current = setInterval(sendFrame, 333);
      };
      
      ws.onmessage = (ev) => {
        try { 
          const msg = JSON.parse(ev.data); 
          if (msg.type === 'detection') setDetectionState(msg); 
        } catch (e) { 
          console.debug('Failed to parse WebSocket message:', e);
        }
      };
      
      ws.onclose = (event) => {
        setDetectionConnState('offline');
        if (detectionIntervalRef.current) { 
          clearInterval(detectionIntervalRef.current); 
          detectionIntervalRef.current = null; 
        }
        detectionWsRef.current = null;
        // Only reconnect if camera is still active
        if (cameraActive && event.code !== 1000) { // Don't reconnect on normal close
          scheduleReconnect();
        }
      };
      
      ws.onerror = (error) => {
        console.debug('WebSocket error:', error);
        try { 
          if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            ws.close();
          }
        } catch (e) {
          console.debug('Error closing WebSocket:', e);
        }
      };
    } catch (e) {
      console.debug('Failed to create WebSocket:', e);
      setDetectionConnState('offline');
      detectionWsRef.current = null;
      // Only schedule reconnect if camera is still active
      if (cameraActive) {
        scheduleReconnect();
      }
    }
  };

  const stopDetection = () => {
    try {
      if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
      if (detectionIntervalRef.current) { clearInterval(detectionIntervalRef.current); detectionIntervalRef.current = null; }
      const ws = detectionWsRef.current;
      if (ws) { try { ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null; ws.close(); } catch (e) {} detectionWsRef.current = null; }
      backoffRef.current = 1000;
      setDetectionConnState('idle');
      setDetectionState({ detections: [] });
    } catch (e) { console.error('stopDetection', e); }
  };

  useEffect(() => {
    if (takePhotoRef) { takePhotoRef.current = takePhotoAndDither; }
    return () => { if (takePhotoRef && takePhotoRef.current === takePhotoAndDither) takePhotoRef.current = null; };
  }, [takePhotoRef]);

  useEffect(() => {
    const video = videoRef.current;
    function onPlaying() { setVideoReady(true); }
    if (cameraActive) {
      setVideoReady(false);
      if (video) {
        video.addEventListener('playing', onPlaying);
        if (!video.paused && (video.readyState >= 2 || video.currentTime > 0)) setVideoReady(true);
      }
      // Only connect WebSocket when camera becomes active
      if (!detectionWsRef.current) {
        connectWS();
      }
    } else {
      // Stop detection when camera is turned off
      stopDetection();
    }
    return () => { 
      if (!cameraActive) {
        stopDetection();
      }
      if (video) video.removeEventListener('playing', onPlaying); 
    };
  }, [cameraActive]);

  useEffect(() => {
    const video = videoRef.current;
    if (cameraActive && pendingStreamRef.current && video) {
      try {
        video.srcObject = pendingStreamRef.current;
        pendingStreamRef.current = null;
        video.onloadedmetadata = () => { setVideoReady(true); video.play().catch(e => console.debug('video.play failed', e)); };
      } catch (e) { console.error('error attaching stream', e); }
    }
  }, [cameraActive]);

  useEffect(() => {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext('2d');
    const w = video.videoWidth || canvas.clientWidth || 320;
    const h = video.videoHeight || canvas.clientHeight || 240;
    canvas.width = w; canvas.height = h;
    ctx.clearRect(0, 0, w, h);
    const dets = detectionState && detectionState.detections ? detectionState.detections : [];
    
    // Check for phone detections
    const phoneDetections = dets.filter(d => {
      const className = (d.class || '').toLowerCase();
      return className.includes('phone') || className.includes('cell phone') || className.includes('mobile phone');
    });
    
    // If phone detected and camera is active, show notification and increment counter
    if (phoneDetections.length > 0 && cameraActive) {
      const now = Date.now();
      // Only trigger notification if it's been at least 3 seconds since last detection (to avoid spam)
      if (!lastPhoneDetectionRef.current || (now - lastPhoneDetectionRef.current) > 3000) {
        lastPhoneDetectionRef.current = now;
        setPhoneDetectionCount(prev => prev + 1);
        setShowPhoneNotification(true);
        // Auto-hide notification after 5 seconds
        setTimeout(() => setShowPhoneNotification(false), 5000);
      }
    }
    
    dets.forEach(d => {
      const bb = d.bbox || {};
      const x = (bb.x || 0) * w;
      const y = (bb.y || 0) * h;
      const bw = (bb.w || 0) * w;
      const bh = (bb.h || 0) * h;
      ctx.lineWidth = 3;
      // Use red color for phone detections
      const isPhone = (d.class || '').toLowerCase().includes('phone');
      ctx.strokeStyle = isPhone ? 'rgba(255,0,0,0.9)' : 'rgba(57,255,20,0.9)';
      ctx.strokeRect(x, y, bw, bh);
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(x, y - 18, Math.max(60, ctx.measureText(d.class || '').width + 12), 18);
      ctx.fillStyle = isPhone ? '#ff0000' : '#39ff14';
      ctx.font = '12px monospace';
      ctx.fillText(`${d.class || ''} ${(d.confidence||0).toFixed(2)}`, x + 6, y - 4);
    });
  }, [detectionState, cameraActive]);

  useEffect(() => {
    let interval = null;
    if (timerRunning && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(t => {
          if (t <= 1) {
            setTimerRunning(false);
            // Increment pomodoro count when work session completes
            if (timerMode === 'WORK') {
              setPomodoroCount(prev => prev + 1);
            }
            return 0;
          }
          return t - 1;
        });
      }, 1000);
    } else if (timeLeft === 0) {
      setTimerRunning(false);
    }
    return () => clearInterval(interval);
  }, [timerRunning, timeLeft, timerMode]);

  // Lockdown countdown timer
  useEffect(() => {
    let interval = null;
    if (lockdownRunning && lockdownTimeLeft > 0) {
      interval = setInterval(() => setLockdownTimeLeft(t => {
        if (t <= 1) {
          setLockdownRunning(false);
          // Could add an alert or notification here when lockdown ends
          return 0;
        }
        return t - 1;
      }), 1000);
    }
    return () => clearInterval(interval);
  }, [lockdownRunning, lockdownTimeLeft]);

  const formatLockdownTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const adjustLockdownTime = (minutes) => {
    const newMinutes = Math.max(1, Math.min(480, minutes)); // 1 minute to 8 hours
    setLockdownDuration(newMinutes * 60);
  };

  const handleStartLockdown = () => {
    setLockdownTimeLeft(lockdownDuration);
    setLockdownRunning(true);
    setShowSetup(false);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
    const secs = (seconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const toggleTimerMode = () => { const newMode = timerMode === 'WORK' ? 'BREAK' : 'WORK'; setTimerMode(newMode); setTimerRunning(false); setTimeLeft(newMode === 'WORK' ? 25 * 60 : 5 * 60); };
  const toggleTask = (id) => setTasks(tasks.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
  const importTasks = () => { const newTasks = availableQuests.map(q => ({ id: Math.random(), text: q.name || q.title || 'Quest', completed: false })); setTasks([...tasks, ...newTasks]); };
  const sendChatMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;
    
    const userMessage = chatInput.trim();
    setChatInput('');
    setIsChatLoading(true);
    
    // Add user message to chat log
    setChatLog(prev => [...prev, { sender: 'OPERATIVE', text: userMessage }]);
    
    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      
      // Build messages array from chat history
      const messages = chatLog.map(msg => ({
        role: msg.sender === 'OPERATIVE' ? 'user' : 'assistant',
        content: msg.text
      }));
      // Add current user message
      messages.push({ role: 'user', content: userMessage });
      
      const response = await fetch(`${backend}/api/chat/gemini`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to get response');
      }
      
      const data = await response.json();
      setChatLog(prev => [...prev, { sender: 'HANDLER', text: data.response || 'No response received.' }]);
    } catch (error) {
      console.error('Error sending chat message:', error);
      setChatLog(prev => [...prev, { sender: 'HANDLER', text: 'Error: Connection failed. Please try again.' }]);
    } finally {
      setIsChatLoading(false);
    }
  };
  
  const addNewTask = () => {
    const newTask = {
      id: Date.now(),
      text: 'New task',
      completed: false
    };
    setTasks([...tasks, newTask]);
    setEditingTaskId(newTask.id);
    setEditingTaskText('New task');
  };
  
  const handleTaskTextChange = (id, newText) => {
    setTasks(tasks.map(t => t.id === id ? { ...t, text: newText } : t));
  };
  
  const handleTaskBlur = () => {
    setEditingTaskId(null);
    setEditingTaskText('');
  };
  
  const handleTaskKeyDown = (e, id) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleTaskBlur();
    } else if (e.key === 'Escape') {
      handleTaskBlur();
    }
  };

  return (
    <>
    <style dangerouslySetInnerHTML={{__html: `
        .uplink-scrollbar::-webkit-scrollbar {
            width: 6px;
        }
        .uplink-scrollbar::-webkit-scrollbar-track {
            background: transparent;
        }
        .uplink-scrollbar::-webkit-scrollbar-thumb {
            background: #666;
            border-radius: 10px;
            border: none;
        }
        .uplink-scrollbar::-webkit-scrollbar-thumb:hover {
            background: #888;
        }
        .uplink-scrollbar {
            scrollbar-width: thin;
            scrollbar-color: #666 transparent;
        }
    `}} />
    <div className="fixed left-0 right-0 top-16 bottom-0 flex items-stretch justify-center p-0 bg-transparent z-40">
       <div className="relative bg-[#dcdcdc] p-6 md:p-8 rounded-none shadow-[0_30px_60px_rgba(0,0,0,0.8),inset_0_2px_5px_rgba(255,255,255,0.4),inset_0_-5px_10px_rgba(0,0,0,0.1)] w-full h-full flex flex-col border-b-[12px] border-r-[12px] border-[#b0b0b0] transition-all overflow-hidden">
          <div className="w-full flex justify-between items-center mb-4 px-4">
              <div className="flex gap-2"><div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div><div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div></div>
              <div className="text-sm font-black text-stone-500 tracking-[0.2em] italic font-serif flex items-center gap-2"><div className="w-4 h-4 bg-red-600 rounded-sm"></div> SONY TRINITRON</div>
          </div>
          <div className="relative flex-1 bg-[#050505] rounded-[2rem] p-2 md:p-3 shadow-[inset_0_5px_15px_rgba(0,0,0,1),0_0_0_8px_#151515]">
             <div className="relative w-full h-full bg-[#0a100a] rounded-[1.5rem] overflow-hidden shadow-[inset_0_0_80px_rgba(0,0,0,0.9)] ring-1 ring-white/5 flex font-mono">
                <div className="absolute inset-0 z-50 pointer-events-none mix-blend-overlay bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(0,255,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%]"></div>
                
                {/* Tab Content - Render all tabs but hide inactive ones */}
                {/* Lock-in Tab */}
                <div 
                  className="w-full h-full absolute inset-0"
                  style={{ display: tabs[activeTabIndex] === 'lockin' ? 'block' : 'none' }}
                >
                {/* Setup Screen */}
                {showSetup ? (
                  <div className="w-full h-full flex items-center justify-center p-8 relative z-10">
                    <div className="max-w-2xl w-full">
                      <div className="text-center mb-8">
                        <div className="flex items-center justify-center gap-3 mb-4">
                          <Lock size={32} className="text-[#39ff14]" />
                          <h2 className="text-3xl font-bold text-[#39ff14] font-mono tracking-wider">LOCKDOWN INITIALIZATION</h2>
                        </div>
                        <p className="text-[#00cc00] text-sm font-mono">Set the duration for your focused work session</p>
                      </div>

                      <div className="bg-[#001100] border border-[#39ff14]/20 rounded-lg p-8 mb-6">
                        <div className="text-center mb-6">
                          <div className="text-[#39ff14] text-6xl font-mono font-bold mb-2 tabular-nums">
                            {formatLockdownTime(lockdownDuration)}
                          </div>
                          <div className="text-[#00cc00] text-xs font-mono uppercase tracking-wider">LOCKDOWN DURATION</div>
                        </div>

                        <div className="flex justify-center gap-4 mb-6">
                          <button
                            onClick={() => adjustLockdownTime(Math.max(1, (lockdownDuration / 60) - 15))}
                            className="w-12 h-12 bg-[#002200] border border-[#39ff14]/30 rounded flex items-center justify-center text-[#39ff14] hover:bg-[#003300] hover:border-[#39ff14] transition-all"
                          >
                            <Minus size={20} />
                          </button>
                          <div className="flex flex-col items-center gap-2">
                            <div className="text-[#39ff14] font-mono text-sm">Adjust Time</div>
                            <div className="flex gap-2">
                              <button
                                onClick={() => adjustLockdownTime(Math.min(480, (lockdownDuration / 60) + 15))}
                                className="px-3 py-1 bg-[#002200] border border-[#39ff14]/30 rounded text-[#39ff14] text-xs font-mono hover:bg-[#003300] transition-all"
                              >
                                +15m
                              </button>
                              <button
                                onClick={() => adjustLockdownTime(Math.min(480, (lockdownDuration / 60) + 30))}
                                className="px-3 py-1 bg-[#002200] border border-[#39ff14]/30 rounded text-[#39ff14] text-xs font-mono hover:bg-[#003300] transition-all"
                              >
                                +30m
                              </button>
                              <button
                                onClick={() => adjustLockdownTime(Math.min(480, (lockdownDuration / 60) + 60))}
                                className="px-3 py-1 bg-[#002200] border border-[#39ff14]/30 rounded text-[#39ff14] text-xs font-mono hover:bg-[#003300] transition-all"
                              >
                                +1h
                              </button>
                            </div>
                          </div>
                          <button
                            onClick={() => adjustLockdownTime(Math.min(480, (lockdownDuration / 60) + 15))}
                            className="w-12 h-12 bg-[#002200] border border-[#39ff14]/30 rounded flex items-center justify-center text-[#39ff14] hover:bg-[#003300] hover:border-[#39ff14] transition-all"
                          >
                            <Plus size={20} />
                          </button>
                        </div>

                        <div className="grid grid-cols-4 gap-2 mb-6">
                          {[15, 30, 60, 120].map((mins) => (
                            <button
                              key={mins}
                              onClick={() => adjustLockdownTime(mins)}
                              className={`px-4 py-2 border rounded font-mono text-sm transition-all ${
                                Math.abs((lockdownDuration / 60) - mins) < 1
                                  ? 'bg-[#39ff14] text-black border-[#39ff14] font-bold'
                                  : 'bg-[#002200] text-[#39ff14] border-[#39ff14]/30 hover:bg-[#003300]'
                              }`}
                            >
                              {mins}m
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="flex justify-center gap-4">
                        <button
                          onClick={handleStartLockdown}
                          className="px-8 py-3 bg-[#39ff14] text-black font-bold font-mono uppercase tracking-wider rounded hover:bg-[#4aff2a] transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(57,255,20,0.5)]"
                        >
                          <span>INITIATE LOCKDOWN</span>
                          <ArrowRight size={18} />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Lockdown Countdown - Top Right Corner */}
                    <div className="absolute top-4 right-4 z-50 bg-[#001100]/90 border border-[#39ff14]/40 rounded px-4 py-2 backdrop-blur-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <Lock size={14} className="text-[#39ff14]" />
                        <span className="text-[10px] text-[#00cc00] font-mono uppercase tracking-wider">LOCKDOWN</span>
                      </div>
                      <div className={`text-2xl font-mono font-bold tabular-nums ${
                        lockdownTimeLeft < 300 ? 'text-red-400' : 'text-[#39ff14]'
                      }`}>
                        {formatLockdownTime(lockdownTimeLeft)}
                      </div>
                    </div>
                    
                    <div className={`w-full h-full grid grid-cols-1 md:grid-cols-2 grid-rows-2 gap-0 transition-opacity duration-500 ${powerOn ? 'opacity-100' : 'opacity-0'}`}>
                    {/* CAMERA */}
                    <div className="relative border-b md:border-r border-[#39ff14]/30 p-6 flex flex-col overflow-hidden group bg-black">
                        <div className="absolute top-3 left-4 text-[10px] font-bold tracking-widest z-20 flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${cameraActive ? 'bg-red-500 animate-pulse' : 'bg-[#003300]'}`}></div>
                          <div className="text-[#39ff14]">CAM_01 [MONITORING]</div>
                          <div className="ml-3 text-[10px] z-30">
                            {detectionConnState === 'connected' && <span className="text-[#39ff14]">DETECTOR: online</span>}
                            {detectionConnState === 'connecting' && <span className="text-[#ffb86b]">DETECTOR: connecting</span>}
                            {detectionConnState === 'offline' && <span className="text-[#ff6b6b]">DETECTOR: offline</span>}
                            {detectionConnState === 'idle' && <span className="text-[#888]">DETECTOR: idle</span>}
                          </div>
                          {phoneDetectionCount > 0 && (
                            <div className="ml-3 text-[10px] text-red-400">
                              PHONE_DETECTIONS: <span className="font-bold">{phoneDetectionCount}</span>
                            </div>
                          )}
                        </div>
                        <div className="flex-1 bg-[#020a02] rounded-sm mt-4 overflow-hidden relative border border-[#39ff14]/20 shadow-[inset_0_0_20px_rgba(57,255,20,0.05)]">
                             {cameraActive ? (
                                <>
                                  <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover opacity-80 contrast-125 saturate-0 sepia hue-rotate-[50deg] brightness-125" style={{ objectFit: 'cover' }} />
                                  <canvas ref={overlayRef} className="absolute inset-0 w-full h-full pointer-events-none" />
                                </>
                            ) : (
                                <div className="w-full h-full flex flex-col items-center justify-center text-[#004400]"><VideoOff size={32} className="mb-2 opacity-50" /><span className="text-xs tracking-widest">NO SIGNAL</span></div>
                            )}
                            <button onClick={toggleCamera} className="absolute bottom-4 right-4 text-[#39ff14] hover:text-white transition-colors p-2 border border-[#39ff14]/30 bg-[#002200]/50 rounded-sm z-10">
                              {cameraActive ? <VideoOff size={16} /> : <Video size={16} />}
                            </button>
                        </div>
                    </div>
                    {/* CHRONOMETER */}
                    <div className="relative border-b border-[#39ff14]/30 p-6 flex flex-col items-center justify-center bg-black">
                        <div className="absolute top-3 right-4 text-[10px] text-[#39ff14] font-bold tracking-widest opacity-70">SYS_CLOCK</div>
                        <div className={`text-7xl md:text-8xl lg:text-9xl font-bold tracking-tighter tabular-nums transition-all ${timerRunning ? 'text-[#39ff14] drop-shadow-[0_0_20px_rgba(57,255,20,0.8)]' : 'text-[#005500]'}`}>{formatTime(timeLeft)}</div>
                        <div className="w-full max-w-xs h-1 bg-[#002200] mt-6 rounded-full overflow-hidden"><div className={`h-full bg-[#39ff14] shadow-[0_0_10px_#39ff14] transition-all duration-1000`} style={{ width: `${(timeLeft / (timerMode === 'WORK' ? 1500 : 300)) * 100}%` }} /></div>
                        <div className="flex gap-6 mt-8">
                            <button onClick={() => setTimerRunning(!timerRunning)} className="text-[#39ff14] hover:text-white hover:drop-shadow-[0_0_10px_white] transition-all"><Play size={32} /></button>
                            <button onClick={() => setTimeLeft(timerMode === 'WORK' ? 1500 : 300)} className="text-[#008800] hover:text-[#39ff14] transition-colors"><RotateCcw size={24} /></button>
                        </div>
                        <div className="mt-6 flex gap-2 text-[10px] uppercase tracking-widest">
                            <button onClick={toggleTimerMode} className={`px-3 py-1 border border-[#39ff14]/30 transition-all ${timerMode === 'WORK' ? 'bg-[#39ff14] text-black font-bold shadow-[0_0_15px_#39ff14]' : 'text-[#008800] hover:text-[#39ff14]'}`}>{timerMode}</button>
                        </div>
                        <div className="mt-4 text-[#39ff14] text-xs font-mono">
                            <span className="text-[#005500]">POMODOROS:</span> <span className="font-bold">{pomodoroCount}</span>
                        </div>
                    </div>
                    {/* OBJECTIVES */}
                    <div className="relative border-r border-[#39ff14]/30 p-6 flex flex-col text-xs overflow-hidden bg-black">
                        <div className="flex justify-between items-center mb-4 pb-2 border-b border-[#39ff14]/30 text-[#39ff14]">
                             <span className="font-bold tracking-[0.2em] flex items-center gap-2"><ClipboardList size={14} /> ACTIVE_DIRECTIVES</span>
                             <div className="flex gap-2">
                                <button onClick={addNewTask} className="hover:text-white hover:drop-shadow-[0_0_5px_white] transition-all" title="Add new task"><Plus size={14} /></button>
                                <button onClick={importTasks} className="hover:text-white hover:drop-shadow-[0_0_5px_white] transition-all" title="Import quests"><Download size={14} /></button>
                             </div>
                        </div>
                        <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar pr-2">
                             {tasks.length === 0 && <div className="text-[#004400] italic text-center py-4">:: NO DATA ::</div>}
                             {tasks.map(task => (
                                <div key={task.id} className={`cursor-pointer group flex items-start gap-3 p-2 border border-transparent hover:border-[#39ff14]/40 hover:bg-[#002200]/50 transition-all ${task.completed ? 'opacity-40' : 'opacity-100'}`}>
                                    <div onClick={() => toggleTask(task.id)} className={`w-3 h-3 mt-0.5 border border-[#39ff14] flex items-center justify-center flex-shrink-0 ${task.completed ? 'bg-[#39ff14] text-black' : ''}`}>{task.completed && <Check size={10} strokeWidth={4} />}</div>
                                    {editingTaskId === task.id ? (
                                      <input
                                        type="text"
                                        value={editingTaskText}
                                        onChange={(e) => {
                                          setEditingTaskText(e.target.value);
                                          handleTaskTextChange(task.id, e.target.value);
                                        }}
                                        onBlur={handleTaskBlur}
                                        onKeyDown={(e) => handleTaskKeyDown(e, task.id)}
                                        className="flex-1 bg-[#001100] border border-[#39ff14]/50 text-[#39ff14] px-2 py-1 outline-none focus:border-[#39ff14]"
                                        autoFocus
                                      />
                                    ) : (
                                      <span 
                                        onClick={() => {
                                          setEditingTaskId(task.id);
                                          setEditingTaskText(task.text);
                                        }}
                                        className={`flex-1 ${task.completed ? 'line-through text-[#006600]' : 'text-[#00dd00] group-hover:text-[#39ff14] group-hover:drop-shadow-[0_0_5px_#39ff14]'}`}
                                      >
                                        {task.text}
                                      </span>
                                    )}
                                </div>
                             ))}
                        </div>
                    </div>
                    {/* COMMS */}
                    <div className="relative p-6 flex flex-col text-xs overflow-hidden bg-black">
                        <div className="flex justify-between items-center mb-4 pb-2 border-b border-[#39ff14]/30 text-[#39ff14]">
                             <span className="font-bold tracking-[0.2em] flex items-center gap-2"><Radio size={14} className="animate-pulse" /> UPLINK_ESTABLISHED</span>
                             <span className="text-[9px] text-[#005500]">CH_04</span>
                        </div>
                        <div className="overflow-y-auto space-y-3 mb-4 pr-2 uplink-scrollbar" style={{ height: '200px' }}>
                            {chatLog.map((msg, i) => (
                                <div key={i} className="flex flex-col animate-in slide-in-from-left-2 duration-300">
                                    <span className="text-[9px] text-[#006600] uppercase mb-0.5 tracking-wider">{msg.sender} &gt;</span>
                                    <span className="text-[#00cc00] pl-2 border-l-2 border-[#003300] py-1">{msg.text}</span>
                                </div>
                            ))}
                        </div>
                        <form onSubmit={sendChatMessage} className="flex gap-3 pt-2 bg-[#001100] p-2 border border-[#003300]">
                            <span className="text-[#39ff14] animate-pulse">&gt;</span>
                            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} disabled={isChatLoading} className="flex-1 bg-transparent border-none outline-none text-[#39ff14] placeholder-[#004400] font-bold disabled:opacity-50" placeholder={isChatLoading ? "PROCESSING..." : "ENTER_COMMAND..."} autoFocus />
                            <button type="submit" disabled={isChatLoading} className="text-[#005500] hover:text-[#39ff14] disabled:opacity-50"><Send size={14} /></button>
                        </form>
                    </div>
                    </div>
                  </>
                )}
                </div>
                
                {/* Gemini Map Tab */}
                <div 
                  className="w-full h-full absolute inset-0"
                  style={{ display: tabs[activeTabIndex] === 'gemini-map' ? 'block' : 'none' }}
                >
                  <GeminiMapView />
                </div>
                
                {/* Placeholder Tabs */}
                {tabs.map((tab, index) => {
                  if (tab === 'lockin' || tab === 'gemini-map') return null;
                  return (
                    <div 
                      key={tab}
                      className="w-full h-full absolute inset-0 flex items-center justify-center p-8 relative z-10"
                      style={{ display: activeTabIndex === index ? 'flex' : 'none' }}
                    >
                      <div className="text-center">
                        <div className="text-[#39ff14] text-2xl font-mono font-bold mb-4 tracking-wider">TAB {index + 1}</div>
                        <div className="text-[#00cc00] text-sm font-mono">Placeholder content for {tab}</div>
                      </div>
                    </div>
                  );
                })}
                {!powerOn && <div className="absolute inset-0 bg-[#080808] z-40 flex items-center justify-center"><div className="w-1 h-1 bg-white rounded-full opacity-50 shadow-[0_0_20px_white] animate-ping duration-[3000ms]"></div></div>}
             </div>
          </div>
          
          {/* Phone Detection Notification */}
          {showPhoneNotification && (
            <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 animate-in slide-in-from-top-2 duration-300">
              <div className="bg-red-900/95 border-2 border-red-500 rounded-sm p-4 shadow-[0_0_20px_rgba(255,0,0,0.5)] backdrop-blur-sm">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                  <div className="text-[#39ff14] font-mono text-sm font-bold">
                    ⚠️ PHONE DETECTED - TURN OFF CAMERA ⚠️
                  </div>
                </div>
                <div className="mt-2 text-[#ff6b6b] text-xs font-mono">
                  Detections: {phoneDetectionCount} | Please turn off your camera to maintain focus.
                </div>
              </div>
            </div>
          )}
          <div className="w-full mt-6 flex justify-between items-center px-8 md:px-12">
              <div className="flex items-center gap-4">
                  <button onClick={() => setPowerOn(!powerOn)} className="group relative w-12 h-12 bg-[#202020] rounded-full shadow-[0_5px_10px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.1)] flex items-center justify-center active:translate-y-1 active:shadow-inner transition-all border border-[#333]">
                      <Power size={20} className={`transition-colors duration-300 ${powerOn ? 'text-green-500 drop-shadow-[0_0_5px_rgba(34,197,94,0.8)]' : 'text-red-900'}`} />
                  </button>
                  <div className="flex flex-col gap-1"><div className="text-[8px] font-black text-stone-400 tracking-widest uppercase">Power</div><div className={`w-2 h-2 rounded-full transition-all duration-500 ${powerOn ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-900'}`}></div></div>
              </div>
              <div className="flex gap-6">
                 <div className="hidden md:flex gap-2">{[1,2,3,4].map(i => <div key={i} className="w-2 h-8 bg-[#151515] rounded-full shadow-[inset_0_1px_2px_rgba(0,0,0,1)] border-b border-white/10"></div>)}</div>
                 <div className="flex gap-2">
                     <button 
                       onClick={(e) => {
                         e.preventDefault();
                         e.stopPropagation();
                         // Cycle to previous tab (wrap around)
                         setActiveTabIndex((prev) => (prev - 1 + tabs.length) % tabs.length);
                       }}
                       className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center transition-all cursor-pointer hover:bg-[#353535]"
                     >
                       A
                     </button>
                     <button 
                       onClick={(e) => {
                         e.preventDefault();
                         e.stopPropagation();
                         // Cycle to next tab (wrap around)
                         setActiveTabIndex((prev) => (prev + 1) % tabs.length);
                       }}
                       className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center transition-all cursor-pointer hover:bg-[#353535]"
                     >
                       B
                     </button>
                 </div>
              </div>
          </div>
       </div>
    </div>
    </>
  );
}