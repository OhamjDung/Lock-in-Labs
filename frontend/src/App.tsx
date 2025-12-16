import { Avatar } from './components/Avatar';
import { QuestLog } from './components/QuestLog';
import { SkillTree } from './components/SkillTree';
import { Timeline } from './components/Timeline';
import geminiBg from './assets/gemini.jpg';

export default function App() {
  return (
    <div className="min-h-screen relative p-4 md:p-8 overflow-hidden">
      {/* Background Image - Using local gemini asset */}
        <div 
          className="absolute inset-0 bg-cover bg-center bg-no-repeat"
          style={{
            backgroundImage: `url(${geminiBg})`,
            backgroundColor: '#8b7d6b', // Fallback color
            backgroundSize: 'cover', // or 'contain', '100px 100px', etc.
            backgroundPosition: 'center'
        }}
      />
      
      {/* ===== TEXTURE OVERLAYS ===== */}
      {/* You can stack multiple texture overlays! Each div adds a new layer. */}
      {/* The order matters - layers stack from bottom to top. */}
      
      {/* ACTIVE: Main gritty texture
      <div 
        className="absolute inset-0 opacity-30 mix-blend-multiply pointer-events-none"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1579547945413-497e1b99dac0?w=512')`,
          backgroundRepeat: 'repeat',
          backgroundSize: '512px 512px'
        }}
      /> */}

      {/* EXAMPLE 1: Paper grain texture (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-20 mix-blend-overlay pointer-events-none"
        style={{
          backgroundImage: `url('YOUR_PAPER_GRAIN_TEXTURE.jpg')`,
          backgroundRepeat: 'repeat',
          backgroundSize: '256px 256px'
        }}
      /> */}

      {/* EXAMPLE 2: Noise/Film grain (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-15 mix-blend-soft-light pointer-events-none"
        style={{
          backgroundImage: `url('YOUR_NOISE_TEXTURE.png')`,
          backgroundRepeat: 'repeat',
          backgroundSize: '200px 200px'
        }}
      /> */}

      {/* EXAMPLE 3: Scratches/Dust (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-10 mix-blend-darken pointer-events-none"
        style={{
          backgroundImage: `url('YOUR_SCRATCHES_TEXTURE.png')`,
          backgroundRepeat: 'no-repeat',
          backgroundSize: 'cover' // Full screen, not tiled
        }}
      /> */}

      {/* EXAMPLE 4: Vignette darkening (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-40 mix-blend-multiply pointer-events-none"
        style={{
          background: 'radial-gradient(circle, transparent 0%, transparent 50%, rgba(0,0,0,0.3) 100%)'
        }}
      /> */}

      {/* EXAMPLE 5: Color tint overlay (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-10 mix-blend-color pointer-events-none"
        style={{
          backgroundColor: '#8b7355' // Warm sepia tone
        }}
      /> */}

      {/* EXAMPLE 6: Large scan lines (uncomment to use) */}
      {/* <div 
        className="absolute inset-0 opacity-5 mix-blend-multiply pointer-events-none"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.1) 2px, rgba(0,0,0,0.1) 4px)',
          backgroundSize: '100% 4px'
        }}
      /> */}

      {/* ===== BLEND MODE OPTIONS ===== */}
      {/* mix-blend-multiply   - Darkens, great for general grit */}
      {/* mix-blend-overlay    - Contrast boost, vibrant */}
      {/* mix-blend-soft-light - Subtle, natural looking */}
      {/* mix-blend-hard-light - Strong contrast */}
      {/* mix-blend-darken     - Only darkens, preserves lights */}
      {/* mix-blend-lighten    - Only lightens, preserves darks */}
      {/* mix-blend-screen     - Lightens overall */}
      {/* mix-blend-color      - Applies color tint only */}

      {/* Content */}
      <div className="max-w-[1600px] mx-auto relative z-10">
        {/* Coffee Stain */}
        <div className="absolute top-10 right-20 w-24 h-24 rounded-full border-4 border-amber-900/20 opacity-30 rotate-12" />
        <div className="absolute top-12 right-22 w-20 h-20 rounded-full border-2 border-amber-900/20 opacity-20 rotate-45" />
        
        {/* Messy Grid - Less structured */}
        <div className="relative grid grid-cols-1 lg:grid-cols-[400px_1fr_400px] gap-4 items-start">
          {/* Quest Log - Left, slightly rotated */}
          <div className="transform lg:-rotate-2 lg:translate-y-8">
            <QuestLog />
          </div>

          {/* Avatar - Center */}
          <div className="flex justify-center transform lg:rotate-1 lg:-translate-y-4">
            <Avatar />
          </div>

          {/* Skill Tree - Right, rotated opposite */}
          <div className="transform lg:rotate-2 lg:translate-y-12">
            <SkillTree />
          </div>
        </div>

        {/* Timeline - Bottom, slightly askew */}
        <div className="mt-8 transform lg:-rotate-1">
          <Timeline />
        </div>

        {/* Scattered desk items */}
        <div className="absolute top-0 left-10 text-4xl opacity-40 rotate-12">📎</div>
        <div className="absolute bottom-20 right-10 text-3xl opacity-40 -rotate-12">✏️</div>
        <div className="absolute top-40 right-5 text-2xl opacity-40 rotate-45">📌</div>
      </div>
    </div>
  );
}