import React, { useState, useRef, useEffect } from 'react';
import { Send, X, User, Check, X as XIcon, Clock, Calendar } from 'lucide-react';
import TypewriterText from '../onboarding/TypewriterText';
import DecisionCard from './DecisionCard';
import { auth } from '../../config/firebase';
import { onAuthStateChanged } from 'firebase/auth';

export default function ReportingChat({ onClose, userId, onReportComplete }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [currentTypingIndex, setCurrentTypingIndex] = useState(-1);
  const [isTypingComplete, setIsTypingComplete] = useState({});
  const [currentPhase, setCurrentPhase] = useState('REVIEW');
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const hasInitialized = useRef(false);

  // Initialize conversation on mount
  useEffect(() => {
    if (!hasInitialized.current && userId) {
      hasInitialized.current = true;
      // Send empty message to get initial greeting
      handleInitialMessage();
    }
  }, [userId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, currentTypingIndex]);

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
      
      // Update phase
      if (data.phase) {
        setCurrentPhase(data.phase);
      }
      
      // Add initial assistant message with decisions and schedule preview
      const assistantMessage = { 
        role: 'assistant', 
        content: data.reply,
        isTyping: true,
        decisions: data.decisions || null,
        schedule_preview: data.schedule_preview || null,
        phase: data.phase || 'REVIEW'
      };
      
      setMessages([assistantMessage]);
      setCurrentTypingIndex(0);
      setIsTypingComplete({ 0: false });
    } catch (error) {
      console.error('Error initializing chat:', error);
      setMessages([{
        role: 'assistant',
        content: 'Sorry, I encountered an error initializing the chat. Please try again.',
        isTyping: false
      }]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isSending) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsSending(true);

    // Build conversation history BEFORE adding new message (API will add it)
    const conversationHistory = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    // Add user message immediately to UI
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
          conversation_history: conversationHistory, // Without the current message (API adds it)
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from reporting agent');
      }

      const data = await response.json();
      
      // Update phase
      if (data.phase) {
        setCurrentPhase(data.phase);
      }
      
      // Add assistant reply with decisions and schedule preview
      // Use functional update to get the latest messages (including the user message we just added)
      setMessages(prev => {
        const newIndex = prev.length;
        const assistantMessage = { 
          role: 'assistant', 
          content: data.reply,
          isTyping: true,
          decisions: data.decisions || null,
          schedule_preview: data.schedule_preview || null,
          phase: data.phase || currentPhase
        };
        
        setCurrentTypingIndex(newIndex);
        setIsTypingComplete(prevComplete => ({ ...prevComplete, [newIndex]: false }));
        
        return [...prev, assistantMessage];
      });

      // If conversation is complete, refresh data and close after a delay
      if (data.is_complete) {
        // Call refresh callback if provided
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
        content: 'Sorry, I encountered an error. Please try again.',
        isTyping: false
      }]);
    } finally {
      setIsSending(false);
    }
  };

  const handleTypingComplete = (index) => {
    setIsTypingComplete(prev => ({ ...prev, [index]: true }));
    setCurrentTypingIndex(-1);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const sendActionMessage = async (messageText) => {
    if (isSending) return;

    setIsSending(true);

    // Build conversation history BEFORE adding the new message
    // API will add the current message itself
    const conversationHistory = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    // Add user message immediately to UI
    const newUserMessage = { role: 'user', content: messageText };
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
          message: messageText,
          conversation_history: conversationHistory,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from reporting agent');
      }

      const data = await response.json();
      
      // Update phase
      if (data.phase) {
        setCurrentPhase(data.phase);
      }
      
      // Add assistant reply with decisions and schedule preview
      // Use functional update to get the latest messages (including the user message we just added)
      setMessages(prev => {
        const newIndex = prev.length;
        const assistantMessage = { 
          role: 'assistant', 
          content: data.reply,
          isTyping: true,
          decisions: data.decisions || null,
          schedule_preview: data.schedule_preview || null,
          phase: data.phase || currentPhase
        };
        
        setCurrentTypingIndex(newIndex);
        setIsTypingComplete(prevComplete => ({ ...prevComplete, [newIndex]: false }));
        
        return [...prev, assistantMessage];
      });

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
      console.error('Error sending action message:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        isTyping: false
      }]);
    } finally {
      setIsSending(false);
    }
  };

  const handleAcceptDecisions = async (decisionIds = null) => {
    // Accept specific decisions or all if null
    const acceptMessage = decisionIds 
      ? `accept ${decisionIds.join(',')}`
      : 'accept all';
    
    await sendActionMessage(acceptMessage);
  };

  const handleRejectDecisions = async () => {
    await sendActionMessage('skip');
  };

  const handleConfirmSchedule = async () => {
    await sendActionMessage('confirm');
  };

  const handleSelectDecision = (decisionIndex) => {
    // Accept a specific decision by index (1-indexed for user)
    handleAcceptDecisions([decisionIndex + 1]);
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
            <span className="font-mono text-stone-600 font-bold tracking-widest text-xs">DAILY REPORT</span>
        </div>

        <div className="absolute inset-0 opacity-[0.15] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        <div className="flex-1 p-8 md:p-16 flex flex-col relative animate-in fade-in slide-in-from-right-8 duration-700 bg-[#f4e9d5]">
          <div className="border-b border-stone-400 pb-4 mb-8 flex justify-between items-end">
            <div className="flex items-center gap-4">
              <div className="border border-stone-800 p-1 rounded-sm"><User size={32} className="text-stone-800" /></div>
              <div>
                <h3 className="font-mono font-bold text-lg tracking-widest text-stone-900 uppercase">Daily Check-In Transcript</h3>
                <div className="text-xs font-mono text-stone-500">SUBJECT: {userId?.toUpperCase() || 'USER'} // MODE: TEXT</div>
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
              <div ref={chatContainerRef} className="h-64 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                {messages.length === 0 && (
                  <div className="text-[11px] text-stone-500 italic">
                    Start the tape. Tell me about your day.
                  </div>
                )}

                {messages.map((m, idx) => {
                  const label = m.role === 'user' ? 'You:' : 'RPT:';
                  const isLatestReport = m.role === 'assistant' && idx === messages.length - 1;
                  const isTyping = currentTypingIndex === idx && !isTypingComplete[idx];
                  const messagePhase = m.phase || currentPhase;

                  return (
                    <div key={`msg-${idx}-${m.content?.substring(0, 20)}`} className="space-y-4">
                      <div className="flex gap-4">
                        <div className="font-bold text-stone-500 select-none w-10 text-right">
                          {label}
                        </div>
                        <div className="flex-1">
                          {m.role === 'user' ? (
                            <div className="whitespace-pre-wrap">{m.content}</div>
                          ) : (
                            <div className="whitespace-pre-wrap">
                              {isTyping ? (
                                <TypewriterText
                                  text={m.content}
                                  speed={20}
                                  onComplete={() => handleTypingComplete(idx)}
                                />
                              ) : (
                                m.content
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Display Decision Cards (PROGRESSION phase) */}
                      {m.role === 'assistant' && !isTyping && m.decisions && m.decisions.length > 0 && (
                        <div className="ml-14 space-y-4">
                          <div className="text-xs font-mono text-stone-600 uppercase tracking-wider mb-2">
                            DECISION CARDS ({m.decisions.length})
                          </div>
                          {m.decisions.map((decision, dIdx) => (
                            <div key={dIdx} className="space-y-2">
                              <DecisionCard 
                                decision={decision} 
                                onCitationClick={(citation) => {
                                  console.log('Citation clicked:', citation);
                                }}
                              />
                              <div className="flex gap-2 ml-4">
                                <button
                                  onClick={() => handleSelectDecision(dIdx)}
                                  disabled={isSending}
                                  className="flex items-center gap-2 px-4 py-2 bg-green-700 text-white text-xs font-bold uppercase tracking-wider hover:bg-green-800 transition-colors rounded-sm border border-green-800 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Check size={14} />
                                  Accept This
                                </button>
                              </div>
                            </div>
                          ))}
                          <div className="flex gap-2 ml-4 mt-4">
                            <button
                              onClick={() => handleAcceptDecisions(null)}
                              disabled={isSending}
                              className="flex items-center gap-2 px-4 py-2 bg-green-700 text-white text-xs font-bold uppercase tracking-wider hover:bg-green-800 transition-colors rounded-sm border border-green-800 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <Check size={14} />
                              Accept All
                            </button>
                            <button
                              onClick={handleRejectDecisions}
                              disabled={isSending}
                              className="flex items-center gap-2 px-4 py-2 bg-stone-600 text-white text-xs font-bold uppercase tracking-wider hover:bg-stone-700 transition-colors rounded-sm border border-stone-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <XIcon size={14} />
                              Skip All
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Display Schedule Preview (SCHEDULING/COMPLETED phase) */}
                      {m.role === 'assistant' && !isTyping && m.schedule_preview && m.schedule_preview.length > 0 && (
                        <div className="ml-14 space-y-3">
                          <div className="text-xs font-mono text-stone-600 uppercase tracking-wider mb-2 flex items-center gap-2">
                            <Calendar size={14} />
                            SCHEDULE PREVIEW ({m.schedule_preview.length} items)
                          </div>
                          <div className="bg-[#e8dcc5] border-2 border-[#d4c5a9] rounded-sm p-4 space-y-2">
                            {m.schedule_preview.map((item, sIdx) => (
                              <div 
                                key={sIdx} 
                                className="flex items-center gap-3 p-2 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm hover:bg-[#ede4d0] transition-colors"
                              >
                                <div className="flex items-center gap-2 min-w-[80px]">
                                  <Clock size={14} className="text-stone-600" />
                                  <span className="font-mono font-bold text-stone-900 text-sm">{item.time || '09:00'}</span>
                                </div>
                                <div className="flex-1">
                                  <div className="font-serif text-stone-900 font-bold">{item.label || item.task || 'Task'}</div>
                                  {item.pillar && (
                                    <div className="text-[10px] font-mono text-stone-600 uppercase mt-0.5">{item.pillar} PROTOCOL</div>
                                  )}
                                </div>
                                {item.status && (
                                  <div className={`text-xs font-mono px-2 py-1 rounded ${
                                    item.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800 border border-yellow-300' :
                                    item.status === 'DONE' ? 'bg-green-100 text-green-800 border border-green-300' :
                                    'bg-stone-100 text-stone-800 border border-stone-300'
                                  }`}>
                                    {item.status}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                          {messagePhase === 'COMPLETED' && (
                            <div className="flex gap-2 ml-4 mt-3">
                              <button
                                onClick={handleConfirmSchedule}
                                disabled={isSending}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-700 text-white text-xs font-bold uppercase tracking-wider hover:bg-blue-800 transition-colors rounded-sm border border-blue-800 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                <Check size={14} />
                                Confirm Schedule
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-stone-400 pt-6 mt-6">
            <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your response..."
                disabled={isSending}
                className="flex-1 bg-transparent border-b-2 border-stone-400 py-2 px-4 font-mono text-stone-900 focus:outline-none focus:border-stone-800 transition-colors placeholder-stone-500/30 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!inputValue.trim() || isSending}
                className="bg-stone-900 text-[#e8dcc5] px-6 py-2 font-bold tracking-[0.2em] uppercase hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg flex items-center justify-center gap-2 border border-stone-700"
              >
                <Send size={16} />
                {isSending ? 'Sending...' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

