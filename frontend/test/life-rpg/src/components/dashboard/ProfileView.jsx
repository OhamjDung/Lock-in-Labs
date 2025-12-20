import React from 'react';
import { 
  Terminal, Paperclip, PenTool, User, Target, Brain, Swords, ShieldAlert, 
  Clock, Video, FileText 
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import QuestItem from './QuestItem';
import SkillItem from './SkillItem';
import TimelineItem from './TimelineItem';

export default function ProfileView({ displayData, ditheredPreviewUrl, fileInputRef, takePhotoRef, sendFile, selectedAlgorithm }) {
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

              {!ditheredPreviewUrl && (
                <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between gap-2 pointer-events-auto z-30">
                  <div className="flex items-center gap-2">
                    <button title="Take photo" onClick={() => { if (takePhotoRef && takePhotoRef.current) takePhotoRef.current(); }} className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600">
                      <Video size={14} />
                    </button>
                    <button title="Upload photo" onClick={() => fileInputRef.current && fileInputRef.current.click()} className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600">
                      <FileText size={14} />
                    </button>
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
  );
}

