import { useState } from 'react';
import { Zap, Code, Dumbbell, Brain, Heart, TrendingUp } from 'lucide-react';

type Skill = {
  id: string;
  name: string;
  level: number;
  maxLevel: number;
  icon: string;
  color: string;
};

const initialSkills: Skill[] = [
  {
    id: '1',
    name: 'Coding',
    level: 7,
    maxLevel: 10,
    icon: '💻',
    color: '#a855f7'
  },
  {
    id: '2',
    name: 'Fitness',
    level: 5,
    maxLevel: 10,
    icon: '💪',
    color: '#ef4444'
  },
  {
    id: '3',
    name: 'Learning',
    level: 6,
    maxLevel: 10,
    icon: '🧠',
    color: '#3b82f6'
  },
  {
    id: '4',
    name: 'Mindfulness',
    level: 4,
    maxLevel: 10,
    icon: '❤️',
    color: '#ec4899'
  },
  {
    id: '5',
    name: 'Productivity',
    level: 8,
    maxLevel: 10,
    icon: '📈',
    color: '#22c55e'
  }
];

export function SkillTree() {
  const [skills] = useState<Skill[]>(initialSkills);

  return (
    <div className="relative">
      {/* Index cards stacked */}
      <div className="bg-white p-6 shadow-xl relative" 
           style={{ 
             backgroundImage: 'repeating-linear-gradient(transparent, transparent 28px, #e5e7eb 28px, #e5e7eb 29px)',
             backgroundSize: '100% 29px'
           }}>
        {/* Red margin line */}
        <div className="absolute left-12 top-0 bottom-0 w-0.5 bg-red-300" />
        
        {/* Pushed pin */}
        <div className="absolute -top-2 left-1/2 text-2xl">📌</div>
        
        <div className="relative z-10 pl-6">
          {/* Header */}
          <div className="mb-6 pb-2 border-b-2 border-black">
            <h2 className="text-3xl" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
              Skills ⚡
            </h2>
          </div>

          {/* Skills - Like progress bars drawn by hand */}
          <div className="space-y-5">
            {skills.map((skill) => (
              <div key={skill.id}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">{skill.icon}</span>
                  <span style={{ fontFamily: 'Comic Sans MS, cursive' }}>
                    {skill.name}
                  </span>
                  <span className="text-xs text-gray-500 ml-auto" style={{ fontFamily: 'Courier New, monospace' }}>
                    Lv.{skill.level}/{skill.maxLevel}
                  </span>
                </div>
                
                {/* Hand-drawn progress bar */}
                <div className="flex gap-1 ml-8">
                  {Array.from({ length: skill.maxLevel }).map((_, i) => (
                    <div
                      key={i}
                      className="w-6 h-6 border-2 border-black transform -rotate-1"
                      style={{ 
                        backgroundColor: i < skill.level ? skill.color : '#e5e7eb',
                        transform: `rotate(${Math.random() * 4 - 2}deg)`
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Total on sticky note */}
          <div className="mt-6 relative">
            <div className="bg-pink-200 p-3 inline-block transform rotate-2 shadow-md border-l-2 border-pink-300">
              <div className="text-xs text-gray-600" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
                Total Points:
              </div>
              <div className="text-2xl" style={{ fontFamily: 'Comic Sans MS, cursive' }}>
                {skills.reduce((sum, skill) => sum + skill.level, 0)} ★
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Pencil doodle */}
      <div className="absolute -bottom-4 -right-4 text-4xl rotate-45 opacity-50">✏️</div>
    </div>
  );
}