// Data transformation utilities for character sheet and skill tree

export const transformCharacterData = (characterSheet, skillTree) => {
  const sheet = characterSheet || {};
  const tree = skillTree || { nodes: [] };

  const pillarStats = [
    { 
      name: 'Career', 
      value: Math.round(
        Object.values(sheet.stats_career || {}).reduce((a, b) => a + b, 0) / 
        (Object.keys(sheet.stats_career || {}).length || 1)
      ) 
    },
    { 
      name: 'Physical', 
      value: Math.round(
        Object.values(sheet.stats_physical || {}).reduce((a, b) => a + b, 0) / 
        (Object.keys(sheet.stats_physical || {}).length || 1)
      ) 
    },
    { 
      name: 'Mental', 
      value: Math.round(
        Object.values(sheet.stats_mental || {}).reduce((a, b) => a + b, 0) / 
        (Object.keys(sheet.stats_mental || {}).length || 1)
      ) 
    },
    { 
      name: 'Social', 
      value: Math.round(
        Object.values(sheet.stats_social || {}).reduce((a, b) => a + b, 0) / 
        (Object.keys(sheet.stats_social || {}).length || 1)
      ) 
    }
  ];

  const progress = sheet.habit_progress || {};
  
  // Get ACTIVE habits from skill tree, grouped by pillar
  // Select 1-2 habits per pillar to show in directives
  const pillarMap = {
    'CAREER': 'Career',
    'PHYSICAL': 'Physical',
    'MENTAL': 'Mental',
    'SOCIAL': 'Social'
  };
  
  // Get all Habit nodes from skill tree
  const habitNodes = tree.nodes.filter(n => n.type === 'Habit' || n.type === 'habit');
  
  // Group by pillar and filter for ACTIVE habits
  const habitsByPillar = {};
  habitNodes.forEach(node => {
    const pillar = node.pillar;
    if (!pillar) return;
    
    const progressData = progress[node.id];
    // Only include ACTIVE habits (not LOCKED or MASTERED)
    if (progressData && progressData.status === 'ACTIVE') {
      if (!habitsByPillar[pillar]) {
        habitsByPillar[pillar] = [];
      }
      habitsByPillar[pillar].push({
        node,
        progress: progressData
      });
    }
  });
  
  // Select 1-2 habits per pillar
  const selectedQuests = [];
  Object.keys(habitsByPillar).forEach(pillar => {
    const habits = habitsByPillar[pillar];
    // Shuffle and take up to 2
    const shuffled = [...habits].sort(() => Math.random() - 0.5);
    const selected = shuffled.slice(0, Math.min(2, habits.length));
    
    selected.forEach(({ node, progress: progressData }) => {
      selectedQuests.push({
        name: node.name,
        status: 'active',
        pillar: pillarMap[pillar] || pillar,
        description: node.description || '',
        nodeId: node.id
      });
    });
  });
  
  const quests = selectedQuests;

  const debuffs = (sheet.debuffs || []).map(d => ({
    name: d,
    effect: "Status Effect",
    type: "Mental"
  }));

  const skills = tree.nodes
    .filter(n => n.type === 'Sub-Skill')
    .map(n => ({ name: n.name, level: 1, pillar: n.pillar }));

  const timeline = [
    { time: "08:00", event: "Wake up and meditate", status: "completed" },
    { time: "08:30", event: "Breakfast", status: "completed" },
    { time: "09:00", event: "Work on project", status: "active" },
    { time: "12:00", event: "Lunch break", status: "upcoming" },
    { time: "13:00", event: "Client meeting", status: "upcoming" },
    { time: "15:00", event: "Gym workout", status: "upcoming" },
    { time: "18:00", event: "Dinner with family", status: "upcoming" },
    { time: "20:00", event: "Read a book", status: "upcoming" },
    { time: "22:00", event: "Sleep", status: "upcoming" },
  ];

  return { 
    stats: pillarStats, 
    quests, 
    debuffs, 
    skills, 
    timeline, 
    user_id: sheet.user_id || 'OPERATIVE_01',
    class: 'Agent',
    level: 1,
    xp: 0,
    nextLevelXp: 1000,
    northStar: "Become the best version of yourself"
  };
};

