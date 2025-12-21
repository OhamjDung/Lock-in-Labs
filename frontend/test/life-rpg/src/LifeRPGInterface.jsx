import React, { useState, useEffect, useMemo, useRef } from 'react';
import { FileText } from 'lucide-react';
import OnboardingModule from './components/onboarding/OnboardingModule';
import Header from './components/layout/Header';
import ProfileView from './components/dashboard/ProfileView';
import ReportView from './components/dashboard/ReportView';
import BlueprintView from './components/blueprint/BlueprintView';
import CalendarView from './components/calendar/CalendarView';
import LockInView from './components/lockin/LockInView';
import { transformCharacterData } from './utils/dataTransform';
import { skillTreeJson, rawCharacterSheet } from './data/mockData';

export default function LifeRPGInterface() {
  const [activeTab, setActiveTab] = useState('sheet'); 
  const [loading, setLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(true);

  // Live profile state (falls back to rawCharacterSheet / skillTreeJson until API load succeeds)
  const [characterSheet, setCharacterSheet] = useState(rawCharacterSheet);
  const [skillTree, setSkillTree] = useState(skillTreeJson);
  
  // Dithering / profile photo state (lifted so Profile and LockInView can share)
  const [ditheredPreviewUrl, setDitheredPreviewUrl] = useState(null);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('FloydSteinberg');
  const fileInputRef = useRef(null);
  const takePhotoRef = useRef(null); // LockInView will register its capture function here
  const isLockIn = activeTab === 'lockin';

  const sendFile = async (file, algorithmOverride, saveToFirebase = false) => {
    try {
      const alg = algorithmOverride || selectedAlgorithm || 'FloydSteinberg';
      const form = new FormData();
      form.append('file', file, file.name || 'photo.png');
      form.append('algorithm', alg);
      const proto = window.location.protocol === 'https:' ? 'https' : 'http';
      const host = window.location.hostname || '127.0.0.1';
      const port = 8000;
      
      // Use avatar endpoint if saving to Firebase, otherwise just dither
      const endpoint = saveToFirebase ? 'avatar' : 'dither';
      const user_id = characterSheet?.user_id || 'user_01';
      const url = saveToFirebase 
        ? `${proto}://${host}:${port}/api/profile/${user_id}/avatar`
        : `${proto}://${host}:${port}/api/dither`;
      
      const resp = await fetch(url, { method: 'POST', body: form });
      if (!resp.ok) {
        console.error(`${endpoint} failed`, resp.statusText);
        return;
      }
      
      if (saveToFirebase) {
        const data = await resp.json();
        if (data.avatar_url) {
          setDitheredPreviewUrl(data.avatar_url);
          // Reload profile to get updated avatar_url
          const profileRes = await fetch(`${proto}://${host}:${port}/api/profile/${user_id}`);
          if (profileRes.ok) {
            const profileData = await profileRes.json();
            if (profileData.character_sheet) {
              setCharacterSheet(profileData.character_sheet);
            }
          }
        }
      } else {
        const blob = await resp.blob();
        const obj = URL.createObjectURL(blob);
        setDitheredPreviewUrl(prev => { if (prev) URL.revokeObjectURL(prev); return obj; });
      }
    } catch (e) {
      console.error('sendFile error', e);
    }
  };

  // --- DATA TRANSFORMATION LOGIC ---
  const displayData = useMemo(() => {
    return transformCharacterData(characterSheet, skillTree);
  }, [characterSheet, skillTree]);

  const handleOnboardingFinish = (data) => {
    if (data?.username) {
      setCharacterSheet(prev => ({ ...prev, user_id: data.username }));
    }
    setShowOnboarding(false);
  };

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  // After onboarding is dismissed, try to load the real profile from the backend.
  useEffect(() => {
    if (showOnboarding) return;

    const fetchProfile = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/profile/user_01');
        if (!res.ok) return; // keep fallback data on failure
        const data = await res.json();
        if (data.character_sheet) {
          setCharacterSheet(data.character_sheet);
          // Load avatar URL if available
          if (data.character_sheet.avatar_url) {
            setDitheredPreviewUrl(data.character_sheet.avatar_url);
          }
        }
        if (data.skill_tree) {
          setSkillTree(data.skill_tree);
        }
      } catch (e) {
        // Silent fallback to mock data
        console.error('Failed to load profile, using mock data.', e);
      }
    };

    fetchProfile();
  }, [showOnboarding]);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-900 flex flex-col items-center justify-center text-stone-200 font-mono">
        <div className="mb-4 animate-bounce"><FileText size={48} /></div>
        <div className="text-sm tracking-[0.3em] uppercase">Opening File...</div>
      </div>
    );
  }

  // --- ONBOARDING CHECK ---
  if (showOnboarding) {
    return <OnboardingModule onFinish={handleOnboardingFinish} />;
  }

  return (
    <div className={`min-h-screen font-sans selection:bg-yellow-200 overflow-x-hidden relative transition-colors duration-500 ${isLockIn ? 'bg-[#050505] text-[#39ff14]' : 'bg-stone-900 text-stone-800'}`}>
      
      {/* CSS For Scrollbar & Shapes */}
      <style>{`
        /* Slim grey scroll thumb with paper-colored track */
        .custom-scrollbar {
          scrollbar-width: thin;                    /* Firefox */
          scrollbar-color: #78716c #f4e9d5;         /* thumb / track colors */
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
          height: 5px;
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #f4e9d5; /* match transcript paper */
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #78716c;
          border-radius: 9999px;
          border: none;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #78716c;
        }
        .clip-hexagon { clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); }
      `}</style>

      {/* BACKGROUND */}
      <div className="fixed inset-0 z-0 bg-cover bg-center pointer-events-none" style={{ backgroundImage: `url('https://images.unsplash.com/photo-1615800098779-1be32e60cca3?q=80&w=2574&auto=format&fit=crop')` }}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.1)_0%,rgba(0,0,0,0.6)_100%)]" />
      </div>

      {/* HEADER */}
      <Header activeTab={activeTab} setActiveTab={setActiveTab} isLockIn={isLockIn} />

      {/* MAIN CONTENT AREA */}
      <main className="pt-24 pb-12 px-4 md:px-8 max-w-7xl mx-auto min-h-screen flex flex-col relative z-10">
        
        {/* VIEW 1: PROFILE DASHBOARD */}
        {activeTab === 'sheet' && (
          <ProfileView 
            displayData={displayData}
            ditheredPreviewUrl={ditheredPreviewUrl}
            fileInputRef={fileInputRef}
            takePhotoRef={takePhotoRef}
            sendFile={sendFile}
            selectedAlgorithm={selectedAlgorithm}
          />
        )}

        {/* VIEW 2: SKILL MAP (Dynamic Blueprint) */}
        {activeTab === 'map' && (
          <BlueprintView 
            skillTree={skillTree} 
            characterSheet={characterSheet} 
          />
        )}

        {/* VIEW 3: REPORT PAGE */}
        {activeTab === 'report' && (
          <ReportView displayData={displayData} />
        )}

        {/* VIEW 4: CALENDAR */}
        {activeTab === 'calendar' && <CalendarView />}

        {/* VIEW 5: LOCK-IN */}
        {activeTab === 'lockin' && (
          <LockInView 
            availableQuests={displayData.quests || []} 
            sendFile={sendFile} 
            selectedAlgorithm={selectedAlgorithm} 
            setSelectedAlgorithm={setSelectedAlgorithm}
            ditheredPreviewUrl={ditheredPreviewUrl} 
            setDitheredPreviewUrl={setDitheredPreviewUrl} 
            fileInputRef={fileInputRef} 
            takePhotoRef={takePhotoRef} 
          />
        )}

      </main>
    </div>
  );
}
