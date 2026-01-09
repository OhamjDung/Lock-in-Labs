import React, { useState, useEffect, useMemo } from 'react';
import { Plus, Minus, Maximize, Star, Diamond, Circle } from 'lucide-react';
import { skillTreeJson } from '../../data/mockData';
import dagre from 'dagre'; 

const TreeVisualizer = ({ pillar, skillTree, characterSheet }) => {
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
    const [isDragging, setIsDragging] = useState(false);
    const [startPan, setStartPan] = useState({ x: 0, y: 0 });
    const [hoveredNodeId, setHoveredNodeId] = useState(null);

    const layout = useMemo(() => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:layout',message:'Layout calculation started',data:{pillar, hasSkillTree: !!skillTree, nodesCount: skillTree?.nodes?.length || 0, nodeTypes: skillTree?.nodes?.reduce((acc, n) => { acc[n.type] = (acc[n.type] || 0) + 1; return acc; }, {}) || {}},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H4-H5'})}).catch(()=>{});
        // #endregion
        
        const nodesSource = (skillTree && skillTree.nodes && skillTree.nodes.length > 0) ? skillTree.nodes : skillTreeJson.nodes;
        const pillarNodes = nodesSource.filter(n => n.pillar === pillar);
        
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:filter',message:'After filtering by pillar',data:{pillar, totalNodes: nodesSource.length, pillarNodesCount: pillarNodes.length},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H5'})}).catch(()=>{});
        // #endregion
        
        if (pillarNodes.length === 0) {
            return { nodes: [], edges: [], width: 800, height: 800 };
        }

        // Initialize Dagre Graph (same as skill_tree_viewer.html)
        const g = new dagre.graphlib.Graph();
        g.setGraph({ 
            rankdir: 'BT', // Bottom-to-Top (Habits at bottom, Goal at top)
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

        // Add Edges (Reverse Prerequisite Logic for BT layout)
        // If A requires B, Arrow goes B -> A (B is prerequisite, A depends on B)
        pillarNodes.forEach(node => {
            if (node.prerequisites && node.prerequisites.length > 0) {
                node.prerequisites.forEach(prereqId => {
                    // Check if prereq exists in this pillar view
                    const prereqNode = pillarNodes.find(n => n.id === prereqId);
                    if (prereqNode) {
                        // Edge from prerequisite to dependent node
                        g.setEdge(prereqId, node.id);
                    }
                });
            }
        });

        // Calculate Layout
        try {
            dagre.layout(g);
        } catch (e) {
            console.error('Dagre layout error:', e);
            return { nodes: [], edges: [], width: 800 };
        }

        // Process nodes with progress data and positions from Dagre
        const processedNodes = [];
        g.nodes().forEach(v => {
            const n = g.node(v);
            const node = n.original;
            
            // Get progress data for habits (same as before)
            let progressPercent = 0;
            let status = 'LOCKED';
            let completed = 0;
            let required = 1;
            
            if (node.type === 'Habit' && characterSheet && characterSheet.habit_progress) {
                const progress = characterSheet.habit_progress[node.id];
                if (progress) {
                    completed = progress.completed_total || 0;
                    required = node.required_completions || 1;
                    progressPercent = Math.min(100, Math.max(0, (completed / required) * 100));
                    status = progress.status === 'ACTIVE' ? 'ACTIVE' : 'LOCKED';
                }
            }
            
            processedNodes.push({
                ...node,
                x: n.x,
                y: n.y,
                progressPercent,
                status,
                completed,
                required
            });
        });

        // Process edges from Dagre
        const processedEdges = [];
        g.edges().forEach(e => {
            const edge = g.edge(e);
            const points = edge.points || [];
            
            if (points.length < 2) return;
            
            // Convert points to path format - use smooth curves between points
            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                if (i === points.length - 1) {
                    // Last point - straight line to target
                    d += ` L ${points[i].x} ${points[i].y}`;
                } else {
                    // Use quadratic bezier for smooth curves (same as skill_tree_viewer.html)
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

        // Calculate total width and height for canvas
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        g.nodes().forEach(v => {
            const n = g.node(v);
            minX = Math.min(minX, n.x - n.width/2);
            minY = Math.min(minY, n.y - n.height/2);
            maxX = Math.max(maxX, n.x + n.width/2);
            maxY = Math.max(maxY, n.y + n.height/2);
        });
        
        const padding = 100;
        const totalWidth = Math.max(2000, maxX + padding);
        const totalHeight = Math.max(2000, maxY + padding);

        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:result',message:'Layout calculation complete',data:{pillar, processedNodesCount: processedNodes.length, processedEdgesCount: processedEdges.length, totalWidth, totalHeight, nodeNames: processedNodes.map(n => n.name)},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H5'})}).catch(()=>{});
        // #endregion
        
        return { nodes: processedNodes, edges: processedEdges, width: totalWidth, height: totalHeight };
      }, [pillar, skillTree, characterSheet]);

    useEffect(() => { setTransform({ x: 0, y: 0, k: 0.8 }); }, [pillar]);

    // Use ref for wheel event to make it non-passive
    const containerRef = React.useRef(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

            const handleWheel = (e) => {
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
                fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleWheel',message:'Zoom transform update - cursor-focused',data:{prevScale:prev.k,newScale,prevX:prev.x,prevY:prev.y,newX,newY,mouseX,mouseY,worldX,worldY,delta,containerWidth:rect.width,containerHeight:rect.height,backgroundSizeBefore:30 * prev.k,backgroundSizeAfter:30 * newScale},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'ZOOM-CURSOR'})}).catch(()=>{});
                // #endregion
                
                return { x: newX, y: newY, k: newScale };
            });
        };

        // Add wheel event listener with { passive: false } to allow preventDefault
        container.addEventListener('wheel', handleWheel, { passive: false });
        
        return () => {
            container.removeEventListener('wheel', handleWheel);
        };
    }, []);

    const handleMouseDown = (e) => { 
        if (e.button !== 0) return; // Only handle left mouse button
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
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:handleMouseMove',message:'Pan transform update',data:{prevX:prev.x,prevY:prev.y,newX,newY,scale:prev.k,layoutWidth:layout.width,layoutHeight:layout.height,clientX:e.clientX,clientY:e.clientY,startPanX:startPan.x,startPanY:startPan.y},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H3,H5'})}).catch(()=>{});
            // #endregion
            return { ...prev, x: newX, y: newY };
        });
    };
    const handleMouseUp = () => setIsDragging(false);
    
    // #region agent log
    React.useEffect(() => {
        const container = containerRef.current;
        if (container) {
            const rect = container.getBoundingClientRect();
            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:container-mount',message:'Container mounted dimensions',data:{containerWidth:rect.width,containerHeight:rect.height,hasOverflowAuto:container.classList.contains('overflow-auto'),transformX:transform.x,transformY:transform.y,transformK:transform.k,layoutWidth:layout.width,layoutHeight:layout.height},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H5'})}).catch(()=>{});
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
            style={{ overscrollBehavior: 'none' }}
        >
            <div 
                className={`absolute origin-top-left ${!isDragging ? 'transition-transform duration-75 ease-out' : ''}`}
                style={{ 
                    transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`, 
                    width: Math.max(layout.width || 2000, 2000), 
                    height: Math.max(layout.height || 2000, 2000),
                    position: 'relative'
                }}
                ref={(el) => {
                    if (el) {
                        // #region agent log
                        const rect = el.getBoundingClientRect();
                        fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:canvas-div',message:'Canvas div dimensions and transform',data:{transformX:transform.x,transformY:transform.y,transformK:transform.k,styleWidth:Math.max(layout.width || 2000, 2000),styleHeight:Math.max(layout.height || 2000, 2000),boundingWidth:rect.width,boundingHeight:rect.height,boundingLeft:rect.left,boundingTop:rect.top,backgroundSizeScaled:30 * transform.k,isDragging,hasTransition:!isDragging},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1,H2,H3,H4'})}).catch(()=>{});
                        // #endregion
                    }
                }}
            >
                <div 
                    className="absolute pointer-events-none" 
                    style={{ 
                        top: `-${(Math.max(layout.width || 2000, 2000))}px`,
                        left: `-${(Math.max(layout.width || 2000, 2000))}px`,
                        width: `${(Math.max(layout.width || 2000, 2000)) * 3}px`,
                        height: `${(Math.max(layout.height || 2000, 2000)) * 3}px`,
                        backgroundImage: 'linear-gradient(#bae6fd 1px, transparent 1px), linear-gradient(90deg, #bae6fd 1px, transparent 1px)', 
                        backgroundSize: `${30 * transform.k}px ${30 * transform.k}px`,
                        backgroundRepeat: 'repeat',
                        backgroundPosition: '0 0',
                        willChange: 'transform'
                    }}
                    ref={(bgEl) => {
                        if (bgEl) {
                            // #region agent log
                            const rect = bgEl.getBoundingClientRect();
                            fetch('http://127.0.0.1:7242/ingest/a5245e3d-b4d2-470b-aedd-e71da8d91edf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'TreeVisualizer.jsx:background-div',message:'Background div dimensions',data:{backgroundWidth:rect.width,backgroundHeight:rect.height,backgroundLeft:rect.left,backgroundTop:rect.top,backgroundSize:30 * transform.k,transformX:transform.x,transformY:transform.y,transformK:transform.k,canvasWidth:layout.width,canvasHeight:layout.height,styleTop:`-${(Math.max(layout.width || 2000, 2000))}px`,styleLeft:`-${(Math.max(layout.width || 2000, 2000))}px`},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H1'})}).catch(()=>{});
                            // #endregion
                        }
                    }}
                ></div>
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                    {layout.edges.map(e => (
                        <path key={e.id} d={e.d} stroke="#3b82f6" strokeWidth="2" fill="none" strokeOpacity="0.4" />
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