import React, { useState, useEffect, useRef } from 'react';

const TypewriterText = ({ text, speed = 25, onComplete, onScroll }) => {
  const [displayedText, setDisplayedText] = useState('');
  const intervalRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  const onScrollRef = useRef(onScroll);
  const textRef = useRef(text);

  // Update refs when props change
  useEffect(() => {
    onCompleteRef.current = onComplete;
    onScrollRef.current = onScroll;
    textRef.current = text;
  }, [onComplete, onScroll, text]);

  useEffect(() => {
    // Reset when text changes
    setDisplayedText('');
    
    if (!text || text.length === 0) {
        if(onCompleteRef.current) onCompleteRef.current();
        return;
    }

    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    let index = 0;
    intervalRef.current = setInterval(() => {
      if (index < textRef.current.length) {
        // Use substring to get text from start to current index (inclusive)
        setDisplayedText(textRef.current.substring(0, index + 1));
        index++;
        
        // Trigger scroll check after every few characters
        if (index % 5 === 0 && onScrollRef.current) {
          onScrollRef.current();
        }
      } else {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        if (onCompleteRef.current) {
          onCompleteRef.current();
        }
        // Final scroll when complete
        if (onScrollRef.current) {
          onScrollRef.current();
        }
      }
    }, speed);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [text, speed]);

  return <span>{displayedText}</span>;
};

export default TypewriterText;