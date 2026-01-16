"""
Utility for regenerating skill tree nodes with adjusted difficulty.
"""
import json
import re
from typing import Literal, Optional, List, Dict, Tuple
from src.models import SkillNode, NodeType, DifficultyTier, REP_MAP, CharacterSheet, Pillar
from src.llm import LLMClient
from src.planners import get_planner
from src.skill_tree.generator import SkillTreeGenerator


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.strip('_')


def _get_ancestors(node_id: str, skill_tree_nodes: List[SkillNode]) -> set:
    """
    Get all ancestor node IDs (nodes that the target node depends on, directly or indirectly).
    Used for cycle detection - we don't want to reuse nodes that are ancestors of our target.
    
    Args:
        node_id: The ID of the target node
        skill_tree_nodes: List of all nodes in the skill tree
    
    Returns:
        Set of ancestor node IDs (including the node itself)
    """
    node_dict = {n.id: n for n in skill_tree_nodes}
    
    if node_id not in node_dict:
        return {node_id}  # Return the node itself if not found
    
    ancestors = set()
    to_process = [node_id]
    visited = set()
    
    while to_process:
        current_id = to_process.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)
        ancestors.add(current_id)
        
        if current_id in node_dict:
            current_node = node_dict[current_id]
            # Add all prerequisites as ancestors
            for prereq_id in (current_node.prerequisites or []):
                if prereq_id not in visited:
                    to_process.append(prereq_id)
    
    return ancestors


def _find_node_by_name(name: str, pillar: Pillar, skill_tree_nodes: List[SkillNode]) -> Optional[SkillNode]:
    """
    Find a node by name within the same pillar (for deduplication).
    Uses case-insensitive matching and handles slight variations.
    
    Args:
        name: Node name to search for
        pillar: Pillar to search within
        skill_tree_nodes: List of all nodes in the skill tree
    
    Returns:
        First matching SkillNode if found, None otherwise
    """
    name_lower = name.lower().strip()
    
    for node in skill_tree_nodes:
        if node.pillar != pillar:
            continue
        
        node_name_lower = node.name.lower().strip()
        
        # Exact match (case-insensitive)
        if node_name_lower == name_lower:
            return node
        
        # Check if names are very similar (fuzzy matching for slight variations)
        # Use a simple similarity check
        if name_lower in node_name_lower or node_name_lower in name_lower:
            # Additional check: if they share most words, consider it a match
            name_words = set(name_lower.split())
            node_words = set(node_name_lower.split())
            if len(name_words) > 0 and len(node_words) > 0:
                similarity = len(name_words & node_words) / max(len(name_words), len(node_words))
                if similarity > 0.8:  # 80% word overlap
                    return node
    
    return None


def _make_unique_id(used_ids: set, prefix: str, name: str) -> str:
    """Generate a unique ID for a node."""
    base = f"{prefix}_{_slugify(name)}"
    if base not in used_ids:
        used_ids.add(base)
        return base
    i = 2
    while f"{base}_{i}" in used_ids:
        i += 1
    new_id = f"{base}_{i}"
    used_ids.add(new_id)
    return new_id


def generate_easier_prerequisite_nodes(
    node: SkillNode,
    amount: Literal["little", "moderate", "a_lot"],
    reason: Optional[str] = None,
    used_ids: Optional[set] = None,
    character_sheet: Optional[CharacterSheet] = None,
    existing_skill_tree_nodes: Optional[List[SkillNode]] = None,
) -> List[SkillNode]:
    """
    Generate intermediate prerequisite nodes that lead up to the current node.
    Uses the Planner system to break down the node as a goal into prerequisite sub-skills and habits.
    
    Args:
        node: The target SkillNode that needs easier prerequisites
        amount: "little" (skill_level=8, shallow), "moderate" (skill_level=5, balanced), or "a_lot" (skill_level=2, deep)
        reason: Optional user-provided reason for the adjustment (passed to planner context)
        used_ids: Set of already-used node IDs to avoid conflicts
        character_sheet: CharacterSheet needed for planner/generator context
    
    Returns:
        List of new SkillNode objects (Sub-Skills + Habits) that should become prerequisites of the target node
    """
    if used_ids is None:
        used_ids = set()
    
    if character_sheet is None:
        # Fallback: create minimal character sheet for planner
        from src.models import CharacterSheet
        character_sheet = CharacterSheet(user_id="temp_adjustment")
    
    # Map amount to skill_level (inverse: lower skill_level = deeper tree)
    skill_level_map = {
        "little": 8,    # Shallow: 1-2 layers, close to target
        "moderate": 5,  # Balanced: 2-3 layers
        "a_lot": 2,     # Deep: 4-5 layers, very foundational
    }
    forced_skill_level = skill_level_map.get(amount, 5)
    
    # #region agent log
    try:
        with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
            import json as json_log, time
            f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:skill_level_mapping","message":"Amount to skill_level mapping","data":{"amount":amount,"mapped_skill_level":forced_skill_level,"node_name":node.name,"node_id":node.id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2,H3"}) + '\n')
    except: pass
    # #endregion
    
    try:
        # 1. Get the appropriate planner based on node's pillar
        pillar_name = node.pillar.value if hasattr(node.pillar, 'value') else str(node.pillar)
        planner = get_planner(pillar_name)
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:before_planner_call","message":"About to call planner.generate_roadmap","data":{"planner_type":type(planner).__name__,"pillar":pillar_name,"north_star":node.name,"forced_skill_level":forced_skill_level,"current_quests":current_quests if 'current_quests' in locals() else []},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H1,H2"}) + '\n')
        except: pass
        # #endregion
        
        # 2. Call planner.generate_roadmap() treating node.name as the goal
        # Include reason in current_quests as context for the planner
        current_quests = []
        if reason:
            # Pass reason as context - planners can use this to inform their breakdown
            current_quests.append(reason)
        
        roadmap_nodes = planner.generate_roadmap(
            north_star=node.name,  # The current node becomes the goal
            current_quests=current_quests,  # Empty or contains reason for context
            debuffs=character_sheet.debuffs if character_sheet else [],
            skill_level=forced_skill_level  # Forces tree depth based on amount
        )
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                # Calculate depth/layers from prerequisite chains
                def calculate_max_depth(nodes):
                    if not nodes:
                        return 0
                    node_dict = {n.id: n for n in nodes}
                    max_depth = 0
                    for node in nodes:
                        depth = 0
                        visited = set()
                        current = node
                        while current.prerequisites and depth < 20:  # Prevent infinite loops
                            if current.id in visited:
                                break
                            visited.add(current.id)
                            # Find first prerequisite that's in our node set
                            next_id = None
                            for prereq_id in current.prerequisites:
                                if prereq_id in node_dict:
                                    next_id = prereq_id
                                    break
                            if next_id:
                                current = node_dict[next_id]
                                depth += 1
                            else:
                                break
                        max_depth = max(max_depth, depth)
                    return max_depth + 1  # +1 because depth 0 = 1 layer
                
                max_depth = calculate_max_depth(roadmap_nodes)
                node_details = [{"id": n.id, "name": n.name, "prerequisites": n.prerequisites, "type": n.type.value if hasattr(n.type, 'value') else str(n.type)} for n in roadmap_nodes]
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:after_planner_call","message":"Planner returned roadmap nodes","data":{"node_count":len(roadmap_nodes),"max_depth_layers":max_depth,"nodes":node_details,"skill_level_received":forced_skill_level},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H2,H3,H4"}) + '\n')
        except Exception as log_err:
            pass
        # #endregion
        
        if not roadmap_nodes:
            raise ValueError("Planner returned no roadmap nodes")
        
        # 2.5. PILLAR-SCOPED DEDUPLICATION: Check for existing nodes and reuse when safe
        # Set up existing nodes mappings for the target pillar
        if existing_skill_tree_nodes is None:
            existing_skill_tree_nodes = []
        
        # Filter existing nodes to this pillar only
        existing_pillar_nodes = [n for n in existing_skill_tree_nodes if n.pillar == node.pillar]
        existing_pillar_nodes_by_id = {n.id: n for n in existing_pillar_nodes}
        existing_pillar_nodes_by_name = {n.name: n for n in existing_pillar_nodes}
        
        # Calculate ancestor IDs - traverse prerequisites from target node
        def _get_ancestors(target_node: SkillNode, nodes_by_id: Dict[str, SkillNode]) -> set:
            """Get all ancestor node IDs by following prerequisite chain."""
            ancestors = set()
            queue = [target_node.id] if target_node.prerequisites else []
            
            # Add direct prerequisites
            for prereq_id in (target_node.prerequisites or []):
                if prereq_id in nodes_by_id:
                    queue.append(prereq_id)
            
            # Traverse prerequisites recursively
            visited = set()
            while queue:
                current_id = queue.pop(0)
                if current_id in visited or current_id not in nodes_by_id:
                    continue
                visited.add(current_id)
                ancestors.add(current_id)
                
                current_node = nodes_by_id[current_id]
                for prereq_id in (current_node.prerequisites or []):
                    if prereq_id not in visited and prereq_id in nodes_by_id:
                        queue.append(prereq_id)
            
            return ancestors
        
        ancestor_ids = _get_ancestors(node, existing_pillar_nodes_by_id)
        
        # Map planner node IDs to actual node IDs (new or reused)
        planner_to_real_id_map: Dict[str, str] = {}  # planner_id -> real_id
        nodes_to_add: List[SkillNode] = []  # Only truly new nodes
        nodes_to_modify: List[SkillNode] = []  # Existing nodes that need prerequisite updates
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:dedup_start","message":"Starting pillar-scoped deduplication","data":{"target_node_id":node.id,"target_node_name":node.name,"ancestor_count":len(ancestor_ids),"existing_pillar_nodes_count":len(existing_pillar_nodes_by_name),"roadmap_nodes_count":len(roadmap_nodes)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
        except: pass
        # #endregion
        
        for planner_node in roadmap_nodes:
            planner_id = planner_node.id
            planner_name = planner_node.name
            
            # CASE A: Cycle Detection - Skip if this node name matches an ancestor
            # Check if any ancestor has the same name (would create a cycle)
            ancestor_names = {existing_pillar_nodes_by_id[aid].name for aid in ancestor_ids if aid in existing_pillar_nodes_by_id}
            if planner_name in ancestor_names:
                # #region agent log
                try:
                    with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        import json as json_log, time
                        f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:cycle_detected","message":"Skipping node due to cycle detection","data":{"planner_node_name":planner_name,"planner_node_id":planner_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
                except: pass
                # #endregion
                continue  # Skip this node to prevent cycle
            
            # CASE B: Node exists in same pillar - REUSE it (unless adjusting a Habit, which should get NEW nodes)
            # For Habit nodes, skip reuse to always generate new prerequisite chains
            existing_node = None
            if node.type != NodeType.HABIT:
                # For Goals/Sub-Skills: try to reuse existing nodes
                existing_node = _find_node_by_name(planner_name, node.pillar, existing_skill_tree_nodes)
                if existing_node:
                    # Verify cycle safety: ensure the existing node is not an ancestor
                    if existing_node.id in ancestor_ids:
                        # #region agent log
                        try:
                            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                import json as json_log, time
                                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:reuse_blocked_by_cycle","message":"Cannot reuse existing node - would create cycle","data":{"planner_node_name":planner_name,"existing_node_id":existing_node.id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
                        except: pass
                        # #endregion
                        # Skip reuse if it would create a cycle
                        existing_node = None
            else:
                # For Habit nodes: force creation of NEW nodes (don't reuse)
                # This ensures we always return something for habit adjustments
                pass
            
            if existing_node:
                # REUSE: Map planner ID to existing node ID
                planner_to_real_id_map[planner_id] = existing_node.id
                
                # Track that we need to merge prerequisites into this existing node
                # We'll do the merging after processing all nodes
                nodes_to_modify.append((existing_node, planner_node))
                
                # #region agent log
                try:
                    with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        import json as json_log, time
                        f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:node_reused","message":"Reusing existing node","data":{"planner_node_name":planner_name,"existing_node_id":existing_node.id,"existing_node_name":existing_node.name},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
                except: pass
                # #endregion
            else:
                # CASE C: Truly new node - generate unique ID and add to list
                prefix = "skill"  # Planner generates Sub-Skills
                new_id = _make_unique_id(used_ids, prefix, planner_name)
                planner_to_real_id_map[planner_id] = new_id
                
                # Update the planner node with the new ID
                planner_node.id = new_id
                nodes_to_add.append(planner_node)
        
        # Now process nodes_to_add and nodes_to_modify to handle prerequisite remapping
        # Remap prerequisites for new nodes: convert planner IDs to real IDs (new or reused)
        for new_node in nodes_to_add:
            remapped_prereqs = []
            for prereq_id in new_node.prerequisites:
                if prereq_id in planner_to_real_id_map:
                    remapped_prereqs.append(planner_to_real_id_map[prereq_id])
                # Note: prereq_id might also be from existing nodes that weren't in planner output
                # Those will be handled by the API endpoint
            new_node.prerequisites = remapped_prereqs
        
        # Merge prerequisites for reused nodes (add new dependencies from planner to existing nodes)
        for existing_node, planner_node in nodes_to_modify:
            # Remap planner's prerequisites to real IDs (could be new IDs or other existing IDs)
            planner_prereqs = []
            for prereq_id in planner_node.prerequisites:
                if prereq_id in planner_to_real_id_map:
                    real_prereq_id = planner_to_real_id_map[prereq_id]
                    planner_prereqs.append(real_prereq_id)
            
            # Merge: Add any new prerequisites that don't already exist (union of dependencies)
            existing_prereqs_set = set(existing_node.prerequisites or [])
            new_prereqs_added = 0
            for new_prereq_id in planner_prereqs:
                if new_prereq_id not in existing_prereqs_set:
                    existing_node.prerequisites.append(new_prereq_id)
                    existing_prereqs_set.add(new_prereq_id)
                    new_prereqs_added += 1
            
            # #region agent log
            try:
                with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    import json as json_log, time
                    f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:prereqs_merged","message":"Merged prerequisites into existing node","data":{"existing_node_id":existing_node.id,"existing_node_name":existing_node.name,"original_prereqs":list(existing_node.prerequisites)[:-new_prereqs_added] if new_prereqs_added > 0 else list(existing_node.prerequisites),"new_prereqs_added":new_prereqs_added,"final_prereqs_count":len(existing_node.prerequisites)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
            except: pass
            # #endregion
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                original_count = len(roadmap_nodes)
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:dedup_complete","message":"Deduplication complete","data":{"original_planner_nodes":original_count,"new_nodes_count":len(nodes_to_add),"reused_nodes_count":len(nodes_to_modify),"nodes_skipped_cycle":original_count - len(nodes_to_add) - len(nodes_to_modify)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
        except: pass
        # #endregion
        
        # Continue with the deduplicated new nodes for further processing (depth checking, habit generation)
        roadmap_nodes = nodes_to_add
        
        # 2.6. Post-process: Enforce depth limit if LLM ignored prompt instructions
        # Note: Depth checking only applies to NEW nodes (reused nodes are already in the tree and shouldn't be pruned)
        # Calculate expected max depth based on skill_level
        expected_max_depth = {
            2: 5,   # a_lot: deep
            3: 5,
            4: 5,
            5: 3,   # moderate: balanced
            6: 3,
            7: 3,
            8: 2,   # little: shallow
            9: 2,
            10: 2,
        }.get(forced_skill_level, 3)
        
        # Calculate actual depth
        def calculate_max_depth(nodes):
            """Calculate maximum depth of prerequisite chain."""
            if not nodes:
                return 0
            node_dict = {n.id: n for n in nodes}
            
            def get_depth(node_id, visited=None):
                if visited is None:
                    visited = set()
                if node_id in visited or node_id not in node_dict:
                    return 0
                visited.add(node_id)
                node = node_dict[node_id]
                if not node.prerequisites:
                    return 1
                max_child_depth = 0
                for prereq_id in node.prerequisites:
                    if prereq_id in node_dict:
                        child_depth = get_depth(prereq_id, visited.copy())
                        max_child_depth = max(max_child_depth, child_depth)
                return max_child_depth + 1
            
            max_depth = 0
            for node in nodes:
                depth = get_depth(node.id)
                max_depth = max(max_depth, depth)
            return max_depth
        
        actual_depth = calculate_max_depth(roadmap_nodes)
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:depth_check","message":"Checking depth compliance","data":{"actual_depth":actual_depth,"expected_max_depth":expected_max_depth,"skill_level":forced_skill_level,"node_count":len(roadmap_nodes),"needs_pruning":actual_depth > expected_max_depth},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H3"}) + '\n')
        except: pass
        # #endregion
        
        # If depth exceeds expected, prune to keep only top layers (terminal nodes and their immediate prerequisites)
        if actual_depth > expected_max_depth:
            # Find terminal nodes (nodes that are NOT prerequisites for other nodes - these are at the top of the chain)
            all_prereq_ids = set()
            for node in roadmap_nodes:
                all_prereq_ids.update(node.prerequisites)
            
            terminal_nodes = [n for n in roadmap_nodes if n.id not in all_prereq_ids]
            
            if terminal_nodes:
                # Simplify: For "little" (expected_max_depth=2), keep only terminal nodes
                # They represent the top of the chain and are closest to the original goal
                # This ensures we have at most 1-2 layers (terminals + maybe their prerequisites)
                original_nodes_dict = {n.id: n for n in roadmap_nodes}
                selected_node_ids = set()
                
                # Collect terminal nodes
                for terminal in terminal_nodes:
                    selected_node_ids.add(terminal.id)
                    # If expected_max_depth allows, also collect their immediate prerequisites (1 level down)
                    if expected_max_depth >= 2:
                        for prereq_id in terminal.prerequisites:
                            if prereq_id in original_nodes_dict:
                                selected_node_ids.add(prereq_id)
                
                # Rebuild roadmap_nodes with only selected nodes and updated prerequisites
                new_roadmap_nodes = []
                for node in roadmap_nodes:
                    if node.id in selected_node_ids:
                        # Create new node with filtered prerequisites (only those also in selected set)
                        filtered_prereqs = [prereq_id for prereq_id in node.prerequisites if prereq_id in selected_node_ids]
                        # Create a copy with updated prerequisites
                        new_node = SkillNode(
                            id=node.id,
                            name=node.name,
                            type=node.type,
                            pillar=node.pillar,
                            prerequisites=filtered_prereqs,
                            xp_reward=node.xp_reward,
                            xp_multiplier=node.xp_multiplier,
                            required_completions=node.required_completions,
                            description=node.description,
                        )
                        new_roadmap_nodes.append(new_node)
                
                roadmap_nodes = new_roadmap_nodes
            else:
                # Fallback: if no terminal nodes found, just keep first 1-3 nodes (shouldn't happen)
                max_nodes_for_level = {8: 2, 9: 2, 10: 2, 5: 4, 6: 4, 7: 4}.get(forced_skill_level, 3)
                roadmap_nodes = roadmap_nodes[:max_nodes_for_level]
                # Clear prerequisites for these nodes since we're using them as simple prerequisites
                for node in roadmap_nodes:
                    node.prerequisites = []
            
            # #region agent log
            try:
                with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    import json as json_log, time
                    pruned_depth = calculate_max_depth(roadmap_nodes)
                    f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:after_pruning","message":"Pruned roadmap to enforce depth limit","data":{"original_depth":actual_depth,"pruned_depth":pruned_depth,"expected_max_depth":expected_max_depth,"original_node_count":len(roadmap_nodes) if 'original_node_count' in locals() else 'unknown',"pruned_node_count":len(roadmap_nodes)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H3"}) + '\n')
            except: pass
            # #endregion
        
        # 3. Finalize new nodes (prerequisites already remapped in step 2.5)
        # Ensure all new nodes have correct pillar and are properly formatted
        remapped_roadmap_nodes: List[SkillNode] = []
        for roadmap_node in roadmap_nodes:
            # Prerequisites already remapped above, pillar already set
            # Just ensure everything is correct and create final SkillNode
            roadmap_node.pillar = node.pillar  # Ensure pillar matches
            
            remapped_roadmap_nodes.append(roadmap_node)
        
        # 4. Generate habits for the sub-skills using SkillTreeGenerator
        generator = SkillTreeGenerator()
        habit_nodes = generator._generate_habits_for_skills(remapped_roadmap_nodes, used_ids)
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:after_habit_generation","message":"Habits generated for roadmap nodes","data":{"roadmap_node_count":len(remapped_roadmap_nodes),"habit_node_count":len(habit_nodes)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H4"}) + '\n')
        except: pass
        # #endregion
        
        # 5. Collect all new nodes (Sub-Skills + Habits)
        all_new_nodes = remapped_roadmap_nodes + habit_nodes
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                # Recalculate depth including habits
                def calculate_total_depth(nodes):
                    """Calculate maximum depth including all nodes (Sub-Skills + Habits)"""
                    if not nodes:
                        return 0
                    node_dict = {n.id: n for n in nodes}
                    
                    # Find all leaf nodes (no prerequisites)
                    leaf_nodes = [n for n in nodes if not n.prerequisites]
                    
                    def get_depth(node_id, visited=None):
                        if visited is None:
                            visited = set()
                        if node_id in visited:
                            return 0
                        visited.add(node_id)
                        if node_id not in node_dict:
                            return 0
                        node = node_dict[node_id]
                        if not node.prerequisites:
                            return 1
                        max_child_depth = 0
                        for prereq_id in node.prerequisites:
                            if prereq_id in node_dict:
                                child_depth = get_depth(prereq_id, visited.copy())
                                max_child_depth = max(max_child_depth, child_depth)
                        return max_child_depth + 1
                    
                    max_depth = 0
                    for node in nodes:
                        depth = get_depth(node.id)
                        max_depth = max(max_depth, depth)
                    return max_depth
                
                total_depth = calculate_total_depth(all_new_nodes)
                subskill_only_depth = calculate_total_depth(remapped_roadmap_nodes)
                
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:final_result","message":"Final node generation complete","data":{"total_nodes":len(all_new_nodes),"subskill_count":len(remapped_roadmap_nodes),"habit_count":len(habit_nodes),"total_depth_with_habits":total_depth,"subskill_only_depth":subskill_only_depth,"amount_requested":amount,"skill_level_used":forced_skill_level},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"H4,H5"}) + '\n')
        except: pass
        # #endregion
        
        # 6. Graph Stitching: Find terminal nodes (nodes that should become prerequisites of the original node)
        # We need to find terminal nodes from BOTH new nodes AND reused nodes
        # Terminal nodes = nodes that are NOT prerequisites for any other node in our processed set
        
        # Collect all prerequisite IDs from new nodes only (for finding terminals among new nodes)
        new_node_prereq_ids = set()
        for new_node in remapped_roadmap_nodes:
            new_node_prereq_ids.update(new_node.prerequisites)
        
        # Terminal nodes from NEW nodes only (reused nodes' terminals will be found by API endpoint)
        terminal_node_ids_from_new = [
            n.id for n in remapped_roadmap_nodes 
            if n.id not in new_node_prereq_ids
        ]
        
        # Also include reused nodes that are terminals (not prerequisites of new nodes)
        terminal_node_ids_from_reused = []
        reused_node_ids = {existing_node.id for existing_node, _ in nodes_to_modify}
        for existing_node, _ in nodes_to_modify:
            # If this reused node is not a prerequisite of any new node, it's a terminal
            if existing_node.id not in new_node_prereq_ids:
                terminal_node_ids_from_reused.append(existing_node.id)
        
        # Combine terminal nodes (API will use these to link to original node)
        all_terminal_node_ids = terminal_node_ids_from_new + terminal_node_ids_from_reused
        
        # If no terminals found in new nodes, use nodes with no prerequisites
        if not all_terminal_node_ids:
            for new_node in remapped_roadmap_nodes:
                if not new_node.prerequisites:
                    all_terminal_node_ids.append(new_node.id)
            for existing_node, _ in nodes_to_modify:
                if not existing_node.prerequisites:
                    all_terminal_node_ids.append(existing_node.id)
        
        # #region agent log
        try:
            with open(r'd:\Noobcept\Lock In Labs\.cursor\debug.log', 'a', encoding='utf-8') as f:
                import json as json_log, time
                f.write(json_log.dumps({"location":"node_regenerator.py:generate_easier_prerequisite_nodes:terminal_nodes","message":"Found terminal nodes for graph stitching","data":{"terminal_node_ids":all_terminal_node_ids,"terminal_count":len(all_terminal_node_ids),"from_new_nodes":len(terminal_node_ids_from_new),"from_reused_nodes":len(terminal_node_ids_from_reused)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"DEDUP"}) + '\n')
        except: pass
        # #endregion
        
        # Return NEW nodes and information about reused nodes
        # The API endpoint will:
        # 1. Add returned new nodes to the skill tree
        # 2. Update existing nodes (from nodes_to_modify) in the skill tree with merged prerequisites
        # 3. Link terminal nodes (both new and reused) to the original node
        
        # Return tuple: (new_nodes, reused_nodes_info)
        # For backwards compatibility, we'll return just new_nodes but store reused info separately
        # Actually, let's return a dict with metadata for now, then API can handle it
        return all_new_nodes
        
    except Exception as e:
        print(f"Error generating easier prerequisite nodes using planner: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: create one basic intermediate node
        prefix = "skill" if node.type == NodeType.SUB_SKILL else "habit"
        fallback_name = f"Basic {node.name}"
        
        if reason:
            # Try to incorporate reason into fallback name
            if any(keyword in reason.lower() for keyword in ["specific", "example", "concrete"]):
                fallback_name = f"Complete specific {node.name.lower()} task with detailed steps"
        
        new_id = _make_unique_id(used_ids, prefix, fallback_name)
        fallback_node = SkillNode(
            id=new_id,
            name=fallback_name,
            type=node.type,
            pillar=node.pillar,
            prerequisites=[],
            xp_reward=15 if node.type == NodeType.HABIT else 100,
            xp_multiplier=1.0,
            required_completions=7,
            description=f"An easier foundational version of {node.name}",
        )
        return [fallback_node]


def regenerate_node_with_difficulty(
    node: SkillNode,
    direction: Literal["easier", "harder"],
    amount: Literal["little", "moderate", "a_lot"],
    reason: Optional[str] = None,
) -> SkillNode:
    """
    Regenerate a skill node with adjusted difficulty using LLM.
    
    NOTE: For "easier" direction, this function should NOT be called directly.
    Use generate_easier_prerequisite_nodes() instead to create intermediate nodes.
    
    For "harder" direction, this function modifies the current node to be harder.
    
    Args:
        node: The original SkillNode to regenerate (only for "harder")
        direction: "easier" (should use generate_easier_prerequisite_nodes) or "harder" (modify this node)
        amount: "little" (25%), "moderate" (50%), or "a_lot" (75%)
        reason: Optional user-provided reason for the adjustment
    
    Returns:
        Updated SkillNode with new name, description, and required_completions (harder version)
    """
    # Only handle "harder" case here
    if direction == "easier":
        raise ValueError("For 'easier' direction, use generate_easier_prerequisite_nodes() instead")
    
    # Calculate adjustment percentage for harder
    amount_map = {
        "little": 0.25,
        "moderate": 0.50,
        "a_lot": 0.75,
    }
    adjustment_pct = amount_map.get(amount, 0.50)
    
    # For harder: Make the task itself harder (increase complexity/duration)
    # Optionally decrease reps (fewer reps but each rep is much harder)
    current_completions = node.required_completions or 30
    
    # Strategy: Make each completion harder, so decrease total required completions
    # This reflects that each rep now requires more effort/time/complexity
    # Decrease by adjustment percentage (e.g., 25% decrease for "little", 50% for "moderate", 75% for "a_lot")
    new_completions = max(1, int(current_completions * (1 - adjustment_pct * 0.5)))  # Decrease reps (50% of adjustment amount)
    
    # Build prompt for LLM to make the task HARDER
    llm_client = LLMClient()
    
    prompt = f"""You are making a {node.type} HARDER for a Life RPG system.

ORIGINAL NODE:
- Name: {node.name}
- Type: {node.type}
- Description: {node.description or "No description"}
- Current required completions: {current_completions}
- Pillar: {node.pillar.value if hasattr(node.pillar, 'value') else node.pillar}

USER REQUEST:
- Make it HARDER
- Amount: {amount} ({adjustment_pct * 100}% harder)
- New required completions: {new_completions} (decreased because each completion is now much harder/more complex)
{f"- User's reason: {reason}" if reason else ""}

INSTRUCTIONS FOR MAKING IT HARDER:
1. Generate a NEW name and description that reflects a HARDER/more advanced version
2. The name should indicate increased complexity, duration, or scope
3. Make the task itself harder, not just increase repetitions:
   - For Habits: Increase duration/complexity (e.g., "Run 1 mile" → "Run 5k", "Read 10 pages" → "Read 50 pages and summarize")
   - For Sub-Skills: Make it more advanced (e.g., "Basic Python" → "Advanced Python with Data Structures", "Financial Analysis" → "Complex Financial Modeling")
4. The description should explain why this harder version is appropriate
5. Maintain the core concept/skill but increase difficulty substantially
6. The name should clearly indicate it's a more advanced/challenging version
{f"7. IMPORTANT: Consider the user's reason. If they say it's too easy, create a deeper/more advanced version. Use the reason to inform how much harder to make it." if reason else ""}

EXAMPLES:
- "Code for 30 mins" → "Build a full-stack application feature"
- "Read 1 chapter" → "Read 3 chapters and write analysis"
- "Basic Excel" → "Advanced Excel with Macros and Power Query"
- "Meditate 5 mins" → "Meditate 20 mins with body scan"

Return JSON ONLY:
{{
    "name": "Harder/more advanced version name",
    "description": "Clear explanation of why this is harder and what makes it more challenging",
    "required_completions": {new_completions}
}}"""
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        response_text = llm_client.chat_completion(messages, json_mode=True)
        data = json.loads(response_text)
        
        # Extract regenerated fields
        new_name = data.get("name", node.name)
        new_description = data.get("description", node.description)
        new_required_completions = data.get("required_completions", new_completions)
        
        # Validate and clamp required_completions
        new_required_completions = max(1, min(100, int(new_required_completions)))
        
        # Create updated node (preserve all other fields)
        updated_node = SkillNode(
            id=node.id,  # Keep same ID
            name=new_name,
            type=node.type,
            pillar=node.pillar,
            prerequisites=node.prerequisites.copy() if node.prerequisites else [],  # Preserve prerequisites
            xp_reward=node.xp_reward,  # Keep XP reward the same (difficulty reflected in completions)
            xp_multiplier=node.xp_multiplier,
            required_completions=new_required_completions,
            description=new_description,
        )
        
        return updated_node
        
    except Exception as e:
        print(f"Error regenerating node with LLM: {e}")
        # Fallback: update required_completions only, keep original name/description
        updated_node = SkillNode(
            id=node.id,
            name=node.name,
            type=node.type,
            pillar=node.pillar,
            prerequisites=node.prerequisites.copy() if node.prerequisites else [],
            xp_reward=node.xp_reward,
            xp_multiplier=node.xp_multiplier,
            required_completions=new_completions,
            description=node.description,
        )
        return updated_node
