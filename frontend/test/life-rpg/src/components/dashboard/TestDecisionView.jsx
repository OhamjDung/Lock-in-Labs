/**
 * TestDecisionView - Load and display Decision JSON from backend test
 * 
 * This component loads the decision JSON from debug/test_decision_output.json
 * and renders it using the DecisionCard component for testing.
 */

import React, { useState, useEffect } from 'react';
import DecisionCard from './DecisionCard';
import { FileText, AlertCircle } from 'lucide-react';

export default function TestDecisionView() {
  const [decisionData, setDecisionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDecisionData();
  }, []);

  const loadDecisionData = async () => {
    try {
      setLoading(true);
      // Load from backend API or static file
      // For now, try to load from the backend's debug output
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      
      // Option 1: Try loading from backend static file endpoint (if you add one)
      // const res = await fetch(`${backend}/static/test_decision_output.json`);
      
      // Option 2: For testing, copy the JSON to the public folder and load it
      // For now, we'll use a simple fetch to the debug directory
      // This will only work if you serve the debug folder statically
      
      // For now, let's just use a placeholder - you can manually copy the JSON
      // from debug/test_decision_output.json to public/test_decision_output.json
      try {
        const res = await fetch('/test_decision_output.json');
        if (res.ok) {
          const data = await res.json();
          setDecisionData(data);
        } else {
          // Fallback: Use mock data structure
          setDecisionData(null);
          setError('Decision JSON file not found. Run: python debug/test_decision_with_running_data.py');
        }
      } catch (e) {
        setError('Could not load decision data. Make sure to run the test script first.');
      }
    } catch (err) {
      console.error('Error loading decision data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-stone-600 font-serif italic">
        Loading decision data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 bg-red-50 border-2 border-red-300 rounded-sm">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle size={20} className="text-red-700" />
          <h3 className="font-bold text-red-900">Error Loading Decision Data</h3>
        </div>
        <p className="text-sm text-red-800 mb-4">{error}</p>
        <div className="bg-red-100 p-4 rounded border border-red-300">
          <p className="text-xs font-mono text-red-900 mb-2">To test:</p>
          <ol className="text-xs text-red-800 list-decimal list-inside space-y-1">
            <li>Run: <code className="bg-red-200 px-1 rounded">python debug/test_decision_with_running_data.py</code></li>
            <li>Copy <code className="bg-red-200 px-1 rounded">debug/test_decision_output.json</code> to <code className="bg-red-200 px-1 rounded">public/test_decision_output.json</code></li>
            <li>Refresh this page</li>
          </ol>
        </div>
      </div>
    );
  }

  if (!decisionData || !decisionData.decision) {
    return (
      <div className="p-8 text-center text-stone-600 font-serif italic">
        No decision data available.
      </div>
    );
  }

  const decision = decisionData.decision;
  const metadata = decisionData.metadata || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-[#e8dcc5] border-2 border-[#d4c5a9] rounded-sm p-6">
        <div className="flex items-center gap-3 mb-4">
          <FileText size={24} className="text-stone-700" />
          <div>
            <h2 className="text-2xl font-black text-stone-900 font-serif uppercase tracking-tight">
              Test Decision View
            </h2>
            <div className="text-xs font-mono text-stone-600 mt-1">
              Testing DecisionCard with running mock data
            </div>
          </div>
        </div>
        
        {metadata.generated_at && (
          <div className="text-xs font-mono text-stone-600 mb-2">
            Generated: {new Date(metadata.generated_at).toLocaleString()}
          </div>
        )}
        
        {metadata.goal_name && (
          <div className="text-sm font-serif text-stone-800 mb-2">
            <strong>Goal:</strong> {metadata.goal_name}
          </div>
        )}
        
        {metadata.reports_count !== undefined && (
          <div className="text-xs font-mono text-stone-600">
            Based on {metadata.reports_count} reports ({metadata.recent_reports_count} recent)
          </div>
        )}
      </div>

      {/* Decision Card */}
      <DecisionCard
        decision={decision}
        onCitationClick={(citation) => {
          console.log('Citation clicked:', citation);
          // You can open a modal or navigate to the log entry here
          alert(`Citation from ${citation.date}:\n"${citation.text}"`);
        }}
      />

      {/* Metadata Debug Info */}
      {decisionData.sample_data && (
        <div className="bg-stone-100 border border-stone-300 rounded-sm p-4">
          <div className="text-xs font-mono text-stone-600 uppercase mb-2">Debug Info</div>
          <pre className="text-xs font-mono text-stone-800 overflow-x-auto">
            {JSON.stringify(decisionData.sample_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
