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

  const quests = [
    ...Object.values(sheet.goals || {}).flatMap(g => 
      g.current_quests.map(q => ({ 
        name: q, 
        status: 'active', 
        pillar: g.pillar, 
        description: g.description 
      }))
    ),
    ...Object.values(sheet.goals || {}).flatMap(g => 
      g.needed_quests.map(q => ({ 
        name: q, 
        status: 'pending', 
        pillar: g.pillar, 
        description: `Prerequisite for: ${g.name}` 
      }))
    )
  ]
  .filter((q, i, a) => a.findIndex(t => t.name === q.name) === i) // de-dupe
  .filter(q => {
    const progress = sheet.habit_progress || {};
    const node = tree.nodes.find(n => n.name === q.name);
    if (!node) return q.status === 'active'; // Keep active quests if node not found
    const habitProgress = progress[node.id];
    return habitProgress?.status === 'ACTIVE' || q.status === 'active';
  });

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

