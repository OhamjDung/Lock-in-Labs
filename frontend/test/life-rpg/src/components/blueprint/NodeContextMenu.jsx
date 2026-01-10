import React, { useEffect, useRef, useState } from 'react';
import { HelpCircle, TrendingUp, TrendingDown } from 'lucide-react';

const NodeContextMenu = ({ node, position, onClose, onAskQuestion, onAdjustDifficulty }) => {
    const menuRef = useRef(null);
    const [adjustedPosition, setAdjustedPosition] = useState({ x: position.x, y: position.y });

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                onClose();
            }
        };

        const handleEscape = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };

        // Add listeners
        document.addEventListener('mousedown', handleClickOutside);
        document.addEventListener('keydown', handleEscape);

        // Position menu (offset already applied in TreeVisualizer)
        // Only adjust for viewport overflow once on mount
        const adjustPosition = () => {
            if (!menuRef.current) return;
            
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            const margin = Math.max(10, viewportWidth * 0.01);
            
            // Use position as-is (offset already applied in TreeVisualizer)
            let finalX = position.x;
            let finalY = position.y;
            
            // Temporarily position to measure dimensions
            menuRef.current.style.left = `${finalX}px`;
            menuRef.current.style.top = `${finalY}px`;
            menuRef.current.style.visibility = 'hidden';
            
            // Force layout calculation
            menuRef.current.offsetHeight;
            
            // Get menu dimensions
            const rect = menuRef.current.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            
            menuRef.current.style.visibility = 'visible';
            
            // Adjust for viewport overflow - handle both positive and negative offsets
            const zoomControlArea = 100; // Space to reserve for zoom controls in bottom-right (bottom-4 right-4 = ~16px + padding)
            
            // Define zoom control area boundaries (bottom-right corner)
            const zoomControlRight = viewportWidth;
            const zoomControlLeft = viewportWidth - zoomControlArea;
            const zoomControlBottom = viewportHeight;
            const zoomControlTop = viewportHeight - zoomControlArea;
            
            // Check if menu would overlap zoom control area (regardless of overflow)
            const menuRight = finalX + width;
            const menuBottom = finalY + height;
            const menuLeft = finalX;
            const menuTop = finalY;
            
            const overlapsZoomControls = 
                menuRight > zoomControlLeft && 
                menuLeft < zoomControlRight && 
                menuBottom > zoomControlTop && 
                menuTop < zoomControlBottom;
            
            if (overlapsZoomControls) {
                // Position menu above zoom controls, or to the left if that's not possible
                if (viewportHeight - zoomControlTop - height - margin >= margin) {
                    // Position above zoom controls
                    finalY = zoomControlTop - height - margin;
                    // If still overlapping horizontally, move left
                    if (menuRight > zoomControlLeft) {
                        finalX = zoomControlLeft - width - margin;
                    }
                } else {
                    // Not enough space above, position to the left of zoom controls
                    finalX = zoomControlLeft - width - margin;
                    // If still overlapping vertically, move up
                    if (menuBottom > zoomControlTop) {
                        finalY = zoomControlTop - height - margin;
                    }
                }
            }
            
            // Check right edge overflow
            if (finalX + width > viewportWidth - margin) {
                finalX = viewportWidth - width - margin;
            }
            // Check left edge overflow (important for large negative offsets like -400px)
            if (finalX < margin) {
                finalX = margin;
            }
            // Check bottom edge overflow
            if (finalY + height > viewportHeight - margin) {
                finalY = viewportHeight - height - margin;
            }
            // Check top edge overflow
            if (finalY < margin) {
                finalY = margin;
            }
            
            setAdjustedPosition({ x: finalX, y: finalY });
        };

        // Adjust position once after render (only for overflow, not offset)
        const timeoutId = setTimeout(adjustPosition, 0);

        return () => {
            clearTimeout(timeoutId);
            document.removeEventListener('mousedown', handleClickOutside);
            document.removeEventListener('keydown', handleEscape);
        };
    }, [position.x, position.y, onClose]);

    // Initialize position when menu first appears (offset already applied in TreeVisualizer)
    useEffect(() => {
        setAdjustedPosition({ x: position.x, y: position.y });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Only run once on mount

    return (
        <div
            ref={menuRef}
            className="fixed z-[100] bg-white rounded-lg shadow-xl border border-slate-200 py-1 min-w-[200px] pointer-events-auto"
            style={{
                left: `${adjustedPosition.x}px`,
                top: `${adjustedPosition.y}px`,
                margin: 0,
            }}
        >
            <div className="px-3 py-2 border-b border-slate-100">
                <div className="font-semibold text-sm text-slate-800 truncate">{node.name}</div>
                <div className="text-xs text-slate-500 capitalize">{node.type}</div>
            </div>
            
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onClose();
                    onAskQuestion();
                }}
                className="w-full px-4 py-2.5 text-left hover:bg-blue-50 transition-colors flex items-center gap-3 text-sm text-slate-700"
            >
                <HelpCircle size={18} className="text-blue-500" />
                <span>Ask Question</span>
            </button>
            
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onClose();
                    onAdjustDifficulty();
                }}
                className="w-full px-4 py-2.5 text-left hover:bg-blue-50 transition-colors flex items-center gap-3 text-sm text-slate-700"
            >
                <TrendingUp size={18} className="text-green-500" />
                <span>Adjust Difficulty</span>
            </button>
        </div>
    );
};

export default NodeContextMenu;
