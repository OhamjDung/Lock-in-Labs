import React, { useState, useRef, useEffect } from 'react';
import { Activity, User, Map, ClipboardList, Calendar, Lock, Settings, LogOut, RotateCcw } from 'lucide-react';
import { signOut } from 'firebase/auth';
import { auth } from '../../config/firebase';

export default function Header({ activeTab, setActiveTab, isLockIn, onLogout, onRestartOnboarding }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    };

    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
      console.log('[Auth] User signed out');
      if (onLogout) {
        onLogout();
      }
      setIsMenuOpen(false);
    } catch (error) {
      console.error('[Auth] Error signing out:', error);
    }
  };

  const handleSettings = () => {
    // TODO: Implement settings functionality
    console.log('[Settings] Settings clicked');
    setIsMenuOpen(false);
  };

  const handleRestartOnboarding = () => {
    if (onRestartOnboarding) {
      onRestartOnboarding();
    }
    setIsMenuOpen(false);
  };

  return (
    <header className={`h-16 border-b flex items-center justify-between px-4 md:px-8 fixed w-full z-50 top-0 shadow-lg transition-all duration-500 ${isLockIn ? 'bg-black/90 border-[#39ff14]/30 backdrop-blur-none' : 'bg-stone-900/40 border-white/10 backdrop-blur-md'}`}>
      <div className="flex items-center gap-4">
        <div className="text-stone-100 font-black tracking-tighter flex items-center gap-2 text-xl drop-shadow-md">
          <div className="bg-stone-100 text-stone-900 p-1 rounded-sm"><Activity size={16} /></div> 
          LIFE_OS <span className="text-[10px] text-stone-300 font-mono font-normal mt-1 opacity-70">CONFIDENTIAL</span>
        </div>
      </div>

      <nav className="flex gap-2 items-center">
        <div className="flex gap-2 bg-black/20 p-1 rounded-lg border border-white/10 backdrop-blur-sm">
          <button 
            onClick={() => setActiveTab('sheet')} 
            className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'sheet' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}
          >
            <User size={12} /> Profile
          </button>
          <button 
            onClick={() => setActiveTab('map')} 
            className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'map' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}
          >
            <Map size={12} /> Blueprint
          </button>
          <button 
            onClick={() => setActiveTab('report')} 
            className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'report' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}
          >
            <ClipboardList size={12} /> Report
          </button>
          <button 
            onClick={() => setActiveTab('calendar')} 
            className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'calendar' ? 'bg-[#e8dcc5] text-stone-900 shadow-lg' : 'text-stone-300 hover:text-white hover:bg-white/10'}`}
          >
            <Calendar size={12} /> Calendar
          </button>
          <button 
            onClick={() => setActiveTab('lockin')} 
            className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${activeTab === 'lockin' ? (isLockIn ? 'bg-[#39ff14] text-black shadow-[0_0_10px_#39ff14]' : 'bg-[#e8dcc5] text-stone-900 shadow-lg') : (isLockIn ? 'text-[#005500] hover:text-[#39ff14]' : 'text-stone-300 hover:text-white hover:bg-white/10')}`}
          >
            <Lock size={12} /> Lock-In
          </button>
        </div>
        
        {/* Burger Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex flex-col items-center justify-center gap-1 text-stone-300 hover:text-white hover:bg-white/10 border border-white/10 min-w-[40px] h-10"
            title="Menu"
          >
            <div className="w-4 h-0.5 bg-current"></div>
            <div className="w-4 h-0.5 bg-current"></div>
            <div className="w-4 h-0.5 bg-current"></div>
          </button>

          {/* Dropdown Menu */}
          {isMenuOpen && (
            <div className={`absolute right-0 top-full mt-2 min-w-[180px] rounded-md shadow-lg border backdrop-blur-md transition-all duration-200 ${isLockIn ? 'bg-black/95 border-[#39ff14]/30' : 'bg-stone-900/95 border-white/20'}`}>
              <div className="py-1">
                <button
                  onClick={handleSettings}
                  className="w-full px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 text-stone-300 hover:text-white hover:bg-white/10"
                >
                  <Settings size={14} /> Settings
                </button>
                <button
                  onClick={handleRestartOnboarding}
                  className="w-full px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 text-stone-300 hover:text-white hover:bg-white/10"
                >
                  <RotateCcw size={14} /> Restart Onboarding
                </button>
                <div className="border-t border-white/10 my-1"></div>
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-[11px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 text-stone-300 hover:text-red-400 hover:bg-red-500/10"
                >
                  <LogOut size={14} /> Logout
                </button>
              </div>
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}

