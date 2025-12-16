export function Avatar() {
  return (
    <div className="relative w-[320px]">
      {/* Polaroid-style photo */}
      <div className="bg-white p-4 pb-16 shadow-xl relative transform rotate-1">
        <div className="relative">
          <div className="w-full aspect-square bg-gradient-to-br from-purple-400 via-pink-400 to-blue-400 flex items-center justify-center overflow-hidden">
            <div className="text-9xl">⚔️</div>
          </div>
          {/* Tape on corners */}
          <div className="absolute -top-2 -left-1 w-12 h-6 bg-yellow-100/80 border border-yellow-200/50 -rotate-45" />
          <div className="absolute -top-2 -right-1 w-12 h-6 bg-yellow-100/80 border border-yellow-200/50 rotate-45" />
        </div>
        <div className="mt-3 text-center" style={{ fontFamily: 'Courier New, monospace' }}>
          <div className="text-sm">Level 1 Hero ★</div>
        </div>
      </div>

      {/* Sticky note with name */}
      <div className="absolute -right-8 top-12 bg-yellow-200 p-3 shadow-lg transform rotate-6 w-32 border-l-2 border-yellow-300">
        <div style={{ fontFamily: 'Comic Sans MS, cursive' }}>
          <div className="text-lg">Hero</div>
          <div className="text-lg">Name</div>
          <div className="text-xs mt-1">✨ The Brave</div>
        </div>
      </div>

      {/* Stats on lined paper */}
      <div className="bg-white mt-4 p-4 shadow-lg relative transform -rotate-1" 
           style={{ 
             backgroundImage: 'repeating-linear-gradient(transparent, transparent 24px, #e5e7eb 24px, #e5e7eb 25px)',
             backgroundSize: '100% 25px'
           }}>
        <div className="relative z-10">
          <div className="text-red-600 mb-3" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            <span className="text-xs">HP:</span> ████████░░ 80/100
          </div>
          <div className="text-blue-600 mb-3" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            <span className="text-xs">MP:</span> ██████░░░░ 60/100
          </div>
          <div className="text-green-600 mb-3" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            <span className="text-xs">XP:</span> ██░░░░░░░░ 250/1000
          </div>
          
          {/* Hand-drawn box for stats */}
          <div className="border-2 border-black border-dashed p-2 mt-3">
            <div className="grid grid-cols-2 gap-2 text-sm" style={{ fontFamily: 'Courier New, monospace' }}>
              <div>STR: <span className="text-lg">12</span></div>
              <div>DEX: <span className="text-lg">10</span></div>
              <div>INT: <span className="text-lg">14</span></div>
              <div>WIS: <span className="text-lg">11</span></div>
            </div>
          </div>
        </div>
        
        {/* Paperclip */}
        <div className="absolute -top-3 right-4 text-3xl opacity-60">📎</div>
      </div>

      {/* Small doodles */}
      <div className="absolute bottom-2 left-2 text-xs rotate-12">
        ⭐ ✨ ★
      </div>
    </div>
  );
}