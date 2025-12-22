import React from 'react';
import { Activity, User, Map, ClipboardList, Calendar, Lock, Settings, LogOut } from 'lucide-react';
import { signOut } from 'firebase/auth';
import { auth } from '../../config/firebase';

export default function Header({ activeTab, setActiveTab, isLockIn, onLogout }) {
  const handleLogout = async () => {
    try {
      await signOut(auth);
      console.log('[Auth] User signed out');
      if (onLogout) {
        onLogout();
      }
    } catch (error) {
      console.error('[Auth] Error signing out:', error);
    }
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
        <button
          onClick={handleLogout}
          className="px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-2 text-stone-300 hover:text-red-400 hover:bg-red-500/10 border border-white/10"
          title="Sign Out"
        >
          <LogOut size={12} /> Logout
        </button>
      </nav>
    </header>
  );
}

