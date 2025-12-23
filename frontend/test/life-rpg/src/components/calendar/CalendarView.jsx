import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { auth } from '../../config/firebase';
import { onAuthStateChanged } from 'firebase/auth';

export default function CalendarView() {
  const [events, setEvents] = useState([]);
  const [userId, setUserId] = useState(null);
  const [showAddEventModal, setShowAddEventModal] = useState(false);
  const [categories, setCategories] = useState([]);
  const [hoveredDay, setHoveredDay] = useState(null);
  const [hoveredEventId, setHoveredEventId] = useState(null);
  const [allCalendarEvents, setAllCalendarEvents] = useState([]); // Store full event objects with IDs
  const [newEvent, setNewEvent] = useState({
    title: '',
    category: '',
    from: '',
    to: '',
    description: ''
  });

  const formatMMDD = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d)) return '';
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${mm}/${dd}`;
    } catch (e) {
      return '';
    }
  };
  const daysOfWeek = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
  const daysInMonth = Array.from({ length: 31 }, (_, i) => i + 1);
  const startOffset = 3; // Starts on Wednesday for example purposes

  // Get current date
  const now = new Date();
  const TODAY_DAY = now.getDate();
  const TODAY_YEAR = now.getFullYear();
  const TODAY_MONTH = now.getMonth(); // 0-indexed

  // Get current user
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        setUserId(user.uid);
      } else {
        setUserId(null);
      }
    });
    return () => unsubscribe();
  }, []);

  // Function to fetch and process events
  const fetchEvents = useCallback(async () => {
    if (!userId) return;
    
    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      // Fetch the full profile for the current user
      const res = await fetch(`${backend}/api/profile/${userId}`);
      
      if (!res.ok) {
         throw new Error("Backend not reachable");
      }

      const data = await res.json();
      if (!data) return;

      // Try to read daily_schedule (map of ISO date -> array of tasks/events)
      const cs = data.character_sheet || data;
      const schedule = (cs && cs.daily_schedule) ? cs.daily_schedule : {};

      // Build simple events array by flattening schedule entries for this month/year
      const flattened = [];
      Object.keys(schedule || {}).forEach(dateKey => {
        try {
          const d = new Date(dateKey);
          if (d.getFullYear() === TODAY_YEAR && d.getMonth() === TODAY_MONTH) { 
            const day = d.getDate();
            const items = schedule[dateKey] || [];
            items.forEach(it => {
              flattened.push({
                day,
                date: dateKey,
                title: it.label || it.title || it.name || (it.node_id || '').replace(/_/g, ' '),
                time: it.time || it.start_time || null,
                status: it.status || null,
              });
            });
          }
        } catch (e) {
          // ignore parse errors
        }
      });

      // Also include any explicit calendar_events if present
      const uniqueCategories = new Set();
      const calendarEventsList = [];
      if (cs && Array.isArray(cs.calendar_events)) {
        cs.calendar_events.forEach(ev => {
          try {
            const dt = new Date(ev.start_time || ev.date || ev.when || ev.time);
            if (!isNaN(dt) && dt.getFullYear() === TODAY_YEAR && dt.getMonth() === TODAY_MONTH) {
              const eventObj = {
                id: ev.id,
                day: dt.getDate(),
                date: dt.toISOString().slice(0,10),
                title: ev.title || ev.name || ev.summary || 'Event',
                time: ev.start_time || ev.time || null,
                status: ev.status || null,
                fullEvent: ev // Store full event for deletion
              };
              flattened.push(eventObj);
              calendarEventsList.push(eventObj);
            }
            // Extract categories from existing events
            if (ev.category) {
              uniqueCategories.add(ev.category);
            } else if (ev.type) {
              uniqueCategories.add(ev.type);
            }
          } catch (e) {}
        });
      }

      setEvents(flattened);
      setAllCalendarEvents(calendarEventsList);
      setCategories(Array.from(uniqueCategories));
    } catch (err) {
      console.warn('Backend fetch failed for calendar data', err);
      setEvents([]);
    }
  }, [userId, TODAY_YEAR, TODAY_MONTH]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Group events for the sidebar
  const upcomingGroups = useMemo(() => {
    const groups = {
      today: [],
      tomorrow: [],
      thisWeek: [],
      thisMonth: []
    };

    // Sort events by day first
    const sortedEvents = [...events].sort((a, b) => a.day - b.day);

    sortedEvents.forEach(ev => {
        if (ev.day === TODAY_DAY) { // Today
            groups.today.push(ev);
        } else if (ev.day === TODAY_DAY + 1) { // Tomorrow
            groups.tomorrow.push(ev);
        } else if (ev.day > TODAY_DAY + 1 && ev.day <= TODAY_DAY + 3) { // This week (2-3 days from now)
            groups.thisWeek.push(ev);
        } else if (ev.day > TODAY_DAY + 3) { // This month (4+ days from now)
            groups.thisMonth.push(ev);
        }
    });

    return groups;
  }, [events, TODAY_DAY]);

  const handleDeleteEvent = async (eventId) => {
    if (!userId || !eventId) return;
    
    if (!confirm('Are you sure you want to delete this event?')) {
      return;
    }

    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      
      const response = await fetch(`${backend}/api/profile/${userId}/calendar/${eventId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete event');
      }

      // Refresh events without page reload
      await fetchEvents();
    } catch (error) {
      console.error('Error deleting event:', error);
      alert('Failed to delete event. Please try again.');
    }
  };

  const handleAddEvent = async (e) => {
    e.preventDefault();
    if (!userId || !newEvent.title || !newEvent.from) {
      alert('Please fill in at least Title and From date/time');
      return;
    }

    try {
      const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
      
      // Format dates to ISO 8601
      const fromDate = new Date(newEvent.from);
      const toDate = newEvent.to ? new Date(newEvent.to) : null;
      
      // If no end time, set it to same as start time (or 1 hour later)
      const endTime = toDate || new Date(fromDate.getTime() + 60 * 60 * 1000);
      
      const eventData = {
        title: newEvent.title,
        category: newEvent.category || null,
        start_time: fromDate.toISOString(),
        end_time: endTime.toISOString(),
        type: 'MEETING', // Default type, can be customized later
        description: newEvent.description || null,
        is_completed: false
      };

      const response = await fetch(`${backend}/api/profile/${userId}/calendar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(eventData),
      });

      if (!response.ok) {
        throw new Error('Failed to save event');
      }

      // Add category to list if it's new
      if (newEvent.category && !categories.includes(newEvent.category)) {
        setCategories([...categories, newEvent.category]);
      }

      // Reset form and close modal
      setNewEvent({
        title: '',
        category: '',
        from: '',
        to: '',
        description: ''
      });
      setShowAddEventModal(false);

      // Refresh events without page reload
      await fetchEvents();
    } catch (error) {
      console.error('Error adding event:', error);
      alert('Failed to add event. Please try again.');
    }
  };

  return (
    <>
    <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&display=swap');
        .font-handwriting { font-family: 'Caveat', cursive; }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }
        .animate-in {
            animation: fadeIn 0.5s ease-out forwards;
        }
    `}} />
    <div className="min-h-screen flex-1 flex flex-col items-center justify-center p-4 md:p-8 animate-in">
      <div className="bg-[#e8dcc5] w-full max-w-6xl rounded-sm shadow-[0_20px_40px_-10px_rgba(0,0,0,0.4)] border border-[#d4c5a9] relative overflow-hidden flex flex-col min-h-[700px] rotate-1 hover:rotate-0 transition-transform duration-500">
        
        {/* Texture Overlay */}
        <div className="absolute inset-0 opacity-[0.08] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        {/* Header */}
        <div className="bg-[#dfd3bc]/50 border-b-2 border-stone-800 p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center relative z-10 gap-4">
          <div>
            <h2 className="text-3xl font-black text-stone-900 uppercase tracking-tighter">Mission Schedule</h2>
            <div className="text-xs font-mono text-stone-600 tracking-widest mt-1">
              {now.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }).toUpperCase()} // SECTOR 4
            </div>
          </div>
          <div className="flex items-center gap-4">
             <button
               onClick={() => setShowAddEventModal(true)}
               className="bg-stone-800 text-[#e8dcc5] px-4 py-2 rounded-sm font-bold font-mono text-sm shadow-md hover:bg-stone-700 transition-colors"
             >
               + ADD EVENT
             </button>
             <div className="bg-stone-800 text-[#e8dcc5] px-4 py-2 rounded-sm font-bold font-mono text-sm shadow-md">
                WEEK 51
             </div>
             <div className="w-12 h-12 border-2 border-red-900/30 rounded-full flex items-center justify-center -rotate-12 bg-red-900/5">
                <div className="text-[10px] font-black text-red-900/50 text-center leading-none">HIGH<br/>PRIORITY</div>
             </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex flex-col lg:flex-row flex-1 relative z-10">
            
            {/* Calendar Grid - Left Column */}
            <div className="flex-1 p-6 border-b lg:border-b-0 lg:border-r border-[#c7bba4]">
                <div className="grid grid-cols-7 gap-2 md:gap-4 h-full content-start">
                    {/* Day Headers */}
                    {daysOfWeek.map(day => (
                    <div key={day} className="text-center font-bold text-stone-500 text-xs tracking-widest border-b border-stone-400 pb-2 mb-2">
                        {day}
                    </div>
                    ))}

                    {/* Empty Slots */}
                    {Array.from({ length: startOffset }).map((_, i) => (
                    <div key={`empty-${i}`} className="bg-transparent hidden md:block" />
                    ))}

                    {/* Days */}
                    {daysInMonth.map(day => {
                    const isToday = day === TODAY_DAY;
                    const eventsForDay = events.filter(e => e.day === day);
                    const isHovered = hoveredDay === day;

                    // Format date for datetime-local input (YYYY-MM-DDTHH:mm)
                    const formatDateForInput = (dayNum) => {
                      const date = new Date(TODAY_YEAR, TODAY_MONTH, dayNum);
                      const year = date.getFullYear();
                      const month = String(date.getMonth() + 1).padStart(2, '0');
                      const dayStr = String(date.getDate()).padStart(2, '0');
                      // Default to 9:00 AM
                      return `${year}-${month}-${dayStr}T09:00`;
                    };

                    return (
                        <div 
                          key={day} 
                          className={`
                            relative border border-[#c7bba4] rounded-sm p-1 md:p-2 min-h-[60px] md:min-h-[80px] transition-all hover:bg-white/20 group
                            ${isToday ? 'bg-white/40 ring-2 ring-stone-800 shadow-lg' : 'bg-[#dcd0b9]/30'}
                          `}
                          onMouseEnter={() => setHoveredDay(day)}
                          onMouseLeave={() => setHoveredDay(null)}
                        >
                        <div className={`font-mono text-sm font-bold ${isToday ? 'text-stone-900' : 'text-stone-500'}`}>{day}</div>

                        {/* Hover "+" button */}
                        {isHovered && (
                          <button
                            onClick={() => {
                              setNewEvent({
                                ...newEvent,
                                from: formatDateForInput(day),
                                to: ''
                              });
                              setShowAddEventModal(true);
                            }}
                            className="absolute top-1 right-1 w-6 h-6 bg-stone-800 text-[#e8dcc5] rounded-full flex items-center justify-center font-bold text-sm shadow-md hover:bg-stone-700 transition-colors z-10"
                            title="Add event to this day"
                          >
                            +
                          </button>
                        )}

                        {eventsForDay.length > 0 && (
                            <div className="mt-1 md:mt-2 space-y-1">
                            {eventsForDay.map((ev, idx) => {
                                const isCompleted = ev.status && (ev.status.toLowerCase() === 'done' || ev.status === 'COMPLETED');
                                const isEventHovered = hoveredEventId === ev.id;
                                const canDelete = ev.id && ev.fullEvent; // Only calendar events with IDs can be deleted
                                return (
                                <div 
                                  key={idx} 
                                  className={`p-1 rounded-sm border text-[9px] font-bold leading-tight shadow-sm flex items-center relative group
                                      ${isCompleted ? 'bg-stone-800 text-[#e8dcc5] border-stone-900 line-through opacity-60' : 'bg-[#f7e6a1] text-amber-900 border-amber-900/20'}
                                  `}
                                  onMouseEnter={() => canDelete && setHoveredEventId(ev.id)}
                                  onMouseLeave={() => setHoveredEventId(null)}
                                >
                                    <div className="truncate w-full">{ev.title}</div>
                                    {canDelete && isEventHovered && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleDeleteEvent(ev.id);
                                        }}
                                        className="absolute top-0 right-0 w-4 h-4 bg-red-600 text-white rounded-full flex items-center justify-center font-bold text-[10px] shadow-md hover:bg-red-700 transition-colors z-10"
                                        title="Delete event"
                                      >
                                        −
                                      </button>
                                    )}
                                </div>
                                );
                            })}
                            </div>
                        )}

                        {isToday && !isHovered && (
                            <div className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                        )}
                        </div>
                    );
                    })}
                </div>
            </div>

            {/* Sidebar - Right Column */}
            <div className="w-full lg:w-72 bg-[#dcd0b9]/20 p-6 flex flex-col gap-6">
                <div className="font-mono text-xs font-bold text-stone-500 tracking-widest uppercase border-b border-stone-400 pb-2">
                    Incoming Intel
                </div>

                {/* Today */}
                <div className="space-y-3">
                    <h3 className="font-bold text-stone-800 text-sm flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-red-500"></span>
                        TODAY
                    </h3>
                    {upcomingGroups.today.length > 0 ? (
                        <div className="space-y-2">
                            {upcomingGroups.today.map((ev, i) => (
                                <div key={i} className="bg-white/50 p-2 rounded-sm border border-[#c7bba4] text-xs shadow-sm">
                                    <div className="font-bold text-stone-800">{ev.title}</div>
                                    <div className="text-stone-500 text-[10px] mt-0.5">{ev.time || 'All Day'}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-stone-400 text-xs italic pl-4">No scheduled ops.</div>
                    )}
                </div>

                {/* Tomorrow */}
                <div className="space-y-3">
                    <h3 className="font-bold text-stone-800 text-sm flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                        TOMORROW
                    </h3>
                    {upcomingGroups.tomorrow.length > 0 ? (
                        <div className="space-y-2">
                            {upcomingGroups.tomorrow.map((ev, i) => (
                                <div key={i} className="bg-white/40 p-2 rounded-sm border border-[#c7bba4] text-xs shadow-sm">
                                    <div className="font-bold text-stone-800">{ev.title}</div>
                                    <div className="text-stone-500 text-[10px] mt-0.5">{ev.time || 'All Day'}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-stone-400 text-xs italic pl-4">No scheduled ops.</div>
                    )}
                </div>

                {/* This Week */}
                <div className="space-y-3">
                    <h3 className="font-bold text-stone-800 text-sm flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-stone-500"></span>
                        THIS WEEK
                    </h3>
                    {upcomingGroups.thisWeek.length > 0 ? (
                        <div className="space-y-2">
                            {upcomingGroups.thisWeek.map((ev, i) => (
                                <div key={i} className="bg-white/20 p-2 rounded-sm border border-[#c7bba4] text-xs">
                                    <div className="flex justify-between">
                                        <span className="font-semibold text-stone-700">{ev.title}</span>
                                        <span className="text-stone-500 font-mono">{formatMMDD(ev.date)}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-stone-400 text-xs italic pl-4">Clear.</div>
                    )}
                </div>

                {/* This Month */}
                <div className="space-y-3">
                    <h3 className="font-bold text-stone-800 text-sm flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-stone-400"></span>
                        THIS MONTH
                    </h3>
                    {upcomingGroups.thisMonth.length > 0 ? (
                        <div className="space-y-2">
                            {upcomingGroups.thisMonth.map((ev, i) => (
                                <div key={i} className="bg-transparent p-1 border-b border-stone-300 text-xs flex justify-between items-center pb-2">
                                    <span className="text-stone-600 truncate mr-2">{ev.title}</span>
                                    <span className="text-stone-400 font-mono whitespace-nowrap">{formatMMDD(ev.date)}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-stone-400 text-xs italic pl-4">No further intel.</div>
                    )}
                </div>
            </div>
        </div>

        {/* Footer Notes */}
        <div className="p-4 border-t border-[#c7bba4] bg-[#dcd0b9]/20 relative z-10">
           <div className="font-handwriting text-stone-600 text-lg rotate-[-1deg] ml-4">
             * Note: Annual review scheduled for the 30th. Prepare field reports.
           </div>
        </div>

      </div>

      {/* Add Event Modal */}
      {showAddEventModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddEventModal(false)}>
          <div className="bg-[#e8dcc5] rounded-sm shadow-2xl border-2 border-stone-800 p-6 w-full max-w-md relative z-10" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-2xl font-black text-stone-900 uppercase tracking-tighter mb-4">Add New Event</h3>
            
            <form onSubmit={handleAddEvent} className="space-y-4">
              {/* Title */}
              <div>
                <label className="block text-sm font-bold text-stone-700 mb-1">Title *</label>
                <input
                  type="text"
                  value={newEvent.title}
                  onChange={(e) => setNewEvent({...newEvent, title: e.target.value})}
                  className="w-full px-3 py-2 border border-stone-600 rounded-sm bg-white text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800"
                  required
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-sm font-bold text-stone-700 mb-1">Category</label>
                <div className="relative">
                  <input
                    type="text"
                    list="categories"
                    placeholder="Select existing or type new category"
                    value={newEvent.category}
                    onChange={(e) => setNewEvent({...newEvent, category: e.target.value})}
                    className="w-full px-3 py-2 border border-stone-600 rounded-sm bg-white text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800"
                  />
                  <datalist id="categories">
                    {categories.map(cat => (
                      <option key={cat} value={cat} />
                    ))}
                  </datalist>
                </div>
                {categories.length > 0 && (
                  <div className="mt-1 text-xs text-stone-500">
                    Existing categories: {categories.join(', ')}
                  </div>
                )}
              </div>

              {/* From */}
              <div>
                <label className="block text-sm font-bold text-stone-700 mb-1">From *</label>
                <input
                  type="datetime-local"
                  value={newEvent.from}
                  onChange={(e) => setNewEvent({...newEvent, from: e.target.value})}
                  className="w-full px-3 py-2 border border-stone-600 rounded-sm bg-white text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800"
                  required
                />
              </div>

              {/* To */}
              <div>
                <label className="block text-sm font-bold text-stone-700 mb-1">To (Optional)</label>
                <input
                  type="datetime-local"
                  value={newEvent.to}
                  onChange={(e) => setNewEvent({...newEvent, to: e.target.value})}
                  className="w-full px-3 py-2 border border-stone-600 rounded-sm bg-white text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-bold text-stone-700 mb-1">Description</label>
                <textarea
                  value={newEvent.description}
                  onChange={(e) => setNewEvent({...newEvent, description: e.target.value})}
                  rows={3}
                  className="w-full px-3 py-2 border border-stone-600 rounded-sm bg-white text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-800 resize-none"
                />
              </div>

              {/* Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  className="flex-1 bg-stone-800 text-[#e8dcc5] px-4 py-2 rounded-sm font-bold font-mono text-sm shadow-md hover:bg-stone-700 transition-colors"
                >
                  SAVE EVENT
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddEventModal(false);
                    setNewEvent({
                      title: '',
                      category: '',
                      from: '',
                      to: '',
                      description: ''
                    });
                  }}
                  className="flex-1 bg-stone-400 text-stone-900 px-4 py-2 rounded-sm font-bold font-mono text-sm shadow-md hover:bg-stone-500 transition-colors"
                >
                  CANCEL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
    </>
  );
}