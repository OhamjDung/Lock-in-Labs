import React from 'react';

export default function TimelineItem({ item }) {
  return (
    <div className="flex flex-col items-center min-w-[100px] relative group">
      <div className="text-[10px] font-mono text-stone-600 mb-2 font-bold">{item.time}</div>
      <div className={`w-3 h-3 rounded-full border-2 z-10 transition-all ${
        item.status === 'completed' ? 'border-stone-800 bg-stone-800' : 
        item.status === 'upcoming' ? 'border-stone-500 bg-[#e8dcc5]' : 'border-[#d4c5a9] bg-[#d4c5a9]'
      }`} />
      <div className="absolute top-[21px] left-[50%] w-full h-0.5 bg-[#d4c5a9] -z-0" /> 
      <div className="mt-3 text-xs font-medium text-center text-stone-800 group-hover:text-black transition-colors px-2 bg-[#f4e8d4] backdrop-blur-sm rounded border border-[#d4c5a9] shadow-sm">
        {item.event}
      </div>
    </div>
  );
}
