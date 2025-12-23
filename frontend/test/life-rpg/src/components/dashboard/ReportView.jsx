import React, { useState, useEffect, useMemo } from 'react';
import { Activity, BarChart2, Mic, Keyboard, Check } from 'lucide-react';
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { auth } from '../../config/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import ReportingChat from './ReportingChat';
import VoiceReporting from './VoiceReporting';

export default function ReportView({ displayData }) {
  const [userId, setUserId] = useState(null);
  const [reportData, setReportData] = useState({
    quests: [],
    performanceData: []
  });
  const [skillTree, setSkillTree] = useState(null);
  const [isToggling, setIsToggling] = useState({});
  const [showChat, setShowChat] = useState(false);
  const [showVoiceLog, setShowVoiceLog] = useState(false);

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

  // Fetch report data function (extracted for reuse)
  const fetchReportData = React.useCallback(async () => {
    if (!userId) return;

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
      const treeData = data.skill_tree || { nodes: [] };
      setSkillTree(treeData);
      
      // Get today's date in ISO format
      const today = new Date().toISOString().split('T')[0];
      
      // Build a map of quest name to node_id for matching tasks
      const questToNodeId = {};
      if (treeData.nodes && Array.isArray(treeData.nodes)) {
        treeData.nodes.forEach(node => {
          if (node.name) {
            questToNodeId[node.name] = node.id;
          }
        });
      }
      
      // Get daily reports and extract task completion data
      const dailyReports = characterSheet.daily_reports || [];
      
      // Sort reports by date (most recent first)
      const sortedReports = [...dailyReports].sort((a, b) => {
        return new Date(b.date) - new Date(a.date);
      });
      
      // Extract quests from character sheet or use displayData
      const quests = [];
      if (characterSheet.goals && Array.isArray(characterSheet.goals)) {
        characterSheet.goals.forEach(goal => {
          if (goal.current_quests && Array.isArray(goal.current_quests)) {
            goal.current_quests.forEach(questName => {
              quests.push({
                name: questName,
                status: 'active', // current_quests are active
                pillar: goal.pillars && goal.pillars.length > 0 ? goal.pillars[0] : 'UNKNOWN',
              });
            });
          }
          if (goal.needed_quests && Array.isArray(goal.needed_quests)) {
            goal.needed_quests.forEach(questName => {
              // Only add if not already in quests (avoid duplicates)
              if (!quests.find(q => q.name === questName)) {
                quests.push({
                  name: questName,
                  status: 'pending', // needed_quests are pending
                  pillar: goal.pillars && goal.pillars.length > 0 ? goal.pillars[0] : 'UNKNOWN',
                });
              }
            });
          }
        });
      }
      
      // Use displayData quests if available (they have status info), otherwise use extracted quests
      const finalQuests = displayData && displayData.quests ? displayData.quests : quests;
      
      // Process each quest to get completion data
      const processedQuests = finalQuests.map(q => {
        const nodeId = questToNodeId[q.name];
        if (!nodeId) {
          // No matching node found, return quest with empty history
          return {
            ...q,
            history: [],
            completionRate: 0,
            isCompletedToday: false
          };
        }
        
        // Get today's completion status
        const todayReport = sortedReports.find(r => r.date === today);
        let isCompletedToday = false;
        if (todayReport && todayReport.tasks) {
          const todayTask = todayReport.tasks.find(t => t.node_id === nodeId);
          if (todayTask) {
            isCompletedToday = todayTask.status === 'COMPLETED' || 
                               (todayTask.completed_repetitions > 0);
          }
        }
        
        // Build history from last 7 days (most recent first, then reverse for display)
        const history = [];
        
        // Get last 7 days including today
        for (let i = 0; i < 7; i++) {
          const date = new Date();
          date.setDate(date.getDate() - i);
          const dateStr = date.toISOString().split('T')[0];
          
          const report = sortedReports.find(r => r.date === dateStr);
          let completed = false;
          if (report && report.tasks) {
            const task = report.tasks.find(t => t.node_id === nodeId);
            if (task) {
              completed = task.status === 'COMPLETED' || 
                         (task.completed_repetitions > 0);
            }
          }
          history.push(completed);
        }
        
        // Reverse to show oldest to newest (left to right)
        history.reverse();
        
        // Calculate completion rate from history
        const completedCount = history.filter(h => h).length;
        const completionRate = history.length > 0 
          ? Math.round((completedCount / history.length) * 100) 
          : 0;
        
        return {
          ...q,
          history,
          completionRate,
          isCompletedToday
        };
      });
      
      // Generate performance data from daily reports
      // Calculate average completion score per day for the last 7 days
      const performanceData = [];
      const dayLabels = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
      
      for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split('T')[0];
        
        const report = sortedReports.find(r => r.date === dateStr);
        let score = 0;
        
        if (report && report.tasks) {
          const totalTasks = report.tasks.length;
          const completedTasks = report.tasks.filter(t => 
            t.status === 'COMPLETED' || t.completed_repetitions > 0
          ).length;
          score = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
        }
        
        const dayIndex = (6 - i) % 7;
        performanceData.push({
          day: dayLabels[dayIndex],
          score
        });
      }
      
      setReportData({
        quests: processedQuests,
        performanceData: performanceData.length > 0 ? performanceData : [
          { day: 'M', score: 0 },
          { day: 'T', score: 0 },
          { day: 'W', score: 0 },
          { day: 'T', score: 0 },
          { day: 'F', score: 0 },
          { day: 'S', score: 0 },
          { day: 'S', score: 0 },
        ]
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
  }, [userId, displayData]);

  // Fetch report data for current user
  useEffect(() => {
    fetchReportData();
  }, [fetchReportData]);

  return (
    <div className="flex-1 flex flex-col gap-10 animate-in fade-in slide-in-from-bottom-4 duration-500 items-center justify-center min-h-[700px]">
      <div className="bg-[#e8dcc5] border border-[#d4c5a9] rounded-sm shadow-[0_12px_40px_rgba(0,0,0,0.5),0_4px_12px_rgba(0,0,0,0.4)] flex flex-col overflow-hidden relative rotate-0 transition-transform duration-300 w-full max-w-4xl p-0 min-h-[70vh]">
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
                // Get quest status - prefer from q (which may come from displayData or characterSheet)
                // If q doesn't have status, try to get it from displayData
                const questStatus = q.status || (displayData?.quests?.find(dq => dq.name === q.name)?.status) || 'active';
                const isActive = questStatus === 'active';
                
                // Use calculated history and completion data
                const history = q.history || []; 
                const isCompletedToday = q.isCompletedToday !== undefined ? q.isCompletedToday : false;
                
                // Check circle should be filled if quest is active AND completed today
                const shouldShowCheck = isActive && isCompletedToday;
                
                // Get node_id for this quest - try multiple matching strategies
                const nodeId = (() => {
                  if (!skillTree?.nodes || !q?.name) return null;
                  
                  // Try exact match first
                  let node = skillTree.nodes.find(n => n.name === q.name);
                  if (node) return node.id;
                  
                  // Try case-insensitive match
                  node = skillTree.nodes.find(n => n.name?.toLowerCase() === q.name?.toLowerCase());
                  if (node) return node.id;
                  
                  // Try matching with trimmed whitespace
                  node = skillTree.nodes.find(n => n.name?.trim() === q.name?.trim());
                  if (node) return node.id;
                  
                  return null;
                })();
                
                const canToggle = isActive && nodeId && userId;
                const isTogglingQuest = isToggling[nodeId] || false;

                const handleToggle = async (e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  
                  console.log('ReportView: handleToggle called', { nodeId, userId, isActive, questName: q.name });
                  
                  if (!nodeId) {
                    console.warn('ReportView: No nodeId found for quest:', q.name, 'Available nodes:', skillTree?.nodes?.map(n => n.name));
                    return;
                  }
                  
                  if (!userId) {
                    console.warn('ReportView: No userId provided');
                    return;
                  }
                  
                  if (!isActive) {
                    console.warn('ReportView: Quest is not active:', questStatus);
                    return;
                  }
                  
                  if (isTogglingQuest) {
                    console.log('ReportView: Already toggling, skipping');
                    return;
                  }

                  setIsToggling(prev => ({ ...prev, [nodeId]: true }));
                  const newCompleted = !isCompletedToday;
                  
                  console.log('ReportView: Toggling task', { userId, nodeId, questName: q.name, newCompleted });

                  try {
                    const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
                    const res = await fetch(`${backend}/api/profile/${userId}/task/${nodeId}/toggle`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                      },
                      body: JSON.stringify({ completed: newCompleted })
                    });

                    if (res.ok) {
                      const data = await res.json();
                      // Update local state
                      setReportData(prev => ({
                        ...prev,
                        quests: prev.quests.map(quest => 
                          quest.name === q.name 
                            ? { ...quest, isCompletedToday: data.completed }
                            : quest
                        )
                      }));
                      // Reload data to get updated history
                      const profileRes = await fetch(`${backend}/api/profile/${userId}`);
                      if (profileRes.ok) {
                        const profileData = await profileRes.json();
                        // Re-run the data processing logic
                        const today = new Date().toISOString().split('T')[0];
                        const updatedCharacterSheet = profileData.character_sheet || profileData;
                        const updatedTree = profileData.skill_tree || { nodes: [] };
                        const updatedReports = updatedCharacterSheet.daily_reports || [];
                        const sortedReports = [...updatedReports].sort((a, b) => {
                          return new Date(b.date) - new Date(a.date);
                        });
                        
                        // Recalculate quest data
                        const questToNodeIdMap = {};
                        if (updatedTree.nodes && Array.isArray(updatedTree.nodes)) {
                          updatedTree.nodes.forEach(node => {
                            if (node.name) {
                              questToNodeIdMap[node.name] = node.id;
                            }
                          });
                        }
                        
                        const finalQuests = displayData && displayData.quests ? displayData.quests : [];
                        const processedQuests = finalQuests.map(quest => {
                          const questNodeId = questToNodeIdMap[quest.name];
                          if (!questNodeId) {
                            return { ...quest, history: [], completionRate: 0, isCompletedToday: false };
                          }
                          
                          const todayReport = sortedReports.find(r => r.date === today);
                          let completedToday = false;
                          if (todayReport && todayReport.tasks) {
                            const todayTask = todayReport.tasks.find(t => t.node_id === questNodeId);
                            if (todayTask) {
                              completedToday = todayTask.status === 'COMPLETED' || todayTask.status === 'DONE' || (todayTask.completed_repetitions > 0);
                            }
                          }
                          
                          const history = [];
                          for (let i = 0; i < 7; i++) {
                            const date = new Date();
                            date.setDate(date.getDate() - i);
                            const dateStr = date.toISOString().split('T')[0];
                            const report = sortedReports.find(r => r.date === dateStr);
                            let completed = false;
                            if (report && report.tasks) {
                              const task = report.tasks.find(t => t.node_id === questNodeId);
                              if (task) {
                                completed = task.status === 'COMPLETED' || task.status === 'DONE' || (task.completed_repetitions > 0);
                              }
                            }
                            history.push(completed);
                          }
                          history.reverse();
                          
                          const completedCount = history.filter(h => h).length;
                          const completionRate = history.length > 0 ? Math.round((completedCount / history.length) * 100) : 0;
                          
                          return { ...quest, history, completionRate, isCompletedToday: completedToday };
                        });
                        
                        setReportData(prev => ({
                          ...prev,
                          quests: processedQuests
                        }));
                      }
                    } else {
                      console.error('Failed to toggle task completion');
                    }
                  } catch (error) {
                    console.error('Error toggling task completion:', error);
                  } finally {
                    setIsToggling(prev => ({ ...prev, [nodeId]: false }));
                  }
                };

                return (
                  <div 
                    key={i} 
                    className="p-4 flex items-center justify-between hover:bg-[#dcd0b9]/30 transition-colors group"
                  >
                    <div className="flex items-center gap-4">
                      <button
                        type="button"
                        onClick={(e) => {
                          console.log('ReportView: RAW CLICK EVENT FIRED!', { 
                            nodeId, 
                            userId, 
                            canToggle, 
                            questName: q.name,
                            disabled: !canToggle || isTogglingQuest,
                            isActive,
                            hasNodeId: !!nodeId,
                            isTogglingQuest
                          });
                          e.stopPropagation();
                          e.preventDefault();
                          handleToggle(e);
                        }}
                        onMouseEnter={() => {
                          console.log('ReportView: Mouse entered button', { nodeId, userId, canToggle, questName: q.name });
                        }}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          console.log('ReportView: Mouse down on button');
                        }}
                        disabled={false}
                        style={{ 
                          pointerEvents: 'auto',
                          zIndex: 50,
                          position: 'relative',
                          minWidth: '24px',
                          minHeight: '24px'
                        }}
                        className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                          shouldShowCheck 
                            ? 'bg-stone-800 border-stone-800 text-white cursor-pointer hover:bg-stone-900 active:scale-95' 
                            : canToggle
                            ? 'border-stone-400 text-transparent cursor-pointer hover:border-stone-600 hover:bg-stone-100 active:scale-95'
                            : 'border-stone-400 text-transparent cursor-not-allowed opacity-50'
                        } ${isTogglingQuest ? 'opacity-50' : ''}`}
                        title={
                          !isActive ? 'Quest is not active' :
                          !nodeId ? `No matching node found for: ${q.name}` :
                          !userId ? 'User not logged in' :
                          isTogglingQuest ? 'Updating...' :
                          shouldShowCheck ? 'Mark as incomplete' : 'Mark as complete'
                        }
                      >
                        {shouldShowCheck && <Check size={14} strokeWidth={4} />}
                      </button>
                      <div>
                        <div className="font-bold text-stone-800 text-sm">{q.name}</div>
                        <div className="text-[10px] font-mono text-stone-500 uppercase">{q.pillar || 'UNKNOWN'} PROTOCOL</div>
                      </div>
                    </div>
                    
                    {/* History Visualization */}
                    <div className="flex items-center gap-4">
                      <div className="flex gap-1">
                        {history.length > 0 ? (
                          history.map((done, hIdx) => (
                            <div 
                              key={hIdx} 
                              className={`w-2 h-2 rounded-full ${done ? 'bg-stone-400' : 'bg-stone-200 border border-stone-300'}`}
                              title={done ? "Completed" : "Missed"}
                            />
                          ))
                        ) : (
                          // Show empty dots if no history available
                          Array.from({ length: 7 }).map((_, hIdx) => (
                            <div 
                              key={hIdx} 
                              className="w-2 h-2 rounded-full bg-stone-200 border border-stone-300"
                              title="No data"
                            />
                          ))
                        )}
                      </div>
                      <div className="text-xs font-mono text-stone-400 w-12 text-right">{q.completionRate || 0}%</div>
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
                  { day: 'M', score: 0 },
                  { day: 'T', score: 0 },
                  { day: 'W', score: 0 },
                  { day: 'T', score: 0 },
                  { day: 'F', score: 0 },
                  { day: 'S', score: 0 },
                  { day: 'S', score: 0 },
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
          <button 
            onClick={() => setShowVoiceLog(true)}
            className="flex-1 bg-stone-800 text-[#e8dcc5] py-3 rounded-sm font-bold flex items-center justify-center gap-3 hover:bg-stone-900 transition-colors shadow-lg active:transform active:scale-[0.98]"
          >
            <Mic size={18} />
            <span>INITIATE VOICE LOG</span>
          </button>
          <button 
            onClick={() => setShowChat(true)}
            className="flex-1 bg-white border border-[#c7bba4] text-stone-800 py-3 rounded-sm font-bold flex items-center justify-center gap-3 hover:bg-[#f5efe6] transition-colors shadow-sm active:transform active:scale-[0.98]"
          >
            <Keyboard size={18} />
            <span>MANUAL ENTRY</span>
          </button>
        </div>

      </div>

      {/* Reporting Chat Modal */}
      {showChat && (
        <ReportingChat
          userId={userId}
          onClose={() => {
            setShowChat(false);
          }}
          onReportComplete={() => {
            // Refresh data when report is completed
            fetchReportData();
          }}
        />
      )}

      {/* Voice Reporting Modal */}
      {showVoiceLog && (
        <VoiceReporting
          userId={userId}
          onClose={() => {
            setShowVoiceLog(false);
          }}
          onReportComplete={() => {
            // Refresh data when report is completed
            fetchReportData();
          }}
        />
      )}
    </div>
  );
}

