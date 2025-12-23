import React, { useEffect, useRef, useState } from 'react';

export default function GeminiMapView() {
  const containerRef = useRef(null);
  const iframeRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Only create iframe once - if it already exists, don't recreate
    if (containerRef.current && !isLoaded && !iframeRef.current) {
      // Create iframe to load the map
      const iframe = document.createElement('iframe');
      iframe.src = '/gemini-map.html';
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      iframe.style.background = '#0a100a'; // Match black/green theme
      iframe.title = 'Gemini Chat Map';
      
      // Store reference to prevent recreation
      iframeRef.current = iframe;
      containerRef.current.appendChild(iframe);
      setIsLoaded(true);
    }
  }, [isLoaded]);

  return (
    <div 
      ref={containerRef}
      className="w-full h-full relative"
      style={{ 
        background: '#0a100a', // Match black/green theme
        overflow: 'hidden',
        fontFamily: 'Inter, sans-serif'
      }}
    >
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center text-[#39ff14] font-mono">
          Loading Gemini Map...
        </div>
      )}
    </div>
  );
}

