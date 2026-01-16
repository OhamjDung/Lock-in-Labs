import json
import re
from typing import List
from src.models import SkillNode, NodeType, Pillar
from src.llm import LLMClient
from src.knowledge_base import retrieve_relevant_skills


class BasePlanner:
    def __init__(self):
        self.llm_client = LLMClient()

    def derive_skill_level(self, goal: str, current_quests: List[str]) -> int:
        """
        Analyzes user's current habits to estimate skill level (1-10).
        - No habits / Vague habits = Level 1-2 (Needs tall tree)
        - Advanced habits = Level 7-8 (Needs short, specific tree)
        """
        if not current_quests:
            return 1
        
        prompt = f"""
        You are an expert assessor.
        **GOAL:** {goal}
        **USER'S CURRENT ACTIONS:** {json.dumps(current_quests)}
        
        Estimate the user's skill level on a scale of 1-10 (1=Novice, 10=World Class).
        Return ONLY the integer.
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat_completion(messages, json_mode=False)
        try:
            # Use regex to extract first digit (handles "The skill level is 7" or "7.")
            match = re.search(r'\d+', response)
            if match:
                level = int(match.group())
                # Clamp to valid range (1-10)
                return max(1, min(10, level))
            return 1  # Default to beginner if no digit found
        except Exception:
            return 1  # Default to beginner on any error

    def _generate_deep_prompt(self, north_star, current_quests, debuffs, skill_level, pillar_name):
        """Generates prompt that enforces tree depth based on skill level."""
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"planners.py:_generate_deep_prompt:entry","message":"Generating depth prompt","data":{"skill_level":skill_level,"north_star":north_star,"pillar":pillar_name},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2"}) + '\n')
        except: pass
        # #endregion
        
        if skill_level <= 3:
            depth_instruction = "The user is a BEGINNER. Create a TALL, DEEP tree (4-5 layers). Break down complex skills into foundational prerequisites."
            max_layers = 5
            max_nodes = 8
            capstone_examples = "Level 1-3 Capstone Examples: 'Have a 5-minute conversation', 'Complete first project', 'Run 1 mile without stopping'"
            branch = "BEGINNER"
        elif skill_level <= 7:
            depth_instruction = "The user is INTERMEDIATE. Create a balanced tree (2-3 layers). Focus on bridging the gap to mastery."
            max_layers = 3
            max_nodes = 5
            capstone_examples = "Level 4-6 Capstone Examples: 'Attend 3 meetups and initiate 5 conversations', 'Complete portfolio project', 'Run 5K in 25 minutes'"
            branch = "INTERMEDIATE"
        else:
            depth_instruction = "The user is an EXPERT. Create a WIDE, FLAT tree (1-2 layers MAXIMUM). Focus only on elite-level refinements."
            max_layers = 2
            max_nodes = 3
            capstone_examples = "Level 7-10 Capstone Examples: 'Host a networking event', 'Land senior role', 'Run marathon in under 3 hours'"
            branch = "EXPERT"
        
        if skill_level <= 3:
            max_layers = 5
            max_nodes = 8
        elif skill_level <= 7:
            max_layers = 3
            max_nodes = 5
        else:
            max_layers = 2
            max_nodes = 3
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"planners.py:_generate_deep_prompt:branch_selected","message":"Depth instruction branch selected","data":{"skill_level":skill_level,"branch":branch,"depth_instruction":depth_instruction,"max_layers":max_layers,"max_nodes":max_nodes},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2"}) + '\n')
        except: pass
        # #endregion

        # Include RAG retrieval
        verified_skills = retrieve_relevant_skills(north_star, top_k=5, pillar=Pillar[pillar_name.upper()])
        rag_context = json.dumps(verified_skills, indent=2) if verified_skills else "[]"
        
        # FALLBACK: If RAG returns nothing, allow LLM to use internal knowledge
        if not verified_skills or len(verified_skills) == 0:
            rag_warning = (
                "\n**⚠️ WARNING: No verified skills found in knowledge base for this goal.**\n"
                "You MUST use your internal knowledge to generate a basic roadmap.\n"
                "Use industry-standard skills and best practices for this domain.\n"
                "Example: For 'Become a plumber', generate skills like:\n"
                "  - Basic Plumbing Tools Knowledge\n"
                "  - Pipe Fitting Basics\n"
                "  - Water System Understanding\n"
                "  - Obtain Apprenticeship or Certification\n\n"
            )
        else:
            rag_warning = ""

        return f"""
        You are a {pillar_name} Architect.
        
        **GOAL:** {north_star}
        **CURRENT LEVEL:** {skill_level}/10
        {depth_instruction}
        
        **VERIFIED SKILL LIBRARY (Prioritize these):**
        {rag_context}
        {rag_warning}
        
        **CRITICAL RULES FOR DEPTH (MANDATORY - DO NOT VIOLATE):**
        0. **DEPTH LIMIT (CRITICAL)**: You MUST create EXACTLY {max_layers} layers or fewer. The maximum depth from any starting node to the capstone must be {max_layers} layers or less. If you need to simplify, create fewer nodes, not more layers.
        1. **MAXIMUM NODES**: Generate AT MOST {max_nodes} Sub-Skill nodes total. For EXPERT level (skill_level > 7), use 1-3 nodes maximum.
        2. **Chain Prerequisites**: Do NOT connect everything to the Goal. Connect Basic Skills -> Intermediate Skills -> Advanced Skills -> Goal.
        3. **CHECK THE LIBRARY**: If a Verified Skill fits a step, USE IT exactly as written.
        4. **FILL GAPS**: If the library doesn't cover a necessary step, GENERATE a new skill node (but respect the {max_layers} layer limit).
        5. **CAPSTONE RULE**: The final node MUST be a concrete milestone appropriate for skill level {skill_level}/10, NOT the Goal name itself.
           {capstone_examples}
           **CRITICAL**: 
           - Match the capstone complexity to the user's level. A Level 4 user should NOT get a Level 9-10 milestone.
           - The capstone name MUST be DIFFERENT from the Goal name. If Goal is "Become an accountant", capstone should be "Pass CPA Exam" or "Land First Job", NOT "Become an Accountant".
           - The capstone must describe a MECHANISM OF COMPLETION (certification, job offer, project completion), not restate the goal.
        6. **DEPENDENCY LOGIC**: Only link Skill A -> Skill B if A is strictly required to learn B. 
           - *Bad Logic:* Data Analysis -> Tax Law (These are parallel skills).
           - *Good Logic:* Accounting Principles -> Financial Statement Analysis (Principles are foundational).
        7. **NO FILLER**: Do not use generic names like "Advanced {{north_star}}". Use specific industry terms (e.g., "Forensic Accounting").
        8. **Examples of Correct Depth**:
           For EXPERT (1-2 layers):
           - Example 1: 'Intermediate Skill' (Prereq: None) -> 'Capstone' (Prereq: ['Intermediate Skill']) = 2 layers ✓
           - Example 2: 'Capstone' (Prereq: None) = 1 layer ✓
           For INTERMEDIATE (2-3 layers):
           - Example: 'Basic Skill' (Prereq: None) -> 'Intermediate Skill' (Prereq: ['Basic Skill']) -> 'Capstone' (Prereq: ['Intermediate Skill']) = 3 layers ✓
        
        **OUTPUT SCHEMA (JSON):**
        {{
            "nodes": [
                {{
                    "id": "skill_python_basics",
                    "name": "Python Basics",
                    "type": "Sub-Skill",
                    "pillar": "{pillar_name}",
                    "prerequisites": [],
                    "xp_reward": 100,
                    "description": "Description here"
                }}
            ]
        }}
        
        **CRITICAL:** Every node MUST include ALL fields: id (string), name (string), type ("Sub-Skill"), pillar ("{pillar_name}"), prerequisites (array of strings), xp_reward (number), description (string).
        """

    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str], skill_level: int = 1) -> List[SkillNode]:
        raise NotImplementedError

    def _call_llm(self, prompt: str) -> List[SkillNode]:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.llm_client.chat_completion(messages, json_mode=True)
            data = json.loads(response)
            nodes: List[SkillNode] = []

            for raw in data.get("nodes", []):
                node_data = dict(raw)  # shallow copy so we can normalize

                # --- Auto-generate missing required fields ---
                if "id" not in node_data or not node_data.get("id"):
                    # Generate ID from name
                    name = node_data.get("name", "unknown")
                    import re as re_module
                    safe_name = re_module.sub(r'[^a-z0-9_]', '_', name.lower().replace(' ', '_').replace('-', '_'))
                    node_data["id"] = f"skill_{safe_name[:40]}"
                
                # --- Normalize type ---
                t = node_data.get("type")
                if not t:
                    # Default to Sub-Skill if not specified
                    node_data["type"] = NodeType.SUB_SKILL.value
                elif isinstance(t, str):
                    # If it's not one of the allowed enum values, fall back to Sub-Skill
                    if t not in {e.value for e in NodeType}:
                        node_data["type"] = NodeType.SUB_SKILL.value

                # --- Normalize pillar ---
                p = node_data.get("pillar")
                if not p:
                    # Try to infer from prompt context or default to CAREER
                    # For now, default to CAREER (should be set by planner subclass)
                    node_data["pillar"] = Pillar.CAREER.value
                elif isinstance(p, str):
                    # Map common title‑case forms to our enum values
                    pillar_map = {
                        "Career": Pillar.CAREER.value,
                        "Physical": Pillar.PHYSICAL.value,
                        "Mental": Pillar.MENTAL.value,
                        "Social": Pillar.SOCIAL.value,
                    }
                    if p in pillar_map:
                        node_data["pillar"] = pillar_map[p]
                    else:
                        up = p.upper()
                        if up in Pillar.__members__:
                            node_data["pillar"] = Pillar[up].value
                        else:
                            # Default to CAREER if unrecognizable
                            node_data["pillar"] = Pillar.CAREER.value

                try:
                    nodes.append(SkillNode(**node_data))
                except Exception as node_err:
                    print(f"Planner Node Error: {node_err}")
                    continue

            return nodes
        except Exception as e:
            print(f"Planner Error: {e}")
            return []


class CareerPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str], skill_level: int = 1) -> List[SkillNode]:
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"planners.py:CareerPlanner.generate_roadmap:entry","message":"CareerPlanner.generate_roadmap called","data":{"north_star":north_star,"skill_level":skill_level,"current_quests":current_quests,"default_skill_level":1},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1"}) + '\n')
        except: pass
        # #endregion
        
        base_prompt = self._generate_deep_prompt(north_star, current_quests, debuffs, skill_level, "Career")
        
        # Add Career-specific constraints
        career_constraints = f"""
        
        **CAREER-SPECIFIC RULES:**
        1. **CAPSTONE RULE (CRITICAL)**: The final node MUST be a "Milestone Event" (e.g., "Pass CPA Exam", "Land First Job", "Complete Portfolio Project"), NEVER the Goal name itself.
           - *Forbidden:* If Goal is "Become an accountant", final node CANNOT be "Become an Accountant"
           - *Required:* Final node must describe HOW the goal is achieved (certification, job offer, project completion)
           - *Examples for Level {skill_level}:*
             * Level 1-3: "Complete first project", "Get first certification"
             * Level 4-6: "Pass entry-level exam", "Land first job", "Complete portfolio"
             * Level 7-9: "Earn advanced certification", "Land senior role"
             * Level 10: "Become industry expert", "Publish research"
        2. **DEPENDENCY LOGIC**: Only link Skill A -> Skill B if A is strictly required to learn B. 
           - *Bad Logic:* Data Analysis -> Tax Law (These are parallel skills).
           - *Good Logic:* Accounting Principles -> Financial Statement Analysis (Principles are foundational).
        3. **NO FILLER**: Do not use generic names like "Advanced {north_star}". Use specific industry terms (e.g., "Forensic Accounting", "Tax Compliance", "Financial Modeling").
        4. **O*NET ALIGNMENT**: Use O*NET skill names when available (e.g., "Financial Analysis", "Data Entry", "Active Listening").
        5. **NON-CODING CAREER CONSTRAINT**: If the career goal is NOT explicitly about software development, coding, or programming, FORBID any coding-related habits or skills.
           - *Forbidden for non-coding careers:* "LeetCode", "Git", "Code", "Programming", "Algorithm"
           - *Use instead:* Industry-standard tools like "Excel", "Tableau", "SAP", "QuickBooks", "Financial Modeling"
           - *Example:* For "Become an accountant", use "Create 1 Excel Macro" or "Balance a 3-statement model", NOT "Solve 1 LeetCode Easy"
        """
        
        prompt = base_prompt + career_constraints
        nodes = self._call_llm(prompt)
        goal_name_lower = north_star.lower()
        goal_words = set(goal_name_lower.split())
        
        # Ensure all nodes have the correct pillar and fix redundancy
        for i, node in enumerate(nodes):
            if node.pillar != Pillar.CAREER:
                node.pillar = Pillar.CAREER
            
            node_name_lower = node.name.lower()
            node_words = set(node_name_lower.split())
            
            # Check ALL nodes for redundancy (not just capstone)
            # If node name is too similar to goal name, rename it
            similarity_score = len(goal_words & node_words) / max(len(goal_words), len(node_words), 1)
            
            if similarity_score > 0.5 or goal_name_lower in node_name_lower or node_name_lower in goal_name_lower:
                # This node is redundant - rename it
                if i == len(nodes) - 1:  # Last node is capstone - use milestone event
                    if "accountant" in goal_name_lower or "accounting" in goal_name_lower:
                        node.name = "Pass CPA Exam" if skill_level >= 4 else "Complete Accounting Certification"
                    elif any(word in goal_name_lower for word in ["developer", "programmer", "engineer", "software"]):
                        node.name = "Land First Developer Job" if skill_level <= 6 else "Land Senior Developer Role"
                    elif any(word in goal_name_lower for word in ["manager", "lead", "executive"]):
                        node.name = "Land Management Role" if skill_level >= 5 else "Complete Leadership Training"
                    elif any(word in goal_name_lower for word in ["designer", "artist", "creative"]):
                        node.name = "Complete Portfolio Project" if skill_level <= 6 else "Land Creative Role"
                    else:
                        node.name = "Land First Job" if skill_level <= 6 else "Earn Industry Certification"
                else:  # Not capstone - rename to a specific skill
                    # Extract key words from goal and create a specific skill name
                    if "accountant" in goal_name_lower:
                        skill_options = ["Financial Statement Analysis", "Tax Compliance", "Audit Procedures", "Forensic Accounting"]
                        node.name = skill_options[min(i, len(skill_options) - 1)]
                    elif any(word in goal_name_lower for word in ["developer", "programmer"]):
                        skill_options = ["Data Structures", "API Development", "Database Design", "System Architecture"]
                        node.name = skill_options[min(i, len(skill_options) - 1)]
                    else:
                        # Generic fallback - use a numbered skill
                        node.name = f"Essential Skill {i+1}"
        
        return nodes


class PhysicalPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str], skill_level: int = 1) -> List[SkillNode]:
        base_prompt = self._generate_deep_prompt(north_star, current_quests, debuffs, skill_level, "Physical")
        
        # Add Physical-specific constraints with Periodization framework
        physical_constraints = f"""
        
        **PHYSICAL-SPECIFIC RULES (Periodization Framework):**
        1. **PERIODIZATION PHASES** (Use this structure):
           - **Phase 1: Foundation/Stability** (Mobility, Form, Connective Tissue)
           - **Phase 2: Hypertrophy/Capacity** (Volume, Aerobic Base/Zone 2)
           - **Phase 3: Strength/Threshold** (Intensity, Lactate Threshold)
           - **Phase 4: Power/VO2 Max** (Speed, Peak Output)
           - **Phase 5: Specificity** (Race Pace, 1RM Testing)
        
        2. **NO FILLER NAMES**: Do NOT create nodes called "Increased Endurance" or "Endurance Progression". 
           Use specific terms like "Zone 2 Base Building", "Lactate Threshold Training", "VO2 Max Intervals".
        
        3. **DEBUFF HANDLING**: If 'Sleep Deprivation' is in debuffs, Phase 1 MUST include 'Sleep Hygiene Protocol'.
        
        4. **CAPSTONE RULE**: The final node MUST be a concrete milestone appropriate for skill level {skill_level}/10, NOT the Goal name itself.
           - Level 1-3: "Run 1 mile without stopping", "Complete first workout"
           - Level 4-6: "Run 5K in 25 minutes", "Deadlift bodyweight"
           - Level 7-9: "Run 5K in 20 minutes", "Deadlift 1.5x bodyweight"
           - Level 10: "Run marathon in under 3 hours", "Deadlift 2x bodyweight"
        """
        
        prompt = base_prompt + physical_constraints
        nodes = self._call_llm(prompt)
        # Ensure all nodes have the correct pillar
        for node in nodes:
            if node.pillar != Pillar.PHYSICAL:
                node.pillar = Pillar.PHYSICAL
        return nodes


class MentalPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str], skill_level: int = 1) -> List[SkillNode]:
        base_prompt = self._generate_deep_prompt(north_star, current_quests, debuffs, skill_level, "Mental")
        
        # Add Mental-specific constraints
        mental_constraints = f"""
        
        **MENTAL-SPECIFIC RULES:**
        1. **SKILLS NOT STATES (CRITICAL)**: All skill names MUST be actionable Methods, Protocols, or Practices, NOT states of being.
           - *Forbidden States:* "Inner Peace", "Wellbeing", "Happiness", "Increased Wellbeing", "Mental Clarity", "Contentment" (These are passive states, not active skills)
           - *Required Format:* "{{Action}} {{Method/Protocol/Practice}}" (e.g., "Daily Mental Hygiene Protocol", "Personal Alignment Practice", "Self-Reflection Routine")
           - *Test:* If you cannot "perform" or "do" the skill name, it's a state. Rename it to the MAINTENANCE ROUTINE that generates that state.
           - *Example:* "Increased Wellbeing" → "Wellness Integration Routine" or "Daily Mental Hygiene Protocol"
        2. **CAPSTONE RULE**: The final node MUST be a concrete milestone appropriate for skill level {skill_level}/10, NOT the Goal name itself.
           - *Forbidden:* If Goal is "Be more in tune with myself", final node CANNOT be "Be More In Tune With Myself"
           - *Required:* Final node must be an actionable protocol (e.g., "Establish Daily Mental Hygiene Routine", "Complete Values Alignment Assessment")
        3. **ACTIONABLE**: Every skill must be something the user can DO, not something they can BE. All skills must be Methods, Protocols, or Practices.
        """
        
        prompt = base_prompt + mental_constraints
        nodes = self._call_llm(prompt)
        goal_name_lower = north_star.lower()
        
        # Ensure all nodes have the correct pillar and filter state-based names
        forbidden_states = ["wellbeing", "inner peace", "happiness", "increased wellbeing", "peace", "calm", "contentment", "mental clarity", "serenity", "joy", "bliss", "tranquility"]
        forbidden_patterns = [r"\b(increased|greater|improved|enhanced)\s+(wellbeing|wellness|happiness|peace|calm)\b"]
        
        for i, node in enumerate(nodes):
            if node.pillar != Pillar.MENTAL:
                node.pillar = Pillar.MENTAL
            
            node_name_lower = node.name.lower()
            
        # Post-process: Replace state-based names with actionable skills
        is_state_based = any(state in node_name_lower for state in forbidden_states)
        # Check for patterns like "increased wellbeing" using regex
        if not is_state_based:
            for pattern in forbidden_patterns:
                if re.search(pattern, node_name_lower):
                    is_state_based = True
                    break
            
            if is_state_based:
                # Replace with actionable alternative based on context
                if "wellbeing" in node_name_lower or "wellness" in node_name_lower:
                    if i == len(nodes) - 1:
                        node.name = "Establish Daily Mental Hygiene Protocol"
                    else:
                        node.name = "Wellness Integration Routine"
                elif "peace" in node_name_lower or "calm" in node_name_lower or "serenity" in node_name_lower or "tranquility" in node_name_lower:
                    node.name = "Stress Management Protocol"
                elif "happiness" in node_name_lower or "joy" in node_name_lower or "contentment" in node_name_lower or "bliss" in node_name_lower:
                    node.name = "Positive Psychology Practice"
                elif "clarity" in node_name_lower:
                    node.name = "Mental Clarity Practice"
                else:
                    # Generic fallback - convert state to action
                    node.name = "Daily Mental Hygiene Protocol"
            
            # Also check if capstone matches goal name (redundancy check)
            if i == len(nodes) - 1:  # Last node is capstone
                goal_words = set(goal_name_lower.split())
                node_words = set(node_name_lower.split())
                similarity_score = len(goal_words & node_words) / max(len(goal_words), len(node_words), 1)
                
                # If capstone is too similar to goal, rename it
                if similarity_score > 0.4 or goal_name_lower in node_name_lower or node_name_lower in goal_name_lower:
                    # Generate a mechanism-based name
                    if any(word in goal_name_lower for word in ["tune", "myself", "aware", "conscious"]):
                        node.name = "Establish Daily Mental Hygiene Routine"
                    elif any(word in goal_name_lower for word in ["wellbeing", "wellness", "health"]):
                        node.name = "Complete Wellness Integration Assessment"
                    elif any(word in goal_name_lower for word in ["peace", "calm", "stress"]):
                        node.name = "Complete Stress Management Protocol"
                    else:
                        node.name = "Complete Personal Alignment Protocol"
        
        return nodes


class ConnectionPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str], skill_level: int = 1) -> List[SkillNode]:
        base_prompt = self._generate_deep_prompt(north_star, current_quests, debuffs, skill_level, "Social")
        
        # Add Social-specific constraints with Chronology of Interaction framework
        social_constraints = f"""
        
        **SOCIAL-SPECIFIC RULES (Chronology of Interaction):**
        1. **CHRONOLOGY OF INTERACTION** (Follow this order):
           - **Phase 1: Approach/Signal** (Body language, Openers, Conversation Starters)
           - **Phase 2: Hook/Engagement** (Active Listening, Humor, Empathy)
           - **Phase 3: Rapport/Comfort** (Vulnerability, Common Ground, Nonverbal Communication)
           - **Phase 4: Connection/Intimacy** (Deep Dive questions, Rapport Building)
        
        2. **CHRONOLOGY CHECK**: You cannot build Rapport before you have Conversation Starters. 
           - *Bad Logic:* Rapport Building -> Conversation Starters (Wrong order)
           - *Good Logic:* Conversation Starters -> Active Listening -> Rapport Building
        
        3. **O*NET ALIGNMENT**: Use O*NET Social Skills (e.g., 'Social Perceptiveness', 'Active Listening', 'Persuasion') as node names when applicable.
        
        4. **CAPSTONE RULE (CRITICAL)**: The final node MUST be an ACTION-BASED milestone appropriate for skill level {skill_level}/10, NOT the Goal name itself.
           - **LEAD MEASURES ONLY**: Capstones must be actions YOU control, NOT outcomes dependent on others' reactions.
           - *Forbidden Outcomes:* "Make a friend", "Get a girlfriend", "Become popular" (These depend on others' reactions)
           - *Required Actions:* "Have a 20-minute conversation", "Attend 3 meetups", "Give a presentation" (These are under your control)
           - *Examples for Level {skill_level}:*
             * Level 1-3: "Have a 5-minute conversation with a stranger", "Introduce yourself to 1 new person"
             * Level 4-6: "Have a meaningful 20-minute conversation", "Attend 3 meetups and initiate 5 conversations"
             * Level 7-9: "Host a dinner party with 6 people", "Give a presentation to 20+ people"
             * Level 10: "Host a networking event with 30+ attendees", "Lead a workshop for 50+ people"
           **CRITICAL**: 
           - A Level 4 user should NOT get a Level 9-10 milestone like "Host a networking event"
           - Capstones must be LEAD MEASURES (actions you control), not LAG MEASURES (outcomes like "make a friend")
        """
        
        prompt = base_prompt + social_constraints
        nodes = self._call_llm(prompt)
        goal_name_lower = north_star.lower()
        
        # Outcome keywords that indicate lag measures (results, not actions)
        outcome_keywords = ["make a friend", "make friends", "get a friend", "get friends", "become popular", "find a friend", "find friends", "get someone to", "get a girlfriend", "get a boyfriend", "make them like", "win them over", "impress others"]
        
        for i, node in enumerate(nodes):
            if node.pillar != Pillar.SOCIAL:
                node.pillar = Pillar.SOCIAL
            
            node_name_lower = node.name.lower()
            
            # Check ALL nodes for outcome-based language (not just capstone)
            # But be more aggressive on capstone
            is_outcome_based = any(outcome in node_name_lower for outcome in outcome_keywords)
            
            if is_outcome_based:
                # Replace outcome-based language with action-based alternatives
                if "make" in node_name_lower and "friend" in node_name_lower:
                    if skill_level <= 3:
                        node.name = "Have a 5-minute conversation with a stranger"
                    elif skill_level <= 6:
                        node.name = "Have a meaningful 20-minute conversation"
                    else:
                        node.name = "Host a dinner party with 6 people"
                elif "get" in node_name_lower and "friend" in node_name_lower:
                    node.name = "Attend 3 meetups and initiate 5 conversations" if skill_level <= 6 else "Host a networking event"
                elif "popular" in node_name_lower or "impress" in node_name_lower:
                    node.name = "Give a presentation to 10+ people" if skill_level >= 5 else "Attend 3 social events"
                elif "find" in node_name_lower and "friend" in node_name_lower:
                    node.name = "Attend 3 meetups and initiate 5 conversations"
                elif "get a girlfriend" in node_name_lower or "get a boyfriend" in node_name_lower:
                    node.name = "Have a meaningful 20-minute conversation with someone new"
                else:
                    # Generic fallback - convert outcome to action
                    node.name = "Attend 3 meetups and initiate 5 conversations" if skill_level <= 6 else "Host a networking event"
            
            # Also check if capstone matches goal name (redundancy check)
            if i == len(nodes) - 1:  # Last node is capstone
                goal_words = set(goal_name_lower.split())
                node_words = set(node_name_lower.split())
                similarity_score = len(goal_words & node_words) / max(len(goal_words), len(node_words), 1)
                
                # If capstone is too similar to goal, rename it
                if similarity_score > 0.4 or goal_name_lower in node_name_lower or node_name_lower in goal_name_lower:
                    # Generate action-based capstone
                    if skill_level <= 3:
                        node.name = "Have a 5-minute conversation with a stranger"
                    elif skill_level <= 6:
                        node.name = "Have a meaningful 20-minute conversation"
                    else:
                        node.name = "Host a dinner party with 6 people"
        
        return nodes


def get_planner(category: str):
    """Returns an instance of the appropriate planner based on the category."""
    category_upper = category.upper()
    if "CAREER" in category_upper:
        return CareerPlanner()
    elif "PHYSICAL" in category_upper:
        return PhysicalPlanner()
    elif "MENTAL" in category_upper:
        return MentalPlanner()
    elif "SOCIAL" in category_upper or "CONNECTION" in category_upper:
        return ConnectionPlanner()
    else:
        # Default or fallback planner
        return CareerPlanner()