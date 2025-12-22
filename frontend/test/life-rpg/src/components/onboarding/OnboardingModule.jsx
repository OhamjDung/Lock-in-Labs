import React, { useState, useRef, useEffect } from 'react';
import { ArrowRight, Mic, Keyboard, Fingerprint, Send, ChevronRight, User, Lock, Mail } from 'lucide-react';
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from 'firebase/auth';
import { doc, setDoc, getDoc } from 'firebase/firestore';
import { auth, db } from '../../config/firebase';
import TypewriterText from './TypewriterText';
import VoiceLogsPanel from './VoiceLogsPanel';

const architectOpening =
  "Listen kid, I've seen a lot of people come through that door. Most of 'em don't know what they want. But you? You got that look. The look of someone who's gotta find their way outta this concrete jungle. So here's what I need to know: in some perfect future, when that alarm clock goes off and you're finally livin' the dream—what's the first thing you do?";

const OnboardingModule = ({ onFinish }) => {
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [authError, setAuthError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [mode, setMode] = useState(null);
  const [isTypingDone, setIsTypingDone] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [onboardingProgress, setOnboardingProgress] = useState(0); 
  const [messages, setMessages] = useState([
    { role: 'assistant', content: architectOpening },
  ]);
  const [isSending, setIsSending] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [phase, setPhase] = useState("phase1");
  const [pendingDebuffs, setPendingDebuffs] = useState([]);
  const [pillarsAskedAbout, setPillarsAskedAbout] = useState([]);
  const [pendingGoals, setPendingGoals] = useState([]);
  const playbackContextRef = useRef(null);
  const ttsSocketRef = useRef(null);
  const introSpokenRef = useRef(false);
  const speechRecognitionRef = useRef(null);
  const chatScrollRef = useRef(null);

  const handleAuth = async (e) => {
    e.preventDefault();
    setAuthError('');
    
    if (!email.trim() || !password.trim()) {
      setAuthError('Email and password are required');
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setAuthError('Please enter a valid email address');
      return;
    }

    if (password.length < 6) {
      setAuthError('Password must be at least 6 characters');
      return;
    }

    setIsAuthenticating(true);

    try {
      let userCredential;
      
      if (isSignUp) {
        // Sign up: Create user in Firebase Auth
        userCredential = await createUserWithEmailAndPassword(auth, email, password);
        const user = userCredential.user;

        // Create user profile in Firestore using the Auth UID
        await setDoc(doc(db, "users", user.uid), {
          email: email,
          username: email.split('@')[0], // Use email prefix as username
          createdAt: new Date().toISOString(),
        });

        console.log('[Auth] User created:', user.uid);
      } else {
        // Sign in: Authenticate with Firebase Auth
        userCredential = await signInWithEmailAndPassword(auth, email, password);
        const user = userCredential.user;

        // Check if user profile exists in Firestore (with error handling for network issues)
        try {
          const userDoc = await getDoc(doc(db, "users", user.uid));
          if (!userDoc.exists()) {
            // Create profile if it doesn't exist (for legacy users)
            await setDoc(doc(db, "users", user.uid), {
              email: email,
              username: email.split('@')[0],
              createdAt: new Date().toISOString(),
            });
          }
        } catch (firestoreError) {
          // Log but don't block authentication if Firestore connection fails
          // This can happen with network issues (QUIC protocol errors, etc.)
          console.warn('[Auth] Firestore check failed (non-critical):', firestoreError);
          // User is still authenticated, we'll create the profile later if needed
        }

        console.log('[Auth] User signed in:', user.uid);
      }

      // Authentication successful, proceed to mode selection
      setStep(2);
    } catch (error) {
      console.error('[Auth] Error:', error);
      let errorMessage = 'Authentication failed';
      
      switch (error.code) {
        case 'auth/email-already-in-use':
          errorMessage = 'This email is already registered. Try signing in instead.';
          break;
        case 'auth/invalid-email':
          errorMessage = 'Invalid email address.';
          break;
        case 'auth/weak-password':
          errorMessage = 'Password is too weak.';
          break;
        case 'auth/user-not-found':
          errorMessage = 'No account found with this email.';
          break;
        case 'auth/wrong-password':
          errorMessage = 'Incorrect password.';
          break;
        case 'auth/too-many-requests':
          errorMessage = 'Too many failed attempts. Please try again later.';
          break;
        default:
          errorMessage = error.message || 'Authentication failed. Please try again.';
      }
      
      setAuthError(errorMessage);
    } finally {
      setIsAuthenticating(false);
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

  // Reset messages and phase when starting a new chat session to ensure fresh conversation
  useEffect(() => {
    // When entering step 3 (chat), ensure we start with just the opening message
    if (step === 3 && mode) {
      // Reset phase to phase1 when starting a new chat
      setPhase("phase1");
      setPendingDebuffs([]);
      setPillarsAskedAbout([]);
      setPendingGoals([]);
      // Check if messages array is corrupted (has more than just the opening, or wrong opening)
      const hasOnlyOpening = messages.length === 1 && 
                             messages[0].role === 'assistant' && 
                             messages[0].content === architectOpening;
      
      if (!hasOnlyOpening) {
        console.warn('[Onboarding] Resetting messages to ensure fresh conversation');
        setMessages([{ role: 'assistant', content: architectOpening }]);
        setOnboardingProgress(0);
        // Log the initial architect opening
        console.log('%c[Architect Response]', 'color: #ec4899; font-weight: bold; font-size: 14px;', architectOpening);
      } else if (messages.length === 1) {
        // Log the opening message if it's the first time
        console.log('%c[Architect Response]', 'color: #ec4899; font-weight: bold; font-size: 14px;', architectOpening);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, mode]); // Only run when step or mode changes, not when messages changes

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

        await new Promise((resolve, reject) => {
          ctx.decodeAudioData(
            arrayBuffer,
            (audioBuffer) => {
              try {
                // ElevenLabs already handles speed adjustment server-side with pitch preservation
                // Just play the audio at normal speed
                const sourceNode = ctx.createBufferSource();
                sourceNode.buffer = audioBuffer;
                sourceNode.connect(ctx.destination);
                
                sourceNode.onended = () => {
                  resolve();
                };
                
                sourceNode.start();
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

    ensureTtsSocket();

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
      const historyPayload = messages;

      const res = await fetch("http://127.0.0.1:8000/api/onboarding/architect-reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: historyPayload,
          user_input: trimmed,
          phase: phase,
          pending_debuffs: pendingDebuffs,
          pillars_asked_about: pillarsAskedAbout,
          pending_goals: pendingGoals,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to reach Architect backend");
      }
      const data = await res.json();

      // Update phase and state from response
      if (data.phase) {
        setPhase(data.phase);
        console.log('%c[Current Phase]', 'color: #f59e0b; font-weight: bold; font-size: 14px;', data.phase);
      }
      if (data.pending_debuffs !== undefined) {
        setPendingDebuffs(data.pending_debuffs);
      }
      if (data.pillars_asked_about !== undefined) {
        setPillarsAskedAbout(data.pillars_asked_about);
      }
      if (data.pending_goals !== undefined) {
        setPendingGoals(data.pending_goals);
      }

      // Log accumulated goals
      if (data.accumulated_goals) {
        console.log('%c[Accumulated Goals]', 'color: #f59e0b; font-weight: bold; font-size: 14px;', data.accumulated_goals);
      }

      // Log current quests for each goal
      if (data.accumulated_goals && Array.isArray(data.accumulated_goals)) {
        const questsInfo = data.accumulated_goals.map(goal => ({
          goal: goal.name,
          pillars: goal.pillars,
          current_quests: goal.current_quests || []
        }));
        console.log('%c[Current Quests]', 'color: #8b5cf6; font-weight: bold; font-size: 14px;', questsInfo);
      }

      // Log debug info to browser console
      if (data.debug) {
        if (data.debug.critic_analysis) {
          try {
            const criticData = JSON.parse(data.debug.critic_analysis);
            console.log('%c[Critic Analysis - Current Message]', 'color: #3b82f6; font-weight: bold; font-size: 14px;', criticData);
          } catch (e) {
            console.log('%c[Critic Analysis - Current Message]', 'color: #3b82f6; font-weight: bold; font-size: 14px;', data.debug.critic_analysis);
          }
        }
        if (data.debug.architect_thinking) {
          console.log('%c[Architect Thinking]', 'color: #10b981; font-weight: bold; font-size: 14px;', data.debug.architect_thinking);
        }
      }

      let reply = data.reply || "";
      let progress = 0;
      let match = reply.match(/\[Progress:[^\]]*?(\d{1,3})%\]/i);
      if (!match) {
        match = reply.match(/\[Progress:[^\]]*?\]\s*(\d{1,3})%/i);
      }
      if (match) {
        progress = Math.max(0, Math.min(100, parseInt(match[1], 10)));
        setOnboardingProgress(progress);
        reply = reply.replace(/\[Progress:[^\]]*?(\d{1,3})%\]/i, "").replace(/\[Progress:[^\]]*?\]\s*(\d{1,3})%/i, "").trim();
      } else {
        // Fallback progress bar system based on phase
        const currentPhase = data.phase || phase;
        if (currentPhase === "phase2" && onboardingProgress < 40) {
          progress = 40;
          setOnboardingProgress(progress);
        } else if (currentPhase === "phase3" && onboardingProgress < 70) {
          progress = 70;
          setOnboardingProgress(progress);
        } else if (currentPhase === "phase3.5" && onboardingProgress < 85) {
          progress = 85;
          setOnboardingProgress(progress);
        }
      }

      if (reply) {
        // Only send TTS in voice mode
        if (mode === 'voice') {
          sendTtsText(reply);
        }
      }

      // Log chat messages to console
      console.log('%c[User Message]', 'color: #8b5cf6; font-weight: bold; font-size: 14px;', trimmed);
      if (reply) {
        console.log('%c[Architect Response]', 'color: #ec4899; font-weight: bold; font-size: 14px;', reply);
      }

      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        data.reply ? { role: "assistant", content: reply } : null,
      ].filter(Boolean));
      setUserInput("");
      
      // Auto-extract and save profile when phase4 is reached
      if (data.should_extract_profile && data.phase === "phase4" && auth.currentUser) {
        console.log('%c[Profile] Auto-extracting and saving profile...', 'color: #10b981; font-weight: bold; font-size: 14px;');
        const userId = auth.currentUser.uid;
        
        // Extract profile from conversation history (include the latest messages)
        const updatedMessages = [
          ...messages,
          { role: "user", content: trimmed },
          ...(reply ? [{ role: "assistant", content: reply }] : [])
        ].filter(Boolean);
        
        try {
          const extractRes = await fetch("http://127.0.0.1:8000/api/onboarding/extract-profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history: updatedMessages,
              user_id: userId,
            }),
          });

          if (extractRes.ok) {
            const profileData = await extractRes.json();
            
            // Save the extracted profile to Firestore
            const saveRes = await fetch(`http://127.0.0.1:8000/api/profile/${userId}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(profileData),
            });

            if (saveRes.ok) {
              console.log('%c[Profile] Profile extracted and saved successfully to Firestore', 'color: #10b981; font-weight: bold; font-size: 14px;');
              // Automatically finish onboarding after profile is saved
              if (onFinish) {
                setTimeout(() => {
                  onFinish({ 
                    uid: userId,
                    email: auth.currentUser.email,
                    username: auth.currentUser.email?.split('@')[0] || 'user'
                  });
                }, 1000);
              }
            } else {
              console.error('[Profile] Failed to save profile:', saveRes.statusText);
            }
          } else {
            console.error('[Profile] Failed to extract profile:', extractRes.statusText);
          }
        } catch (error) {
          console.error('[Profile] Error extracting/saving profile:', error);
        }
      }
      
      // Auto-scroll to bottom after message is added
      setTimeout(() => {
        if (chatScrollRef.current) {
          chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
        }
      }, 100);
    } catch (err) {
      const errorMessage = "The line went static trying to reach the Architect. We'll keep your answer on record and try again later.";
      console.log('%c[User Message]', 'color: #8b5cf6; font-weight: bold; font-size: 14px;', trimmed);
      console.log('%c[Architect Response]', 'color: #ec4899; font-weight: bold; font-size: 14px;', errorMessage);
      console.error('[Onboarding] Error sending message:', err);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        {
          role: "assistant",
          content: errorMessage,
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

  const handleFinish = async () => {
    if (!onFinish || !auth.currentUser) return;
    
    setIsSavingProfile(true);
    const userId = auth.currentUser.uid;
    
    try {
      // Extract profile from conversation history
      const extractRes = await fetch("http://127.0.0.1:8000/api/onboarding/extract-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: messages,
          user_id: userId,
        }),
      });

      if (!extractRes.ok) {
        console.error('[Profile] Failed to extract profile:', extractRes.statusText);
        // Continue anyway - user can still proceed
      } else {
        const profileData = await extractRes.json();
        
        // Save the extracted profile to Firestore
        const saveRes = await fetch(`http://127.0.0.1:8000/api/profile/${userId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profileData),
        });

        if (!saveRes.ok) {
          console.error('[Profile] Failed to save profile:', saveRes.statusText);
        } else {
          console.log('[Profile] Profile saved successfully to Firestore');
        }
      }
    } catch (error) {
      console.error('[Profile] Error saving profile:', error);
      // Continue anyway - don't block the user from proceeding
    } finally {
      setIsSavingProfile(false);
    }

    // Pass the Firebase Auth UID instead of username
    onFinish({ 
      uid: userId,
      email: auth.currentUser.email,
      username: auth.currentUser.email?.split('@')[0] || 'user'
    });
  };

  return (
    <div className="fixed inset-0 z-[100] bg-stone-900 flex items-center justify-center p-4 font-sans">
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #a8a29e; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #78716c; }
      `}</style>
      <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: `url('https://www.transparenttextures.com/patterns/aged-paper.png')` }}></div>
      
      <div className={`relative w-full max-w-4xl bg-[#d4c5a9] rounded-sm shadow-2xl transition-all duration-700 ease-in-out min-h-[600px] flex flex-col overflow-hidden border-t-2 border-l-2 border-[#e6dcc5] border-b-4 border-r-4 border-[#8c7b5d] ${step === 3 ? 'rotate-0' : 'rotate-1'}`}>
        
        <div className="absolute -top-8 left-0 w-48 h-10 bg-[#d4c5a9] rounded-t-lg border-t-2 border-l-2 border-[#e6dcc5] flex items-center justify-center">
            <span className="font-mono text-stone-600 font-bold tracking-widest text-xs">CASE FILE #2025-X</span>
        </div>

        <div className="absolute inset-0 opacity-[0.15] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        {step === 1 && (
          <div className="flex-1 p-12 flex flex-col items-center justify-center relative animate-in fade-in zoom-in-95 duration-500">
             <div className="absolute top-8 right-8 text-red-900 border-4 border-red-900/50 p-2 font-black text-xl uppercase -rotate-12 opacity-40 mix-blend-multiply">
                RESTRICTED ACCESS
             </div>
             
             <h2 className="font-serif text-3xl text-stone-900 font-bold mb-8 tracking-tight border-b-2 border-stone-800 pb-2">Identity Verification</h2>
             
             <form onSubmit={handleAuth} className="w-full max-w-sm space-y-6 relative z-10">
                <div className="space-y-2 group">
                    <label className="block font-mono text-xs font-bold text-stone-600 tracking-widest uppercase group-focus-within:text-stone-900">Email Address</label>
                    <div className="relative">
                        <Mail size={16} className="absolute left-0 top-3 text-stone-500" />
                        <input 
                            type="email" 
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full bg-transparent border-b-2 border-stone-400 py-2 pl-6 font-mono text-lg text-stone-900 focus:outline-none focus:border-stone-800 transition-colors placeholder-stone-500/30"
                            placeholder="agent@example.com"
                            autoFocus
                            autoComplete="email"
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
                            autoComplete={isSignUp ? "new-password" : "current-password"}
                        />
                    </div>
                </div>

                {authError && (
                  <div className="text-red-700 text-sm font-mono bg-red-50 border border-red-200 px-3 py-2 rounded">
                    {authError}
                  </div>
                )}

                <div className="pt-4">
                    <button 
                        type="submit"
                        disabled={!email.trim() || !password.trim() || isAuthenticating}
                        className="w-full bg-stone-900 text-[#e8dcc5] py-4 font-bold tracking-[0.2em] uppercase hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg flex items-center justify-center gap-2 group border border-stone-700"
                    >
                        <span>{isAuthenticating ? 'Authenticating...' : (isSignUp ? 'Create Account' : 'Sign In')}</span>
                        {!isAuthenticating && <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />}
                    </button>
                    
                    <div className="text-center mt-4">
                        <button
                            type="button"
                            onClick={() => {
                              setIsSignUp(!isSignUp);
                              setAuthError('');
                            }}
                            className="text-xs font-mono text-stone-600 hover:text-stone-900 underline"
                        >
                            {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
                    </button>
                    </div>
                    
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

        {step === 2 && (
          <div className="flex-1 p-12 flex flex-col items-center justify-center relative animate-in fade-in zoom-in-95 duration-500">
             <div className="absolute top-8 right-8 text-red-900 border-4 border-red-900/50 p-2 font-black text-xl uppercase -rotate-12 opacity-40 mix-blend-multiply">
                Evidence
             </div>
             
             <div className="absolute top-8 left-8">
                 <div className="text-[10px] font-mono text-stone-500">OPERATIVE:</div>
                 <div className="font-bold text-stone-800 font-mono text-sm uppercase">{auth.currentUser?.email?.split('@')[0] || 'USER'}</div>
             </div>
             
             <h2 className="font-serif text-3xl text-stone-900 font-bold mb-2 tracking-tight">Choose Your Protocol</h2>
             <p className="font-mono text-stone-700 mb-12 text-sm">How should we document this investigation?</p>

             <div className="flex flex-col md:flex-row gap-12 items-center justify-center">
                
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
                  <div className="absolute -top-4 -left-4 w-24 h-8 bg-stone-300/50 backdrop-blur-sm -rotate-45 transform translate-y-4"></div>
                </button>

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
                  <div className="absolute -top-4 -right-4 w-24 h-8 bg-stone-300/50 backdrop-blur-sm rotate-45 transform translate-y-4"></div>
                </button>

             </div>
          </div>
        )}

        {step === 3 && (
          <div className="flex-1 p-8 md:p-16 flex flex-col relative animate-in fade-in slide-in-from-right-8 duration-700 bg-[#f4e9d5]">
             <div className="border-b border-stone-400 pb-4 mb-8 flex justify-between items-end">
                <div className="flex items-center gap-4">
                  <div className="border border-stone-800 p-1 rounded-sm"><Fingerprint size={32} className="text-stone-800" /></div>
                  <div>
                    <h3 className="font-mono font-bold text-lg tracking-widest text-stone-900 uppercase">Official Transcript</h3>
                    <div className="text-xs font-mono text-stone-500">SUBJECT: {auth.currentUser?.email?.split('@')[0].toUpperCase() || 'USER'} // MODE: {mode.toUpperCase()}</div>
                  </div>
                </div>
                <div className="flex flex-col items-end min-w-[120px] ml-8">
                  <div className="w-32 h-2 bg-stone-300 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-stone-800 transition-all duration-500"
                      style={{ width: `${onboardingProgress}%` }}
                    ></div>
                  </div>
                  <div className="text-xs font-mono text-stone-500 mt-1 text-right flex items-center justify-between gap-2">
                    <span className="text-stone-400 uppercase">{phase}</span>
                    <span>{onboardingProgress}%</span>
                  </div>
                  </div>
                <div className="text-right hidden md:block">
                  <div className="text-xs font-mono text-stone-500">TIMESTAMP</div>
                  <div className="font-mono text-stone-800">{new Date().toLocaleTimeString()}</div>
                </div>
             </div>

             <div className="flex-1 font-mono text-stone-800 text-sm md:text-base leading-relaxed space-y-6 max-w-2xl">
               {(() => {
                  const lastArcIndex = messages.reduce((acc, m, idx) => (m.role === 'assistant' ? idx : acc), -1);

                  return (
                  <div className="mt-6 space-y-4">
                    <div ref={chatScrollRef} className="h-48 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
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
                          <div key={`msg-${idx}-${m.content?.substring(0, 20)}`} className="flex gap-4">
                            <div className="font-bold text-stone-500 select-none w-10 text-right">
                              {label}
                            </div>
                            <div className={isArc ? 'min-h-[80px]' : 'min-h-[40px]'}>
                              {isArc && isLatestArc ? (
                                <>
                                  <TypewriterText
                                    key={`typewriter-${idx}-${m.content?.substring(0, 20)}`}
                                    speed={25}
                                    text={m.content || ''}
                                    onComplete={() => setIsTypingDone(true)}
                                    onScroll={() => {
                                      // Auto-scroll during typewriter animation
                                      if (chatScrollRef.current) {
                                        const container = chatScrollRef.current;
                                        const isNearBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 50;
                                        if (isNearBottom) {
                                          container.scrollTop = container.scrollHeight;
                                        }
                                      }
                                    }}
                                  />
                                  <span className="animate-pulse inline-block w-2 h-4 bg-stone-800 ml-1 align-middle"></span>
                                </>
                              ) : (
                                <span className="whitespace-pre-wrap">{m.content || ''}</span>
                        )}
                      </div>
                    </div>
                        );
                      })}
                </div>
                
                {mode === 'text' && (
                      <form onSubmit={handleUserSubmit} className="flex flex-col gap-2 pt-2">
                        <textarea
                          value={userInput}
                          onChange={(e) => {
                            setUserInput(e.target.value);
                            // Auto-resize textarea
                            e.target.style.height = 'auto';
                            const lineHeight = 20; // Approximate line height in pixels
                            const minLines = 1;
                            const maxLines = 3;
                            const lines = Math.min(maxLines, Math.max(minLines, e.target.value.split('\n').length));
                            e.target.style.height = `${lineHeight * lines + 16}px`; // 16px for padding
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              handleUserSubmit(e);
                            }
                          }}
                          rows={1}
                          className="bg-[#f9f0dd] border border-[#d4c5a9] rounded-sm px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-500 resize-none overflow-hidden"
                          placeholder="You: In that perfect future, first thing I do is..."
                          style={{ minHeight: '36px', maxHeight: '76px' }}
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

             <div className={`mt-auto flex justify-end transition-opacity duration-1000 ${isTypingDone ? 'opacity-100' : 'opacity-0'}`}>
                <button 
                  onClick={handleFinish}
                  disabled={isSavingProfile}
                  className="bg-stone-800 text-[#e8dcc5] px-8 py-3 rounded-sm font-bold tracking-widest hover:bg-stone-900 transition-colors shadow-lg flex items-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span>{isSavingProfile ? 'SAVING PROFILE...' : 'ACCESS DASHBOARD'}</span>
                  {!isSavingProfile && <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />}
                </button>
             </div>
             
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

export default OnboardingModule;
