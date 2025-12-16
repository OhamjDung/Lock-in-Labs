import { useState } from 'react';
import { Scroll, Swords, Shield, Sparkles } from 'lucide-react';

type Quest = {
  id: string;
  title: string;
  description: string;
  type: 'main' | 'side' | 'daily';
  completed: boolean;
  xp: number;
};

const initialQuests: Quest[] = [
  {
    id: '1',
    title: 'Complete Morning Routine',
    description: 'Start the day with meditation and exercise',
    type: 'daily',
    completed: false,
    xp: 50
  },
  {
    id: '2',
    title: 'Master the Ancient Skill',
    description: 'Complete the online course chapter',
    type: 'main',
    completed: false,
    xp: 200
  },
  {
    id: '3',
    title: 'Gather Resources',
    description: 'Go grocery shopping',
    type: 'side',
    completed: false,
    xp: 75
  },
  {
    id: '4',
    title: 'Train with the Guild',
    description: 'Attend team meeting',
    type: 'main',
    completed: true,
    xp: 150
  }
];

export function QuestLog() {
  const [quests, setQuests] = useState<Quest[]>(initialQuests);

  const toggleQuest = (id: string) => {
    setQuests(quests.map(q => 
      q.id === id ? { ...q, completed: !q.completed } : q
    ));
  };

  const getQuestIcon = (type: Quest['type']) => {
    switch(type) {
      case 'main': return '⚔️';
      case 'side': return '🛡️';
      case 'daily': return '✨';
    }
  };

  return (
    <div className="bg-white p-6 shadow-xl relative" 
         style={{ 
           backgroundImage: 'repeating-linear-gradient(transparent, transparent 28px, #e5e7eb 28px, #e5e7eb 29px)',
           backgroundSize: '100% 29px'
         }}>
      {/* Red margin line */}
      <div className="absolute left-12 top-0 bottom-0 w-0.5 bg-red-300" />
      
      {/* Tape at top */}
      <div className="absolute -top-3 left-8 w-16 h-6 bg-yellow-100/70 border border-yellow-200/50 rotate-3" />
      <div className="absolute -top-3 right-8 w-16 h-6 bg-yellow-100/70 border border-yellow-200/50 -rotate-3" />
      
      <div className="relative z-10 pl-6">
        {/* Header - handwritten style */}
        <div className="mb-6 pb-2 border-b-2 border-black">
          <h2 className="text-3xl" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            Quest Log 📋
          </h2>
          <div className="text-xs text-gray-500 mt-1" style={{ fontFamily: 'Courier New, monospace' }}>
            // TODO list
          </div>
        </div>

        {/* Quest List - Like handwritten tasks */}
        <div className="space-y-4">
          {quests.map((quest) => (
            <div
              key={quest.id}
              className="cursor-pointer group"
              onClick={() => toggleQuest(quest.id)}
            >
              <div className="flex items-start gap-2">
                <div className="mt-1.5 flex-shrink-0">
                  {quest.completed ? (
                    <span className="text-lg">☑</span>
                  ) : (
                    <span className="text-lg">☐</span>
                  )}
                </div>
                <div className="flex-1" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
                  <div className="flex items-center gap-2">
                    <span className={quest.completed ? 'line-through text-gray-400' : ''}>
                      {quest.title}
                    </span>
                    <span className="text-sm">{getQuestIcon(quest.type)}</span>
                  </div>
                  <div className="text-xs text-gray-500 italic ml-4">
                    {quest.description}
                  </div>
                  <div className="text-xs mt-1 ml-4">
                    <span className="bg-yellow-200 px-2 py-0.5 border border-yellow-400">
                      +{quest.xp} XP
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add button - handwritten */}
        <div className="mt-6 pt-4 border-t border-dashed border-gray-300">
          <button className="text-sm text-gray-500 hover:text-black" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
            + add new quest...
          </button>
        </div>
      </div>

      {/* Coffee stain */}
      <div className="absolute bottom-8 right-6 w-16 h-16 rounded-full border-2 border-amber-900/20 opacity-30" />
    </div>
  );
}