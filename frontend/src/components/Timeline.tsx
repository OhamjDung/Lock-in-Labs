import { Trophy, Star, Target, Flame } from 'lucide-react';

type TimelineEvent = {
  id: string;
  date: string;
  title: string;
  description: string;
  type: 'achievement' | 'milestone' | 'quest' | 'streak';
  icon: string;
};

const events: TimelineEvent[] = [
  {
    id: '1',
    date: 'Dec 16',
    title: '7 Day Streak!',
    description: 'Completed daily quests for 7 days straight',
    type: 'streak',
    icon: '🔥'
  },
  {
    id: '2',
    date: 'Dec 15',
    title: 'Level Up!',
    description: 'Reached Level 1 in your journey',
    type: 'milestone',
    icon: '⭐'
  },
  {
    id: '3',
    date: 'Dec 14',
    title: 'Quest Completed',
    description: 'Finished "Master the Ancient Skill"',
    type: 'quest',
    icon: '🎯'
  },
  {
    id: '4',
    date: 'Dec 13',
    title: 'Achievement Unlocked',
    description: 'Early Bird - Completed morning routine 5 times',
    type: 'achievement',
    icon: '🏆'
  },
  {
    id: '5',
    date: 'Dec 12',
    title: 'Skill Upgraded',
    description: 'Coding skill increased to Level 7',
    type: 'milestone',
    icon: '⭐'
  }
];

const typeColors = {
  achievement: '#fbbf24',
  milestone: '#a855f7',
  quest: '#3b82f6',
  streak: '#f97316'
};

export function Timeline() {
  return (
    <div className="bg-white p-6 shadow-xl relative overflow-hidden" 
         style={{ 
           backgroundImage: 'repeating-linear-gradient(transparent, transparent 28px, #e5e7eb 28px, #e5e7eb 29px)',
           backgroundSize: '100% 29px'
         }}>
      {/* Tape strips holding paper down */}
      <div className="absolute -top-3 left-20 w-20 h-6 bg-yellow-100/70 border border-yellow-200/50 rotate-2" />
      <div className="absolute -top-3 right-20 w-20 h-6 bg-yellow-100/70 border border-yellow-200/50 -rotate-2" />
      
      <div className="relative z-10">
        {/* Header */}
        <div className="mb-6 pb-2 border-b-2 border-black">
          <h2 className="text-3xl" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            Recent History 🏆
          </h2>
        </div>

        {/* Timeline - Hand-drawn style */}
        <div className="space-y-6">
          {events.map((event, index) => (
            <div key={event.id} className="flex gap-4 items-start">
              {/* Date stamp */}
              <div className="flex-shrink-0 w-16">
                <div className="text-xs text-gray-500 transform -rotate-2" style={{ fontFamily: 'Courier New, monospace' }}>
                  {event.date}
                </div>
              </div>

              {/* Icon circle */}
              <div 
                className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center border-2 border-black shadow-sm"
                style={{ backgroundColor: typeColors[event.type] }}
              >
                <span className="text-lg">{event.icon}</span>
              </div>

              {/* Content */}
              <div className="flex-1" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
                <div className="font-medium mb-1">{event.title}</div>
                <div className="text-sm text-gray-600">{event.description}</div>
                
                {/* Underline for emphasis */}
                {index === 0 && (
                  <div className="mt-1 text-xs text-orange-600">← NEW! 🔥</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Hand-drawn arrow */}
        <div className="absolute right-8 top-20 text-gray-300 text-2xl rotate-12">
          ↓
        </div>
      </div>

      {/* Crumpled corner effect */}
      <div className="absolute bottom-0 right-0 w-0 h-0 border-l-[40px] border-l-transparent border-b-[40px] border-b-gray-300 opacity-30" />
    </div>
  );
}