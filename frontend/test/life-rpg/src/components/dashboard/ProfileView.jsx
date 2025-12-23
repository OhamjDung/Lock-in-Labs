import React, { useState, useRef, useEffect } from 'react';
import { 
  Terminal, Paperclip, PenTool, User, Target, Brain, Swords, ShieldAlert, 
  Clock, Video, FileText, X, Camera, Plus, Save
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import QuestItem from './QuestItem';
import SkillItem from './SkillItem';
import TimelineItem from './TimelineItem';

export default function ProfileView({ displayData, ditheredPreviewUrl, fileInputRef, takePhotoRef, sendFile, selectedAlgorithm, skillTree, userId, characterSheet, onQuestToggle }) {
  const [showCamera, setShowCamera] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [showNewTaskModal, setShowNewTaskModal] = useState(false);
  const [newTaskName, setNewTaskName] = useState('');
  const [selectedGoal, setSelectedGoal] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Start camera when modal opens
  useEffect(() => {
    if (showCamera) {
      startCamera();
    } else {
      stopCamera();
    }
    return () => stopCamera();
  }, [showCamera]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: 'user' } 
      });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error('Error accessing camera:', err);
      alert('Unable to access camera. Please check permissions.');
      setShowCamera(false);
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const capturePhoto = async () => {
    try {
      const video = videoRef.current;
      if (!video) {
        console.error('Video element not found');
        return;
      }

      // Wait for video to be ready
      if (video.readyState < 2) {
        console.log('Video not ready, waiting...');
        await new Promise((resolve) => {
          const onLoadedMetadata = () => {
            video.removeEventListener('loadedmetadata', onLoadedMetadata);
            resolve();
          };
          video.addEventListener('loadedmetadata', onLoadedMetadata);
          // Timeout after 2 seconds
          setTimeout(resolve, 2000);
        });
      }

      if (!video.videoWidth || !video.videoHeight) {
        console.error('Video dimensions not available:', video.videoWidth, video.videoHeight);
        alert('Camera not ready. Please wait a moment and try again.');
        return;
      }

      // Create or use existing canvas
      let canvas = canvasRef.current;
      if (!canvas) {
        canvas = document.createElement('canvas');
        canvasRef.current = canvas;
      }
      
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      
      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert to blob
      canvas.toBlob(async (blob) => {
        if (!blob) {
          console.error('Failed to create blob from canvas');
          alert('Failed to capture photo. Please try again.');
          return;
        }
        
        try {
          const file = new File([blob], 'capture.png', { type: 'image/png' });
          await sendFile(file, selectedAlgorithm, true); // Save to Firebase
          setShowCamera(false);
          stopCamera();
        } catch (err) {
          console.error('Error sending file:', err);
          alert('Failed to process photo. Please try again.');
        }
      }, 'image/png');
    } catch (err) {
      console.error('Error capturing photo:', err);
      alert('Failed to capture photo. Please try again.');
    }
  };
  return (
    <div className="flex-1 flex flex-col gap-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
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
            {displayData.quests.map((q, idx) => {
              // Check if quest is completed today
              const nodeId = skillTree?.nodes?.find(n => n.name === q.name)?.id;
              let isCompletedToday = false;
              if (nodeId && characterSheet?.daily_reports) {
                const today = new Date().toISOString().split('T')[0];
                const todayReport = characterSheet.daily_reports.find(r => r.date === today);
                if (todayReport?.tasks) {
                  const todayTask = todayReport.tasks.find(t => t.node_id === nodeId);
                  if (todayTask) {
                    isCompletedToday = todayTask.status === 'COMPLETED' || todayTask.status === 'DONE' || (todayTask.completed_repetitions > 0);
                  }
                }
              }
              return (
                <QuestItem 
                  key={idx} 
                  quest={q} 
                  skillTree={skillTree}
                  userId={userId}
                  isCompletedToday={isCompletedToday}
                  onToggle={onQuestToggle}
                />
              );
            })}
            {displayData.quests.length === 0 && <div className="p-8 text-center text-stone-500 text-sm font-serif italic">No active directives found.</div>}
            <button
              onClick={() => setShowNewTaskModal(true)}
              className="p-6 w-full flex items-center justify-center text-stone-500 hover:text-stone-700 cursor-pointer transition-all group"
            >
              <span className="text-xs font-mono uppercase border-b border-dashed border-stone-400 group-hover:border-stone-600 flex items-center gap-2">
                <PenTool size={12} /> Log New Task
              </span>
            </button>
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

              <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between gap-2 pointer-events-auto z-30">
                <div className="flex items-center gap-2">
                  <button 
                    title="Take photo" 
                    onClick={() => setShowCamera(true)} 
                    className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600 hover:bg-[#dfd3bc] transition-colors"
                  >
                    <Video size={14} />
                  </button>
                  <button 
                    title="Upload photo" 
                    onClick={() => fileInputRef.current && fileInputRef.current.click()} 
                    className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600 hover:bg-[#dfd3bc] transition-colors"
                  >
                    <FileText size={14} />
                  </button>
                </div>
                <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={async (e) => {
                  const f = e.target.files && e.target.files[0];
                  if (f) await sendFile(f, selectedAlgorithm, true); // Save to Firebase
                  e.target.value = null;
                }} />
              </div>
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

      {/* Camera Modal */}
      {showCamera && (
        <div className="fixed inset-0 z-[200] bg-black/90 flex items-center justify-center p-4">
          <div className="relative bg-stone-900 rounded-lg shadow-2xl max-w-2xl w-full overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-center p-4 border-b border-stone-700">
              <h3 className="text-stone-200 font-bold text-lg">Take Photo</h3>
              <button
                onClick={() => {
                  setShowCamera(false);
                  stopCamera();
                }}
                className="text-stone-400 hover:text-stone-200 transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            {/* Video Preview */}
            <div className="relative bg-black aspect-video flex items-center justify-center">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
                onLoadedMetadata={() => {
                  console.log('Video metadata loaded:', videoRef.current?.videoWidth, videoRef.current?.videoHeight);
                }}
              />
              {!cameraStream && (
                <div className="absolute inset-0 flex items-center justify-center text-stone-400">
                  <div className="text-center">
                    <Video size={48} className="mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Starting camera...</p>
                  </div>
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="p-4 flex justify-center gap-4 border-t border-stone-700">
              <button
                onClick={() => {
                  setShowCamera(false);
                  stopCamera();
                }}
                className="px-6 py-2 bg-stone-700 text-stone-200 rounded hover:bg-stone-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('Capture button clicked, cameraStream:', !!cameraStream, 'video:', !!videoRef.current);
                  capturePhoto();
                }}
                disabled={!cameraStream}
                className="px-6 py-2 bg-stone-800 text-stone-100 rounded hover:bg-stone-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <Camera size={18} />
                Capture
              </button>
            </div>
          </div>
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}

      {/* New Task Modal */}
      {showNewTaskModal && (
        <div className="fixed inset-0 z-[200] bg-black/90 flex items-center justify-center p-4">
          <div className="relative bg-[#e8dcc5] border-2 border-[#d4c5a9] rounded-sm shadow-2xl max-w-md w-full overflow-hidden">
            {/* Texture */}
            <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
            
            {/* Header */}
            <div className="border-b-2 border-stone-800 p-4 flex justify-between items-center relative z-10 bg-[#dfd3bc]/30">
              <h3 className="text-xl font-serif font-black text-stone-900 tracking-tight uppercase">Log New Task</h3>
              <button
                onClick={() => {
                  setShowNewTaskModal(false);
                  setNewTaskName('');
                  setSelectedGoal('');
                }}
                className="text-stone-600 hover:text-stone-900 transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 relative z-10 space-y-4">
              <div>
                <label className="block text-sm font-bold text-stone-800 mb-2 uppercase tracking-wide">
                  Task Name
                </label>
                <input
                  type="text"
                  value={newTaskName}
                  onChange={(e) => setNewTaskName(e.target.value)}
                  placeholder="e.g., Meditate for 10 minutes"
                  className="w-full px-4 py-2 bg-white/80 border border-[#d4c5a9] rounded-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-800 focus:border-transparent"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-stone-800 mb-2 uppercase tracking-wide">
                  Associated Goal
                </label>
                <select
                  value={selectedGoal}
                  onChange={(e) => setSelectedGoal(e.target.value)}
                  className="w-full px-4 py-2 bg-white/80 border border-[#d4c5a9] rounded-sm text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800 focus:border-transparent"
                >
                  <option value="">Select a goal...</option>
                  {(() => {
                    const goals = characterSheet?.goals || [];
                    const goalsList = Array.isArray(goals) ? goals : Object.values(goals);
                    return goalsList.map((goal, idx) => {
                      const goalName = typeof goal === 'string' ? goal : goal.name;
                      const pillars = typeof goal === 'object' ? goal.pillars : null;
                      return (
                        <option key={idx} value={goalName}>
                          {goalName} {pillars && pillars.length > 0 ? `(${pillars[0]})` : ''}
                        </option>
                      );
                    });
                  })()}
                </select>
              </div>

              {(!characterSheet?.goals || characterSheet.goals.length === 0) && (
                <div className="text-xs text-stone-600 italic">
                  No goals available. Please complete onboarding first.
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 bg-[#d4c5a9]/30 border-t border-[#d4c5a9] flex gap-4 relative z-10">
              <button
                onClick={() => {
                  setShowNewTaskModal(false);
                  setNewTaskName('');
                  setSelectedGoal('');
                }}
                className="flex-1 bg-white border border-[#c7bba4] text-stone-800 py-2 rounded-sm font-bold flex items-center justify-center gap-2 hover:bg-[#f5efe6] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (!newTaskName.trim() || !selectedGoal || !userId) {
                    alert('Please fill in all fields');
                    return;
                  }

                  setIsSaving(true);
                  try {
                    const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
                    const res = await fetch(`${backend}/api/profile/${userId}/quest/add`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                      },
                      body: JSON.stringify({
                        task_name: newTaskName.trim(),
                        goal_name: selectedGoal
                      })
                    });

                    if (res.ok) {
                      const data = await res.json();
                      console.log('Task added successfully:', data);
                      setShowNewTaskModal(false);
                      setNewTaskName('');
                      setSelectedGoal('');
                      
                      // Reload profile data
                      if (onQuestToggle) {
                        await onQuestToggle();
                      }
                    } else {
                      const errorText = await res.text();
                      console.error('Failed to add task:', res.status, errorText);
                      alert(`Failed to add task: ${errorText || res.statusText}`);
                    }
                  } catch (error) {
                    console.error('Error adding task:', error);
                    alert('Error adding task. Please try again.');
                  } finally {
                    setIsSaving(false);
                  }
                }}
                disabled={!newTaskName.trim() || !selectedGoal || isSaving}
                className="flex-1 bg-stone-800 text-[#e8dcc5] py-2 rounded-sm font-bold flex items-center justify-center gap-2 hover:bg-stone-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? (
                  <>Saving...</>
                ) : (
                  <>
                    <Save size={16} />
                    Add Task
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
