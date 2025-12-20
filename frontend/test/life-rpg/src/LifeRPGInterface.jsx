import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Brain, 
  Activity, 
  Zap, 
  Map, 
  User, 
  Terminal, 
  Target, 
  ChevronRight,
  ShieldAlert,
  Hexagon,
  Ghost,
  Lock,
  Star,
  Clock,
  Calendar,
  Swords,
  Paperclip,
  PenTool,
  FileText,
  Briefcase,
  Heart,
  Users,
  Lightbulb,
  CheckCircle,
  Circle,
  Diamond,
  Plus,
  Minus,
  Maximize,
  ClipboardList,
  RotateCcw,
  Download,
  Radio,
  Send,
  Power,
  Video,
  VideoOff,
  Mic,
  Keyboard,
  BarChart2,
  Check,
  Fingerprint,
  Search,
  X,
  Settings,
  ArrowRight,
  Play,
  Pause
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import TypewriterText from './components/onboarding/TypewriterText';
import VoiceLogsPanel from './components/onboarding/VoiceLogsPanel';
import CalendarView from './components/calendar/CalendarView';
import QuestItem from './components/dashboard/QuestItem';
import SkillItem from './components/dashboard/SkillItem';
import TimelineItem from './components/dashboard/TimelineItem';

// --- ONBOARDING COMPONENTS ---

// `TypewriterText` and `VoiceLogsPanel` have been extracted to
// `src/components/onboarding/TypewriterText.jsx` and
// `src/components/onboarding/VoiceLogsPanel.jsx` and are imported above.

const architectOpening =
  "Listen kid, I've seen a lot of people come through that door. Most of 'em don't know what they want. But you? You got that look. The look of someone who's gotta find their way outta this concrete jungle. So here's what I need to know: in some perfect future, when that alarm clock goes off and you're finally livin' the dream—what's the first thing you do?";

const OnboardingModule = ({ onFinish }) => {
  const [step, setStep] = useState(1); // 1: Login, 2: Mode Selection, 3: Transcript
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState(null); // 'voice' or 'text'
  const [isTypingDone, setIsTypingDone] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [onboardingProgress, setOnboardingProgress] = useState(0); // Progress bar state
  // Initialize history with the Architect's opening line so it appears inside the scrollable chat.
  const [messages, setMessages] = useState([
    { role: 'assistant', content: architectOpening },
  ]);
  const [isSending, setIsSending] = useState(false);
  const playbackContextRef = useRef(null);
  const ttsSocketRef = useRef(null);
  const introSpokenRef = useRef(false);
  const speechRecognitionRef = useRef(null);

  const handleLogin = (e) => {
    e.preventDefault();
    if (username.trim() && password.trim()) {
      setStep(2);
    }
  };

  const handleModeSelect = (selectedMode) => {
    console.debug('[Onboarding] mode selected:', selectedMode);
    setMode(selectedMode);
    setStep(3);

    if (selectedMode === 'voice' && !introSpokenRef.current) {
      introSpokenRef.current = true;
      console.debug('[VoiceLogs] sending Architect opening line to ElevenLabs TTS (on mode select)');
      sendTtsText(architectOpening);
    }
  };

  useEffect(() => {
    console.debug('[Onboarding] step/mode changed:', step, mode);
  }, [step, mode]);

  useEffect(() => () => {
    if (ttsSocketRef.current && ttsSocketRef.current.readyState === WebSocket.OPEN) {
      ttsSocketRef.current.close();
    }
    if (speechRecognitionRef.current) {
      try {
        speechRecognitionRef.current.onresult = null;
        speechRecognitionRef.current.onend = null;
        speechRecognitionRef.current.onerror = null;
        speechRecognitionRef.current.stop();
      } catch (e) {
        // ignore cleanup errors
      }
    }
  }, []);

  const ensureTtsSocket = () => {
    if (ttsSocketRef.current && ttsSocketRef.current.readyState === WebSocket.OPEN) {
      return ttsSocketRef.current;
    }

    const ws = new WebSocket('ws://127.0.0.1:8000/ws/voice');
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      console.log('[TTS] WebSocket to /ws/voice opened');
    };

    ws.onmessage = async (event) => {
      const { data } = event;
      if (typeof data === 'string') {
        // Optional: log status/error messages from the backend.
        console.log('[TTS] text message from backend:', data);
        return;
      }

      try {
        let arrayBuffer;
        if (data instanceof ArrayBuffer) {
          arrayBuffer = data;
        } else if (data instanceof Blob) {
          arrayBuffer = await data.arrayBuffer();
        } else {
          console.warn('[TTS] unsupported binary message type from backend:', data);
          return;
        }
        console.log('[TTS] received audio buffer from backend:', arrayBuffer.byteLength, 'bytes');

        const AudioCtxPlayback = window.AudioContext || window.webkitAudioContext;
        const ctx = playbackContextRef.current || new AudioCtxPlayback();
        playbackContextRef.current = ctx;

        if (ctx.state === 'suspended') {
          try {
            await ctx.resume();
          } catch (resumeErr) {
            console.warn('[TTS] failed to resume AudioContext:', resumeErr);
          }
        }

        // Use callback-style decodeAudioData, which works across browsers and
        // avoids the confusion between promise and callback forms.
        await new Promise((resolve, reject) => {
          ctx.decodeAudioData(
            arrayBuffer,
            (audioBuffer) => {
              try {
                const sourceNode = ctx.createBufferSource();
                sourceNode.buffer = audioBuffer;
                sourceNode.connect(ctx.destination);
                sourceNode.start();
                resolve();
              } catch (playErr) {
                reject(playErr);
              }
            },
            (decodeErr) => {
              reject(decodeErr || new Error('Unknown decodeAudioData error'));
            },
          );
        });
      } catch (err) {
        console.error('[TTS] error playing back audio from backend:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('[TTS] WebSocket error:', err);
    };

    ws.onclose = () => {
      console.debug('[TTS] WebSocket to /ws/voice closed');
      ttsSocketRef.current = null;
    };

    ttsSocketRef.current = ws;
    return ws;
  };

  const sendTtsText = (text) => {
    const trimmed = (text || '').trim();
    if (!trimmed) return;

    const ws = ensureTtsSocket();
    if (!ws) return;

    console.log('[TTS] sending text over /ws/voice:', trimmed.slice(0, 80));

    const payload = { type: 'tts-text', text: trimmed };

    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    } else {
      ws.addEventListener('open', () => {
        ws.send(JSON.stringify(payload));
      }, { once: true });
    }
  };

  const handleToggleRecording = async () => {
    console.debug('[VoiceLogs] toggle recording clicked. Current state:', isRecording);

    // Ensure the TTS socket exists so replies can still be spoken.
    ensureTtsSocket();

    // --- END TTS AUDIO CONTEXT WHEN RECORDING STARTS ---
    if (!isRecording && playbackContextRef.current) {
      try {
        await playbackContextRef.current.close();
        playbackContextRef.current = null;
      } catch (e) {
        console.warn('[VoiceLogs] Error closing TTS AudioContext:', e);
      }
    }

    const SpeechRecognition =
      typeof window !== 'undefined'
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;

    if (!SpeechRecognition) {
      console.warn('[VoiceLogs] SpeechRecognition API not available in this browser.');
      setIsRecording(false);
      return;
    }

    if (!speechRecognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event) => {
        try {
          const result = event.results[0][0];
          const transcript = result && result.transcript ? result.transcript : '';
          console.log('[VoiceLogs] STT result:', transcript);
          if (transcript) {
            // For Voice Logs, auto-send the recognized text as a turn to the
            // Architect instead of requiring a separate "Send" action.
            void sendUserTurn(transcript);
          }
        } catch (err) {
          console.error('[VoiceLogs] error handling STT result:', err);
        }
      };

      recognition.onend = () => {
        console.log('[VoiceLogs] STT recognition ended');
        setIsRecording(false);
      };

      recognition.onerror = (event) => {
        console.error('[VoiceLogs] STT recognition error:', event.error || event);
        setIsRecording(false);
      };

      speechRecognitionRef.current = recognition;
    }

    // Toggle recording: start if currently off, stop if on.
    setIsRecording((prev) => {
      const next = !prev;
      try {
        if (next) {
          console.log('[VoiceLogs] starting STT recognition');
          speechRecognitionRef.current.start();
        } else {
          console.log('[VoiceLogs] stopping STT recognition');
          speechRecognitionRef.current.stop();
        }
      } catch (e) {
        console.error('[VoiceLogs] error toggling STT recognition:', e);
      }
      return next;
    });
  };
  const sendUserTurn = async (content) => {
    const trimmed = (content || '').trim();
    if (!trimmed) return;

    setIsSending(true);

    try {
      // History for the backend: full prior turns (including the Architect opening).
      const historyPayload = messages;

      const res = await fetch("http://127.0.0.1:8000/api/onboarding/architect-reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: historyPayload,
          user_input: trimmed,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to reach Architect backend");
      }
      const data = await res.json();

      let reply = data.reply || "";
      let progress = 0;
      // Regex: [Progress: ... 20%] or [Progress: ...] 20%
      // 1. [Progress: ... 20%]
      let match = reply.match(/\[Progress:[^\]]*?(\d{1,3})%\]/i);
      if (!match) {
        // 2. [Progress: ...] 20%
        match = reply.match(/\[Progress:[^\]]*?\]\s*(\d{1,3})%/i);
      }
      if (match) {
        progress = Math.max(0, Math.min(100, parseInt(match[1], 10)));
        setOnboardingProgress(progress);
        // Remove the entire [Progress: ... 20%] or [Progress: ...] 20% from the reply
        reply = reply.replace(/\[Progress:[^\]]*?(\d{1,3})%\]/i, "").replace(/\[Progress:[^\]]*?\]\s*(\d{1,3})%/i, "").trim();
      }

      if (reply) {
        sendTtsText(reply);
      }

      // Append the user line and the Architect reply (with progress string stripped) into the local chat log.
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        data.reply ? { role: "assistant", content: reply } : null,
      ].filter(Boolean));
      setUserInput("");
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        {
          role: "assistant",
          content:
            "The line went static trying to reach the Architect. We'll keep your answer on record and try again later.",
        },
      ]);
      setUserInput("");
    } finally {
      setIsSending(false);
    }
  };

  const handleUserSubmit = async (e) => {
    e.preventDefault();
    await sendUserTurn(userInput);
  };

  const handleFinish = () => {
    if (onFinish) {
      onFinish({ username });
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-stone-900 flex items-center justify-center p-4 font-sans">
      {/* Local scrollbar styling so onboarding uses the same slim grey bar as the main app */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #a8a29e; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #78716c; }
      `}</style>
      {/* Background Ambience */}
      <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: `url('https://www.transparenttextures.com/patterns/aged-paper.png')` }}></div>
      
      {/* The Case Folder */}
      <div className={`relative w-full max-w-4xl bg-[#d4c5a9] rounded-sm shadow-2xl transition-all duration-700 ease-in-out min-h-[600px] flex flex-col overflow-hidden border-t-2 border-l-2 border-[#e6dcc5] border-b-4 border-r-4 border-[#8c7b5d] ${step === 3 ? 'rotate-0' : 'rotate-1'}`}>
        
        {/* Folder Tab */}
        <div className="absolute -top-8 left-0 w-48 h-10 bg-[#d4c5a9] rounded-t-lg border-t-2 border-l-2 border-[#e6dcc5] flex items-center justify-center">
            <span className="font-mono text-stone-600 font-bold tracking-widest text-xs">CASE FILE #2025-X</span>
        </div>

        {/* Paper Texture Overlay */}
        <div className="absolute inset-0 opacity-[0.15] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        {/* --- PAGE 1: LOGIN / ACCOUNT CREATION --- */}
        {step === 1 && (
          <div className="flex-1 p-12 flex flex-col items-center justify-center relative animate-in fade-in zoom-in-95 duration-500">
             <div className="absolute top-8 right-8 text-red-900 border-4 border-red-900/50 p-2 font-black text-xl uppercase -rotate-12 opacity-40 mix-blend-multiply">
                RESTRICTED ACCESS
             </div>
             
             <h2 className="font-serif text-3xl text-stone-900 font-bold mb-8 tracking-tight border-b-2 border-stone-800 pb-2">Identity Verification</h2>
             
             <form onSubmit={handleLogin} className="w-full max-w-sm space-y-6 relative z-10">
                <div className="space-y-2 group">
                    <label className="block font-mono text-xs font-bold text-stone-600 tracking-widest uppercase group-focus-within:text-stone-900">Operative Codename</label>
                    <div className="relative">
                        <User size={16} className="absolute left-0 top-3 text-stone-500" />
                        <input 
                            type="text" 
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full bg-transparent border-b-2 border-stone-400 py-2 pl-6 font-mono text-lg text-stone-900 focus:outline-none focus:border-stone-800 transition-colors placeholder-stone-500/30 uppercase"
                            placeholder="ENTER NAME"
                            autoFocus
                            autoComplete="off"
                        />
                    </div>
                </div>

                <div className="space-y-2 group">
                    <label className="block font-mono text-xs font-bold text-stone-600 tracking-widest uppercase group-focus-within:text-stone-900">Clearance Code</label>
                    <div className="relative">
                        <Lock size={16} className="absolute left-0 top-3 text-stone-500" />
                        <input 
                            type="password" 
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full bg-transparent border-b-2 border-stone-400 py-2 pl-6 font-mono text-lg text-stone-900 focus:outline-none focus:border-stone-800 transition-colors placeholder-stone-500/30"
                            placeholder="••••••••"
                        />
                    </div>
                </div>

                <div className="pt-8">
                    <button 
                        type="submit"
                        disabled={!username.trim() || !password.trim()}
                        className="w-full bg-stone-900 text-[#e8dcc5] py-4 font-bold tracking-[0.2em] uppercase hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg flex items-center justify-center gap-2 group border border-stone-700"
                    >
                        <span>Authenticate</span>
                        <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                    </button>
                    <div className="text-center mt-4">
                        <span className="text-[10px] font-mono text-stone-500 opacity-60">
                            WARNING: UNAUTHORIZED ACCESS IS A CLASS A FELONY
                        </span>
                    </div>
                </div>
             </form>
             
             <div className="absolute bottom-6 left-6 opacity-30">
                <Fingerprint size={64} className="text-stone-800" />
             </div>
          </div>
        )}

        {/* --- PAGE 2: EVIDENCE / SELECTION --- */}
        {step === 2 && (
          <div className="flex-1 p-12 flex flex-col items-center justify-center relative animate-in fade-in zoom-in-95 duration-500">
             <div className="absolute top-8 right-8 text-red-900 border-4 border-red-900/50 p-2 font-black text-xl uppercase -rotate-12 opacity-40 mix-blend-multiply">
                Evidence
             </div>
             
             <div className="absolute top-8 left-8">
                 <div className="text-[10px] font-mono text-stone-500">OPERATIVE:</div>
                 <div className="font-bold text-stone-800 font-mono text-sm uppercase">{username}</div>
             </div>
             
             <h2 className="font-serif text-3xl text-stone-900 font-bold mb-2 tracking-tight">Choose Your Protocol</h2>
             <p className="font-mono text-stone-700 mb-12 text-sm">How should we document this investigation?</p>

             <div className="flex flex-col md:flex-row gap-12 items-center justify-center">
                
                {/* Polaroid 1: Voice */}
                <button 
                  onClick={() => handleModeSelect('voice')}
                  className="group relative bg-white p-3 pb-12 shadow-[0_10px_20px_rgba(0,0,0,0.2)] hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] transform -rotate-3 hover:rotate-0 hover:scale-105 transition-all duration-300 w-64"
                >
                  <div className="bg-stone-200 aspect-square w-full flex items-center justify-center overflow-hidden grayscale group-hover:grayscale-0 transition-all duration-500 border border-stone-300">
                    <img src="https://images.unsplash.com/photo-1590602847861-f357a9332bbc?q=80&w=800&auto=format&fit=crop" className="object-cover w-full h-full opacity-80 mix-blend-multiply" alt="Voice" />
                    <div className="absolute">
                        <div className="bg-stone-900 text-white p-4 rounded-full"><Mic size={32} /></div>
                    </div>
                  </div>
                  <div className="font-handwriting text-stone-800 text-xl font-bold text-center mt-4 rotate-1 font-serif">Voice Logs</div>
                  <div className="absolute -top-4 -left-4 w-24 h-8 bg-stone-300/50 backdrop-blur-sm -rotate-45 transform translate-y-4"></div> {/* Tape effect */}
                </button>

                {/* Polaroid 2: Text */}
                <button 
                  onClick={() => handleModeSelect('text')}
                  className="group relative bg-white p-3 pb-12 shadow-[0_10px_20px_rgba(0,0,0,0.2)] hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] transform rotate-2 hover:rotate-0 hover:scale-105 transition-all duration-300 w-64"
                >
                   <div className="bg-stone-200 aspect-square w-full flex items-center justify-center overflow-hidden grayscale group-hover:grayscale-0 transition-all duration-500 border border-stone-300">
                    <img src="https://images.unsplash.com/photo-1587829741301-dc798b91add4?q=80&w=800&auto=format&fit=crop" className="object-cover w-full h-full opacity-80 mix-blend-multiply" alt="Text" />
                    <div className="absolute">
                        <div className="bg-stone-900 text-white p-4 rounded-full"><Keyboard size={32} /></div>
                    </div>
                  </div>
                  <div className="font-handwriting text-stone-800 text-xl font-bold text-center mt-4 -rotate-1 font-serif">Transcript</div>
                  <div className="absolute -top-4 -right-4 w-24 h-8 bg-stone-300/50 backdrop-blur-sm rotate-45 transform translate-y-4"></div> {/* Tape effect */}
                </button>

             </div>
          </div>
        )}

        {/* --- PAGE 3: TRANSCRIPT --- */}
        {step === 3 && (
          <div className="flex-1 p-8 md:p-16 flex flex-col relative animate-in fade-in slide-in-from-right-8 duration-700 bg-[#f4e9d5]">
             {/* Paper Header with Progress Bar to the Right */}
             <div className="border-b border-stone-400 pb-4 mb-8 flex justify-between items-end">
                <div className="flex items-center gap-4">
                  <div className="border border-stone-800 p-1 rounded-sm"><Fingerprint size={32} className="text-stone-800" /></div>
                  <div>
                    <h3 className="font-mono font-bold text-lg tracking-widest text-stone-900 uppercase">Official Transcript</h3>
                    <div className="text-xs font-mono text-stone-500">SUBJECT: {username.toUpperCase()} // MODE: {mode.toUpperCase()}</div>
                  </div>
                </div>
                {/* Progress Bar to the right of header */}
                <div className="flex flex-col items-end min-w-[120px] ml-8">
                  <div className="w-32 h-2 bg-stone-300 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-stone-800 transition-all duration-500"
                      style={{ width: `${onboardingProgress}%` }}
                    ></div>
                  </div>
                  <div className="text-xs font-mono text-stone-500 mt-1 text-right">{onboardingProgress}%</div>
                </div>
                <div className="text-right hidden md:block">
                  <div className="text-xs font-mono text-stone-500">TIMESTAMP</div>
                  <div className="font-mono text-stone-800">{new Date().toLocaleTimeString()}</div>
                </div>
             </div>

             {/* Typing Area + Scrollable Transcript (inline styling, no bubbles) */}
             <div className="flex-1 font-mono text-stone-800 text-sm md:text-base leading-relaxed space-y-6 max-w-2xl">
               {(() => {
                  // Find index of the most recent Architect message for typewriter animation.
                  const lastArcIndex = messages.reduce((acc, m, idx) => (m.role === 'assistant' ? idx : acc), -1);

                  return (
                  <div className="mt-6 space-y-4">
                    <div className="h-48 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                      {messages.length === 0 && (
                        <div className="text-[11px] text-stone-500 italic">
                          Start the tape. Tell the Architect what that perfect morning looks like.
                        </div>
                      )}

                      {messages.map((m, idx) => {
                        const label = m.role === 'user' ? 'You:' : 'ARC:';
                        const isArc = m.role === 'assistant';
                        const isLatestArc = isArc && idx === lastArcIndex;

                        return (
                          <div key={idx} className="flex gap-4">
                            <div className="font-bold text-stone-500 select-none w-10 text-right">
                              {label}
                            </div>
                            <div className={isArc ? 'min-h-[80px]' : 'min-h-[40px]'}>
                              {isArc && isLatestArc ? (
                                <>
                                  <TypewriterText
                                    speed={25}
                                    text={m.content}
                                    onComplete={() => setIsTypingDone(true)}
                                  />
                                  <span className="animate-pulse inline-block w-2 h-4 bg-stone-800 ml-1 align-middle"></span>
                                </>
                              ) : (
                                <span className="whitespace-pre-wrap">{m.content}</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Bottom controls: text chat or voice recording, same layout */}
                    {mode === 'text' && (
                      <form onSubmit={handleUserSubmit} className="flex flex-col gap-2 pt-2">
                        <input
                          value={userInput}
                          onChange={(e) => setUserInput(e.target.value)}
                          className="bg-[#f9f0dd] border border-[#d4c5a9] rounded-sm px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-500"
                          placeholder="You: In that perfect future, first thing I do is..."
                        />
                        <div className="flex items-center gap-3">
                          <button
                            type="submit"
                            className="px-3 py-1.5 bg-stone-900 text-[#e8dcc5] text-[11px] font-mono uppercase tracking-wider rounded-sm border border-stone-800 hover:bg-black disabled:opacity-60 disabled:cursor-not-allowed"
                            disabled={isSending}
                          >
                            {isSending ? "Sending..." : "Send"}
                          </button>
                          <span className="text-[11px] text-stone-600">
                            This answer goes straight into your case file.
                          </span>
                        </div>
                      </form>
                    )}

                    {mode === 'voice' && (
                      <VoiceLogsPanel
                        isRecording={isRecording}
                        onToggleRecording={handleToggleRecording}
                      />
                    )}
                  </div>
                  );
                })()}
             </div>

             {/* Footer Action */}
             <div className={`mt-auto flex justify-end transition-opacity duration-1000 ${isTypingDone ? 'opacity-100' : 'opacity-0'}`}>
                <button 
                  onClick={handleFinish}
                  className="bg-stone-800 text-[#e8dcc5] px-8 py-3 rounded-sm font-bold tracking-widest hover:bg-stone-900 transition-colors shadow-lg flex items-center gap-2 group"
                >
                  <span>ACCESS DASHBOARD</span>
                  <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />
                </button>
             </div>
             
             {/* Decorative Stamp */}
             <div className="absolute bottom-12 left-12 border-4 border-stone-800/20 p-2 rounded-full w-32 h-32 flex items-center justify-center -rotate-12 pointer-events-none mix-blend-multiply">
               <div className="text-stone-800/20 font-black text-center text-xs leading-tight">
                  DEPARTMENT OF<br/>HABIT FORMATION<br/>APPROVED
               </div>
             </div>
          </div>
        )}
      </div>
    </div>
  );
};

// --- FULL SKILL TREE DATA ---
const skillTreeJson = {
    "nodes": [
        { "id": "goal_build_and_adapt_code", "name": "Build and Adapt Code", "type": "Goal", "pillar": "CAREER", "prerequisites": [ "skill_self_assessment___exploration", "skill_basic_coding_fundamentals", "skill_data_analysis_introduction", "skill_pandas_library", "skill_sql_database_fundamentals", "skill_project_based_learning", "skill_career_transition___networking" ], "xp_reward": 100, "xp_multiplier": 1.0, "required_completions": 30, "description": "Focus on developing and adapting code independently, demonstrating resilience and problem-solving skills." },
        { "id": "skill_self_assessment___exploration", "name": "Self-Assessment & Exploration", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_journaling___reflect_on_the_day", "habit_identify_1_area_for_improvement", "habit_read_a_relevant_article_or_blog_post" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_basic_coding_fundamentals", "name": "Basic Coding Fundamentals", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_codecademy___30_minutes", "habit_solve_a_simple_coding_challenge", "habit_read_a_coding_tutorial" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_data_analysis_introduction", "name": "Data Analysis Introduction", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_datacamp___30_minutes", "habit_explore_a_public_dataset", "habit_watch_a_data_analysis_tutorial" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_pandas_library", "name": "Pandas Library", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_pandas_tutorial___45_minutes", "habit_practice_with_a_dataset", "habit_read_pandas_documentation" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_sql_database_fundamentals", "name": "SQL Database Fundamentals", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_sql_tutorial___30_minutes", "habit_practice_writing_sql_queries", "habit_explore_a_database_schema" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_project_based_learning", "name": "Project-Based Learning", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_brainstorm_project_ideas___15_minutes", "habit_break_down_a_project_into_smaller_tasks___30_minutes", "habit_work_on_a_project_for_60_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "skill_career_transition___networking", "name": "Career Transition & Networking", "type": "Sub-Skill", "pillar": "CAREER", "prerequisites": [ "habit_linkedin___connect_with_3_people", "habit_reach_out_to_a_contact___15_minutes", "habit_attend_a_virtual_networking_event___60_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Build and Adapt Code'." },
        { "id": "goal_exercise", "name": "Exercise", "type": "Goal", "pillar": "PHYSICAL", "prerequisites": [ "skill_recovery_foundation", "skill_sleep_hygiene", "skill_knee_pushup_progression", "skill_pushup_progression", "skill_incline_pushup_progression", "skill_floor_pushup_progression", "skill_diamond_pushup_progression", "skill_plyometric_progression" ], "xp_reward": 100, "xp_multiplier": 1.0, "required_completions": 30, "description": "Increase muscle mass through targeted exercise." },
        { "id": "skill_recovery_foundation", "name": "Recovery Foundation", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_mindful_breathing___5_minutes", "habit_hydration___drink_8_glasses_of_water", "habit_gentle_stretching___10_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_sleep_hygiene", "name": "Sleep Hygiene", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_digital_detox___1_hour_before_bed", "habit_consistent_sleep_schedule___maintain_a_regular_sleep_wake_cycle", "habit_relaxing_bedtime_routine___30_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_knee_pushup_progression", "name": "Knee Pushup Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_knee_pushups___3_sets_of_8_12_reps", "habit_rest___60_seconds_between_sets", "habit_progression___increase_reps_or_sets" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_pushup_progression", "name": "Pushup Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_wall_pushups___3_sets_of_10_15_reps", "habit_incline_pushups___3_sets_of_8_12_reps", "habit_rest___60_seconds_between_sets_2" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_incline_pushup_progression", "name": "Incline Pushup Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_incline_pushups___3_sets_of_8_12_reps_2", "habit_decrease_incline___gradually_lower_the_surface", "habit_rest___60_seconds_between_sets_3" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_floor_pushup_progression", "name": "Floor Pushup Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_floor_pushups___3_sets_of_5_8_reps", "habit_modify___perform_pushups_with_hands_closer_together", "habit_rest___60_seconds_between_sets_4" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_diamond_pushup_progression", "name": "Diamond Pushup Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_diamond_pushups___3_sets_of_3_5_reps", "habit_rest___90_seconds_between_sets", "habit_progression___increase_reps_or_sets_2" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "skill_plyometric_progression", "name": "Plyometric Progression", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_box_jumps___3_sets_of_5_8_reps", "habit_rest___90_seconds_between_sets_2", "habit_progression___increase_box_height" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Exercise'." },
        { "id": "goal_spend_time_with_family_and_friends", "name": "Spend Time with Family and Friends", "type": "Goal", "pillar": "SOCIAL", "prerequisites": [ "skill_initial_social_assessment", "skill_manage_social_anxiety", "skill_active_listening_practice", "skill_develop_empathy", "skill_initiate_small_social_interactions", "skill_conflict_resolution_skills", "skill_strengthen_existing_relationships", "skill_leadership_through_connection" ], "xp_reward": 100, "xp_multiplier": 1.0, "required_completions": 30, "description": "Cultivate and maintain meaningful relationships with friends and family." },
        { "id": "skill_initial_social_assessment", "name": "Initial Social Assessment", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_observe_social_interactions___15_minutes", "habit_reflect_on_your_own_social_behavior___10_minutes", "habit_identify_a_social_skill_to_focus_on___5_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_manage_social_anxiety", "name": "Manage Social Anxiety", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_grounding_technique___5_minutes", "habit_positive_self_talk___10_minutes", "habit_exposure___start_with_small_social_interactions___30_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_active_listening_practice", "name": "Active Listening Practice", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_listen_attentively___30_minutes", "habit_paraphrase___summarize_what_you_heard", "habit_ask_clarifying_questions___15_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_develop_empathy", "name": "Develop Empathy", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_read_fiction___30_minutes", "habit_listen_to_podcasts___30_minutes", "habit_practice_perspective_taking___15_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_initiate_small_social_interactions", "name": "Initiate Small Social Interactions", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_smile_and_make_eye_contact___throughout_the_day", "habit_start_a_conversation___15_minutes", "habit_offer_a_compliment___5_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_conflict_resolution_skills", "name": "Conflict Resolution Skills", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_practice_active_listening___30_minutes", "habit_express_your_needs_clearly___15_minutes", "habit_brainstorm_solutions___30_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_strengthen_existing_relationships", "name": "Strengthen Existing Relationships", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_reach_out_to_a_loved_one___15_minutes", "habit_plan_a_quality_time_activity___30_minutes", "habit_express_gratitude___10_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "skill_leadership_through_connection", "name": "Leadership Through Connection", "type": "Sub-Skill", "pillar": "SOCIAL", "prerequisites": [ "habit_ask_for_input___15_minutes", "habit_recognize_and_appreciate_contributions___10_minutes", "habit_show_empathy_and_understanding___30_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Spend Time with Family and Friends'." },
        { "id": "goal_journaling", "name": "Journaling", "type": "Goal", "pillar": "MENTAL", "prerequisites": [ "skill_box_breathing_technique", "skill_thought_logging", "skill_cognitive_restructuring", "skill_self_compassion_practice", "skill_smart_goal_setting", "skill_growth_mindset_adoption", "skill_resilience_framework" ], "xp_reward": 100, "xp_multiplier": 1.0, "required_completions": 30, "description": "Daily journaling practice." },
        { "id": "skill_box_breathing_technique", "name": "Box Breathing Technique", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_practice_box_breathing___5_minutes", "habit_repeat_throughout_the_day___as_needed", "habit_focus_on_the_sensation_of_breath___10_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_thought_logging", "name": "Thought Logging", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_record_thoughts___10_minutes", "habit_identify_patterns___15_minutes", "habit_challenge_negative_thoughts___15_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_cognitive_restructuring", "name": "Cognitive Restructuring", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_identify_cognitive_distortions___15_minutes", "habit_challenge_distorted_thoughts___30_minutes", "habit_replace_distorted_thoughts___15_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_self_compassion_practice", "name": "Self-Compassion Practice", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_self_kindness___10_minutes", "habit_recognize_common_humanity___15_minutes", "habit_practice_self_acceptance___10_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_smart_goal_setting", "name": "SMART Goal Setting", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_define_a_smart_goal___15_minutes", "habit_break_down_the_goal___10_minutes", "habit_track_progress___5_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_growth_mindset_adoption", "name": "Growth Mindset Adoption", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_embrace_challenges___10_minutes", "habit_learn_from_mistakes___15_minutes", "habit_value_effort___10_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "skill_resilience_framework", "name": "Resilience Framework", "type": "Sub-Skill", "pillar": "MENTAL", "prerequisites": [ "habit_identify_coping_mechanisms___15_minutes", "habit_practice_self_care___30_minutes", "habit_seek_support___15_minutes" ], "xp_reward": 150, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skill needed for goal 'Journaling'." },
        { "id": "goal_fix_overcome_solitary_focus", "name": "Overcome Solitary Focus", "type": "Goal", "pillar": "PHYSICAL", "prerequisites": [ "skill_fix_recovery_skills_for_solitary_focus" ], "xp_reward": 500, "xp_multiplier": 1.0, "required_completions": 30, "description": "Recovery quest to remove debuff." },
        { "id": "skill_fix_recovery_skills_for_solitary_focus", "name": "Recovery Skills for Solitary Focus", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_mindful_movement___20_minutes", "habit_sensory_grounding___10_minutes", "habit_creative_expression___30_minutes" ], "xp_reward": 200, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skills to overcome debuff 'Solitary Focus'." },
        { "id": "goal_fix_overcome_negative_reaction_to_failure", "name": "Overcome Negative Reaction to Failure", "type": "Goal", "pillar": "PHYSICAL", "prerequisites": [ "skill_fix_recovery_skills_for_negative_reaction_to_failure" ], "xp_reward": 500, "xp_multiplier": 1.0, "required_completions": 30, "description": "Recovery quest to remove debuff." },
        { "id": "skill_fix_recovery_skills_for_negative_reaction_to_failure", "name": "Recovery Skills for Negative Reaction to Failure", "type": "Sub-Skill", "pillar": "PHYSICAL", "prerequisites": [ "habit_self_compassion___15_minutes", "habit_reframe_the_failure___20_minutes", "habit_focus_on_progress___10_minutes" ], "xp_reward": 200, "xp_multiplier": 1.0, "required_completions": 30, "description": "Skills to overcome debuff 'Negative Reaction to Failure'." },
        { "id": "habit_journaling___reflect_on_the_day", "name": "Journaling - Reflect on the day", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Spend 15 minutes writing about your experiences, emotions, and learnings." },
        { "id": "habit_identify_1_area_for_improvement", "name": "Identify 1 area for improvement", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Pinpoint one small area where you could have acted differently or learned something new." },
        { "id": "habit_read_a_relevant_article_or_blog_post", "name": "Read a relevant article or blog post", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Dedicate 30 minutes to reading content related to self-awareness or personal growth." },
        { "id": "habit_codecademy___30_minutes", "name": "Codecademy - 30 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Complete a lesson on a basic coding concept (e.g., variables, loops)." },
        { "id": "habit_solve_a_simple_coding_challenge", "name": "Solve a simple coding challenge", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Work through a beginner-friendly coding challenge on platforms like HackerRank or LeetCode." },
        { "id": "habit_read_a_coding_tutorial", "name": "Read a coding tutorial", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Read a short tutorial on a specific coding concept or library." },
        { "id": "habit_datacamp___30_minutes", "name": "DataCamp - 30 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Work through a module on data analysis fundamentals." },
        { "id": "habit_explore_a_public_dataset", "name": "Explore a public dataset", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Find a publicly available dataset and spend 30 minutes exploring it using a tool like Google Sheets or Excel." },
        { "id": "habit_watch_a_data_analysis_tutorial", "name": "Watch a data analysis tutorial", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Watch a video tutorial on a specific data analysis technique (e.g., data cleaning, visualization)." },
        { "id": "habit_pandas_tutorial___45_minutes", "name": "Pandas tutorial - 45 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Follow a tutorial on using Pandas for data manipulation and analysis." },
        { "id": "habit_practice_with_a_dataset", "name": "Practice with a dataset", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Load a small dataset into Pandas and practice applying different functions (e.g., filtering, sorting, grouping)." },
        { "id": "habit_read_pandas_documentation", "name": "Read Pandas documentation", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Spend 15 minutes reviewing the Pandas documentation for a specific function or method." },
        { "id": "habit_sql_tutorial___30_minutes", "name": "SQL tutorial - 30 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Complete a lesson on SQL basics (e.g., SELECT, FROM, WHERE)." },
        { "id": "habit_practice_writing_sql_queries", "name": "Practice writing SQL queries", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Write SQL queries to retrieve data from a sample database." },
        { "id": "habit_explore_a_database_schema", "name": "Explore a database schema", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Examine the schema of a database and understand the relationships between tables." },
        { "id": "habit_brainstorm_project_ideas___15_minutes", "name": "Brainstorm project ideas - 15 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Generate 3-5 potential project ideas that align with your interests and skills." },
        { "id": "habit_break_down_a_project_into_smaller_tasks___30_minutes", "name": "Break down a project into smaller tasks - 30 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Choose one project idea and break it down into smaller, manageable tasks." },
        { "id": "habit_work_on_a_project_for_60_minutes", "name": "Work on a project for 60 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Dedicate focused time to working on one of the smaller tasks." },
        { "id": "habit_linkedin___connect_with_3_people", "name": "LinkedIn - Connect with 3 people", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Connect with 3 professionals in your field on LinkedIn." },
        { "id": "habit_reach_out_to_a_contact___15_minutes", "name": "Reach out to a contact - 15 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Send a personalized message to a contact, expressing interest in their work or seeking advice." },
        { "id": "habit_attend_a_virtual_networking_event___60_minutes", "name": "Attend a virtual networking event - 60 minutes", "type": "Habit", "pillar": "CAREER", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Participate in a virtual networking event or webinar." },
        { "id": "habit_mindful_breathing___5_minutes", "name": "Mindful Breathing - 5 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Practice deep, mindful breathing to calm the nervous system." },
        { "id": "habit_hydration___drink_8_glasses_of_water", "name": "Hydration - Drink 8 glasses of water", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Ensure adequate hydration throughout the day." },
        { "id": "habit_gentle_stretching___10_minutes", "name": "Gentle Stretching - 10 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform gentle stretches to release tension in the body." },
        { "id": "habit_digital_detox___1_hour_before_bed", "name": "Digital Detox - 1 hour before bed", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Avoid screens (phone, computer, TV) for at least one hour before bedtime." },
        { "id": "habit_consistent_sleep_schedule___maintain_a_regular_sleep_wake_cycle", "name": "Consistent Sleep Schedule - Maintain a regular sleep-wake cycle", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Go to bed and wake up around the same time each day, even on weekends." },
        { "id": "habit_relaxing_bedtime_routine___30_minutes", "name": "Relaxing Bedtime Routine - 30 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Engage in a relaxing activity before bed (e.g., reading, taking a warm bath)." },
        { "id": "habit_knee_pushups___3_sets_of_8_12_reps", "name": "Knee Pushups - 3 sets of 8-12 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform knee pushups, focusing on proper form." },
        { "id": "habit_rest___60_seconds_between_sets", "name": "Rest - 60 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_progression___increase_reps_or_sets", "name": "Progression - Increase reps or sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Gradually increase the number of reps or sets as you get stronger." },
        { "id": "habit_wall_pushups___3_sets_of_10_15_reps", "name": "Wall Pushups - 3 sets of 10-15 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform wall pushups to build strength." },
        { "id": "habit_incline_pushups___3_sets_of_8_12_reps", "name": "Incline Pushups - 3 sets of 8-12 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform incline pushups using a stable surface." },
        { "id": "habit_rest___60_seconds_between_sets_2", "name": "Rest - 60 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_incline_pushups___3_sets_of_8_12_reps_2", "name": "Incline Pushups - 3 sets of 8-12 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform incline pushups using a stable surface." },
        { "id": "habit_decrease_incline___gradually_lower_the_surface", "name": "Decrease incline - Gradually lower the surface", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Reduce the height of the incline to increase difficulty." },
        { "id": "habit_rest___60_seconds_between_sets_3", "name": "Rest - 60 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_floor_pushups___3_sets_of_5_8_reps", "name": "Floor Pushups - 3 sets of 5-8 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform floor pushups, focusing on proper form." },
        { "id": "habit_modify___perform_pushups_with_hands_closer_together", "name": "Modify - Perform pushups with hands closer together", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Adjust hand placement to increase difficulty." },
        { "id": "habit_rest___60_seconds_between_sets_4", "name": "Rest - 60 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_diamond_pushups___3_sets_of_3_5_reps", "name": "Diamond Pushups - 3 sets of 3-5 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform diamond pushups, focusing on proper form." },
        { "id": "habit_rest___90_seconds_between_sets", "name": "Rest - 90 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_progression___increase_reps_or_sets_2", "name": "Progression - Increase reps or sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Gradually increase the number of reps or sets as you get stronger." },
        { "id": "habit_box_jumps___3_sets_of_5_8_reps", "name": "Box Jumps - 3 sets of 5-8 reps", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Perform box jumps, focusing on proper form." },
        { "id": "habit_rest___90_seconds_between_sets_2", "name": "Rest - 90 seconds between sets", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Allow adequate rest between sets." },
        { "id": "habit_progression___increase_box_height", "name": "Progression - Increase box height", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Gradually increase the height of the box as you get stronger." },
        { "id": "habit_observe_social_interactions___15_minutes", "name": "Observe social interactions - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Pay attention to how others interact in a social setting." },
        { "id": "habit_reflect_on_your_own_social_behavior___10_minutes", "name": "Reflect on your own social behavior - 10 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Consider how you typically behave in social situations." },
        { "id": "habit_identify_a_social_skill_to_focus_on___5_minutes", "name": "Identify a social skill to focus on - 5 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Choose one specific social skill you'd like to improve." },
        { "id": "habit_grounding_technique___5_minutes", "name": "Grounding Technique - 5 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Practice grounding techniques (e.g., 5-4-3-2-1 method) to manage anxiety." },
        { "id": "habit_positive_self_talk___10_minutes", "name": "Positive Self-Talk - 10 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Challenge negative thoughts and replace them with positive affirmations." },
        { "id": "habit_exposure___start_with_small_social_interactions___30_minutes", "name": "Exposure - Start with small social interactions - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Gradually expose yourself to social situations, starting with small, manageable interactions." },
        { "id": "habit_listen_attentively___30_minutes", "name": "Listen attentively - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Focus entirely on the speaker without interrupting or formulating a response." },
        { "id": "habit_paraphrase___summarize_what_you_heard", "name": "Paraphrase - Summarize what you heard", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Repeat back what you heard in your own words to ensure understanding." },
        { "id": "habit_ask_clarifying_questions___15_minutes", "name": "Ask clarifying questions - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Ask questions to gain a deeper understanding of the speaker's perspective." },
        { "id": "habit_read_fiction___30_minutes", "name": "Read fiction - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Read novels or short stories to gain insight into different perspectives." },
        { "id": "habit_listen_to_podcasts___30_minutes", "name": "Listen to podcasts - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Listen to podcasts featuring diverse voices and experiences." },
        { "id": "habit_practice_perspective_taking___15_minutes", "name": "Practice perspective-taking - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Try to imagine yourself in someone else's shoes and understand their feelings." },
        { "id": "habit_smile_and_make_eye_contact___throughout_the_day", "name": "Smile and make eye contact - Throughout the day", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Practice smiling and making eye contact with people you encounter." },
        { "id": "habit_start_a_conversation___15_minutes", "name": "Start a conversation - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Initiate a brief conversation with someone you don't know well." },
        { "id": "habit_offer_a_compliment___5_minutes", "name": "Offer a compliment - 5 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Give a genuine compliment to someone." },
        { "id": "habit_practice_active_listening___30_minutes", "name": "Practice active listening - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Focus on understanding the other person's perspective." },
        { "id": "habit_express_your_needs_clearly___15_minutes", "name": "Express your needs clearly - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Communicate your needs and feelings assertively but respectfully." },
        { "id": "habit_brainstorm_solutions___30_minutes", "name": "Brainstorm solutions - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Work collaboratively to find mutually agreeable solutions." },
        { "id": "habit_reach_out_to_a_loved_one___15_minutes", "name": "Reach out to a loved one - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Call, text, or email someone you care about." },
        { "id": "habit_plan_a_quality_time_activity___30_minutes", "name": "Plan a quality time activity - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Schedule time to spend with someone you value." },
        { "id": "habit_express_gratitude___10_minutes", "name": "Express gratitude - 10 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Tell someone you appreciate them." },
        { "id": "habit_ask_for_input___15_minutes", "name": "Ask for input - 15 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Solicit opinions and ideas from others." },
        { "id": "habit_recognize_and_appreciate_contributions___10_minutes", "name": "Recognize and appreciate contributions - 10 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Acknowledge and celebrate the efforts of team members." },
        { "id": "habit_show_empathy_and_understanding___30_minutes", "name": "Show empathy and understanding - 30 minutes", "type": "Habit", "pillar": "SOCIAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Demonstrate genuine care and concern for others." },
        { "id": "habit_practice_box_breathing___5_minutes", "name": "Practice Box Breathing - 5 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Inhale for 4 seconds, hold for 4 seconds, exhale for 4 seconds, hold for 4 seconds." },
        { "id": "habit_repeat_throughout_the_day___as_needed", "name": "Repeat throughout the day - As needed", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Use box breathing whenever you feel stressed or anxious." },
        { "id": "habit_focus_on_the_sensation_of_breath___10_minutes", "name": "Focus on the sensation of breath - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Pay attention to the rise and fall of your chest or abdomen." },
        { "id": "habit_record_thoughts___10_minutes", "name": "Record thoughts - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Write down your thoughts and feelings as they arise." },
        { "id": "habit_identify_patterns___15_minutes", "name": "Identify patterns - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Review your logs to identify recurring themes or thought patterns." },
        { "id": "habit_challenge_negative_thoughts___15_minutes", "name": "Challenge negative thoughts - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Question the validity of negative thoughts and replace them with more realistic ones." },
        { "id": "habit_identify_cognitive_distortions___15_minutes", "name": "Identify cognitive distortions - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Learn about common cognitive distortions (e.g., catastrophizing, all-or-nothing thinking)." },
        { "id": "habit_challenge_distorted_thoughts___30_minutes", "name": "Challenge distorted thoughts - 30 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Examine the evidence for and against distorted thoughts." },
        { "id": "habit_replace_distorted_thoughts___15_minutes", "name": "Replace distorted thoughts - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Develop more balanced and realistic thoughts." },
        { "id": "habit_self_kindness___10_minutes", "name": "Self-kindness - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Treat yourself with the same kindness and understanding you would offer a friend." },
        { "id": "habit_recognize_common_humanity___15_minutes", "name": "Recognize common humanity - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Remind yourself that everyone makes mistakes and experiences suffering." },
        { "id": "habit_practice_self_acceptance___10_minutes", "name": "Practice self-acceptance - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Accept yourself, flaws and all." },
        { "id": "habit_define_a_smart_goal___15_minutes", "name": "Define a SMART goal - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Ensure your goal is Specific, Measurable, Achievable, Relevant, and Time-bound." },
        { "id": "habit_break_down_the_goal___10_minutes", "name": "Break down the goal - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Divide the goal into smaller, manageable steps." },
        { "id": "habit_track_progress___5_minutes", "name": "Track progress - 5 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Monitor your progress and make adjustments as needed." },
        { "id": "habit_embrace_challenges___10_minutes", "name": "Embrace challenges - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "View challenges as opportunities for growth." },
        { "id": "habit_learn_from_mistakes___15_minutes", "name": "Learn from mistakes - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Analyze your mistakes and identify what you can learn from them." },
        { "id": "habit_value_effort___10_minutes", "name": "Value effort - 10 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Recognize that effort is more important than innate talent." },
        { "id": "habit_identify_coping_mechanisms___15_minutes", "name": "Identify coping mechanisms - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "List strategies you use to cope with stress and adversity." },
        { "id": "habit_practice_self_care___30_minutes", "name": "Practice self-care - 30 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Engage in activities that promote your physical and mental well-being." },
        { "id": "habit_seek_support___15_minutes", "name": "Seek support - 15 minutes", "type": "Habit", "pillar": "MENTAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Connect with trusted friends, family members, or a therapist." },
        { "id": "habit_mindful_movement___20_minutes", "name": "Mindful Movement - 20 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Engage in gentle movement like yoga or tai chi." },
        { "id": "habit_sensory_grounding___10_minutes", "name": "Sensory Grounding - 10 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Focus on sensory experiences (e.g., touch, smell, taste) to reconnect with the present moment." },
        { "id": "habit_creative_expression___30_minutes", "name": "Creative Expression - 30 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Engage in a creative activity like drawing, writing, or playing music." },
        { "id": "habit_self_compassion___15_minutes", "name": "Self-Compassion - 15 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Practice self-kindness and understanding when experiencing failure." },
        { "id": "habit_reframe_the_failure___20_minutes", "name": "Reframe the failure - 20 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Challenge negative interpretations of the failure and focus on what you learned." },
        { "id": "habit_focus_on_progress___10_minutes", "name": "Focus on progress - 10 minutes", "type": "Habit", "pillar": "PHYSICAL", "prerequisites": [], "xp_reward": 15, "xp_multiplier": 1.0, "required_completions": 30, "description": "Recognize and celebrate small steps forward, regardless of setbacks." }
    ]
};

// --- DATA PROCESSING UTILS ---
// Default / fallback character sheet used until a real profile is loaded.
const rawCharacterSheet = {
    "user_id": "OPERATIVE_01",
    "goals": {
        "CAREER": {
            "name": "Build and Adapt Code",
            "pillar": "CAREER",
            "current_quests": [],
            "needed_quests": [ "Self-Assessment & Exploration", "Basic Coding Fundamentals", "Data Analysis Introduction", "Pandas Library", "SQL Database Fundamentals", "Project-Based Learning", "Career Transition & Networking" ],
            "description": "Focus on developing and adapting code independently, demonstrating resilience and problem-solving skills."
        },
        "PHYSICAL": {
            "name": "Exercise",
            "pillar": "PHYSICAL",
            "current_quests": [ "Do plyometrics", "Do weight training" ],
            "needed_quests": [ "Recovery Foundation", "Sleep Hygiene", "Knee Pushup Progression", "Pushup Progression", "Incline Pushup Progression", "Floor Pushup Progression", "Diamond Pushup Progression", "Plyometric Progression" ],
            "description": "Increase muscle mass through targeted exercise."
        },
        "SOCIAL": {
            "name": "Spend Time with Family and Friends",
            "pillar": "SOCIAL",
            "current_quests": [],
            "needed_quests": [ "Initial Social Assessment", "Manage Social Anxiety", "Active Listening Practice", "Develop Empathy", "Initiate Small Social Interactions", "Conflict Resolution Skills", "Strengthen Existing Relationships", "Leadership Through Connection" ],
            "description": "Cultivate and maintain meaningful relationships with friends and family."
        },
        "MENTAL": {
            "name": "Journaling",
            "pillar": "MENTAL",
            "current_quests": [],
            "needed_quests": [ "Box Breathing Technique", "Thought Logging", "Cognitive Restructuring", "Self-Compassion Practice", "SMART Goal Setting", "Growth Mindset Adoption", "Resilience Framework" ],
            "description": "Daily journaling practice."
        }
    },
    "stats_career": { "Learn to Code": 6, "Build and Adapt Code": 9, "Research and Experiment": 7 },
    "stats_physical": { "Exercise": 8 },
    "stats_mental": { "Journaling": 8, "Problem Solving": 6 },
    "stats_social": { "Volleyball": 6, "Spend Time with Family and Friends": 9, "Communication Style": 7 },
    "debuffs": [ "Solitary Focus", "Negative Reaction to Failure" ],
    "habit_progress": {
        "habit_journaling___reflect_on_the_day": { "node_id": "habit_journaling___reflect_on_the_day", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_identify_1_area_for_improvement": { "node_id": "habit_identify_1_area_for_improvement", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_read_a_relevant_article_or_blog_post": { "node_id": "habit_read_a_relevant_article_or_blog_post", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_codecademy___30_minutes": { "node_id": "habit_codecademy___30_minutes", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_solve_a_simple_coding_challenge": { "node_id": "habit_solve_a_simple_coding_challenge", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_read_a_coding_tutorial": { "node_id": "habit_read_a_coding_tutorial", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_datacamp___30_minutes": { "node_id": "habit_datacamp___30_minutes", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_explore_a_public_dataset": { "node_id": "habit_explore_a_public_dataset", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        "habit_watch_a_data_analysis_tutorial": { "node_id": "habit_watch_a_data_analysis_tutorial", "status": "ACTIVE", "completed_total": 1, "completed_since_last_report": 1, "last_completed_date": "2025-12-17", "streak_days": 0 },
        // Fallback for missing entries if any
    }
};

// --- COMPONENT: TREE VISUALIZER ---
const TreeVisualizer = ({ pillar, skillTree, characterSheet }) => {
    // State for Pan and Zoom
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
    const [isDragging, setIsDragging] = useState(false);
    const [startPan, setStartPan] = useState({ x: 0, y: 0 });
    // State for Hover (Tooltip) - ensures only the specific node is hovered
    const [hoveredNodeId, setHoveredNodeId] = useState(null);

    const layout = useMemo(() => {
        // 1. Filter Nodes
        const nodesSource = (skillTree && skillTree.nodes) ? skillTree.nodes : skillTreeJson.nodes;
        const pillarNodes = nodesSource.filter(n => n.pillar === pillar);
        const goalNode = pillarNodes.find(n => n.type === 'Goal');
        
        if (!goalNode) return { nodes: [], edges: [], width: 800 };

        // 2. Build Hierarchy
        const hierarchy = {
            goal: goalNode,
            skills: [],
        };

        // Find Skills linked to Goal
        if (goalNode.prerequisites) {
            goalNode.prerequisites.forEach(skillId => {
                const skillNode = pillarNodes.find(n => n.id === skillId);
                if (skillNode) {
                    const skillObj = { ...skillNode, habits: [] };
                    // Find Habits linked to Skill
                    if (skillNode.prerequisites) {
                        skillNode.prerequisites.forEach(habitId => {
                            const habitNode = pillarNodes.find(n => n.id === habitId) || { id: habitId, name: habitId.replace(/_/g, ' ').replace('habit ', ''), type: 'Habit', required_completions: 10 }; // Fallback
                            skillObj.habits.push(habitNode);
                        });
                    }
                    hierarchy.skills.push(skillObj);
                }
            });
        }

        // 3. Calculate Geometry
        const NODE_WIDTH = 140;
        const NODE_SPACING = 40;
        const HABIT_WIDTH = 100;
        
        let currentX = 50;
        const processedNodes = [];
        const processedEdges = [];

        // Y-Levels
        const Y_GOAL = 100;
        const Y_SKILL = 350;
        const Y_HABIT = 600;

        hierarchy.skills.forEach(skill => {
            const habitCount = skill.habits.length || 1;
            const skillWidth = habitCount * (HABIT_WIDTH + 20);
            const skillCenterX = currentX + (skillWidth / 2);

            processedNodes.push({ ...skill, x: skillCenterX, y: Y_SKILL });
            processedEdges.push({ x1: 0, y1: Y_GOAL + 40, x2: skillCenterX, y2: Y_SKILL - 30, id: `edge-${hierarchy.goal.id}-${skill.id}` });

            skill.habits.forEach((habit, idx) => {
                const habitX = currentX + (idx * (HABIT_WIDTH + 20)) + (HABIT_WIDTH/2);

                // --- PROGRESS CALCULATION ---
                const progressData = characterSheet?.habit_progress?.[habit.id];
                const completed = progressData?.completed_total || 0;
                const required = habit.required_completions || 1; 
                const progressPercent = Math.min(100, Math.max(0, (completed / required) * 100));
                
                // Determine status (default to LOCKED if not in progress map or explicitly active)
                const status = progressData?.status === 'ACTIVE' ? 'ACTIVE' : 'LOCKED';

                processedNodes.push({ 
                    ...habit, 
                    x: habitX, 
                    y: Y_HABIT, 
                    progressPercent, 
                    status,
                    completed,
                    required
                });
                processedEdges.push({ x1: skillCenterX, y1: Y_SKILL + 30, x2: habitX, y2: Y_HABIT - 20, id: `edge-${skill.id}-${habit.id}` });
            });

            currentX += skillWidth + NODE_SPACING;
        });

        const totalWidth = currentX;
        const goalX = totalWidth / 2;
        processedNodes.push({ ...hierarchy.goal, x: goalX, y: Y_GOAL });

        processedEdges.forEach(e => { if (e.y1 === Y_GOAL + 40) e.x1 = goalX; });

        return { nodes: processedNodes, edges: processedEdges, width: totalWidth };

      }, [pillar, skillTree, characterSheet]);

    // Zoom Handlers
    useEffect(() => { setTransform({ x: 0, y: 0, k: 0.8 }); }, [pillar]);

    const handleWheel = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const container = e.currentTarget.getBoundingClientRect();
        const mouseX = e.clientX - container.left;
        const mouseY = e.clientY - container.top;

        const scaleSensitivity = 0.001;
        const delta = -e.deltaY * scaleSensitivity;
        
        let newScale = transform.k + delta;
        newScale = Math.min(Math.max(0.2, newScale), 3);

        const scaleRatio = newScale / transform.k;
        const newX = mouseX - (mouseX - transform.x) * scaleRatio;
        const newY = mouseY - (mouseY - transform.y) * scaleRatio;

        setTransform({ x: newX, y: newY, k: newScale });
    };

    const handleMouseDown = (e) => { setIsDragging(true); setStartPan({ x: e.clientX - transform.x, y: e.clientY - transform.y }); };
    const handleMouseMove = (e) => { if (!isDragging) return; e.preventDefault(); setTransform(prev => ({ ...prev, x: e.clientX - startPan.x, y: e.clientY - startPan.y })); };
    const handleMouseUp = () => setIsDragging(false);
    
    const zoomIn = () => { const newScale = Math.min(transform.k + 0.2, 3); setTransform(prev => ({ ...prev, k: newScale })); };
    const zoomOut = () => { const newScale = Math.max(transform.k - 0.2, 0.2); setTransform(prev => ({ ...prev, k: newScale })); };
    const resetZoom = () => setTransform({ x: 0, y: 0, k: 0.8 });

    return (
        <div 
            className="w-full h-full relative bg-[#f0f9ff] border-t-4 border-blue-900/10 overflow-hidden cursor-grab active:cursor-grabbing select-none"
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
        >
            <div 
                className="absolute origin-top-left transition-transform duration-75 ease-out"
                style={{ transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`, width: Math.max(layout.width, 2000), height: '2000px' }}
            >
               <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(#bae6fd 1px, transparent 1px), linear-gradient(90deg, #bae6fd 1px, transparent 1px)', backgroundSize: '30px 30px' }}></div>
               
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                    {layout.edges.map(e => {
                        if (isNaN(e.x1) || isNaN(e.y1) || isNaN(e.x2) || isNaN(e.y2)) return null;
                        // Ensure coordinates are valid numbers before rendering
                        const x1 = Number(e.x1) || 0;
                        const y1 = Number(e.y1) || 0;
                        const x2 = Number(e.x2) || 0;
                        const y2 = Number(e.y2) || 0;
                        return (
                            <path key={e.id} d={`M ${x1} ${y1} C ${x1} ${(y1+y2)/2} ${x2} ${(y1+y2)/2} ${x2} ${y2}`} stroke="#3b82f6" strokeWidth="2" fill="none" strokeOpacity="0.4" />
                        );
                    })}
                </svg>

                {layout.nodes.map(node => (
                    <div 
                        key={node.id}
                        className="absolute flex flex-col items-center justify-center transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10 hover:z-50"
                        style={{ left: node.x, top: node.y }}
                        onMouseEnter={() => setHoveredNodeId(node.id)}
                        onMouseLeave={() => setHoveredNodeId(null)}
                    >
                        {/* TOOLTIP FOR HABITS - Controlled by React State */}
                        {node.type === 'Habit' && hoveredNodeId === node.id && (
                            <div className="absolute bottom-full mb-3 bg-slate-900/95 backdrop-blur text-white p-3 rounded-lg shadow-xl z-50 w-56 text-xs border border-slate-700 pointer-events-none animate-in fade-in slide-in-from-bottom-2 duration-200">
                                <div className="font-bold text-sm mb-1 text-blue-200">{node.name}</div>
                                <div className="flex justify-between items-center mb-2 border-b border-slate-700 pb-1">
                                    <span className="text-slate-400">Progress</span>
                                    <span className="font-mono text-blue-400">{node.completed}/{node.required}</span>
                                </div>
                                <div className="text-slate-300 mb-2 leading-relaxed italic">"{node.description || ""}"</div>
                                <div className="flex justify-end">
                                    <span className="text-yellow-400 font-bold bg-yellow-400/10 px-1.5 py-0.5 rounded border border-yellow-400/20">+{node.xp_reward} XP</span>
                                </div>
                                {/* Tooltip Arrow */}
                                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900/95"></div>
                            </div>
                        )}

                        <div 
                            className={`flex items-center justify-center shadow-lg transition-all duration-300 relative overflow-hidden
                            ${node.type === 'Goal' ? 'w-24 h-24 bg-blue-600 text-white clip-hexagon z-30' : ''}
                            ${node.type === 'Sub-Skill' ? 'w-16 h-16 bg-white border-2 border-blue-500 rotate-45 z-20 hover:scale-110' : ''}
                            ${node.type === 'Habit' && node.status === 'ACTIVE' ? 'w-10 h-10 bg-blue-50 border-2 border-blue-400 rounded-full z-10 shadow-[0_0_15px_rgba(59,130,246,0.3)]' : ''}
                            ${node.type === 'Habit' && node.status === 'LOCKED' ? 'w-10 h-10 bg-slate-100 border-2 border-slate-300 rounded-full z-10 opacity-70 grayscale' : ''}
                        `}>
                            {/* HABIT FILL LOGIC */}
                            {node.type === 'Habit' && (
                                <div 
                                    className={`absolute bottom-0 left-0 right-0 transition-all duration-500 ease-in-out ${node.status === 'ACTIVE' ? 'bg-blue-500' : 'bg-slate-400'}`}
                                    style={{ height: `${node.progressPercent}%`, opacity: 0.3 }}
                                />
                            )}

                            <div className="relative z-10">
                                {node.type === 'Goal' && <Star size={40} />}
                                {node.type === 'Sub-Skill' && <div className="-rotate-45 text-blue-600"><Diamond size={24} /></div>}
                                {node.type === 'Habit' && <Circle size={14} className={node.status === 'ACTIVE' ? "text-blue-600" : "text-slate-400"} />}
                            </div>
                        </div>

                        <div className={`
                            mt-4 text-center font-mono font-bold pointer-events-none bg-white/90 backdrop-blur-sm px-2 py-0.5 rounded border border-slate-100 shadow-sm
                            ${node.type === 'Goal' ? 'text-xl text-blue-900 uppercase tracking-widest' : ''}
                            ${node.type === 'Sub-Skill' ? 'text-xs text-blue-800 w-32' : ''}
                            ${node.type === 'Habit' ? 'text-[10px] w-28 text-slate-600' : ''}
                        `}>
                            {node.name}
                            {/* Show percentage for active habits */}
                            {node.type === 'Habit' && node.status === 'ACTIVE' && (
                                <div className="text-[8px] text-blue-600 mt-0.5">{Math.round(node.progressPercent)}%</div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <div className="absolute bottom-4 right-4 flex flex-col gap-2 pointer-events-auto shadow-lg bg-white/50 backdrop-blur-sm p-1 rounded-lg border border-blue-200">
                <button onClick={zoomIn} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm transition-colors border border-blue-100"><Plus size={20} /></button>
                <button onClick={zoomOut} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm transition-colors border border-blue-100"><Minus size={20} /></button>
                <button onClick={resetZoom} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm transition-colors border border-blue-100" title="Reset View"><Maximize size={20} /></button>
            </div>
        </div>
    );
};

// Calendar and dashboard subcomponents have been extracted into
// `src/components/calendar/CalendarView.jsx` and
// `src/components/dashboard/*`. They are imported at the top of this file.

const LockInView = ({ availableQuests = [], sendFile, selectedAlgorithm, setSelectedAlgorithm, ditheredPreviewUrl, setDitheredPreviewUrl, fileInputRef, takePhotoRef }) => {
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const canvasRef = useRef(null);
  const pendingStreamRef = useRef(null);
  const detectionWsRef = useRef(null);
  const detectionIntervalRef = useRef(null);
  const [detectionState, setDetectionState] = useState({ detections: [] });
  const [videoReady, setVideoReady] = useState(false);
  const [lastSentFrameTs, setLastSentFrameTs] = useState(0);
  // Build detector WS URL based on current host; defaults to port 8000 where backend runs
  const DETECTOR_WS_URL = useMemo(() => {
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.hostname || '127.0.0.1';
      const port = 8000; // backend server port
      return `${proto}://${host}:${port}/ws/phone-detect`;
    } catch (e) {
      return 'ws://127.0.0.1:8000/ws/phone-detect';
    }
  }, []);
  const [detectionConnState, setDetectionConnState] = useState('idle'); // 'idle'|'connecting'|'connected'|'offline'
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
  // dither state and fileInputRef are provided by parent

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
        // store stream until video element mounts
        pendingStreamRef.current = stream;
        setCameraActive(true);
      } catch (err) { /* camera denied */ }
    }
  };

  // Detection: send frames to local WS server and draw overlays
  const sendFrame = async () => {
    try {
      const ws = detectionWsRef.current;
      const video = videoRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (!video) return;
      // ensure video has dimensions; if not ready, skip
      if (!video.videoWidth || !video.videoHeight) return;

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
      try {
        ws.send(JSON.stringify(payload));
      } catch (e) { /* ignore send errors */ }
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
        if (detectionIntervalRef.current) { clearInterval(detectionIntervalRef.current); }
        detectionIntervalRef.current = setInterval(sendFrame, 333); // ~3 FPS
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'detection') setDetectionState(msg);
        } catch (e) { /* parse error */ }
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

  const startDetection = () => {
    if (!cameraActive) return;
    if (detectionConnState === 'connected' || detectionConnState === 'connecting') return;
    connectWS();
  };

  const stopDetection = () => {
    try {
      if (reconnectTimerRef.current) { clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
      if (detectionIntervalRef.current) { clearInterval(detectionIntervalRef.current); detectionIntervalRef.current = null; }
      const ws = detectionWsRef.current;
      if (ws) {
        try { ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null; ws.close(); } catch (e) {}
        detectionWsRef.current = null;
      }
      backoffRef.current = 1000;
      setDetectionConnState('idle');
      setDetectionState({ detections: [] });
    } catch (e) { console.error('stopDetection', e); }
  };

  // expose capture to parent via takePhotoRef
  useEffect(() => {
    if (takePhotoRef) {
      takePhotoRef.current = takePhotoAndDither;
    }
    return () => {
      if (takePhotoRef && takePhotoRef.current === takePhotoAndDither) takePhotoRef.current = null;
    };
  }, [takePhotoRef, takePhotoAndDither]);

  useEffect(() => {
    const video = videoRef.current;
    function onPlaying() {
      console.debug('video playing event');
      setVideoReady(true);
    }

    if (cameraActive) {
      setVideoReady(false);
      if (video) {
        video.addEventListener('playing', onPlaying);
        // if video is already playing
        if (!video.paused && (video.readyState >= 2 || video.currentTime > 0)) {
          setVideoReady(true);
        }
      }
      // Connect WS immediately when camera is enabled so we can start sending once frames exist
      connectWS();
    }

    if (!cameraActive) stopDetection();

    return () => {
      stopDetection();
      if (video) video.removeEventListener('playing', onPlaying);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraActive, videoReady]);

  // Attach pending stream to video element when it becomes available/mounted
  useEffect(() => {
    const video = videoRef.current;
    if (cameraActive && pendingStreamRef.current && video) {
      try {
        console.debug('Attaching pending stream to video element');
        video.srcObject = pendingStreamRef.current;
        console.debug('pending stream tracks:', pendingStreamRef.current.getTracks().map(t => t.kind));
        pendingStreamRef.current = null;
        video.onloadedmetadata = () => {
          console.debug('video onloadedmetadata (effect):', video.videoWidth, video.videoHeight);
          setVideoReady(true);
          video.play().catch(e => console.debug('video.play on attach failed', e));
        };
      } catch (e) {
        console.error('error attaching pending stream', e);
      }
    }
    return () => {};
  }, [cameraActive]);

  // Draw overlay when detections update
  useEffect(() => {
    const canvas = overlayRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext('2d');
    const w = video.videoWidth || canvas.clientWidth || 320;
    const h = video.videoHeight || canvas.clientHeight || 240;
    canvas.width = w;
    canvas.height = h;
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

  const toggleTimerMode = () => {
    const newMode = timerMode === 'WORK' ? 'BREAK' : 'WORK';
    setTimerMode(newMode);
    setTimerRunning(false);
    setTimeLeft(newMode === 'WORK' ? 25 * 60 : 5 * 60);
  };

  const toggleTask = (id) => setTasks(tasks.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
  const importTasks = () => {
    const newTasks = availableQuests.map(q => ({ id: Math.random(), text: q.name || q.title || 'Quest', completed: false }));
    setTasks([...tasks, ...newTasks]);
  };

  const sendChatMessage = (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const newLog = [...chatLog, { sender: 'OPERATIVE', text: chatInput }];
    setChatLog(newLog);
    const captured = chatInput;
    setChatInput('');
    setTimeout(() => setChatLog(prev => [...prev, { sender: 'HANDLER', text: `Copy that. Logging: "${captured}".` }]), 1000);
  };

  return (
    <div className="fixed left-0 right-0 top-16 bottom-0 flex items-stretch justify-center p-0 bg-transparent z-40">
       <div className="relative bg-[#dcdcdc] p-6 md:p-8 rounded-none shadow-[0_30px_60px_rgba(0,0,0,0.8),inset_0_2px_5px_rgba(255,255,255,0.4),inset_0_-5px_10px_rgba(0,0,0,0.1)] w-full h-full flex flex-col border-b-[12px] border-r-[12px] border-[#b0b0b0] transition-all overflow-hidden">
          {/* Top Branding / Vents */}
          <div className="w-full flex justify-between items-center mb-4 px-4">
              <div className="flex gap-2">
                 <div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div>
                 <div className="w-16 h-2 bg-[#222] rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"></div>
              </div>
              <div className="text-sm font-black text-stone-500 tracking-[0.2em] italic font-serif flex items-center gap-2">
                  <div className="w-4 h-4 bg-red-600 rounded-sm"></div> SONY TRINITRON
              </div>
          </div>

          {/* SCREEN CONTAINER (GLASS) */}
          <div className="relative flex-1 bg-[#050505] rounded-[2rem] p-2 md:p-3 shadow-[inset_0_5px_15px_rgba(0,0,0,1),0_0_0_8px_#151515]">
             <div className="relative w-full h-full bg-[#0a100a] rounded-[1.5rem] overflow-hidden shadow-[inset_0_0_80px_rgba(0,0,0,0.9)] ring-1 ring-white/5 flex font-mono">
                <div className="absolute inset-0 z-50 pointer-events-none mix-blend-overlay bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(0,255,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%]"></div>
                <div className={`w-full h-full grid grid-cols-1 md:grid-cols-2 grid-rows-2 gap-0 transition-opacity duration-500 ${powerOn ? 'opacity-100' : 'opacity-0'}`}>
                    {/* QUADRANT 1: CAMERA */}
                    <div className="relative border-b md:border-r border-[#39ff14]/30 p-6 flex flex-col overflow-hidden group bg-black">
                        <div className="absolute top-3 left-4 text-[10px] font-bold tracking-widest z-20 flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${cameraActive ? 'bg-red-500 animate-pulse' : 'bg-[#003300]'}`}></div>
                          <div className="text-[#39ff14]">CAM_01 [MONITORING]</div>
                          <div className="ml-3 text-[10px] z-30">
                            {detectionConnState === 'connected' && <span className="text-[#39ff14]">DETECTOR: online</span>}
                            {detectionConnState === 'connecting' && <span className="text-[#ffb86b]">DETECTOR: connecting</span>}
                            {detectionConnState === 'offline' && <span className="text-[#ff6b6b]">DETECTOR: offline</span>}
                            {detectionConnState === 'idle' && <span className="text-[#888]">DETECTOR: idle</span>}
                            <div className="mt-1 text-[10px]">
                              {lastSentFrameTs && (Date.now() - lastSentFrameTs) < 3000 ? (
                                <span className="text-[#39ff14]">sending...</span>
                              ) : (
                                <span className="text-[#888]">not sending</span>
                              )}
                              <span className="ml-2 text-[#39ff14]">{(detectionState && detectionState.detections && detectionState.detections.length) || 0} hits</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex-1 bg-[#020a02] rounded-sm mt-4 overflow-hidden relative border border-[#39ff14]/20 shadow-[inset_0_0_20px_rgba(57,255,20,0.05)]">
                             {cameraActive ? (
                                <>
                                  <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover opacity-80 contrast-125 saturate-0 sepia hue-rotate-[50deg] brightness-125" />
                                  <canvas ref={overlayRef} className="absolute inset-0 w-full h-full pointer-events-none" />
                                  {/* debug info removed */}
                                </>
                            ) : (
                                <div className="w-full h-full flex flex-col items-center justify-center text-[#004400]">
                                    <VideoOff size={32} className="mb-2 opacity-50" />
                                    <span className="text-xs tracking-widest">NO SIGNAL</span>
                                </div>
                            )}
                            {/* Camera toggle for Lock-In page */}
                            <button onClick={toggleCamera} className="absolute bottom-4 right-4 text-[#39ff14] hover:text-white transition-colors p-2 border border-[#39ff14]/30 bg-[#002200]/50 rounded-sm">
                              {cameraActive ? <VideoOff size={16} /> : <Video size={16} />}
                            </button>
                            {/* Controls moved to Profile card per UX — camera quadrant shows only video/overlay */}
                        </div>
                    </div>

                    {/* QUADRANT 2: CHRONOMETER */}
                    <div className="relative border-b border-[#39ff14]/30 p-6 flex flex-col items-center justify-center bg-black">
                        <div className="absolute top-3 right-4 text-[10px] text-[#39ff14] font-bold tracking-widest opacity-70">SYS_CLOCK</div>
                        <div className={`text-7xl md:text-8xl lg:text-9xl font-bold tracking-tighter tabular-nums transition-all ${timerRunning ? 'text-[#39ff14] drop-shadow-[0_0_20px_rgba(57,255,20,0.8)]' : 'text-[#005500]'}`}>
                            {formatTime(timeLeft)}
                        </div>
                        <div className="w-full max-w-xs h-1 bg-[#002200] mt-6 rounded-full overflow-hidden">
                            <div className={`h-full bg-[#39ff14] shadow-[0_0_10px_#39ff14] transition-all duration-1000`} style={{ width: `${(timeLeft / (timerMode === 'WORK' ? 1500 : 300)) * 100}%` }} />
                        </div>
                        <div className="flex gap-6 mt-8">
                            <button onClick={() => setTimerRunning(!timerRunning)} className="text-[#39ff14] hover:text-white hover:drop-shadow-[0_0_10px_white] transition-all"><Play size={32} /></button>
                            <button onClick={() => setTimeLeft(timerMode === 'WORK' ? 1500 : 300)} className="text-[#008800] hover:text-[#39ff14] transition-colors"><RotateCcw size={24} /></button>
                        </div>
                        <div className="mt-6 flex gap-2 text-[10px] uppercase tracking-widest">
                            <button onClick={toggleTimerMode} className={`px-3 py-1 border border-[#39ff14]/30 transition-all ${timerMode === 'WORK' ? 'bg-[#39ff14] text-black font-bold shadow-[0_0_15px_#39ff14]' : 'text-[#008800] hover:text-[#39ff14]'}`}>{timerMode}</button>
                        </div>
                    </div>

                    {/* QUADRANT 3: OBJECTIVES */}
                    <div className="relative border-r border-[#39ff14]/30 p-6 flex flex-col text-xs overflow-hidden bg-black">
                        <div className="flex justify-between items-center mb-4 pb-2 border-b border-[#39ff14]/30 text-[#39ff14]">
                             <span className="font-bold tracking-[0.2em] flex items-center gap-2"><ClipboardList size={14} /> ACTIVE_DIRECTIVES</span>
                             <button onClick={importTasks} className="hover:text-white hover:drop-shadow-[0_0_5px_white] transition-all"><Download size={14} /></button>
                        </div>
                        <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar pr-2">
                             {tasks.length === 0 && <div className="text-[#004400] italic text-center py-4">:: NO DATA ::</div>}
                             {tasks.map(task => (
                                <div key={task.id} onClick={() => toggleTask(task.id)} className={`cursor-pointer group flex items-start gap-3 p-2 border border-transparent hover:border-[#39ff14]/40 hover:bg-[#002200]/50 transition-all ${task.completed ? 'opacity-40' : 'opacity-100'}`}>
                                    <div className={`w-3 h-3 mt-0.5 border border-[#39ff14] flex items-center justify-center ${task.completed ? 'bg-[#39ff14] text-black' : ''}`}>
                                        {task.completed && <Check size={10} strokeWidth={4} />}
                                    </div>
                                    <span className={`${task.completed ? 'line-through text-[#006600]' : 'text-[#00dd00] group-hover:text-[#39ff14] group-hover:drop-shadow-[0_0_5px_#39ff14]'}`}>{task.text}</span>
                                </div>
                             ))}
                        </div>
                    </div>

                    {/* QUADRANT 4: COMMS */}
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

                {/* --- POWER OFF BLACK SCREEN --- */}
                {!powerOn && (
                    <div className="absolute inset-0 bg-[#080808] z-40 flex items-center justify-center">
                        <div className="w-1 h-1 bg-white rounded-full opacity-50 shadow-[0_0_20px_white] animate-ping duration-[3000ms]"></div>
                    </div>
                )}
             </div>
          </div>

          {/* BOTTOM CONTROLS PANEL */}
          <div className="w-full mt-6 flex justify-between items-center px-8 md:px-12">
              <div className="flex items-center gap-4">
                  <button 
                    onClick={() => setPowerOn(!powerOn)}
                    className="group relative w-12 h-12 bg-[#202020] rounded-full shadow-[0_5px_10px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.1)] flex items-center justify-center active:translate-y-1 active:shadow-inner transition-all border border-[#333]"
                  >
                      <Power size={20} className={`transition-colors duration-300 ${powerOn ? 'text-green-500 drop-shadow-[0_0_5px_rgba(34,197,94,0.8)]' : 'text-red-900'}`} />
                  </button>
                  <div className="flex flex-col gap-1">
                      <div className="text-[8px] font-black text-stone-400 tracking-widest uppercase">Power</div>
                      <div className={`w-2 h-2 rounded-full transition-all duration-500 ${powerOn ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-900'}`}></div>
                  </div>
              </div>
               
              <div className="flex gap-6">
                 <div className="hidden md:flex gap-2">
                    {[1,2,3,4].map(i => (
                        <div key={i} className="w-2 h-8 bg-[#151515] rounded-full shadow-[inset_0_1px_2px_rgba(0,0,0,1)] border-b border-white/10"></div>
                    ))}
                 </div>
                 <div className="flex gap-2">
                     <button className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center">A</button>
                     <button className="w-8 h-8 bg-[#252525] rounded shadow-[0_2px_4px_rgba(0,0,0,0.4)] border-t border-white/10 active:translate-y-0.5 text-[8px] font-mono text-stone-500 font-bold flex items-center justify-center">B</button>
                 </div>
              </div>
          </div>

       </div>
    </div>
  );
};

// --- MAIN APPLICATION ---

export default function LifeRPGInterface() {
  const [activeTab, setActiveTab] = useState('sheet'); 
  const [activePillar, setActivePillar] = useState('CAREER');
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(true);

  // Live profile state (falls back to rawCharacterSheet / skillTreeJson until API load succeeds)
  const [characterSheet, setCharacterSheet] = useState(rawCharacterSheet);
  const [skillTree, setSkillTree] = useState(skillTreeJson);
  // Dithering / profile photo state (lifted so Profile and LockInView can share)
  const [ditheredPreviewUrl, setDitheredPreviewUrl] = useState(null);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('FloydSteinberg');
  const fileInputRef = useRef(null);
  const takePhotoRef = useRef(null); // LockInView will register its capture function here
  const isLockIn = activeTab === 'lockin';

  const sendFile = async (file, algorithmOverride) => {
    try {
      const alg = algorithmOverride || selectedAlgorithm || 'FloydSteinberg';
      const form = new FormData();
      form.append('file', file, file.name || 'photo.png');
      form.append('algorithm', alg);
      const proto = window.location.protocol === 'https:' ? 'https' : 'http';
      const host = window.location.hostname || '127.0.0.1';
      const port = 8000;
      const url = `${proto}://${host}:${port}/api/dither`;
      const resp = await fetch(url, { method: 'POST', body: form });
      if (!resp.ok) {
        console.error('dither failed', resp.statusText);
        return;
      }
      const blob = await resp.blob();
      const obj = URL.createObjectURL(blob);
      setDitheredPreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return obj; });
    } catch (e) {
      console.error('sendFile error', e);
    }
  };

  // --- DATA TRANSFORMATION LOGIC ---
  const displayData = useMemo(() => {
    const sheet = characterSheet || rawCharacterSheet;
    const tree = skillTree || skillTreeJson;

    const pillarStats = [
      { name: 'Career', value: Math.round(Object.values(sheet.stats_career || {}).reduce((a, b) => a + b, 0) / (Object.keys(sheet.stats_career || {}).length || 1)) },
      { name: 'Physical', value: Math.round(Object.values(sheet.stats_physical || {}).reduce((a, b) => a + b, 0) / (Object.keys(sheet.stats_physical || {}).length || 1)) },
      { name: 'Mental', value: Math.round(Object.values(sheet.stats_mental || {}).reduce((a, b) => a + b, 0) / (Object.keys(sheet.stats_mental || {}).length || 1)) },
      { name: 'Social', value: Math.round(Object.values(sheet.stats_social || {}).reduce((a, b) => a + b, 0) / (Object.keys(sheet.stats_social || {}).length || 1)) }
    ];

    const quests = [
      ...Object.values(sheet.goals).flatMap(g => g.current_quests.map(q => ({ name: q, status: 'active', pillar: g.pillar, description: g.description }))),
      ...Object.values(sheet.goals).flatMap(g => g.needed_quests.map(q => ({ name: q, status: 'pending', pillar: g.pillar, description: `Prerequisite for: ${g.name}` })))
    ]
    .filter((q, i, a) => a.findIndex(t => t.name === q.name) === i) // de-dupe
    .filter(q => {
      const progress = sheet.habit_progress || {};
      const node = tree.nodes.find(n => n.name === q.name);
      if (!node) return q.status === 'active'; // Keep active quests if node not found
      const habitProgress = progress[node.id];
      return habitProgress?.status === 'ACTIVE' || q.status === 'active';
    });

    const debuffs = sheet.debuffs.map(d => ({
      name: d,
      effect: "Status Effect",
      type: "Mental"
    }));

    // --- ADDED: Skills List for Profile Tab ---
    const skills = tree.nodes
      .filter(n => n.type === 'Sub-Skill')
      .map(n => ({ name: n.name, level: 1, pillar: n.pillar }));

    const analytics = {
      // Mocked data for performance analytics
      sessions: [
        { day: 'Mon', duration: 120, quality: 80 },
        { day: 'Tue', duration: 90, quality: 70 },
        { day: 'Wed', duration: 150, quality: 90 },
        { day: 'Thu', duration: 60, quality: 50 },
        { day: 'Fri', duration: 180, quality: 100 },
        { day: 'Sat', duration: 0, quality: 0 },
        { day: 'Sun', duration: 0, quality: 0 },
      ],
      // More metrics can be added here
    };

    const timeline = [
      { time: "08:00", event: "Wake up and meditate", status: "completed" },
      { time: "08:30", event: "Breakfast", status: "completed" },
      { time: "09:00", event: "Work on project", status: "active" },
      { time: "12:00", event: "Lunch break", status: "upcoming" },
      { time: "13:00", event: "Client meeting", status: "upcoming" },
      { time: "15:00", event: "Gym workout", status: "upcoming" },
      { time: "18:00", event: "Dinner with family", status: "upcoming" },
      { time: "20:00", event: "Read a book", status: "upcoming" },
      { time: "22:00", event: "Sleep", status: "upcoming" },
    ];

    const tabs = [
      { name: 'Profile', icon: User },
      { name: 'Blueprint', icon: Map },
      { name: 'Report', icon: ClipboardList },
      { name: 'Calendar', icon: Calendar },
      { name: 'Settings', icon: Settings },
    ];

    

    const mainGoal = {
      name: 'Chronicle Log',
      icon: Calendar,
      content: (
        <div className="space-y-4">
          {timeline.map((item, idx) => <TimelineItem key={idx} item={item} />)}
        </div>
      )
    };

    return { stats: pillarStats, quests, debuffs, analytics, timeline, tabs, mainGoal, skills, user_id: sheet.user_id };
  }, [characterSheet, skillTree]);

  const handleSelectQuest = (quest) => {
    console.log('Selected quest:', quest);
    // Add your quest handling logic here
  };
  
  const handleOnboardingFinish = (data) => {
    if (data?.username) {
        setCharacterSheet(prev => ({ ...prev, user_id: data.username }));
    }
    setShowOnboarding(false);
  };

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  // After onboarding is dismissed, try to load the real profile from the backend.
  useEffect(() => {
    if (showOnboarding) return;

    const fetchProfile = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/profile/user_01');
        if (!res.ok) return; // keep fallback data on failure
        const data = await res.json();
        if (data.character_sheet) {
          setCharacterSheet(data.character_sheet);
        }
        if (data.skill_tree) {
          setSkillTree(data.skill_tree);
        }
      } catch (e) {
        // Silent fallback to mock data
        console.error('Failed to load profile, using mock data.', e);
      }
    };

    fetchProfile();
  }, [showOnboarding]);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-900 flex flex-col items-center justify-center text-stone-200 font-mono">
        <div className="mb-4 animate-bounce"><FileText size={48} /></div>
        <div className="text-sm tracking-[0.3em] uppercase">Opening File...</div>
      </div>
    );
  }

  // --- ONBOARDING CHECK ---
  if (showOnboarding) {
    return <OnboardingModule onFinish={handleOnboardingFinish} />;
  }

  return (
    <div className={`min-h-screen font-sans selection:bg-yellow-200 overflow-x-hidden relative transition-colors duration-500 ${isLockIn ? 'bg-[#050505] text-[#39ff14]' : 'bg-stone-900 text-stone-800'}`}>
      
      {/* CSS For Scrollbar & Shapes */}
      <style>{`
        /* Slim grey scroll thumb with paper-colored track */
        .custom-scrollbar {
          scrollbar-width: thin;                    /* Firefox */
          scrollbar-color: #78716c #f4e9d5;         /* thumb / track colors */
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
          height: 5px;
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #f4e9d5; /* match transcript paper */
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #78716c;
          border-radius: 9999px;
          border: none;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #78716c;
        }
        .clip-hexagon { clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); }
      `}</style>

      {/* BACKGROUND */}
      <div className="fixed inset-0 z-0 bg-cover bg-center pointer-events-none" style={{ backgroundImage: `url('https://images.unsplash.com/photo-1615800098779-1be32e60cca3?q=80&w=2574&auto=format&fit=crop')` }}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.1)_0%,rgba(0,0,0,0.6)_100%)]" />
      </div>

      {/* HEADER */}
      <header className={`h-16 border-b flex items-center justify-between px-4 md:px-8 fixed w-full z-50 top-0 shadow-lg transition-all duration-500 ${isLockIn ? 'bg-black/90 border-[#39ff14]/30 backdrop-blur-none' : 'bg-stone-900/40 border-white/10 backdrop-blur-md'}`}>
        <div className="flex items-center gap-4">
           <div className="text-stone-100 font-black tracking-tighter flex items-center gap-2 text-xl drop-shadow-md">
             <div className="bg-stone-100 text-stone-900 p-1 rounded-sm"><Activity size={16} /></div> 
             LIFE_OS <span className="text-[10px] text-stone-300 font-mono font-normal mt-1 opacity-70">CONFIDENTIAL</span>
           </div>
        </div>

        <nav className="flex gap-2 bg-black/20 p-1 rounded-lg border border-white/10 backdrop-blur-sm">
          <button onClick={() => setActiveTab('sheet')} className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'sheet' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}>
            <User size={12} /> Profile
          </button>
          <button onClick={() => setActiveTab('map')} className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'map' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}>
            <Map size={12} /> Blueprint
          </button>
          <button onClick={() => setActiveTab('report')} className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'report' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}>
            <ClipboardList size={12} /> Report
          </button>
          <button onClick={() => setActiveTab('calendar')} className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'calendar' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}>
            <Calendar size={12} /> Calendar
          </button>
          <button onClick={() => setActiveTab('lockin')} className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'lockin' ? (isLockIn ? 'bg-[#39ff14] text-black shadow-[0_0_10px_#39ff14]' : 'bg-[#e8dcc5] text-stone-900 shadow-lg') : (isLockIn ? 'text-[#005500] hover:text-[#39ff14]' : 'text-stone-300 hover:text-white hover:bg-white/10')}`}>
            <Lock size={12} /> Lock-In
          </button>
        </nav>
      </header>

      {/* MAIN CONTENT AREA */}
      <main className="pt-24 pb-12 px-4 md:px-8 max-w-7xl mx-auto min-h-screen flex flex-col relative z-10">
        
        {/* VIEW 1: ONE PAGE DASHBOARD */}
        {activeTab === 'sheet' && (
          <div className="flex-1 flex flex-col gap-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* ... (Existing Sheet Content) ... */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:min-h-[600px] items-stretch perspective-1000">
              
              {/* LEFT: QUEST LOG */}
              <div className="bg-[#e8dcc5] rounded-sm shadow-[0_3px_10px_rgb(0,0,0,0.2)] flex flex-col overflow-hidden relative -rotate-1 hover:rotate-0 transition-transform duration-300 h-full border border-[#d4c5a9]">
                <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
                <div className="absolute -top-3 left-6 text-stone-400 z-20 drop-shadow-lg"><Paperclip size={28} className="rotate-12 text-[#5c564b]" /></div>
                <div className="p-5 border-b-2 border-[#d4c5a9] bg-[#dfd3bc]/30 flex justify-between items-center mt-3 relative z-10">
                  <h3 className="font-black text-stone-800 flex items-center gap-2 text-sm uppercase tracking-wide"><Terminal size={16} className="text-stone-600" /> Directives</h3>
                  <span className="text-[10px] bg-red-800/10 text-red-900 px-2 py-1 rounded-sm font-bold border border-red-800/20 shadow-sm">TOP SECRET</span>
                </div>
                <div className="flex-1 overflow-y-auto custom-scrollbar bg-[linear-gradient(transparent_23px,#d4c5a9_24px)] bg-[length:100%_24px] p-0 relative z-10 max-h-[500px]">
                  {displayData.quests.map((q, idx) => <QuestItem key={idx} quest={q} />)}
                  {displayData.quests.length === 0 && <div className="p-8 text-center text-stone-500 text-sm font-serif italic">No active directives found.</div>}
                  <div className="p-6 flex items-center justify-center text-stone-500 hover:text-stone-700 cursor-pointer transition-all group">
                    <span className="text-xs font-mono uppercase border-b border-dashed border-stone-400 group-hover:border-stone-600 flex items-center gap-2"><PenTool size={12} /> Log New Task</span>
                  </div>
                </div>
              </div>

              {/* CENTER: AVATAR & HERO STATS */}
              <div className="flex flex-col gap-6 relative z-10 lg:mt-4">
                 <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm p-3 shadow-[0_20px_25px_-5px_rgba(0,0,0,0.3)] relative rotate-2 hover:rotate-0 transition-transform duration-300">
                    <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
                    <div className="bg-[#dcd0b9] aspect-square rounded-sm border border-[#c7bba4] relative overflow-hidden flex items-center justify-center group shadow-inner">
                        {ditheredPreviewUrl ? (
                          <img src={ditheredPreviewUrl} alt="profile" className="absolute inset-0 w-full h-full object-cover" />
                        ) : (
                          <User size={120} className="text-[#b8ad96] group-hover:scale-105 transition-transform duration-500" />
                        )}
                        <div className="absolute top-4 right-4 border-4 border-double border-emerald-700 text-emerald-800 px-2 py-1 font-black text-sm -rotate-12 opacity-70 rounded-sm bg-emerald-600/10 mix-blend-multiply z-20">ACTIVE</div>

                        {/* Profile photo controls: Take / Upload / Algorithm / Preview (hidden when image present) */}
                        {!ditheredPreviewUrl && (
                          <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between gap-2 pointer-events-auto z-30">
                              <div className="flex items-center gap-2">
                                <button title="Take photo" onClick={() => { if (takePhotoRef && takePhotoRef.current) takePhotoRef.current(); }} className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600">
                                  <Video size={14} />
                                </button>

                                <button title="Upload photo" onClick={() => fileInputRef.current && fileInputRef.current.click()} className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600">
                                  <FileText size={14} />
                                </button>

                                {/* settings button removed per request */}
                              </div>
                            <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={async (e) => {
                                const f = e.target.files && e.target.files[0];
                                if (f) await sendFile(f, selectedAlgorithm);
                                e.target.value = null;
                              }} />
                          </div>
                        )}
                    </div>
                    <div className="mt-4 px-2 pb-2 text-center relative z-10">
                        <h1 className="text-4xl font-serif font-bold text-stone-900 tracking-tight uppercase">{displayData.user_id}</h1>
                        <div className="flex justify-center gap-2 mt-2 text-xs font-mono text-stone-600 uppercase"><span>CL: {displayData.class}</span><span>•</span><span>LVL: {displayData.level}</span></div>
                         <div className="mt-6 bg-[#f7e6a1] rotate-[-2deg] shadow-md p-4 inline-block relative max-w-[95%] mx-auto transform hover:scale-105 transition-transform">
                            <div className="absolute -top-3 left-[40%] w-8 h-4 bg-white/30 rotate-2 backdrop-blur-sm border border-white/20 shadow-sm"></div>
                            <div className="text-[10px] font-bold text-amber-900 uppercase tracking-wider mb-1 flex items-center justify-center gap-1"><Target size={10} /> Prime Directive</div>
                            <div className="text-sm font-serif italic text-stone-900 leading-tight">"{displayData.northStar}"</div>
                         </div>
                    </div>
                 </div>
                 <div className="bg-[#2c2926] text-[#e8dcc5] p-4 rounded-sm shadow-xl -rotate-1 relative mx-2 border border-[#1a1918]">
                    <div className="flex justify-between text-[10px] font-mono mb-2 text-[#a8a29e]"><span>PROGRESSION METRICS</span><span>{displayData.xp} / {displayData.nextLevelXp}</span></div>
                    <div className="w-full h-2 bg-[#44403c] rounded-full overflow-hidden border border-[#57534e]"><div className="h-full bg-stone-500 w-[80%] shadow-[0_0_10px_rgba(255,255,255,0.1)]" /></div>
                 </div>
              </div>

              {/* RIGHT: SKILL TREE & STATS */}
              <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm shadow-[0_3px_10px_rgb(0,0,0,0.2)] flex flex-col overflow-hidden relative rotate-1 hover:rotate-0 transition-transform duration-300 h-full">
                 <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
                 <div className="h-[300px] relative border-b border-[#d4c5a9] bg-[#dfd3bc]/30">
                    <div className="absolute top-4 left-4 flex items-center gap-2 text-stone-500"><Brain size={14} /><span className="text-[10px] font-mono uppercase tracking-widest">Psychometrics</span></div>
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="75%" data={displayData.stats}>
                        <PolarGrid stroke="#c7bba4" />
                        <PolarAngleAxis dataKey="name" tick={{ fill: '#57534e', fontSize: 10, fontWeight: 'bold' }} />
                        <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                        <Radar name="Stats" dataKey="value" stroke="#2c2926" strokeWidth={2} fill="#2c2926" fillOpacity={0.15} />
                      </RadarChart>
                    </ResponsiveContainer>
                 </div>
                 <div className="flex-1 p-5 flex flex-col relative z-10">
                    <div className="flex items-center justify-between mb-4 text-stone-600 border-b border-[#d4c5a9] pb-2"><span className="text-xs font-bold uppercase flex items-center gap-2"><Swords size={14} /> Capability Set</span></div>
                    <div className="space-y-1 overflow-y-auto max-h-[240px] pr-2 custom-scrollbar">
                       {displayData.skills.map((skill, idx) => <SkillItem key={idx} skill={skill} />)}
                    </div>
                    <div className="mt-auto pt-4">
                       <div className="text-[10px] font-bold text-red-700 mb-2 flex items-center gap-1 uppercase tracking-wide"><ShieldAlert size={12} /> Negative Status</div>
                       {displayData.debuffs.map((d, idx) => (
                          <div key={idx} className="text-xs text-red-900 bg-red-100/50 border border-red-200/60 p-2 rounded-sm flex justify-between items-center shadow-sm">
                             <span className="font-bold">{d.name}</span><span className="font-mono bg-[#fdf2f2] px-1 border border-red-100 rounded text-[10px]">{d.effect}</span>
                          </div>
                       ))}
                    </div>
                 </div>
              </div>
            </div>

            {/* BOTTOM: TIMELINE */}
            <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm shadow-[0_10px_20px_rgba(0,0,0,0.2)] p-6 relative lg:mx-12 rotate-[0.5deg]">
              <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
              <div className="flex items-center gap-2 text-stone-600 mb-4 px-2 relative z-10"><Clock size={16} /><span className="text-xs font-bold uppercase tracking-wider">Chronicle Log</span></div>
              <div className="flex items-center overflow-x-auto pb-4 custom-scrollbar relative z-10">
                 <div className="flex min-w-full px-4 gap-0">
                    {displayData.timeline.map((item, idx) => <TimelineItem key={idx} item={item} />)}
                    <div className="flex flex-col items-center min-w-[50px] relative"><div className="text-[10px] font-mono text-stone-400 mb-2">END</div><div className="w-2 h-2 rounded-full bg-[#c7bba4]" /><div className="absolute top-[21px] left-[-50%] w-full h-0.5 bg-[#d4c5a9] -z-0" /></div>
                 </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: SKILL MAP (Dynamic Blueprint) */}
        {activeTab === 'map' && (
          <div className="h-[80vh] w-full bg-[#f0f9ff] border-4 border-white rounded-sm relative overflow-hidden animate-in zoom-in-95 duration-500 group shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] rotate-1 flex flex-col">
            <div className="absolute top-0 left-0 right-0 z-40 p-6 flex justify-between items-start pointer-events-none">
                <div>
                    <div className="text-3xl font-black text-blue-900 uppercase tracking-tighter opacity-90 drop-shadow-sm">Skill Architecture</div>
                    <div className="text-xs font-mono text-blue-500">SYSTEM_BLUEPRINT_V2 // {activePillar}</div>
                </div>
                <div className="pointer-events-auto bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-blue-200 shadow-sm flex gap-1">
                    {['CAREER', 'PHYSICAL', 'SOCIAL', 'MENTAL'].map(pillar => (
                        <button key={pillar} onClick={() => setActivePillar(pillar)} className={`px-3 py-1.5 rounded text-[10px] font-bold transition-all ${activePillar === pillar ? 'bg-blue-600 text-white shadow-md' : 'text-blue-400 hover:bg-blue-50 hover:text-blue-600'}`}>{pillar}</button>
                    ))}
                </div>
            </div>
            <TreeVisualizer pillar={activePillar} skillTree={skillTree} characterSheet={characterSheet} />
          </div>
        )}

        {/* VIEW 3: REPORT PAGE */}
        {activeTab === 'report' && (
          <div className="flex-1 flex flex-col gap-10 animate-in fade-in slide-in-from-bottom-4 duration-500 items-center justify-center min-h-[700px]">
             <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm shadow-[0_25px_50px_-12px_rgba(0,0,0,0.3)] flex flex-col overflow-hidden relative rotate-0 transition-transform duration-300 w-full max-w-4xl p-0 min-h-[70vh]">
                {/* Texture */}
                <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
                
                {/* Header */}
                <div className="border-b-2 border-stone-800 p-8 flex justify-between items-end relative z-10 bg-[#dfd3bc]/30">
                    <div>
                        <div className="text-xs font-mono text-stone-500 mb-2">INTELLIGENCE BRIEFING // DAILY LOG</div>
                        <h1 className="text-4xl font-serif font-black text-stone-900 tracking-tight uppercase">Field Report</h1>
                        <div className="text-xs font-mono text-stone-600 mt-1">OPERATIVE: {displayData.user_id}</div>
                    </div>
                    <div className="text-right">
                        <div className="text-xs font-mono text-stone-500">DATE: {new Date().toLocaleDateString()}</div>
                        <div className="text-red-900 font-bold border-2 border-red-900 px-2 py-1 text-xs inline-block mt-2 rotate-[-5deg] opacity-80">CONFIDENTIAL</div>
                    </div>
                </div>

                {/* Content Body */}
                <div className="flex-1 p-8 font-serif text-stone-800 leading-relaxed space-y-8 relative z-10 overflow-y-auto">
                    
                    {/* Section 1: Today's Status */}
                    <div>
                        <h3 className="font-bold border-b-2 border-stone-800 mb-4 text-sm uppercase tracking-wider text-stone-900 flex items-center gap-2">
                            <Activity size={16} /> Current Directives Status
                        </h3>
                        <div className="grid grid-cols-1 gap-0 bg-white/40 border border-[#d4c5a9] rounded-sm divide-y divide-[#d4c5a9]">
                            {/* Filter for active habits only */}
                            {displayData.quests.map((q, i) => {
                                // Mock some random history for visualization
                                const history = [true, true, false, true, true]; 
                                const isCompletedToday = i % 3 === 0; // Mock completion status

                                return (
                                    <div key={i} className="p-4 flex items-center justify-between hover:bg-[#dcd0b9]/30 transition-colors group">
                                        <div className="flex items-center gap-4">
                                            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${isCompletedToday ? 'bg-stone-800 border-stone-800 text-white' : 'border-stone-400 text-transparent'}`}>
                                                <Check size={14} strokeWidth={4} />
                                            </div>
                                            <div>
                                                <div className="font-bold text-stone-800 text-sm">{q.title}</div>
                                                <div className="text-[10px] font-mono text-stone-500 uppercase">{q.type} PROTOCOL</div>
                                            </div>
                                        </div>
                                        
                                        {/* History Visualization */}
                                        <div className="flex items-center gap-4">
                                            <div className="flex gap-1">
                                                {history.map((done, hIdx) => (
                                                    <div 
                                                        key={hIdx} 
                                                        className={`w-2 h-2 rounded-full ${done ? 'bg-stone-400' : 'bg-stone-200 border border-stone-300'}`}
                                                        title={done ? "Completed" : "Missed"}
                                                    />
                                                ))}
                                            </div>
                                            <div className="text-xs font-mono text-stone-400 w-12 text-right">80%</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Section 2: Performance Summary (Mock Chart) */}
                    <div>
                         <h3 className="font-bold border-b-2 border-stone-800 mb-4 text-sm uppercase tracking-wider text-stone-900 flex items-center gap-2">
                            <BarChart2 size={16} /> Performance Analytics
                        </h3>
                        <div className="bg-white/40 border border-[#d4c5a9] p-4 h-48 rounded-sm">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={[
                                    { day: 'M', score: 65 },
                                    { day: 'T', score: 40 },
                                    { day: 'W', score: 75 },
                                    { day: 'T', score: 50 },
                                    { day: 'F', score: 85 },
                                    { day: 'S', score: 30 },
                                    { day: 'S', score: 60 },
                                ]}>
                                    <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{fill: '#78716c', fontSize: 10}} />
                                    <Tooltip 
                                        contentStyle={{ backgroundColor: '#2c2926', border: 'none', borderRadius: '4px', color: '#fff' }}
                                        itemStyle={{ color: '#fff' }}
                                        cursor={{fill: '#dcd0b9', opacity: 0.4}}
                                    />
                                    <Bar dataKey="score" fill="#57534e" radius={[2, 2, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* Footer: Input Controls */}
                <div className="p-6 bg-[#d4c5a9]/30 border-t border-[#d4c5a9] flex gap-4 relative z-20">
                    <button className="flex-1 bg-stone-800 text-[#e8dcc5] py-3 rounded-sm font-bold flex items-center justify-center gap-3 hover:bg-stone-900 transition-colors shadow-lg active:transform active:scale-[0.98]">
                        <Mic size={18} />
                        <span>INITIATE VOICE LOG</span>
                    </button>
                    <button className="flex-1 bg-white border border-[#c7bba4] text-stone-800 py-3 rounded-sm font-bold flex items-center justify-center gap-3 hover:bg-[#f5efe6] transition-colors shadow-sm active:transform active:scale-[0.98]">
                        <Keyboard size={18} />
                        <span>MANUAL ENTRY</span>
                    </button>
                </div>

             </div>
          </div>
        )}

        {/* VIEW 4: CALENDAR */}
        {activeTab === 'calendar' && <CalendarView />}

        

        {/* VIEW 5: LOCK-IN */}
        {activeTab === 'lockin' && <LockInView availableQuests={displayData.quests || []} sendFile={sendFile} selectedAlgorithm={selectedAlgorithm} setSelectedAlgorithm={setSelectedAlgorithm} ditheredPreviewUrl={ditheredPreviewUrl} setDitheredPreviewUrl={setDitheredPreviewUrl} fileInputRef={fileInputRef} takePhotoRef={takePhotoRef} />}

      </main>
    </div>
  );
}