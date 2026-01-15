import React, { useState, useEffect } from 'react';
import { Clock, Mail, Save, Loader } from 'lucide-react';

/**
 * ReminderSettings - Component for managing email reminder preferences
 * 
 * Allows users to set custom reminder times for morning and evening emails
 * for each day of the week.
 */
export default function ReminderSettings({ userId }) {
  const [preferences, setPreferences] = useState({
    morning: {
      monday: '08:00',
      tuesday: '08:00',
      wednesday: '08:00',
      thursday: '08:00',
      friday: '08:00',
      saturday: '08:00',
      sunday: '08:00',
    },
    evening: {
      monday: '20:00',
      tuesday: '20:00',
      wednesday: '20:00',
      thursday: '20:00',
      friday: '20:00',
      saturday: '20:00',
      sunday: '20:00',
    },
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' or 'error'
  const [error, setError] = useState(null);

  const days = [
    { key: 'monday', label: 'Monday' },
    { key: 'tuesday', label: 'Tuesday' },
    { key: 'wednesday', label: 'Wednesday' },
    { key: 'thursday', label: 'Thursday' },
    { key: 'friday', label: 'Friday' },
    { key: 'saturday', label: 'Saturday' },
    { key: 'sunday', label: 'Sunday' },
  ];

  useEffect(() => {
    if (userId) {
      fetchPreferences();
    }
  }, [userId]);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      const backend = (window && window.location && window.location.hostname === 'localhost') 
        ? 'http://127.0.0.1:8000' 
        : '';
      
      const response = await fetch(`${backend}/api/profile/${userId}/reminder-preferences`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch preferences');
      }
      
      const data = await response.json();
      setPreferences(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching reminder preferences:', err);
      setError('Failed to load reminder preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleTimeChange = (reminderType, day, time) => {
    setPreferences(prev => ({
      ...prev,
      [reminderType]: {
        ...prev[reminderType],
        [day]: time,
      },
    }));
    setSaveStatus(null);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaveStatus(null);
      setError(null);
      
      const backend = (window && window.location && window.location.hostname === 'localhost') 
        ? 'http://127.0.0.1:8000' 
        : '';
      
      const response = await fetch(`${backend}/api/profile/${userId}/reminder-preferences`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(preferences),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to save preferences');
      }
      
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      console.error('Error saving reminder preferences:', err);
      setError(err.message || 'Failed to save preferences');
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const setAllDays = (reminderType, time) => {
    setPreferences(prev => ({
      ...prev,
      [reminderType]: {
        monday: time,
        tuesday: time,
        wednesday: time,
        thursday: time,
        friday: time,
        saturday: time,
        sunday: time,
      },
    }));
    setSaveStatus(null);
  };

  if (loading) {
    return (
      <div className="p-6 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm">
        <div className="flex items-center justify-center gap-2 text-stone-600">
          <Loader size={16} className="animate-spin" />
          <span>Loading reminder preferences...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-[#f4e9d5] border border-[#d4c5a9] rounded-sm">
      <div className="mb-6">
        <h3 className="text-lg font-black text-stone-900 font-serif uppercase tracking-tight mb-2 flex items-center gap-2">
          <Mail size={20} />
          Email Reminder Settings
        </h3>
        <p className="text-sm text-stone-700 font-serif">
          Set custom reminder times for morning task reminders and evening report reminders.
          Each day can have its own reminder time.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 rounded text-red-800 text-sm">
          {error}
        </div>
      )}

      {saveStatus === 'success' && (
        <div className="mb-4 p-3 bg-green-100 border border-green-300 rounded text-green-800 text-sm">
          Preferences saved successfully!
        </div>
      )}

      {/* Morning Reminders */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-base font-bold text-stone-800 flex items-center gap-2">
            <Clock size={16} />
            Morning Reminders
          </h4>
          <div className="flex items-center gap-2">
            <input
              type="time"
              className="px-2 py-1 border border-stone-300 rounded text-sm"
              defaultValue="08:00"
              onChange={(e) => setAllDays('morning', e.target.value)}
            />
            <span className="text-xs text-stone-600">Set all days</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {days.map(day => (
            <div key={day.key} className="flex items-center justify-between p-3 bg-white border border-[#d4c5a9] rounded">
              <span className="text-sm font-medium text-stone-700">{day.label}</span>
              <input
                type="time"
                value={preferences.morning[day.key]}
                onChange={(e) => handleTimeChange('morning', day.key, e.target.value)}
                className="px-2 py-1 border border-stone-300 rounded text-sm font-mono"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Evening Reminders */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-base font-bold text-stone-800 flex items-center gap-2">
            <Clock size={16} />
            Evening Reminders
          </h4>
          <div className="flex items-center gap-2">
            <input
              type="time"
              className="px-2 py-1 border border-stone-300 rounded text-sm"
              defaultValue="20:00"
              onChange={(e) => setAllDays('evening', e.target.value)}
            />
            <span className="text-xs text-stone-600">Set all days</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {days.map(day => (
            <div key={day.key} className="flex items-center justify-between p-3 bg-white border border-[#d4c5a9] rounded">
              <span className="text-sm font-medium text-stone-700">{day.label}</span>
              <input
                type="time"
                value={preferences.evening[day.key]}
                onChange={(e) => handleTimeChange('evening', day.key, e.target.value)}
                className="px-2 py-1 border border-stone-300 rounded text-sm font-mono"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-stone-800 text-white rounded hover:bg-stone-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? (
            <>
              <Loader size={16} className="animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Save size={16} />
              <span>Save Preferences</span>
            </>
          )}
        </button>
      </div>

      <div className="mt-4 pt-4 border-t border-[#d4c5a9] text-xs text-stone-600 font-serif">
        <p className="mb-1">
          <strong>Morning reminders</strong> will include your daily tasks and schedule.
        </p>
        <p>
          <strong>Evening reminders</strong> will include your progress summary and encourage you to complete your daily report.
        </p>
      </div>
    </div>
  );
}