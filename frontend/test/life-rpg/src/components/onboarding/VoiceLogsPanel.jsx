import React from 'react';
import { Mic } from 'lucide-react';

const VoiceLogsPanel = ({ isRecording, onToggleRecording }) => {
  return (
    <div className="flex flex-col gap-2 pt-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleRecording}
          className={`relative w-12 h-12 rounded-full flex items-center justify-center border border-stone-900 bg-stone-900 text-[#e8dcc5] shadow-lg transition-transform ${
            isRecording ? "scale-105" : ""
          }`}
        >
          <Mic size={20} className={isRecording ? "text-red-400" : "text-[#e8dcc5]"} />
          {isRecording && (
            <span className="absolute -top-2 -right-2 h-2 w-2 rounded-full bg-red-500 animate-ping" />
          )}
        </button>
        <div className="flex flex-col">
          <span className="text-[11px] font-mono text-stone-700 uppercase tracking-wide">
            {isRecording ? "Recording..." : "Hold to record"}
          </span>
          <span className="text-[11px] text-stone-600">
            Press the mic instead of typing. Audio streams live inside this case file.
          </span>
        </div>
      </div>
      <div className="text-[10px] text-stone-500">
        (Voice Logs plays the Architect's replies out loud using the /ws/voice channel.)
      </div>
    </div>
  );
};

export default VoiceLogsPanel;