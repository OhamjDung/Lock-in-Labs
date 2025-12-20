import React, { useState, useEffect, useMemo } from 'react';
import { Plus, Minus, Maximize, Star, Diamond, Circle } from 'lucide-react';
import { skillTreeJson } from '../../data/mockData'; 

const TreeVisualizer = ({ pillar, skillTree, characterSheet }) => {
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
    const [isDragging, setIsDragging] = useState(false);
    const [startPan, setStartPan] = useState({ x: 0, y: 0 });
    const [hoveredNodeId, setHoveredNodeId] = useState(null);

    const layout = useMemo(() => {
        const nodesSource = (skillTree && skillTree.nodes && skillTree.nodes.length > 0) ? skillTree.nodes : skillTreeJson.nodes;
        const pillarNodes = nodesSource.filter(n => n.pillar === pillar);
        const goalNode = pillarNodes.find(n => n.type === 'Goal');
        
        if (!goalNode) return { nodes: [], edges: [], width: 800 };

        const hierarchy = { goal: goalNode, skills: [] };

        if (goalNode.prerequisites) {
            goalNode.prerequisites.forEach(skillId => {
                const skillNode = pillarNodes.find(n => n.id === skillId);
                if (skillNode) {
                    const skillObj = { ...skillNode, habits: [] };
                    if (skillNode.prerequisites) {
                        skillNode.prerequisites.forEach(habitId => {
                            const habitNode = pillarNodes.find(n => n.id === habitId) || { id: habitId, name: habitId.replace(/_/g, ' ').replace('habit ', ''), type: 'Habit', required_completions: 10 };
                            skillObj.habits.push(habitNode);
                        });
                    }
                    hierarchy.skills.push(skillObj);
                }
            });
        }

        const HABIT_WIDTH = 100;
        const NODE_SPACING = 40;
        let currentX = 50;
        const processedNodes = [];
        const processedEdges = [];
        const Y_GOAL = 100;
        const Y_SKILL = 350;
        const Y_HABIT = 600;

        hierarchy.skills.forEach(skill => {
            const habitCount = skill.habits.length || 1;
            const skillWidth = habitCount * (HABIT_WIDTH + 20);
            const skillCenterX = currentX + (skillWidth / 2);

            processedNodes.push({ ...skill, x: skillCenterX, y: Y_SKILL });
            processedEdges.push({ x1: 0, y1: Y_GOAL + 40, x2: skillCenterX, y2: Y_SKILL - 30, id: `edge-${hierarchy.goal.id}-${skill.id}` });

            skill.habits.forEach((habit, idx) => {
                const habitX = currentX + (idx * (HABIT_WIDTH + 20)) + (HABIT_WIDTH/2);
                const progressData = characterSheet?.habit_progress?.[habit.id];
                const completed = progressData?.completed_total || 0;
                const required = habit.required_completions || 1; 
                const progressPercent = Math.min(100, Math.max(0, (completed / required) * 100));
                const status = progressData?.status === 'ACTIVE' ? 'ACTIVE' : 'LOCKED';

                processedNodes.push({ ...habit, x: habitX, y: Y_HABIT, progressPercent, status, completed, required });
                processedEdges.push({ x1: skillCenterX, y1: Y_SKILL + 30, x2: habitX, y2: Y_HABIT - 20, id: `edge-${skill.id}-${habit.id}` });
            });
            currentX += skillWidth + NODE_SPACING;
        });

        const totalWidth = currentX;
        const goalX = totalWidth / 2;
        processedNodes.push({ ...hierarchy.goal, x: goalX, y: Y_GOAL });
        processedEdges.forEach(e => { if (e.y1 === Y_GOAL + 40) e.x1 = goalX; });

        return { nodes: processedNodes, edges: processedEdges, width: totalWidth };
      }, [pillar, skillTree, characterSheet]);

    useEffect(() => { setTransform({ x: 0, y: 0, k: 0.8 }); }, [pillar]);

    const handleWheel = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const delta = -e.deltaY * 0.001;
        setTransform(prev => ({ ...prev, k: Math.min(Math.max(0.2, prev.k + delta), 3) }));
    };

    const handleMouseDown = (e) => { setIsDragging(true); setStartPan({ x: e.clientX - transform.x, y: e.clientY - transform.y }); };
    const handleMouseMove = (e) => { if (!isDragging) return; e.preventDefault(); setTransform(prev => ({ ...prev, x: e.clientX - startPan.x, y: e.clientY - startPan.y })); };
    const handleMouseUp = () => setIsDragging(false);
    
    return (
        <div className="w-full h-full relative bg-[#f0f9ff] border-t-4 border-blue-900/10 overflow-hidden cursor-grab active:cursor-grabbing select-none"
            onWheel={handleWheel} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
            <div className="absolute origin-top-left transition-transform duration-75 ease-out"
                style={{ transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`, width: Math.max(layout.width, 2000), height: '2000px' }}>
                <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(#bae6fd 1px, transparent 1px), linear-gradient(90deg, #bae6fd 1px, transparent 1px)', backgroundSize: '30px 30px' }}></div>
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                    {layout.edges.map(e => (
                        <path key={e.id} d={`M ${e.x1} ${e.y1} C ${e.x1} ${(e.y1+e.y2)/2} ${e.x2} ${(e.y1+e.y2)/2} ${e.x2} ${e.y2}`} stroke="#3b82f6" strokeWidth="2" fill="none" strokeOpacity="0.4" />
                    ))}
                </svg>
                {layout.nodes.map(node => (
                    <div key={node.id} className="absolute flex flex-col items-center justify-center transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10 hover:z-50"
                        style={{ left: node.x, top: node.y }} onMouseEnter={() => setHoveredNodeId(node.id)} onMouseLeave={() => setHoveredNodeId(null)}>
                        {node.type === 'Habit' && hoveredNodeId === node.id && (
                            <div className="absolute bottom-full mb-3 bg-slate-900/95 backdrop-blur text-white p-3 rounded-lg shadow-xl z-50 w-56 text-xs border border-slate-700 pointer-events-none animate-in fade-in slide-in-from-bottom-2 duration-200">
                                <div className="font-bold text-sm mb-1 text-blue-200">{node.name}</div>
                                <div className="flex justify-between items-center mb-2 border-b border-slate-700 pb-1">
                                    <span className="text-slate-400">Progress</span><span className="font-mono text-blue-400">{node.completed}/{node.required}</span>
                                </div>
                                <div className="text-slate-300 mb-2 leading-relaxed italic">"{node.description || ""}"</div>
                                <div className="flex justify-end"><span className="text-yellow-400 font-bold bg-yellow-400/10 px-1.5 py-0.5 rounded border border-yellow-400/20">+{node.xp_reward} XP</span></div>
                            </div>
                        )}
                        <div className={`flex items-center justify-center shadow-lg transition-all duration-300 relative overflow-hidden
                            ${node.type === 'Goal' ? 'w-24 h-24 bg-blue-600 text-white clip-hexagon z-30' : ''}
                            ${node.type === 'Sub-Skill' ? 'w-16 h-16 bg-white border-2 border-blue-500 rotate-45 z-20 hover:scale-110' : ''}
                            ${node.type === 'Habit' ? 'w-10 h-10 rounded-full z-10' : ''}
                            ${node.type === 'Habit' && node.status === 'ACTIVE' ? 'bg-blue-50 border-2 border-blue-400' : ''}
                            ${node.type === 'Habit' && node.status === 'LOCKED' ? 'bg-slate-100 border-2 border-slate-300 opacity-70 grayscale' : ''}
                        `}>
                            {node.type === 'Habit' && (
                                <div className={`absolute bottom-0 left-0 right-0 transition-all duration-500 ease-in-out ${node.status === 'ACTIVE' ? 'bg-blue-500' : 'bg-slate-400'}`} style={{ height: `${node.progressPercent}%`, opacity: 0.3 }} />
                            )}
                            <div className="relative z-10">
                                {node.type === 'Goal' && <Star size={40} />}
                                {node.type === 'Sub-Skill' && <div className="-rotate-45 text-blue-600"><Diamond size={24} /></div>}
                                {node.type === 'Habit' && <Circle size={14} className={node.status === 'ACTIVE' ? "text-blue-600" : "text-slate-400"} />}
                            </div>
                        </div>
                        <div className="mt-4 text-center font-mono font-bold bg-white/90 backdrop-blur-sm px-2 py-0.5 rounded border border-slate-100 shadow-sm text-[10px] w-28 text-slate-600">{node.name}</div>
                    </div>
                ))}
            </div>
            <div className="absolute bottom-4 right-4 flex flex-col gap-2 pointer-events-auto shadow-lg bg-white/50 backdrop-blur-sm p-1 rounded-lg border border-blue-200">
                <button onClick={() => setTransform(p => ({...p, k: p.k + 0.2}))} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Plus size={20} /></button>
                <button onClick={() => setTransform(p => ({...p, k: p.k - 0.2}))} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Minus size={20} /></button>
                <button onClick={() => setTransform({x:0, y:0, k:0.8})} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Maximize size={20} /></button>
            </div>
        </div>
    );
};

export default TreeVisualizer;