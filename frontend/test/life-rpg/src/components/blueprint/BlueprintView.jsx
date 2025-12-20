import React, { useState } from 'react';
import TreeVisualizer from './TreeVisualizer';

export default function BlueprintView({ skillTree, characterSheet }) {
  const [activePillar, setActivePillar] = useState('CAREER');

  return (
    <div className="h-[80vh] w-full bg-[#f0f9ff] border-4 border-white rounded-sm relative overflow-hidden animate-in zoom-in-95 duration-500 group shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] rotate-1 flex flex-col">
      <div className="absolute top-0 left-0 right-0 z-40 p-6 flex justify-between items-start pointer-events-none">
        <div>
          <div className="text-3xl font-black text-blue-900 uppercase tracking-tighter opacity-90 drop-shadow-sm">Skill Architecture</div>
          <div className="text-xs font-mono text-blue-500">SYSTEM_BLUEPRINT_V2 // {activePillar}</div>
        </div>
        <div className="pointer-events-auto bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-blue-200 shadow-sm flex gap-1">
          {['CAREER', 'PHYSICAL', 'SOCIAL', 'MENTAL'].map(pillar => (
            <button 
              key={pillar} 
              onClick={() => setActivePillar(pillar)} 
              className={`px-3 py-1.5 rounded text-[10px] font-bold transition-all ${activePillar === pillar ? 'bg-blue-600 text-white shadow-md' : 'text-blue-400 hover:bg-blue-50 hover:text-blue-600'}`}
            >
              {pillar}
            </button>
          ))}
        </div>
      </div>
      <TreeVisualizer pillar={activePillar} skillTree={skillTree} characterSheet={characterSheet} />
    </div>
  );
}

