import React, { useRef, useState, useEffect, useMemo } from 'react';
import { RotateCcw, Download, Radio, Send, Power, Video, VideoOff, Check, Play, ClipboardList } from 'lucide-react';

export default function LockInView({ availableQuests = [], sendFile, selectedAlgorithm, setSelectedAlgorithm, ditheredPreviewUrl, setDitheredPreviewUrl, fileInputRef, takePhotoRef }) {
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
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.hostname || '127.0.0.1';
      const port = 8000;
      return `${proto}://${host}:${port}/ws/phone-detect`;
    } catch (e) {
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
    if (detectionWsRef.current) return;
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
        try { const msg = JSON.parse(ev.data); if (msg.type === 'detection') setDetectionState(msg); } catch (e) { }
      };
      ws.onclose = () => {
        setDetectionConnState('offline');
        if (detectionIntervalRef.current) { clearInterval(detectionIntervalRef.current); detectionIntervalRef.current = null; }
        detectionWsRef.current = null;
        if (cameraActive) scheduleReconnect();
      };
      ws.onerror = () => { try { ws.close(); } catch (e) {} };
    } catch (e) {
      setDetectionConnState('offline');
      scheduleReconnect();
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
      connectWS();
    }
    if (!cameraActive) stopDetection();
    return () => { stopDetection(); if (video) video.removeEventListener('playing', onPlaying); };
  }, [cameraActive, videoReady]);

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
    dets.forEach(d => {
      const bb = d.bbox || {};
      const x = (bb.x || 0) * w;
      const y = (bb.y || 0) * h;
      const bw = (bb.w || 0) * w;
      const bh = (bb.h || 0) * h;
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(57,255,20,0.9)';
      ctx.strokeRect(x, y, bw, bh);
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.fillRect(x, y - 18, Math.max(60, ctx.measureText(d.class || '').width + 12), 18);
      ctx.fillStyle = '#39ff14';
      ctx.font = '12px monospace';
      ctx.fillText(`${d.class || ''} ${(d.confidence||0).toFixed(2)}`, x + 6, y - 4);
    });
  }, [detectionState]);

  useEffect(() => {
    let interval = null;
    if (timerRunning && timeLeft > 0) interval = setInterval(() => setTimeLeft(t => t - 1), 1000);
    else if (timeLeft === 0) setTimerRunning(false);
    return () => clearInterval(interval);
  }, [timerRunning, timeLeft]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
    const secs = (seconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const toggleTimerMode = () => { const newMode = timerMode === 'WORK' ? 'BREAK' : 'WORK'; setTimerMode(newMode); setTimerRunning(false); setTimeLeft(newMode === 'WORK' ? 25 * 60 : 5 * 60); };
  const toggleTask = (id) => setTasks(tasks.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
  const importTasks = () => { const newTasks = availableQuests.map(q => ({ id: Math.random(), text: q.name || q.title || 'Quest', completed: false })); setTasks([...tasks, ...newTasks]); };
  const sendChatMessage = (e) => { e.preventDefault(); if (!chatInput.trim()) return; const newLog = [...chatLog, { sender: 'OPERATIVE', text: chatInput }]; setChatLog(newLog); const captured = chatInput; setChatInput(''); setTimeout(() => setChatLog(prev => [...prev, { sender: 'HANDLER', text: `Copy that. Logging: "${captured}".` }]), 1000); };

  return (
    <div className="fixed left-0 right-0 top-16 bottom-0 flex items-stretch justify-center p-0 bg-transparent z-40">
       <div className="relative bg-[#dcdcdc] p-6 md:p-8 rounded-none shadow-[0_30px_60px_rgba(0,0,0,0.8),inset_0_2px_5px_rgba(255,255,255,0.4),inset_0_-5px_10px_rgba(0,0,0,0.1)] w-full h-full flex flex-col border-b-[12px] border-r-[12px] border-[#b0b0b0] transition-all overflow-hidden">
          <div className="w-full flex justify-between items-center mb-4 px-4">
              <div className="flex gap-2"><div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div><div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div></div>
              <div className="text-sm font-black text-stone-500 tracking-[0.2em] italic font-serif flex items-center gap-2"><div className="w-4 h-4 bg-red-600 rounded-sm"></div> SONY TRINITRON</div>
          </div>
          <div className="relative flex-1 bg-[#050505] rounded-[2rem] p-2 md:p-3 shadow-[inset_0_5px_15px_rgba(0,0,0,1),0_0_0_8px_#151515]">
             <div className="relative w-full h-full bg-[#0a100a] rounded-[1.5rem] overflow-hidden shadow-[inset_0_0_80px_rgba(0,0,0,0.9)] ring-1 ring-white/5 flex font-mono">
                <div className="absolute inset-0 z-50 pointer-events-none mix-blend-overlay bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(0,255,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%]"></div>
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
                        </div>
                        <div className="flex-1 bg-[#020a02] rounded-sm mt-4 overflow-hidden relative border border-[#39ff14]/20 shadow-[inset_0_0_20px_rgba(57,255,20,0.05)]">
                             {cameraActive ? (
                                <>
                                  <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover opacity-80 contrast-125 saturate-0 sepia hue-rotate-[50deg] brightness-125" />
                                  <canvas ref={overlayRef} className="absolute inset-0 w-full h-full pointer-events-none" />
                                </>
                            ) : (
                                <div className="w-full h-full flex flex-col items-center justify-center text-[#004400]"><VideoOff size={32} className="mb-2 opacity-50" /><span className="text-xs tracking-widest">NO SIGNAL</span></div>
                            )}
                            <button onClick={toggleCamera} className="absolute bottom-4 right-4 text-[#39ff14] hover:text-white transition-colors p-2 border border-[#39ff14]/30 bg-[#002200]/50 rounded-sm">
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
                    </div>
                    {/* OBJECTIVES */}
                    <div className="relative border-r border-[#39ff14]/30 p-6 flex flex-col text-xs overflow-hidden bg-black">
                        <div className="flex justify-between items-center mb-4 pb-2 border-b border-[#39ff14]/30 text-[#39ff14]">
                             <span className="font-bold tracking-[0.2em] flex items-center gap-2"><ClipboardList size={14} /> ACTIVE_DIRECTIVES</span>
                             <button onClick={importTasks} className="hover:text-white hover:drop-shadow-[0_0_5px_white] transition-all"><Download size={14} /></button>
                        </div>
                        <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar pr-2">
                             {tasks.length === 0 && <div className="text-[#004400] italic text-center py-4">:: NO DATA ::</div>}
                             {tasks.map(task => (
                                <div key={task.id} onClick={() => toggleTask(task.id)} className={`cursor-pointer group flex items-start gap-3 p-2 border border-transparent hover:border-[#39ff14]/40 hover:bg-[#002200]/50 transition-all ${task.completed ? 'opacity-40' : 'opacity-100'}`}>
                                    <div className={`w-3 h-3 mt-0.5 border border-[#39ff14] flex items-center justify-center ${task.completed ? 'bg-[#39ff14] text-black' : ''}`}>{task.completed && <Check size={10} strokeWidth={4} />}</div>
                                    <span className={`${task.completed ? 'line-through text-[#006600]' : 'text-[#00dd00] group-hover:text-[#39ff14] group-hover:drop-shadow-[0_0_5px_#39ff14]'}`}>{task.text}</span>
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
                        <div className="flex-1 overflow-y-auto space-y-3 mb-4 custom-scrollbar pr-2">
                            {chatLog.map((msg, i) => (
                                <div key={i} className="flex flex-col animate-in slide-in-from-left-2 duration-300">
                                    <span className="text-[9px] text-[#006600] uppercase mb-0.5 tracking-wider">{msg.sender} &gt;</span>
                                    <span className="text-[#00cc00] pl-2 border-l-2 border-[#003300] py-1">{msg.text}</span>
                                </div>
                            ))}
                        </div>
                        <form onSubmit={sendChatMessage} className="flex gap-3 pt-2 bg-[#001100] p-2 border border-[#003300]">
                            <span className="text-[#39ff14] animate-pulse">&gt;</span>
                            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} className="flex-1 bg-transparent border-none outline-none text-[#39ff14] placeholder-[#004400] font-bold" placeholder="ENTER_COMMAND..." autoFocus />
                            <button type="submit" className="text-[#005500] hover:text-[#39ff14]"><Send size={14} /></button>
                        </form>
                    </div>
                </div>
                {!powerOn && <div className="absolute inset-0 bg-[#080808] z-40 flex items-center justify-center"><div className="w-1 h-1 bg-white rounded-full opacity-50 shadow-[0_0_20px_white] animate-ping duration-[3000ms]"></div></div>}
             </div>
          </div>
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
                     <button className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center">A</button>
                     <button className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center">B</button>
                 </div>
              </div>
          </div>
       </div>
    </div>
  );
}