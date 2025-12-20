import React from 'react';
import { Briefcase, Activity, Brain, Users } from 'lucide-react';

export default function SkillItem({ skill }) {
  return (
    <div className="flex items-center justify-between p-2 bg-[#dfd3bc]/50 rounded border border-[#d4c5a9] mb-2 shadow-sm mr-1">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-[#e8dcc5] border border-[#d4c5a9] flex items-center justify-center text-stone-600">
          {skill.pillar === 'CAREER' && <Briefcase size={14} />}
          {skill.pillar === 'PHYSICAL' && <Activity size={14} />}
          {skill.pillar === 'MENTAL' && <Brain size={14} />}
          {skill.pillar === 'SOCIAL' && <Users size={14} />}
        </div>
        <div>
          <div className="text-xs font-bold text-stone-900">{skill.name}</div>
          <div className="text-[10px] text-stone-600 font-mono">{skill.pillar} • LVL {skill.level}</div>
        </div>
      </div>
      <div className="w-16">
        <div className="h-1.5 bg-[#d4c5a9] rounded-full overflow-hidden border border-[#c7bba4]">
          <div className="h-full bg-stone-700" style={{ width: `${(skill.level / 10) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}
