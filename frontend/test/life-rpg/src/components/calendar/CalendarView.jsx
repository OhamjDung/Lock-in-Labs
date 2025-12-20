import React, { useState, useEffect } from 'react';

export default function CalendarView() {
  const [events, setEvents] = useState([]);
  const [upcomingOpen, setUpcomingOpen] = useState(false);

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

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
        // Fetch the full profile so we can read `daily_schedule` and other local schedule fields
        const res = await fetch(`${backend}/api/profile/user_01`);
        if (!res.ok) {
          console.warn('Failed to fetch profile for calendar', res.status);
          return;
        }
        const data = await res.json();
        if (!mounted || !data) return;

        // Try to read daily_schedule (map of ISO date -> array of tasks/events)
        const cs = data.character_sheet || data;
        const schedule = (cs && cs.daily_schedule) ? cs.daily_schedule : {};

        // Build simple events array by flattening schedule entries for this month/year (Dec 2025)
        const flattened = [];
        Object.keys(schedule || {}).forEach(dateKey => {
          try {
            const d = new Date(dateKey);
            if (d.getFullYear() === 2025 && d.getMonth() === 11) { // month is 0-indexed (11 = December)
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
        if (cs && Array.isArray(cs.calendar_events)) {
          cs.calendar_events.forEach(ev => {
            try {
              const dt = new Date(ev.start_time || ev.date || ev.when || ev.time);
              if (!isNaN(dt) && dt.getFullYear() === 2025 && dt.getMonth() === 11) {
                flattened.push({
                  day: dt.getDate(),
                  date: dt.toISOString().slice(0,10),
                  title: ev.title || ev.name || ev.summary || 'Event',
                  time: ev.start_time || ev.time || null,
                  status: ev.status || null,
                });
              }
            } catch (e) {}
          });
        }

        setEvents(flattened);
      } catch (err) {
        console.error('Error fetching calendar events', err);
      }
    })();
    return () => { mounted = false; };
  }, []);

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8 animate-in fade-in zoom-in-95 duration-500">
      <div className="bg-[#e8dcc5] w-full max-w-5xl rounded-sm shadow-[0_20px_40px_-10px_rgba(0,0,0,0.4)] border border-[#d4c5a9] relative overflow-hidden flex flex-col min-h-[700px] rotate-1 hover:rotate-0 transition-transform duration-500">
        
        {/* Texture Overlay */}
        <div className="absolute inset-0 opacity-[0.08] pointer-events-none bg-repeat mix-blend-multiply" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>

        {/* Simple event list (fetched from backend) - collapsible widget */}
        <div className="absolute top-4 right-4 z-40">
          {!upcomingOpen ? (
            <button
              onClick={() => setUpcomingOpen(true)}
              className="bg-white/90 backdrop-blur-sm px-3 py-2 rounded-full shadow-sm text-xs font-medium border border-stone-200"
              title="Open Upcoming"
            >
              Upcoming ({events.length})
            </button>
          ) : (
            <div className="bg-white/90 backdrop-blur-sm p-3 rounded border shadow-sm w-64 text-xs">
              <div className="flex justify-between items-center mb-2">
                <div className="font-bold text-stone-800">Upcoming</div>
                <div className="flex items-center gap-2">
                  <div className="text-[11px] text-stone-500">{events.length} items</div>
                  <button onClick={() => setUpcomingOpen(false)} className="text-stone-500 text-xs px-2">Close</button>
                </div>
              </div>

              {events.length === 0 ? (
                <div className="text-stone-500">No events</div>
              ) : (
                <div className="space-y-2 max-h-40 overflow-auto">
                  {events.map((ev) => (
                    <div key={(ev.date || '') + (ev.title || '')} className="flex flex-col text-stone-700 border-b border-stone-100 pb-1">
                      <div className="font-semibold text-[13px]">{formatMMDD(ev.date)} {ev.title || ev.name || 'Untitled'}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Header */}
        <div className="bg-[#dfd3bc]/50 border-b-2 border-stone-800 p-6 flex justify-between items-center relative z-10">
          <div>
            <h2 className="text-3xl font-black text-stone-900 uppercase tracking-tighter">Mission Schedule</h2>
            <div className="text-xs font-mono text-stone-600 tracking-widest mt-1">DECEMBER 2025 // SECTOR 4</div>
          </div>
          <div className="flex items-center gap-4">
             <div className="bg-stone-800 text-[#e8dcc5] px-4 py-2 rounded-sm font-bold font-mono text-sm shadow-md">
                WEEK 51
             </div>
             <div className="w-12 h-12 border-2 border-red-900/30 rounded-full flex items-center justify-center -rotate-12">
                <div className="text-[10px] font-black text-red-900/50 text-center leading-none">HIGH<br/>PRIORITY</div>
             </div>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="flex-1 p-6 relative z-10">
          <div className="grid grid-cols-7 gap-4 h-full">
            {/* Day Headers */}
            {daysOfWeek.map(day => (
              <div key={day} className="text-center font-bold text-stone-500 text-xs tracking-widest border-b border-stone-400 pb-2 mb-2">
                {day}
              </div>
            ))}

            {/* Empty Slots */}
            {Array.from({ length: startOffset }).map((_, i) => (
              <div key={`empty-${i}`} className="bg-transparent" />
            ))}

            {/* Days */}
            {daysInMonth.map(day => {
              const isToday = day === 18; // Mock today
              const eventsForDay = events.filter(e => e.day === day);

              return (
                <div key={day} className={`
                  relative border border-[#c7bba4] rounded-sm p-2 min-h-[80px] transition-all hover:bg-white/20 group
                  ${isToday ? 'bg-white/40 ring-2 ring-stone-800 shadow-lg' : 'bg-[#dcd0b9]/30'}
                `}>
                  <div className={`font-mono text-sm font-bold ${isToday ? 'text-stone-900' : 'text-stone-500'}`}>{day}</div>

                  {eventsForDay.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {eventsForDay.map((ev, idx) => {
                        const isCompleted = ev.status && (ev.status.toLowerCase() === 'done' || ev.status === 'COMPLETED');
                        return (
                          <div key={idx} className={`p-1.5 rounded-sm border text-[9px] font-bold leading-tight shadow-sm flex items-center
                            ${isCompleted ? 'bg-stone-800 text-[#e8dcc5] border-stone-900 line-through opacity-60' : 'bg-[#f7e6a1] text-amber-900 border-amber-900/20'}
                          `}>
                            <div className="truncate">{ev.title}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {isToday && (
                    <div className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer Notes */}
        <div className="p-4 border-t border-[#c7bba4] bg-[#dcd0b9]/20 relative z-10">
           <div className="font-handwriting text-stone-600 text-lg rotate-[-1deg] ml-4">
             * Note: Annual review scheduled for the 30th. Prepare field reports.
           </div>
        </div>

      </div>
    </div>
  );
}