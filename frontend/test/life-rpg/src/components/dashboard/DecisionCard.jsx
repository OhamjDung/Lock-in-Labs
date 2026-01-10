import React, { useState } from 'react';
import { ArrowRight, ArrowUp, ArrowDown, Minus, AlertCircle, CheckCircle2, FileText, Calendar } from 'lucide-react';

/**
 * DecisionCard - "Evidence Locker" UI for Explainable AI Decisions
 * 
 * Displays a decision with:
 * - Diff view: old_value → new_value (with colored arrow)
 * - Contributing factors grid
 * - Hover tooltips showing citation evidence
 * - Verification badges (verified/unverified citations)
 */
export default function DecisionCard({ decision, onCitationClick }) {
  const [hoveredFactor, setHoveredFactor] = useState(null);

  if (!decision) return null;

  const {
    target,
    old_value,
    new_value,
    decision_type,
    confidence_score,
    explanation,
    contributing_factors = [],
  } = decision;

  // Determine arrow and color based on decision type
  const getDecisionDisplay = () => {
    switch (decision_type) {
      case 'INCREASE_INTENSITY':
        return { arrow: <ArrowUp size={20} />, color: 'text-green-700', bg: 'bg-green-50', border: 'border-green-300' };
      case 'DECREASE_INTENSITY':
        return { arrow: <ArrowDown size={20} />, color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-300' };
      case 'MAINTAIN':
        return { arrow: <Minus size={20} />, color: 'text-stone-600', bg: 'bg-stone-50', border: 'border-stone-300' };
      case 'CHANGE_STRATEGY':
        return { arrow: <ArrowRight size={20} />, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-300' };
      default:
        return { arrow: <ArrowRight size={20} />, color: 'text-stone-600', bg: 'bg-stone-50', border: 'border-stone-300' };
    }
  };

  const display = getDecisionDisplay();
  
  // Format target for display
  const targetDisplay = target.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  return (
    <div className="bg-[#e8dcc5] border-2 border-[#d4c5a9] rounded-sm shadow-[0_8px_30px_rgba(0,0,0,0.3)] relative overflow-hidden -rotate-1 hover:rotate-0 transition-all duration-300 group">
      {/* Texture overlay */}
      <div className="absolute inset-0 opacity-[0.06] pointer-events-none bg-repeat mix-blend-multiply" 
           style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
      
      <div className="relative z-10 p-6">
        {/* Header: Diff View */}
        <div className="mb-6 pb-4 border-b-2 border-[#d4c5a9]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full ${display.bg} ${display.border} border-2 flex items-center justify-center ${display.color}`}>
                {display.arrow}
              </div>
              <div>
                <h3 className="text-lg font-black text-stone-900 font-serif uppercase tracking-tight">
                  {targetDisplay}
                </h3>
                <div className="text-[10px] font-mono text-stone-600 mt-0.5">DECISION #{decision_type}</div>
              </div>
            </div>
            
            {/* Confidence Score */}
            <div className="flex items-center gap-2">
              <div className="text-xs font-mono text-stone-600">CONFIDENCE</div>
              <div className="px-2 py-1 bg-stone-800 text-white text-xs font-bold rounded">
                {Math.round(confidence_score * 100)}%
              </div>
            </div>
          </div>
          
          {/* Value Diff */}
          <div className="flex items-center justify-center gap-4 mt-4">
            <div className="px-4 py-2 bg-stone-100 border-2 border-stone-300 rounded font-mono text-stone-800 font-bold text-lg">
              {old_value}
            </div>
            <div className={`${display.color} flex items-center`}>
              {display.arrow}
            </div>
            <div className={`px-4 py-2 ${display.bg} ${display.border} border-2 rounded font-mono ${display.color} font-bold text-lg`}>
              {new_value}
            </div>
          </div>
        </div>

        {/* Explanation */}
        <div className="mb-6 p-4 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm">
          <div className="text-xs font-mono text-stone-600 mb-2 uppercase tracking-wider">RATIONALE</div>
          <p className="text-sm text-stone-800 font-serif leading-relaxed italic">{explanation}</p>
        </div>

        {/* Contributing Factors Grid - "The Evidence Locker" */}
        <div className="mb-4">
          <div className="text-xs font-mono text-stone-600 mb-3 uppercase tracking-wider flex items-center gap-2">
            <FileText size={14} />
            CONTRIBUTING FACTORS ({contributing_factors.length})
          </div>
          
          <div className="space-y-3">
            {contributing_factors.map((factor, idx) => {
              const isVerified = factor.is_verified !== false; // Default to true if not specified
              const dateCorrected = factor.date_corrected === true;
              const verificationScore = factor.verification_score || 0;
              
              // Determine icon and color based on weight
              const weightConfig = {
                positive: { icon: <CheckCircle2 size={14} />, color: 'text-green-700', bg: 'bg-green-50', border: 'border-green-300' },
                negative: { icon: <AlertCircle size={14} />, color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-300' },
                neutral: { icon: <FileText size={14} />, color: 'text-stone-600', bg: 'bg-stone-50', border: 'border-stone-300' },
              };
              
              const factorStyle = weightConfig[factor.weight] || weightConfig.neutral;
              
              return (
                <div
                  key={idx}
                  className={`relative p-4 border-2 ${factorStyle.border} rounded-sm ${factorStyle.bg} transition-all duration-200 cursor-pointer hover:shadow-md hover:scale-[1.02]`}
                  onMouseEnter={() => setHoveredFactor(idx)}
                  onMouseLeave={() => setHoveredFactor(null)}
                  onClick={() => {
                    if (onCitationClick && factor.verified_date && factor.citation_text) {
                      onCitationClick({
                        date: factor.verified_date || factor.citation_date,
                        text: factor.citation_text,
                        factor: factor.factor,
                      });
                    }
                  }}
                >
                  {/* Factor Header */}
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 flex-1">
                      <div className={`${factorStyle.color} flex-shrink-0`}>
                        {factorStyle.icon}
                      </div>
                      <div className="flex-1">
                        <div className="font-bold text-stone-900 text-sm flex items-center gap-2">
                          {factor.factor}
                          {factor.factor_type && (
                            <span className="text-[10px] font-mono text-stone-500 font-normal px-1.5 py-0.5 bg-stone-200 rounded">
                              {factor.factor_type}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-stone-700 mt-1 font-serif italic">
                          {factor.description}
                        </div>
                      </div>
                    </div>
                    
                    {/* Verification Badge */}
                    <div className="flex-shrink-0 ml-3">
                      {isVerified ? (
                        <div className="flex items-center gap-1 px-2 py-1 bg-green-100 border border-green-300 rounded text-[10px] font-mono text-green-800">
                          <CheckCircle2 size={10} />
                          VERIFIED
                          {dateCorrected && (
                            <span className="ml-1 text-[9px] text-green-600" title="Date was corrected">
                              (CORRECTED)
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 px-2 py-1 bg-red-100 border border-red-300 rounded text-[10px] font-mono text-red-800">
                          <AlertCircle size={10} />
                          UNVERIFIED
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Citation Info */}
                  {(factor.verified_date || factor.citation_date) && (
                    <div className="mt-2 pt-2 border-t border-stone-300 flex items-center gap-2 text-[10px] font-mono text-stone-600">
                      <Calendar size={10} />
                      <span className="font-bold">
                        {factor.verified_date || factor.citation_date}
                      </span>
                      {dateCorrected && factor.original_citation_date && (
                        <span className="text-stone-400 line-through">
                          (was {factor.original_citation_date})
                        </span>
                      )}
                      {verificationScore > 0 && (
                        <span className="ml-auto text-stone-500">
                          {Math.round(verificationScore * 100)}% match
                        </span>
                      )}
                    </div>
                  )}

                  {/* Hover Tooltip - "The Evidence" */}
                  {hoveredFactor === idx && factor.citation_text && (
                    <div className="absolute z-50 top-full left-0 right-0 mt-2 p-4 bg-stone-900 text-stone-100 rounded-sm shadow-2xl border-2 border-stone-700 animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="text-[10px] font-mono text-stone-400 mb-2 uppercase tracking-wider">EVIDENCE</div>
                      <div className="text-sm font-serif leading-relaxed mb-2">
                        "{factor.citation_text}"
                      </div>
                      {factor.verified_content && factor.verified_content !== factor.citation_text && (
                        <div className="mt-2 pt-2 border-t border-stone-700">
                          <div className="text-[10px] font-mono text-stone-400 mb-1">FULL CONTEXT</div>
                          <div className="text-xs text-stone-300 font-serif italic">
                            {factor.verified_content}
                          </div>
                        </div>
                      )}
                      <div className="mt-3 pt-2 border-t border-stone-700 text-[10px] font-mono text-stone-400">
                        Click to view full log entry
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer Stats */}
        <div className="mt-4 pt-4 border-t border-[#d4c5a9] flex items-center justify-between text-[10px] font-mono text-stone-600">
          <div>
            VERIFIED: {contributing_factors.filter(f => f.is_verified !== false).length} / {contributing_factors.length}
          </div>
          {decision.date_corrected_count > 0 && (
            <div className="text-yellow-700">
              {decision.date_corrected_count} DATE(S) CORRECTED
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
