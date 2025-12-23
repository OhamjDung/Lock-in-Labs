import React, { useState, useEffect } from 'react';
import { Check } from 'lucide-react';

export default function QuestItem({ quest, skillTree, userId, isCompletedToday, onToggle }) {
  const [isChecked, setIsChecked] = useState(isCompletedToday || false);
  const [isLoading, setIsLoading] = useState(false);

  // Sync state with prop changes
  useEffect(() => {
    setIsChecked(isCompletedToday || false);
  }, [isCompletedToday]);

  // Find node_id from quest object first, then fall back to skill tree matching
  const nodeId = React.useMemo(() => {
    // If quest has nodeId directly, use it
    if (quest?.nodeId) return quest.nodeId;
    
    // Otherwise, try to find by name in skill tree
    if (!skillTree?.nodes || !quest?.name) return null;
    
    // Try exact match first
    let node = skillTree.nodes.find(n => n.name === quest.name);
    if (node) return node.id;
    
    // Try case-insensitive match
    node = skillTree.nodes.find(n => n.name?.toLowerCase() === quest.name?.toLowerCase());
    if (node) return node.id;
    
    // Try matching with trimmed whitespace
    node = skillTree.nodes.find(n => n.name?.trim() === quest.name?.trim());
    if (node) return node.id;
    
    return null;
  }, [skillTree, quest]);

  const handleToggle = async (e) => {
    console.log('QuestItem: handleToggle called!', { 
      questName: quest.name, 
      nodeId, 
      userId, 
      status: quest.status,
      isActive,
      isChecked 
    });
    
    e.stopPropagation();
    e.preventDefault();
    
    if (!nodeId) {
      console.warn('QuestItem: No nodeId found for quest:', quest.name, 'Available nodes:', skillTree?.nodes?.map(n => n.name));
      alert(`Cannot toggle: No matching node found for "${quest.name}". Available nodes: ${skillTree?.nodes?.map(n => n.name).join(', ') || 'none'}`);
      return;
    }
    
    if (!userId) {
      console.warn('QuestItem: No userId provided');
      alert('Cannot toggle: User not logged in');
      return;
    }
    
    if (quest.status !== 'active') {
      console.warn('QuestItem: Quest is not active:', quest.status);
      alert(`Cannot toggle: Quest status is "${quest.status}", not "active"`);
      return;
    }

    setIsLoading(true);
    const newChecked = !isChecked;
    
    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      const url = `${backend}/api/profile/${userId}/task/${nodeId}/toggle`;
      console.log('QuestItem: Toggling task', { userId, nodeId, questName: quest.name, newChecked, url });
      
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ completed: newChecked })
      });

      if (res.ok) {
        const data = await res.json();
        console.log('QuestItem: Toggle successful', data);
        setIsChecked(data.completed);
        if (onToggle) {
          onToggle(quest.name, data.completed);
        }
      } else {
        const errorText = await res.text();
        console.error('QuestItem: Failed to toggle task completion', res.status, errorText);
      }
    } catch (error) {
      console.error('QuestItem: Error toggling task completion:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const isActive = quest.status === 'active';
  const showCheck = isActive && isChecked;

  const handleButtonClick = (e) => {
    e.stopPropagation();
    e.preventDefault();
    console.log('QuestItem: Button clicked!', { nodeId, userId, isActive, questName: quest.name });
    handleToggle(e);
  };

  // Debug: Log button state
  React.useEffect(() => {
    console.log('QuestItem render:', {
      questName: quest.name,
      nodeId,
      userId,
      isActive,
      isChecked,
      disabled: !isActive || !nodeId || isLoading,
      skillTreeNodes: skillTree?.nodes?.length || 0
    });
  }, [quest.name, nodeId, userId, isActive, isChecked, isLoading, skillTree]);

  return (
    <div className="flex flex-col p-4 border-b border-[#d4c5a9] last:border-0 hover:bg-[#dfd3bc] transition-colors group relative">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={(e) => {
              console.log('QuestItem: RAW CLICK EVENT FIRED!', { 
                nodeId, 
                userId, 
                isActive, 
                questName: quest.name,
                disabled: !isActive || !nodeId || isLoading,
                isActive,
                hasNodeId: !!nodeId,
                isLoading
              });
              handleButtonClick(e);
            }}
            onMouseEnter={() => {
              console.log('QuestItem: Mouse entered button', { nodeId, userId, isActive, questName: quest.name });
            }}
            onMouseDown={(e) => {
              console.log('QuestItem: Mouse down on button');
              e.stopPropagation();
            }}
            disabled={false}
            style={{ 
              pointerEvents: 'auto',
              zIndex: 50,
              position: 'relative',
              minWidth: '20px',
              minHeight: '20px'
            }}
            className={`w-6 h-6 rounded-sm border-2 flex items-center justify-center transition-all ${
              isActive && nodeId
                ? showCheck
                  ? 'bg-stone-800 border-stone-800 text-white cursor-pointer hover:bg-stone-900 active:scale-95'
                  : 'border-stone-500 hover:border-stone-800 cursor-pointer hover:bg-stone-100 active:scale-95'
                : 'border-red-500 bg-red-100 opacity-100 cursor-pointer'
            } ${isLoading ? 'opacity-50' : ''}`}
            title={
              !isActive ? 'Quest is not active' :
              !nodeId ? `No matching node found for: ${quest.name}` :
              !userId ? 'User not logged in' :
              isLoading ? 'Updating...' :
              showCheck ? 'Mark as incomplete' : 'Mark as complete'
            }
          >
            {showCheck && <Check size={12} strokeWidth={3} />}
          </button>
          <span className={`text-sm font-bold text-stone-900 group-hover:text-black transition-colors ${isActive ? 'underline decoration-stone-800/40 decoration-2 underline-offset-2' : 'text-stone-500'}`}>
              {quest.name}
          </span>
        </div>
        <div className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${isActive ? 'text-stone-700 bg-[#d4c5a9]/40 border-[#c7bba4]' : 'text-stone-400 bg-stone-100 border-stone-200'}`}>
          {isActive ? 'ACTIVE' : 'PENDING'}
        </div>
      </div>
      <div className="pl-7 text-xs text-stone-700 leading-relaxed font-serif italic opacity-90">{quest.description}</div>
    </div>
  );
}
