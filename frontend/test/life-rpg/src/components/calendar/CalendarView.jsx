import React, { useState, useEffect, useMemo } from 'react';

export default function App() {
  const [events, setEvents] = useState([]);

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

  // Mock "Today" is Dec 18, 2025
  const TODAY_DAY = 18;
  const TODAY_YEAR = 2025;
  const TODAY_MONTH = 11; // 0-indexed (Dec)

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const backend = (window && window.location && window.location.hostname === 'localhost') ? 'http://127.0.0.1:8000' : '';
        // Fetch the full profile so we can read `daily_schedule` and other local schedule fields
        const res = await fetch(`${backend}/api/profile/user_01`);
        
        if (!res.ok) {
           throw new Error("Backend not reachable");
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
        if (cs && Array.isArray(cs.calendar_events)) {
          cs.calendar_events.forEach(ev => {
            try {
              const dt = new Date(ev.start_time || ev.date || ev.when || ev.time);
              if (!isNaN(dt) && dt.getFullYear() === TODAY_YEAR && dt.getMonth() === TODAY_MONTH) {
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
        console.warn('Backend fetch failed, loading mock data for demo', err);
        // Fallback mock data for display purposes
        if (mounted) {
            setEvents([
                { day: 2, date: '2025-12-02', title: 'Equipment Check', status: 'COMPLETED' },
                { day: 5, date: '2025-12-05', title: 'Target Recon', status: 'COMPLETED' },
                { day: 10, date: '2025-12-10', title: 'Intel Briefing', status: 'done' },
                { day: 18, date: '2025-12-18', title: 'Operation: Nightfall', status: 'active' },
                { day: 19, date: '2025-12-19', title: 'Debrief w/ Command', status: 'pending' },
                { day: 20, date: '2025-12-20', title: 'Gear Maintenance', status: 'pending' },
                { day: 24, date: '2025-12-24', title: 'Report Due', status: 'pending' },
                { day: 30, date: '2025-12-30', title: 'Annual Review', status: 'pending' }
            ]);
        }
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Group events for the sidebar
  const upcomingGroups = useMemo(() => {
    const groups = {
      tomorrow: [],
      thisWeek: [],
      thisMonth: []
    };

    // Sort events by day first
    const sortedEvents = [...events].sort((a, b) => a.day - b.day);

    sortedEvents.forEach(ev => {
        // Logic based on mock Today = 18th (Thursday)
        if (ev.day === TODAY_DAY + 1) { // 19th
            groups.tomorrow.push(ev);
        } else if (ev.day > TODAY_DAY + 1 && ev.day <= TODAY_DAY + 3) { // 20th, 21st (Fri-Sun)
            groups.thisWeek.push(ev);
        } else if (ev.day > TODAY_DAY + 3) { // 22nd+
            groups.thisMonth.push(ev);
        }
    });

    return groups;
  }, [events]);

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
            <div className="text-xs font-mono text-stone-600 tracking-widest mt-1">DECEMBER 2025 // SECTOR 4</div>
          </div>
          <div className="flex items-center gap-4">
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

                    return (
                        <div key={day} className={`
                        relative border border-[#c7bba4] rounded-sm p-1 md:p-2 min-h-[60px] md:min-h-[80px] transition-all hover:bg-white/20 group
                        ${isToday ? 'bg-white/40 ring-2 ring-stone-800 shadow-lg' : 'bg-[#dcd0b9]/30'}
                        `}>
                        <div className={`font-mono text-sm font-bold ${isToday ? 'text-stone-900' : 'text-stone-500'}`}>{day}</div>

                        {eventsForDay.length > 0 && (
                            <div className="mt-1 md:mt-2 space-y-1">
                            {eventsForDay.map((ev, idx) => {
                                const isCompleted = ev.status && (ev.status.toLowerCase() === 'done' || ev.status === 'COMPLETED');
                                return (
                                <div key={idx} className={`p-1 rounded-sm border text-[9px] font-bold leading-tight shadow-sm flex items-center
                                    ${isCompleted ? 'bg-stone-800 text-[#e8dcc5] border-stone-900 line-through opacity-60' : 'bg-[#f7e6a1] text-amber-900 border-amber-900/20'}
                                `}>
                                    <div className="truncate w-full">{ev.title}</div>
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

            {/* Sidebar - Right Column */}
            <div className="w-full lg:w-72 bg-[#dcd0b9]/20 p-6 flex flex-col gap-6">
                <div className="font-mono text-xs font-bold text-stone-500 tracking-widest uppercase border-b border-stone-400 pb-2">
                    Incoming Intel
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
    </div>
    </>
  );
}