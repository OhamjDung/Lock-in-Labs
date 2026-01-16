import React, { useState, useEffect, useMemo } from 'react';
import { Plus, Minus, Maximize, Star, Diamond, Circle } from 'lucide-react';
import { skillTreeJson } from '../../data/mockData';
import dagre from 'dagre';
import NodeContextMenu from './NodeContextMenu';
import NodeQuestionDialog from './NodeQuestionDialog';
import NodeDifficultyDialog from './NodeDifficultyDialog';

// Only send ingest logs when explicitly enabled to avoid noisy console errors
const INGEST_ENDPOINT = typeof window !== 'undefined' && window.__INGEST_URL ? window.__INGEST_URL : null;
const safeIngest = (body) => {
    if (!INGEST_ENDPOINT) return;
    fetch(INGEST_ENDPOINT, body).catch(() => {});
};

const TreeVisualizer = ({ pillar, skillTree, characterSheet, onSkillTreeUpdate }) => {
    const [transform, setTransform] = useState({ x: 500, y: 50, k: 0.8 });
    const [isDragging, setIsDragging] = useState(false);
    const [startPan, setStartPan] = useState({ x: 0, y: 0 });
    const [hoveredNodeId, setHoveredNodeId] = useState(null);
    const [contextMenu, setContextMenu] = useState(null);
    const [questionDialog, setQuestionDialog] = useState(null);
    const [difficultyDialog, setDifficultyDialog] = useState(null);
    
    // Position preservation system (from skill_tree_viewer.html)
    const [nodePositions, setNodePositions] = useState({}); // Cache node positions
    const [previousNodeIds, setPreviousNodeIds] = useState(new Set()); // Track existing nodes
    const [lastAdjustedNodeId, setLastAdjustedNodeId] = useState(null); // Track adjusted node

    const layout = useMemo(() => {
        // #region agent log
        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:layout',message:'Layout calculation started',data:{pillar, hasSkillTree: !!skillTree, nodesCount: skillTree?.nodes?.length || 0, nodeTypes: skillTree?.nodes?.reduce((acc, n) => { acc[n.type] = (acc[n.type] || 0) + 1; return acc; }, {}) || {}},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H4-H5'})});
        // #endregion
        
        const nodesSource = (skillTree && skillTree.nodes && skillTree.nodes.length > 0) ? skillTree.nodes : skillTreeJson.nodes;
        const pillarNodes = nodesSource.filter(n => n.pillar === pillar);
        
        console.log(`\n🌳 [LAYOUT] Starting layout calculation for ${pillar}:`);
        console.log(`   Total nodes: ${nodesSource.length}`);
        console.log(`   Pillar nodes: ${pillarNodes.length}`);
        console.log(`   Cached positions: ${Object.keys(nodePositions).length}`);
        console.log(`   Last adjusted: ${lastAdjustedNodeId || 'none'}`);
        
        if (pillarNodes.length === 0) {
            return { nodes: [], edges: [], width: 800, height: 800 };
        }

        // Initialize Dagre Graph (FIXED: Use BT like working HTML version)
        const g = new dagre.graphlib.Graph();
        g.setGraph({ 
            rankdir: 'BT', // Bottom-to-Top (Habits at bottom, Goal at top) - MATCHES HTML
            nodesep: 100,   // Horizontal spacing
            ranksep: 150,   // Vertical spacing
            edgesep: 20,
            ranker: 'tight-tree'
        });
        g.setDefaultEdgeLabel(() => ({}));

        // Add Nodes to Graph
        pillarNodes.forEach(node => {
            let w = 70, h = 70;
            if (node.type === 'Goal') { w = 120; h = 120; }
            if (node.type === 'Habit') { w = 50; h = 50; }
            
            g.setNode(node.id, { 
                label: node.name, 
                type: node.type, 
                width: w, 
                height: h, 
                original: node 
            });
        });

        // Add Edges (FIXED: Use BT logic from HTML - prerequisite -> dependent)
        let edgeCount = 0;
        let missingEdges = 0;
        const debugEdges = [];
        
        pillarNodes.forEach(node => {
            if (node.prerequisites && node.prerequisites.length > 0) {
                node.prerequisites.forEach(prereqId => {
                    // Check if prereq exists in this pillar view
                    const prereqNode = pillarNodes.find(n => n.id === prereqId);
                    if (prereqNode) {
                        // Edge from prerequisite to dependent node (BT layout)
                        g.setEdge(prereqId, node.id);
                        edgeCount++;
                        if (debugEdges.length < 5) {
                            debugEdges.push(`${prereqNode.name} → ${node.name}`);
                        }
                    } else {
                        missingEdges++;
                    }
                });
            }
        });
        
        console.log(`\n🔗 [EDGES] Edge creation summary:`);
        console.log(`   Total edges created: ${edgeCount}`);
        console.log(`   Missing prerequisites: ${missingEdges}`);
        console.log(`   Sample edges:`, debugEdges);

        // Calculate Layout
        try {
            dagre.layout(g);
        } catch (e) {
            console.error('Dagre layout error:', e);
            return { nodes: [], edges: [], width: 800, height: 800 };
        }

        // Position restoration logic (from skill_tree_viewer.html lines 1035-1055)
        let restoredCount = 0;
        let newNodeCount = 0;
        console.log(`\n📊 [POSITION RESTORE] Starting position restoration:`);
        
        g.nodes().forEach(nodeId => {
            const current = g.node(nodeId);
            
            // If we just adjusted a node, don't restore ANY positions - let Dagre recalculate everything fresh
            if (lastAdjustedNodeId) {
                newNodeCount++;
                if (newNodeCount <= 5) {
                    console.log(`   ✨ [FRESH LAYOUT] "${current.label}": Dagre calculated (${current.x}, ${current.y})`);
                }
                return;
            }
            
            if (previousNodeIds.has(nodeId) && nodePositions[nodeId]) {
                // This node existed before - restore its position
                const cached = nodePositions[nodeId];
                current.x = cached.x;
                current.y = cached.y;
                restoredCount++;
                
                if (restoredCount <= 5) {
                    console.log(`   ✓ Restored "${current.label}": (${current.x}, ${current.y})`);
                }
            } else {
                // This is a new node - keep Dagre's position
                newNodeCount++;
                if (newNodeCount <= 5) {
                    console.log(`   ✨ New node "${current.label}": (${current.x}, ${current.y})`);
                }
            }
        });
        
        console.log(`\n📍 Position Summary:`);
        console.log(`   Existing nodes restored: ${restoredCount}`);
        console.log(`   New nodes placed: ${newNodeCount}`);
        console.log(`   Total nodes now: ${g.nodes().length}\n`);

        // Calculate bounds to normalize coordinates into positive space (avoids node/edge drift)
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        g.nodes().forEach(v => {
            const n = g.node(v);
            minX = Math.min(minX, n.x - n.width/2);
            minY = Math.min(minY, n.y - n.height/2);
            maxX = Math.max(maxX, n.x + n.width/2);
            maxY = Math.max(maxY, n.y + n.height/2);
        });

        const padding = 100;
        // Calculate SVG size to cover all nodes with padding (NO offsetX/offsetY transformation)
        const svgWidth = Math.max(2000, maxX + padding);
        const svgHeight = Math.max(2000, maxY + padding);

        // Process nodes - use direct dagre positions (NO offset added)
        const processedNodes = [];
        
        g.nodes().forEach(v => {
            const n = g.node(v);
            const node = n.original;
            
            // Use direct Dagre position - NO offsetX/offsetY translation
            const nodeX = n.x;
            const nodeY = n.y;
            
            // Get progress data for habits (same as before)
            let progressPercent = 0;
            let status = 'LOCKED';
            let completed = 0;
            // Default to node's required_completions or 30 (model default), only use 1 as fallback for non-habits
            let required = (node.type === 'Habit') ? (node.required_completions ?? 30) : 1;
            
            if (node.type === 'Habit' && characterSheet && characterSheet.habit_progress) {
                const progress = characterSheet.habit_progress[node.id];
                if (progress) {
                    completed = progress.completed_total || 0;
                    // Use nullish coalescing to preserve 0 values, only default if null/undefined
                    required = node.required_completions ?? 30;
                    progressPercent = Math.min(100, Math.max(0, (completed / required) * 100));
                    status = progress.status === 'ACTIVE' ? 'ACTIVE' : 'LOCKED';
                } else {
                    // Even if no progress yet, set the required value from the node
                    required = node.required_completions ?? 30;
                }
            } else if (node.type === 'Habit') {
                // Set required even if no characterSheet or habit_progress
                required = node.required_completions ?? 30;
            }
            
            processedNodes.push({
                ...node,
                x: nodeX,
                y: nodeY,
                progressPercent,
                status,
                completed,
                required
            });
        });

        // Process edges with smooth curves (same as HTML)
        const processedEdges = [];
        let drawnEdges = 0;
        
        g.edges().forEach(e => {
            const edge = g.edge(e);
            const points = edge.points || [];
            
            if (points.length < 2) return;
            
            drawnEdges++;
            
            // Create smooth curve using quadratic bezier (matches HTML logic)
            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                if (i === points.length - 1) {
                    // Last point - straight line
                    d += ` L ${points[i].x} ${points[i].y}`;
                } else {
                    // Use quadratic bezier for smooth curves
                    const midX = (points[i].x + points[i-1].x) / 2;
                    const midY = (points[i].y + points[i-1].y) / 2;
                    d += ` Q ${points[i-1].x} ${points[i-1].y} ${midX} ${midY}`;
                }
            }
            
            processedEdges.push({
                id: `edge-${e.v}-${e.w}`,
                d: d,
                sourceId: e.v,
                targetId: e.w
            });
        });
        
        console.log(`\n📈 [DRAWN EDGES] Total edges drawn: ${drawnEdges}`);

        // #region agent log
        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:result',message:'Layout calculation complete',data:{pillar, processedNodesCount: processedNodes.length, processedEdgesCount: processedEdges.length, svgWidth, svgHeight, nodeNames: processedNodes.map(n => n.name)},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H5'})});
        // #endregion
        
        return { nodes: processedNodes, edges: processedEdges, width: svgWidth, height: svgHeight };
      }, [pillar, skillTree, characterSheet, nodePositions, previousNodeIds, lastAdjustedNodeId]);

    // Cache node positions after layout (from HTML lines 1285-1299)
    useEffect(() => {
        if (layout.nodes.length > 0) {
            const positions = {};
            const nodeIds = new Set();
            
            layout.nodes.forEach(node => {
                positions[node.id] = { x: node.x, y: node.y };
                nodeIds.add(node.id);
            });
            
            setNodePositions(positions);
            setPreviousNodeIds(nodeIds);
            console.log(`📸 [CACHE SAVED] Cached ${nodeIds.size} node positions for future adjustments`);
            
            // Clear the adjustment flag now that we've cached everything
            setLastAdjustedNodeId(null);
        }
    }, [layout.nodes]);

    useEffect(() => { setTransform({ x: 500, y: 50, k: 0.8 }); }, [pillar]);

    // Use ref for wheel event to make it non-passive
    const containerRef = React.useRef(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const handleWheel = (e) => {
            // Disable zoom when difficulty dialog is open
            if (difficultyDialog) return;
            
            e.preventDefault();
            e.stopPropagation();
            const delta = -e.deltaY * 0.001;
            setTransform(prev => {
                const newScale = Math.min(Math.max(0.2, prev.k + delta), 3);
                
                // Get mouse position relative to the container
                const rect = container.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                // Calculate the point in world coordinates before zoom
                const worldX = (mouseX - prev.x) / prev.k;
                const worldY = (mouseY - prev.y) / prev.k;
                
                // Calculate new transform to keep the same point under the cursor
                const newX = mouseX - worldX * newScale;
                const newY = mouseY - worldY * newScale;
                
                // #region agent log
                safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleWheel',message:'Zoom transform update - cursor-focused',data:{prevScale:prev.k,newScale,prevX:prev.x,prevY:prev.y,newX,newY,mouseX,mouseY,worldX,worldY,delta,containerWidth:rect.width,containerHeight:rect.height,backgroundSizeBefore:30 * prev.k,backgroundSizeAfter:30 * newScale},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'ZOOM-CURSOR'})});
                // #endregion
                
                return { x: newX, y: newY, k: newScale };
            });
        };

        // Add wheel event listener with { passive: false } to allow preventDefault
        container.addEventListener('wheel', handleWheel, { passive: false });
        
        return () => {
            container.removeEventListener('wheel', handleWheel);
        };
    }, [difficultyDialog]);

    const handleMouseDown = (e) => {
        // #region agent log
        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleMouseDown',message:'Container mousedown event',data:{button:e.button,targetTag:e.target.tagName,targetClassName:e.target.className,clientX:e.clientX,clientY:e.clientY,isRightClick:e.button===2},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2'})});
        // #endregion
        if (e.button !== 0) return; // Only handle left mouse button
        if (difficultyDialog) return; // Disable panning when difficulty dialog is open
        setIsDragging(true); 
        setStartPan({ x: e.clientX - transform.x, y: e.clientY - transform.y }); 
    };
    const handleMouseMove = (e) => { 
        if (!isDragging) return; 
        e.preventDefault(); 
        setTransform(prev => {
            const newX = e.clientX - startPan.x;
            const newY = e.clientY - startPan.y;
            // #region agent log
            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleMouseMove',message:'Pan transform update',data:{prevX:prev.x,prevY:prev.y,newX,newY,scale:prev.k,layoutWidth:layout.width,layoutHeight:layout.height,clientX:e.clientX,clientY:e.clientY,startPanX:startPan.x,startPanY:startPan.y},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H3,H5'})});
            // #endregion
            return { ...prev, x: newX, y: newY };
        });
    };
    const handleMouseUp = () => setIsDragging(false);

    const handleNodeContextMenu = (e, node) => {
        // #region agent log
        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleNodeContextMenu',message:'Context menu handler called',data:{nodeId:node.id,nodeType:node.type,nodeName:node.name,clientX:e.clientX,clientY:e.clientY,targetTag:e.target.tagName,targetClassName:e.target.className},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
        // #endregion
        // Only show context menu for Habit and Sub-Skill nodes
        if (node.type !== 'Habit' && node.type !== 'Sub-Skill') {
            // #region agent log
            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleNodeContextMenu',message:'Context menu rejected - wrong node type',data:{nodeType:node.type},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
            // #endregion
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        // #region agent log
        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleNodeContextMenu',message:'Setting context menu state',data:{nodeId:node.id,positionX:e.clientX,positionY:e.clientY,pageX:e.pageX,pageY:e.pageY},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
        // #endregion
        // Use clientX/Y for fixed positioning (viewport coordinates)
        // Position menu to the LEFT of cursor, slightly above
        const cursorOffsetX = -220; // Horizontal: negative = left (position menu left of cursor)
        const cursorOffsetY = -60; // Vertical: negative = up, positive = down
        setContextMenu({
            node: node,
            position: { x: e.clientX + cursorOffsetX, y: e.clientY + cursorOffsetY }
        });
    };

    const handleCloseContextMenu = () => {
        setContextMenu(null);
    };

    const handleAskQuestion = () => {
        if (!contextMenu) return;
        setQuestionDialog(contextMenu.node);
        setContextMenu(null);
    };

    const handleAdjustDifficulty = () => {
        if (!contextMenu) return;
        setDifficultyDialog(contextMenu.node);
        setContextMenu(null);
    };

    const handleQuestionAnswered = () => {
        // Question answered - no tree updates needed
        // Dialog will be closed by user
    };

    const handleDifficultyAdjusted = async (data) => {
        // Track which node was adjusted (like HTML version)
        if (difficultyDialog) {
            setLastAdjustedNodeId(difficultyDialog.id);
        }
        
        console.log(`\n🔄 [DIFFICULTY ADJUSTED] Node: ${difficultyDialog?.id}`);
        console.log(`   Updated node: ${data.updated_node?.id}`);
        console.log(`   New nodes: ${data.new_nodes?.length || 0}`);
        console.log(`   Full skill tree nodes: ${data.skill_tree?.nodes?.length || 0}`);
        
        // Clear cached positions to force fresh Dagre layout on the updated tree
        setNodePositions({});
        setPreviousNodeIds(new Set());
        
        // Reset view like pillar switching does
        setTransform({ x: 500, y: 50, k: 0.8 });
        
        // Refresh skill tree data after difficulty adjustment
        if (data.skill_tree && onSkillTreeUpdate) {
            onSkillTreeUpdate(data.skill_tree);
            // Position restoration will handle layout stability
        } else {
            // #region agent log  
            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleDifficultyAdjusted:fallback',message:'Using fallback reload',data:{reason:'No skill_tree in response or no update handler'},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
            // #endregion
            // Fallback: reload from backend
            const userId = characterSheet?.user_id || 'user_01';
            try {
                const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
                const res = await fetch(`${backend}/api/profile/${userId}`);
                if (res.ok) {
                    const profileData = await res.json();
                    if (profileData.skill_tree && onSkillTreeUpdate) {
                        onSkillTreeUpdate(profileData.skill_tree);
                    }
                }
            } catch (error) {
                console.error('Error reloading skill tree:', error);
            }
        }
    };
    
    // #region agent log
    React.useEffect(() => {
        const container = containerRef.current;
        if (container) {
            const rect = container.getBoundingClientRect();
            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:container-mount',message:'Container mounted dimensions',data:{containerWidth:rect.width,containerHeight:rect.height,hasOverflowAuto:container.classList.contains('overflow-auto'),transformX:transform.x,transformY:transform.y,transformK:transform.k,layoutWidth:layout.width,layoutHeight:layout.height},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H5'})});
        }
    }, [transform, layout.width, layout.height]);
    // #endregion
    
    return (
            <div 
                ref={containerRef}
                className="w-full h-full relative bg-[#f0f9ff] border-t-4 border-blue-900/10 overflow-auto cursor-grab active:cursor-grabbing select-none"
                onMouseDown={handleMouseDown} 
                onMouseMove={handleMouseMove} 
                onMouseUp={handleMouseUp} 
                onMouseLeave={handleMouseUp}
                onContextMenu={(e) => {
                    // #region agent log
                    safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:container-contextmenu',message:'Container context menu event',data:{targetTag:e.target.tagName,targetClassName:e.target.className,clientX:e.clientX,clientY:e.clientY},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2'})});
                    // #endregion
                    // Only prevent default if not clicking on a node (let node handler handle it)
                    const isNode = e.target.closest('[data-node-id]');
                    if (!isNode) {
                        e.preventDefault();
                    }
                }}
                style={{ overscrollBehavior: 'none' }}
            >
                <div 
                    className="absolute inset-0 pointer-events-none" 
                    style={{ 
                        backgroundImage: 'linear-gradient(#bae6fd 1px, transparent 1px), linear-gradient(90deg, #bae6fd 1px, transparent 1px)', 
                        backgroundSize: `${30 * transform.k}px ${30 * transform.k}px`,
                        backgroundPosition: `${transform.x}px ${transform.y}px`,
                    }}
                />
            <div 
                className={`absolute origin-top-left ${!isDragging ? 'transition-transform duration-75 ease-out' : ''}`}
                style={{ 
                    transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`, 
                    width: layout.width, 
                    height: layout.height,
                    position: 'relative'
                }}
                ref={(el) => {
                    if (el) {
                        // #region agent log
                        const rect = el.getBoundingClientRect();
                        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:canvas-div',message:'Canvas div dimensions and transform',data:{transformX:transform.x,transformY:transform.y,transformK:transform.k,styleWidth:layout.width,styleHeight:layout.height,boundingWidth:rect.width,boundingHeight:rect.height,boundingLeft:rect.left,boundingTop:rect.top,backgroundSizeScaled:30 * transform.k,isDragging,hasTransition:!isDragging},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H3,H4'})});
                        // #endregion
                    }
                }}
            >
                <svg 
                    className="absolute inset-0 pointer-events-none"
                    style={{
                        width: '100%',
                        height: '100%',
                        top: 0,
                        left: 0,
                        overflow: 'visible'
                    }}
                    width={layout.width}
                    height={layout.height}
                >
                    {layout.edges.map(e => (
                        <path key={e.id} d={e.d} stroke="#3b82f6" strokeWidth="2" fill="none" strokeOpacity="0.4" />
                    ))}
                </svg>
                {layout.nodes.map(node => {
                    // #region agent log
                    if (node.type === 'Habit' || node.type === 'Sub-Skill') {
                        safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:node-render',message:'Rendering node with context menu handler',data:{nodeId:node.id,nodeType:node.type,nodeName:node.name,nodeX:node.x,nodeY:node.y},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
                    }
                    // #endregion
                    return (
                    <div 
                        key={node.id}
                        data-node-id={node.id}
                        className="absolute flex flex-col items-center justify-center cursor-pointer z-10 hover:z-50"
                        style={{ 
                            left: node.x + 'px', 
                            top: node.y + 'px',
                            transform: 'translate(-50%, -50%)',
                            transition: 'all 0.3s ease'
                        }} 
                        onMouseEnter={() => setHoveredNodeId(node.id)} 
                        onMouseLeave={() => setHoveredNodeId(null)}
                        onContextMenu={(e) => {
                            // #region agent log
                            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:node-contextmenu-event',message:'onContextMenu event fired on node',data:{nodeId:node.id,nodeType:node.type,clientX:e.clientX,clientY:e.clientY,defaultPrevented:e.defaultPrevented},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H3'})});
                            // #endregion
                            handleNodeContextMenu(e, node);
                        }}
                        onMouseDown={(e) => {
                            // #region agent log
                            safeIngest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:node-mousedown',message:'Node mousedown event',data:{nodeId:node.id,nodeType:node.type,button:e.button,isRightClick:e.button===2,clientX:e.clientX,clientY:e.clientY},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2'})});
                            // #endregion
                            if (e.button === 2) {
                                // Right click - stop propagation to prevent container handler
                                e.stopPropagation();
                            }
                        }}
                    >
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
                    );
                })}
            </div>
            <div className="absolute bottom-4 right-4 flex flex-col gap-2 pointer-events-auto shadow-lg bg-white/50 backdrop-blur-sm p-1 rounded-lg border border-blue-200">
                <button onClick={() => setTransform(p => ({...p, k: p.k + 0.2}))} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Plus size={20} /></button>
                <button onClick={() => setTransform(p => ({...p, k: p.k - 0.2}))} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Minus size={20} /></button>
                <button onClick={() => setTransform({x:0, y:0, k:0.8})} className="bg-white p-2 rounded hover:bg-blue-50 text-blue-600 shadow-sm border border-blue-100"><Maximize size={20} /></button>
            </div>

            {/* Context Menu */}
            {contextMenu && (
                <NodeContextMenu
                    node={contextMenu.node}
                    position={contextMenu.position}
                    onClose={handleCloseContextMenu}
                    onAskQuestion={handleAskQuestion}
                    onAdjustDifficulty={handleAdjustDifficulty}
                />
            )}

            {/* Question Dialog */}
            {questionDialog && (
                <NodeQuestionDialog
                    node={questionDialog}
                    userId={characterSheet?.user_id}
                    onClose={() => setQuestionDialog(null)}
                    onQuestionAnswered={handleQuestionAnswered}
                />
            )}

            {/* Difficulty Adjustment Dialog */}
            {difficultyDialog && (
                <NodeDifficultyDialog
                    node={difficultyDialog}
                    userId={characterSheet?.user_id}
                    onClose={() => setDifficultyDialog(null)}
                    onDifficultyAdjusted={handleDifficultyAdjusted}
                />
            )}
        </div>
    );
};

export default TreeVisualizer;