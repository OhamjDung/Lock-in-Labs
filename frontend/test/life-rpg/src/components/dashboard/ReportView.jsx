import React, { useState, useEffect } from 'react';
import { Activity, BarChart2, Mic, Keyboard, Check } from 'lucide-react';
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { auth } from '../../config/firebase';
import { onAuthStateChanged } from 'firebase/auth';

export default function ReportView({ displayData }) {
  const [userId, setUserId] = useState(null);
  const [reportData, setReportData] = useState({
    quests: [],
    performanceData: []
  });

  // Get current user
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        setUserId(user.uid);
      } else {
        setUserId(null);
      }
    });
    return () => unsubscribe();
  }, []);

  // Fetch report data for current user
  useEffect(() => {
    if (!userId) return;

    const fetchReportData = async () => {
      try {
        const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
        const res = await fetch(`${backend}/api/profile/${userId}`);
        
        if (!res.ok) {
          console.warn('Failed to fetch profile for report');
          // Use displayData as fallback
          if (displayData && displayData.quests) {
            setReportData({
              quests: displayData.quests.map(q => ({
                ...q,
                history: [],
                completionRate: 0,
                isCompletedToday: false
              })),
              performanceData: []
            });
          }
          return;
        }

        const data = await res.json();
        const characterSheet = data.character_sheet || data;
        
        // Extract quests from character sheet
        const quests = [];
        if (characterSheet.goals && Array.isArray(characterSheet.goals)) {
          characterSheet.goals.forEach(goal => {
            // Add current_quests as quests
            if (goal.current_quests && Array.isArray(goal.current_quests)) {
              goal.current_quests.forEach(questName => {
                quests.push({
                  name: questName,
                  pillar: goal.pillars && goal.pillars.length > 0 ? goal.pillars[0] : 'UNKNOWN',
                  history: [], // TODO: Get from daily reports
                  completionRate: 0, // TODO: Calculate from history
                  isCompletedToday: false // TODO: Check today's reports
                });
              });
            }
          });
        }

        // Generate performance data (TODO: Get from actual daily reports)
        // For now, use displayData quests if available, otherwise use extracted quests
        const finalQuests = displayData && displayData.quests ? displayData.quests : quests;
        
        setReportData({
          quests: finalQuests.map((q, i) => ({
            ...q,
            history: [true, true, false, true, true], // TODO: Get real history
            completionRate: 80, // TODO: Calculate from real data
            isCompletedToday: i % 3 === 0 // TODO: Check real status
          })),
          performanceData: [
            { day: 'M', score: 65 },
            { day: 'T', score: 40 },
            { day: 'W', score: 75 },
            { day: 'T', score: 50 },
            { day: 'F', score: 85 },
            { day: 'S', score: 30 },
            { day: 'S', score: 60 },
          ] // TODO: Get from actual daily reports
        });
      } catch (error) {
        console.error('Error fetching report data:', error);
        // Fallback to displayData
        if (displayData && displayData.quests) {
          setReportData({
            quests: displayData.quests.map(q => ({
              ...q,
              history: [],
              completionRate: 0,
              isCompletedToday: false
            })),
            performanceData: []
          });
        }
      }
    };

    fetchReportData();
  }, [userId, displayData]);

  return (
    <div className="flex-1 flex flex-col gap-10 animate-in fade-in slide-in-from-bottom-4 duration-500 items-center justify-center min-h-[700px]">
      <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm shadow-[0_25px_50px_-12px_rgba(0,0,0,0.3)] flex flex-col overflow-hidden relative rotate-0 transition-transform duration-300 w-full max-w-4xl p-0 min-h-[70vh]">
        {/* Texture */}
        <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
        
        {/* Header */}
        <div className="border-b-2 border-stone-800 p-8 flex justify-between items-end relative z-10 bg-[#dfd3bc]/30">
          <div>
            <div className="text-xs font-mono text-stone-500 mb-2">INTELLIGENCE BRIEFING // DAILY LOG</div>
            <h1 className="text-4xl font-serif font-black text-stone-900 tracking-tight uppercase">Field Report</h1>
            <div className="text-xs font-mono text-stone-600 mt-1">OPERATIVE: {userId || displayData?.user_id || 'UNKNOWN'}</div>
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
              {(reportData.quests.length > 0 ? reportData.quests : (displayData?.quests || [])).map((q, i) => {
                const history = q.history || [true, true, false, true, true]; 
                const isCompletedToday = q.isCompletedToday !== undefined ? q.isCompletedToday : (i % 3 === 0);

                return (
                  <div key={i} className="p-4 flex items-center justify-between hover:bg-[#dcd0b9]/30 transition-colors group">
                    <div className="flex items-center gap-4">
                      <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${isCompletedToday ? 'bg-stone-800 border-stone-800 text-white' : 'border-stone-400 text-transparent'}`}>
                        <Check size={14} strokeWidth={4} />
                      </div>
                      <div>
                        <div className="font-bold text-stone-800 text-sm">{q.name}</div>
                        <div className="text-[10px] font-mono text-stone-500 uppercase">{q.pillar} PROTOCOL</div>
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
                      <div className="text-xs font-mono text-stone-400 w-12 text-right">{q.completionRate || 80}%</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Performance Summary */}
          <div>
            <h3 className="font-bold border-b-2 border-stone-800 mb-4 text-sm uppercase tracking-wider text-stone-900 flex items-center gap-2">
              <BarChart2 size={16} /> Performance Analytics
            </h3>
            <div className="bg-white/40 border border-[#d4c5a9] p-4 h-48 rounded-sm">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reportData.performanceData.length > 0 ? reportData.performanceData : [
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
  );
}

