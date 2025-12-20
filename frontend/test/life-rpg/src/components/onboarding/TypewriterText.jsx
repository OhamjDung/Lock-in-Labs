import React, { useState, useEffect, useRef } from 'react';

export default function TypewriterText({ text, speed = 30, onComplete }) {
  const [index, setIndex] = useState(0);
  const hasCompletedRef = useRef(false);

  useEffect(() => {
    setIndex(0);
    hasCompletedRef.current = false;
  }, [text]);

  useEffect(() => {
    if (index >= text.length) {
      if (!hasCompletedRef.current && onComplete) {
        hasCompletedRef.current = true;
        console.debug('[TypewriterText] completed text:', text.slice(0, 40), '...');
        onComplete();
      }
      return;
    }

    const timeoutId = setTimeout(() => {
      setIndex((prev) => prev + 1);
    }, speed);

    return () => clearTimeout(timeoutId);
  }, [index, text, speed, onComplete]);

  const displayedText = text.slice(0, index);
  return <span className="whitespace-pre-wrap">{displayedText}</span>;
}
