// Data transformation utilities for character sheet and skill tree

// Generate sample value based on stat names (deterministic hash)
function generateSampleValue(statNames) {
  if (!statNames || statNames.length === 0) return 0;
  
  // Create a hash from stat names to generate consistent values
  const hash = statNames.join('|').split('').reduce((acc, char) => {
    return ((acc << 5) - acc) + char.charCodeAt(0);
  }, 0);
  
  // Generate value between 1-10 based on hash
  return Math.abs(hash % 10) + 1;
}

export const transformCharacterData = (characterSheet, skillTree) => {
  const sheet = characterSheet || {};
  const tree = skillTree || { nodes: [] };

  // Get stat names for each pillar
  const careerStatNames = Object.keys(sheet.stats_career || {});
  const physicalStatNames = Object.keys(sheet.stats_physical || {});
  const mentalStatNames = Object.keys(sheet.stats_mental || {});
  const socialStatNames = Object.keys(sheet.stats_social || {});

  // Calculate averages, or use sample data if all zeros
  const careerValues = Object.values(sheet.stats_career || {});
  const careerAvg = careerValues.length > 0 
    ? Math.round(careerValues.reduce((a, b) => a + b, 0) / careerValues.length)
    : 0;
  const careerSample = careerAvg === 0 && careerStatNames.length > 0
    ? generateSampleValue(careerStatNames)
    : careerAvg;

  const physicalValues = Object.values(sheet.stats_physical || {});
  const physicalAvg = physicalValues.length > 0
    ? Math.round(physicalValues.reduce((a, b) => a + b, 0) / physicalValues.length)
    : 0;
  const physicalSample = physicalAvg === 0 && physicalStatNames.length > 0
    ? generateSampleValue(physicalStatNames)
    : physicalAvg;

  const mentalValues = Object.values(sheet.stats_mental || {});
  const mentalAvg = mentalValues.length > 0
    ? Math.round(mentalValues.reduce((a, b) => a + b, 0) / mentalValues.length)
    : 0;
  const mentalSample = mentalAvg === 0 && mentalStatNames.length > 0
    ? generateSampleValue(mentalStatNames)
    : mentalAvg;

  const socialValues = Object.values(sheet.stats_social || {});
  const socialAvg = socialValues.length > 0
    ? Math.round(socialValues.reduce((a, b) => a + b, 0) / socialValues.length)
    : 0;
  const socialSample = socialAvg === 0 && socialStatNames.length > 0
    ? generateSampleValue(socialStatNames)
    : socialAvg;

  const pillarStats = [
    { 
      name: 'Career', 
      value: careerSample
    },
    { 
      name: 'Physical', 
      value: physicalSample
    },
    { 
      name: 'Mental', 
      value: mentalSample
    },
    { 
      name: 'Social', 
      value: socialSample
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

