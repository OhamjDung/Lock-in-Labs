import React from 'react';

export default function QuestItem({ quest }) {
  return (
    <div className="flex flex-col p-4 border-b border-[#d4c5a9] last:border-0 hover:bg-[#dfd3bc] transition-colors cursor-pointer group relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className={`w-4 h-4 rounded-sm border-2 flex items-center justify-center transition-all ${quest.status === 'active' ? 'border-stone-500 group-hover:border-stone-800' : 'border-stone-300 opacity-50'}`}>
             {quest.status === 'active' && <div className="w-2 h-2 bg-stone-500 rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />}
          </div>
          <span className={`text-sm font-bold text-stone-900 group-hover:text-black transition-colors ${quest.status === 'active' ? 'underline decoration-stone-800/40 decoration-2 underline-offset-2' : 'text-stone-500'}`}>
              {quest.name}
          </span>
        </div>
        <div className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${quest.status === 'active' ? 'text-stone-700 bg-[#d4c5a9]/40 border-[#c7bba4]' : 'text-stone-400 bg-stone-100 border-stone-200'}`}>
          {quest.status === 'active' ? 'ACTIVE' : 'PENDING'}
        </div>
      </div>
      <div className="pl-7 text-xs text-stone-700 leading-relaxed font-serif italic opacity-90">{quest.description}</div>
    </div>
  );
}
