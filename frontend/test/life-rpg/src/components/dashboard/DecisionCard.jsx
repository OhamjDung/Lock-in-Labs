import React, { useState } from 'react';
import { ArrowRight, ArrowUp, ArrowDown, Minus, AlertCircle, CheckCircle2, FileText, Calendar, BarChart3, TrendingUp, TrendingDown } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';

/**
 * DecisionCard - "Evidence Locker" UI for Explainable AI Decisions
 * 
 * Displays a decision with:
 * - Diff view: old_value → new_value (with colored arrow)
 * - Contributing factors grid
 * - Always-visible citation evidence inline with each factor
 * - Verification badges (verified/unverified citations)
 */
export default function DecisionCard({ decision, onCitationClick }) {
  const [showGraphs, setShowGraphs] = useState(false);
  
  if (!decision) return null;

  const {
    target,
    old_value,
    new_value,
    decision_type,
    confidence_score,
    explanation,
    contributing_factors = [],
    metadata = {},
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

  // Prepare data for visualizations
  const taskStats = metadata.task_stats || {};
  const trendData = metadata.trend_data || [];
  
  // Chart data: Task completion rates
  const taskCompletionData = Object.entries(taskStats).map(([name, stats]) => ({
    name: name.length > 20 ? name.substring(0, 20) + '...' : name,
    completion: Math.round((stats.completed / stats.total) * 100),
    completed: stats.completed,
    total: stats.total,
    fullName: name,
  }));

  // Chart data: Trend over time
  const trendChartData = trendData.map(d => ({
    date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    rate: Math.round(d.completion_rate),
    completed: d.completed_tasks,
    total: d.total_tasks,
  }));

  // Chart data: Factor weights
  const factorWeightData = contributing_factors.map((f, idx) => ({
    name: f.factor.length > 15 ? f.factor.substring(0, 15) + '...' : f.factor,
    value: f.weight === 'positive' ? 1 : f.weight === 'negative' ? -1 : 0,
    weight: f.weight,
    type: f.factor_type || 'data',
    fullName: f.factor,
  }));

  // Calculate summary statistics
  const avgCompletionRate = taskCompletionData.length > 0
    ? Math.round(taskCompletionData.reduce((sum, d) => sum + d.completion, 0) / taskCompletionData.length)
    : 0;
  
  // Determine trend direction
  let trendDirection = 'stable';
  let trendIcon = <Minus size={12} />;
  if (trendChartData.length >= 2) {
    const firstHalf = trendChartData.slice(0, Math.floor(trendChartData.length / 2));
    const secondHalf = trendChartData.slice(Math.floor(trendChartData.length / 2));
    const firstAvg = firstHalf.reduce((sum, d) => sum + d.rate, 0) / firstHalf.length;
    const secondAvg = secondHalf.reduce((sum, d) => sum + d.rate, 0) / secondHalf.length;
    
    if (secondAvg > firstAvg + 5) {
      trendDirection = 'improving';
      trendIcon = <TrendingUp size={12} />;
    } else if (secondAvg < firstAvg - 5) {
      trendDirection = 'declining';
      trendIcon = <TrendingDown size={12} />;
    }
  }

  const dateRange = trendData.length > 0
    ? {
        start: trendData[0].date,
        end: trendData[trendData.length - 1].date,
      }
    : null;

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

        {/* Explanation with Causal Chain */}
        <div className="mb-6 p-4 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm">
          <div className="text-xs font-mono text-stone-600 mb-2 uppercase tracking-wider">RATIONALE</div>
          <p className="text-sm text-stone-800 font-serif leading-relaxed italic mb-4">{explanation}</p>
          
          {/* Causal Chain Visualization */}
          {contributing_factors.length > 0 && (
            <div className="mt-4 pt-4 border-t border-stone-300">
              <div className="text-xs font-mono text-stone-600 mb-3 uppercase tracking-wider">
                CAUSAL CHAIN
              </div>
              <div className="space-y-2">
                {contributing_factors.map((factor, idx) => {
                  const weightColor = factor.weight === 'positive' ? 'bg-green-600' :
                                     factor.weight === 'negative' ? 'bg-red-600' :
                                     'bg-stone-500';
                  return (
                    <div key={idx}>
                      <div className="flex items-start gap-2 text-xs">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 ${weightColor}`}>
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <div className="font-semibold text-stone-800">{factor.factor}</div>
                          <div className="text-stone-600 italic">{factor.description}</div>
                        </div>
                      </div>
                      {idx < contributing_factors.length - 1 && (
                        <div className="text-stone-400 text-center my-1">↓</div>
                      )}
                    </div>
                  );
                })}
                <div className="flex items-center gap-2 text-xs mt-3 pt-3 border-t border-stone-300">
                  <div className="font-bold text-stone-800">→</div>
                  <div className="flex-1">
                    <div className="font-bold text-stone-900 uppercase">{decision_type.replace('_', ' ')}</div>
                    <div className="text-stone-600">{old_value} → {new_value}</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Summary Statistics */}
        {metadata && (taskStats && Object.keys(taskStats).length > 0 || trendData.length > 0) && (
          <div className="mb-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm text-center">
              <div className="text-[10px] font-mono text-stone-600 uppercase mb-1">Avg Completion</div>
              <div className="text-xl font-bold text-stone-900">{avgCompletionRate}%</div>
              <div className={`text-xs mt-1 flex items-center justify-center gap-1 ${
                trendDirection === 'improving' ? 'text-green-700' :
                trendDirection === 'declining' ? 'text-red-700' :
                'text-stone-600'
              }`}>
                {trendIcon}
                <span className="capitalize">{trendDirection}</span>
              </div>
            </div>
            <div className="p-3 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm text-center">
              <div className="text-[10px] font-mono text-stone-600 uppercase mb-1">Data Points</div>
              <div className="text-xl font-bold text-stone-900">{metadata.recent_reports_count || trendData.length || 0}</div>
              <div className="text-xs text-stone-600 mt-1 font-mono">Last {metadata.analysis_period_days || 7} days</div>
            </div>
            <div className="p-3 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm text-center">
              <div className="text-[10px] font-mono text-stone-600 uppercase mb-1">Analysis Period</div>
              <div className="text-sm font-bold text-stone-900">
                {dateRange ? (
                  <>
                    {new Date(dateRange.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    <span className="text-stone-600 font-normal"> to </span>
                    {new Date(dateRange.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </>
                ) : (
                  'N/A'
                )}
              </div>
            </div>
          </div>
        )}

        {/* Graphs Toggle */}
        {metadata && (taskStats && Object.keys(taskStats).length > 0 || trendData.length > 0) && (
          <div className="mb-4">
            <button
              onClick={() => setShowGraphs(!showGraphs)}
              className="flex items-center gap-2 px-3 py-1.5 bg-stone-800 text-white text-xs font-mono rounded hover:bg-stone-900 transition-colors"
            >
              <BarChart3 size={14} />
              {showGraphs ? 'HIDE' : 'SHOW'} ANALYTICS
            </button>
          </div>
        )}

        {/* Graphs Section */}
        {showGraphs && metadata && (
          <div className="mb-6 p-4 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm space-y-6">
            <div className="text-xs font-mono text-stone-600 mb-4 uppercase tracking-wider">
              DATA VISUALIZATION
            </div>

            {/* Graph 1: Completion Rate Trend */}
            {trendChartData.length > 0 && (
              <div>
                <div className="text-sm font-bold text-stone-800 mb-2 flex items-center gap-2">
                  <TrendingUp size={14} />
                  Completion Rate Trend (Last 7 Days)
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={trendChartData}>
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <Tooltip 
                      formatter={(value, name) => {
                        if (name === 'rate') return [`${value}%`, 'Completion Rate'];
                        return [value, name === 'completed' ? 'Completed Tasks' : 'Total Tasks'];
                      }}
                      labelFormatter={(label) => `Date: ${label}`}
                    />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="rate" 
                      stroke="#8b5cf6" 
                      strokeWidth={2}
                      dot={{ fill: '#8b5cf6', r: 4 }}
                      name="Completion %"
                    />
                    <Line 
                      type="monotone" 
                      dataKey="total" 
                      stroke="#94a3b8" 
                      strokeWidth={1}
                      strokeDasharray="3 3"
                      dot={false}
                      name="Total Tasks"
                    />
                  </LineChart>
                </ResponsiveContainer>
                <div className="text-[10px] text-stone-600 mt-1 font-mono">
                  Solid line: Completion % | Dashed: Total tasks scheduled
                </div>
              </div>
            )}

            {/* Graph 2: Task Completion Comparison */}
            {taskCompletionData.length > 0 && (
              <div>
                <div className="text-sm font-bold text-stone-800 mb-2 flex items-center gap-2">
                  <BarChart3 size={14} />
                  Task Completion Rates
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={taskCompletionData}>
                    <XAxis 
                      dataKey="name" 
                      angle={-45} 
                      textAnchor="end" 
                      height={80}
                      tick={{ fontSize: 9 }}
                    />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <Tooltip 
                      formatter={(value, name, props) => {
                        if (name === 'completion') {
                          return [`${value}%`, 'Completion Rate'];
                        }
                        return [value, name];
                      }}
                      labelFormatter={(label) => {
                        const fullName = taskCompletionData.find(d => d.name === label)?.fullName;
                        return fullName || label;
                      }}
                    />
                    <Bar dataKey="completion">
                      {taskCompletionData.map((entry, index) => {
                        const fillColor = entry.completion >= 80 ? '#10b981' :
                                         entry.completion >= 50 ? '#eab308' :
                                         '#ef4444';
                        return (
                          <Cell 
                            key={`cell-${index}`}
                            fill={fillColor}
                          />
                        );
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="text-[10px] text-stone-600 mt-1 font-mono">
                  Shows completion percentage for each task/habit
                </div>
              </div>
            )}

            {/* Graph 3: Factor Weight Distribution */}
            {factorWeightData.length > 0 && (
              <div>
                <div className="text-sm font-bold text-stone-800 mb-2 flex items-center gap-2">
                  <FileText size={14} />
                  Contributing Factors Impact
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={factorWeightData} layout="vertical">
                    <XAxis type="number" domain={[-1, 1]} tick={{ fontSize: 10 }} />
                    <YAxis 
                      type="category" 
                      dataKey="name" 
                      width={120}
                      tick={{ fontSize: 9 }}
                    />
                    <Tooltip 
                      formatter={(value, name, props) => {
                        const weight = props.payload.weight;
                        return [
                          weight === 'positive' ? 'Positive Impact' : 
                          weight === 'negative' ? 'Negative Impact' : 
                          'Neutral Impact',
                          'Factor Weight'
                        ];
                      }}
                      labelFormatter={(label) => {
                        const fullName = factorWeightData.find(d => d.name === label)?.fullName;
                        return fullName || label;
                      }}
                    />
                    <Bar dataKey="value">
                      {factorWeightData.map((entry, index) => {
                        const fillColor = entry.weight === 'positive' ? '#10b981' :
                                         entry.weight === 'negative' ? '#ef4444' :
                                         '#6b7280';
                        return (
                          <Cell 
                            key={`cell-factor-${index}`}
                            fill={fillColor}
                          />
                        );
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="text-[10px] text-stone-600 mt-1 font-mono">
                  Positive = Supports decision | Negative = Opposes decision
                </div>
              </div>
            )}

            {/* Graph 4: Confidence Score Visualization */}
            <div>
              <div className="text-sm font-bold text-stone-800 mb-2 flex items-center gap-2">
                <CheckCircle2 size={14} />
                Decision Confidence Breakdown
              </div>
              <div className="mt-2">
                <div className="h-8 bg-stone-200 rounded-full overflow-hidden relative flex items-center justify-center">
                  <div 
                    className="h-full bg-gradient-to-r from-green-500 to-green-700 flex items-center justify-center text-white text-xs font-bold transition-all"
                    style={{ width: `${confidence_score * 100}%` }}
                  >
                    {Math.round(confidence_score * 100)}%
                  </div>
                </div>
                <div className="flex justify-between mt-2 text-xs font-mono text-stone-600">
                  <span>
                    {contributing_factors.filter(f => f.is_verified !== false).length} / {contributing_factors.length} verified
                  </span>
                  <span>Based on {contributing_factors.length} contributing factors</span>
                </div>
              </div>
            </div>
          </div>
        )}

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
                  className={`relative p-4 border-2 ${factorStyle.border} rounded-sm ${factorStyle.bg} transition-all duration-200 hover:shadow-md`}
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

                  {/* Citation Evidence - Always Visible */}
                  {factor.citation_text && (
                    <div className="mt-3 pt-3 border-t border-stone-300">
                      <div className="text-[10px] font-mono text-stone-500 mb-1.5 uppercase tracking-wider flex items-center gap-2">
                        <FileText size={10} />
                        EVIDENCE
                        {(factor.verified_date || factor.citation_date) && (
                          <span className="ml-auto flex items-center gap-1">
                            <Calendar size={9} />
                            <span className="font-bold text-stone-600">
                              {factor.verified_date || factor.citation_date}
                            </span>
                            {dateCorrected && (factor.original_citation_date || factor.citation_date) && (
                              <span className="text-stone-400 line-through text-[9px]">
                                (was {factor.original_citation_date || factor.citation_date})
                              </span>
                            )}
                          </span>
                        )}
                        {verificationScore > 0 && (
                          <span className="text-stone-500 text-[9px]">
                            {Math.round(verificationScore * 100)}% match
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-stone-700 font-serif italic leading-relaxed bg-stone-50 p-2 rounded border border-stone-200">
                        "{factor.citation_text}"
                      </div>
                      {factor.verified_content && factor.verified_content !== factor.citation_text && (
                        <div className="mt-2 pt-2 border-t border-stone-200">
                          <div className="text-[10px] font-mono text-stone-500 mb-1">FULL CONTEXT</div>
                          <div className="text-xs text-stone-600 font-serif italic leading-relaxed">
                            {factor.verified_content}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Citation Date Only (if no citation_text) */}
                  {!factor.citation_text && (factor.verified_date || factor.citation_date) && (
                    <div className="mt-2 pt-2 border-t border-stone-300 flex items-center gap-2 text-[10px] font-mono text-stone-600">
                      <Calendar size={10} />
                      <span className="font-bold">
                        {factor.verified_date || factor.citation_date}
                      </span>
                      {dateCorrected && (factor.original_citation_date || factor.citation_date) && (
                        <span className="text-stone-400 line-through">
                          (was {factor.original_citation_date || factor.citation_date})
                        </span>
                      )}
                      {verificationScore > 0 && (
                        <span className="ml-auto text-stone-500">
                          {Math.round(verificationScore * 100)}% match
                        </span>
                      )}
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
          {contributing_factors.filter(f => f.date_corrected === true).length > 0 && (
            <div className="text-yellow-700">
              {contributing_factors.filter(f => f.date_corrected === true).length} DATE(S) CORRECTED
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
