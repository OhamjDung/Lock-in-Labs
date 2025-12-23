import React, { useState, useRef, useEffect } from 'react';
import { Mic, X, User, Volume2 } from 'lucide-react';
import { auth } from '../../config/firebase';
import { onAuthStateChanged } from 'firebase/auth';

export default function VoiceReporting({ onClose, userId, onReportComplete }) {
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [userEmail, setUserEmail] = useState(null);
  const speechRecognitionRef = useRef(null);
  const ttsWebSocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const hasInitialized = useRef(false);

  // Get user email
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user && user.email) {
        setUserEmail(user.email);
      } else {
        setUserEmail(null);
      }
    });
    return () => unsubscribe();
  }, []);

  // Initialize conversation on mount
  useEffect(() => {
    if (!hasInitialized.current && userId) {
      hasInitialized.current = true;
      handleInitialMessage();
    }
    return () => {
      // Cleanup
      if (speechRecognitionRef.current) {
        try {
          speechRecognitionRef.current.stop();
        } catch (e) {}
      }
      if (ttsWebSocketRef.current) {
        ttsWebSocketRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [userId]);

  // Initialize TTS WebSocket connection
  const ensureTtsSocket = () => {
    if (ttsWebSocketRef.current && ttsWebSocketRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const backend = (window && window.location && window.location.hostname === 'localhost') 
      ? 'ws://127.0.0.1:8000' 
      : `ws://${window.location.host}`;
    
    const ws = new WebSocket(`${backend}/ws/voice`);
    
    ws.onopen = () => {
      console.log('[VoiceReporting] TTS WebSocket connected');
    };

    ws.onerror = (error) => {
      console.error('[VoiceReporting] TTS WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('[VoiceReporting] TTS WebSocket closed');
    };

    ws.onmessage = async (event) => {
      const { data } = event;
      
      // Handle text messages (errors or status)
      if (typeof data === 'string') {
        try {
          const jsonData = JSON.parse(data);
          if (jsonData.type === 'error') {
            console.error('[VoiceReporting] TTS error:', jsonData);
            setIsPlaying(false);
          }
        } catch (e) {
          // Not JSON, ignore
        }
        return;
      }

      // Handle binary audio data
      try {
        let arrayBuffer;
        if (data instanceof ArrayBuffer) {
          arrayBuffer = data;
        } else if (data instanceof Blob) {
          arrayBuffer = await data.arrayBuffer();
        } else {
          console.warn('[VoiceReporting] unsupported binary message type:', data);
          return;
        }

        if (!audioContextRef.current) {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }

        const ctx = audioContextRef.current;
        
        if (ctx.state === 'suspended') {
          try {
            await ctx.resume();
          } catch (resumeErr) {
            console.warn('[VoiceReporting] failed to resume AudioContext:', resumeErr);
          }
        }

        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        
        setIsPlaying(true);
        source.onended = () => {
          setIsPlaying(false);
        };
        source.start(0);
      } catch (error) {
        console.error('[VoiceReporting] Error playing audio:', error);
        setIsPlaying(false);
      }
    };

    ttsWebSocketRef.current = ws;
    
    // Initialize AudioContext for playback
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
  };

  const handleInitialMessage = async () => {
    setIsSending(true);
    
    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') 
        ? 'http://127.0.0.1:8000' 
        : '';
      
      const response = await fetch(`${backend}/api/reporting/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          message: '', // Empty message triggers initial greeting
          conversation_history: [],
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to initialize reporting agent');
      }

      const data = await response.json();
      
      // Add initial assistant message
      const assistantMessage = { 
        role: 'assistant', 
        content: data.reply
      };
      
      setMessages([assistantMessage]);
      
      // Play TTS for initial message
      ensureTtsSocket();
      if (ttsWebSocketRef.current && ttsWebSocketRef.current.readyState === WebSocket.OPEN) {
        ttsWebSocketRef.current.send(JSON.stringify({ type: 'tts-text', text: data.reply }));
      }
    } catch (error) {
      console.error('Error initializing chat:', error);
      setMessages([{
        role: 'assistant',
        content: 'Sorry, I encountered an error initializing the voice log. Please try again.'
      }]);
    } finally {
      setIsSending(false);
    }
  };

  const handleToggleRecording = async () => {
    // Ensure TTS socket exists
    ensureTtsSocket();

    // Stop TTS playback when starting to record
    if (!isRecording && audioContextRef.current) {
      try {
        await audioContextRef.current.close();
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        console.warn('[VoiceReporting] Error closing AudioContext:', e);
      }
    }

    const SpeechRecognition =
      typeof window !== 'undefined'
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;

    if (!SpeechRecognition) {
      console.warn('[VoiceReporting] SpeechRecognition API not available in this browser.');
      alert('Speech recognition is not available in your browser. Please use the manual entry option.');
      setIsRecording(false);
      return;
    }

    if (!speechRecognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.continuous = false; // Stop after one result

      recognition.onresult = async (event) => {
        try {
          const result = event.results[0][0];
          const transcript = result && result.transcript ? result.transcript : '';
          console.log('[VoiceReporting] STT result:', transcript);
          if (transcript) {
            await handleSendMessage(transcript);
          }
        } catch (err) {
          console.error('[VoiceReporting] error handling STT result:', err);
        }
      };

      recognition.onend = () => {
        console.log('[VoiceReporting] STT recognition ended');
        setIsRecording(false);
      };

      recognition.onerror = (event) => {
        console.error('[VoiceReporting] STT recognition error:', event.error || event);
        setIsRecording(false);
        if (event.error === 'no-speech') {
          // This is normal, user might have stopped without speaking
        } else {
          alert(`Speech recognition error: ${event.error || 'Unknown error'}`);
        }
      };

      speechRecognitionRef.current = recognition;
    }

    // Toggle recording
    setIsRecording((prev) => {
      const next = !prev;
      try {
        if (next) {
          console.log('[VoiceReporting] starting STT recognition');
          speechRecognitionRef.current.start();
        } else {
          console.log('[VoiceReporting] stopping STT recognition');
          speechRecognitionRef.current.stop();
        }
      } catch (e) {
        console.error('[VoiceReporting] error toggling STT recognition:', e);
        if (e.name === 'InvalidStateError') {
          // Already started/stopped, ignore
        }
      }
      return next;
    });
  };

  const handleSendMessage = async (userMessage) => {
    if (!userMessage.trim() || isSending) return;

    setIsSending(true);

    // Add user message immediately
    const newUserMessage = { role: 'user', content: userMessage };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') 
        ? 'http://127.0.0.1:8000' 
        : '';
      
      const response = await fetch(`${backend}/api/reporting/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          message: userMessage,
          conversation_history: messages,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from reporting agent');
      }

      const data = await response.json();
      
      // Add assistant reply
      const assistantMessage = { 
        role: 'assistant', 
        content: data.reply
      };
      
      setMessages(prev => [...prev, assistantMessage]);

      // Play TTS for assistant reply
      ensureTtsSocket();
      if (ttsWebSocketRef.current && ttsWebSocketRef.current.readyState === WebSocket.OPEN) {
        ttsWebSocketRef.current.send(JSON.stringify({ type: 'tts-text', text: data.reply }));
      }

      // If conversation is complete, refresh data and close after a delay
      if (data.is_complete) {
        if (onReportComplete) {
          onReportComplete();
        }
        setTimeout(() => {
          onClose();
        }, 3000);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      }]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[200] bg-stone-900 flex items-center justify-center p-4 font-sans">
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #a8a29e; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #78716c; }
      `}</style>
      <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: `url('https://www.transparenttextures.com/patterns/aged-paper.png')` }}></div>
      
      <div className="relative w-full max-w-4xl bg-[#d4c5a9] rounded-sm shadow-2xl transition-all duration-700 ease-in-out min-h-[600px] flex flex-col overflow-hidden border-t-2 border-l-2 border-[#e6dcc5] border-b-4 border-r-4 border-[#8c7b5d] rotate-1">
        
        <div className="absolute -top-8 left-0 w-48 h-10 bg-[#d4c5a9] rounded-t-lg border-t-2 border-l-2 border-[#e6dcc5] flex items-center justify-center">
            <span className="font-mono text-stone-600 font-bold tracking-widest text-xs">VOICE LOG</span>
        </div>

        <div className="absolute inset-0 opacity-[0.15] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        <div className="flex-1 p-8 md:p-16 flex flex-col relative animate-in fade-in slide-in-from-right-8 duration-700 bg-[#f4e9d5]">
          <div className="border-b border-stone-400 pb-4 mb-8 flex justify-between items-end">
            <div className="flex items-center gap-4">
              <div className="border border-stone-800 p-1 rounded-sm"><Mic size={32} className="text-stone-800" /></div>
              <div>
                <h3 className="font-mono font-bold text-lg tracking-widest text-stone-900 uppercase">Voice Check-In Transcript</h3>
                <div className="text-xs font-mono text-stone-500">SUBJECT: {userEmail ? userEmail.split('@')[0].toUpperCase() : (userId?.toUpperCase() || 'USER')} // MODE: VOICE</div>
              </div>
            </div>
            <div className="text-right hidden md:block">
              <div className="text-xs font-mono text-stone-500">TIMESTAMP</div>
              <div className="font-mono text-stone-800">{new Date().toLocaleTimeString()}</div>
            </div>
            <button
              onClick={onClose}
              className="text-stone-600 hover:text-stone-900 transition-colors p-2 hover:bg-stone-200/50 rounded-sm ml-4"
              title="Close"
            >
              <X size={24} />
            </button>
          </div>

          <div className="flex-1 font-mono text-stone-800 text-sm md:text-base leading-relaxed space-y-6 max-w-2xl">
            <div className="mt-6 space-y-4">
              <div className="h-64 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                {messages.length === 0 && (
                  <div className="text-[11px] text-stone-500 italic">
                    Press the microphone to start recording. Speak your report.
                  </div>
                )}

                {messages.map((m, idx) => {
                  const label = m.role === 'user' ? 'You:' : 'RPT:';

                  return (
                    <div key={`msg-${idx}-${m.content?.substring(0, 20)}`} className="flex gap-4">
                      <div className="font-bold text-stone-500 select-none w-10 text-right">
                        {label}
                      </div>
                      <div className="flex-1 whitespace-pre-wrap">{m.content}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Voice Control Area */}
          <div className="border-t border-stone-400 pt-6 mt-6">
            <div className="flex items-center justify-center gap-4">
              <button
                type="button"
                onClick={handleToggleRecording}
                disabled={isSending || isPlaying}
                className={`relative w-16 h-16 rounded-full flex items-center justify-center border-2 transition-all ${
                  isRecording 
                    ? 'bg-red-600 border-red-700 text-white scale-110 shadow-lg' 
                    : 'bg-stone-900 border-stone-800 text-[#e8dcc5] hover:bg-stone-800'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
                title={isRecording ? 'Stop recording' : 'Start recording'}
              >
                <Mic size={24} className={isRecording ? "animate-pulse" : ""} />
                {isRecording && (
                  <span className="absolute -top-2 -right-2 h-3 w-3 rounded-full bg-red-500 animate-ping" />
                )}
              </button>
              <div className="flex flex-col">
                <span className="text-sm font-mono text-stone-700 uppercase tracking-wide">
                  {isRecording ? "Recording..." : isPlaying ? "Playing response..." : isSending ? "Processing..." : "Press to record"}
                </span>
                <span className="text-xs text-stone-600">
                  {isRecording 
                    ? "Speak your report. The system will transcribe and send automatically." 
                    : "Click the microphone to start voice recording"}
                </span>
              </div>
              {isPlaying && (
                <div className="flex items-center gap-2 text-stone-600">
                  <Volume2 size={20} className="animate-pulse" />
                  <span className="text-xs font-mono">Playing response...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

