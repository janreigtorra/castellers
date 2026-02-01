import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import ChatInterface from './components/ChatInterface';
import Header from './components/Header';
import SessionManager from './components/SessionManager';
import WelcomePage from './components/WelcomePage';
import JocDelMocador from './components/JocDelMocador/index';
import ColorSelector from './components/ColorSelector';
import ProfileModal from './components/ProfileModal';
import AboutPage from './components/AboutPage';
import ContactPage from './components/ContactPage';
import PilarLoader from './components/PilarLoader';
import { authHelpers } from './supabaseClient';
import { getColorPreference, saveColorPreference, getCurrentTheme, getUserDefaultColor, getThemeForColor } from './colorTheme';

function App() {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [selectedColor, setSelectedColor] = useState(getColorPreference());
  const [theme, setTheme] = useState(getCurrentTheme());
  const [unsavedMessagesCount, setUnsavedMessagesCount] = useState(0);
  const [newConversationKey, setNewConversationKey] = useState(0); // Key to force new conversation
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false); // Track if chat input is focused (for mobile keyboard)
  const saveChatRef = useRef(null);
  
  // Derive currentPage from URL
  const getPageFromPath = useCallback(() => {
    const path = window.location.pathname;
    if (path === '/joc-del-mocador') return 'joc-del-mocador';
    if (path === '/sobre-xiquet-ai') return 'about';
    if (path === '/contacte') return 'contact';
    return 'chat';
  }, []);
  
  const [currentPage, setCurrentPageState] = useState(getPageFromPath);
  
  const setCurrentPage = useCallback((page) => {
    let path = '/';
    if (page === 'joc-del-mocador') path = '/joc-del-mocador';
    else if (page === 'about') path = '/sobre-xiquet-ai';
    else if (page === 'contact') path = '/contacte';
    
    window.history.pushState({}, '', path);
    setCurrentPageState(page);
  }, []);
  
  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPageState(getPageFromPath());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [getPageFromPath]);

  useEffect(() => {
    // Check if user is logged in with Supabase
    const checkAuth = async () => {
      try {
        const { user, error } = await authHelpers.getCurrentUser();
        if (user && !error) {
          setUser({
            id: user.id,
            username: user.user_metadata?.username || user.email?.split('@')[0],
            email: user.email
          });
          
          // Load user's colla color as their default
          const userCollaColor = getUserDefaultColor(user.id);
          if (userCollaColor) {
            setSelectedColor(userCollaColor);
            setTheme(getThemeForColor(userCollaColor));
          }
        }
      } catch (error) {
        console.error('Auth check failed:', error);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();

    // Listen to auth state changes
    const { data: { subscription } } = authHelpers.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session?.user) {
        setUser({
          id: session.user.id,
          username: session.user.user_metadata?.username || session.user.email?.split('@')[0],
          email: session.user.email
        });
        
        // Load user's colla color as their default
        const userCollaColor = getUserDefaultColor(session.user.id);
        if (userCollaColor) {
          setSelectedColor(userCollaColor);
          setTheme(getThemeForColor(userCollaColor));
        }
      } else if (event === 'SIGNED_OUT') {
        setUser(null);
        // Reset to default white when user logs out
        setSelectedColor('white');
        setTheme(getThemeForColor('white'));
      }
    });

    return () => subscription?.unsubscribe();
  }, []);

  // Update theme when color changes
  useEffect(() => {
    saveColorPreference(selectedColor);
    const newTheme = getCurrentTheme();
    setTheme(newTheme);
  }, [selectedColor]);

  // Apply CSS variables when theme changes
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--theme-primary', theme.primary);
    root.style.setProperty('--theme-secondary', theme.secondary);
    root.style.setProperty('--theme-accent', theme.accent);
    root.style.setProperty('--theme-background', theme.background);
    root.style.setProperty('--theme-text', theme.text);
    root.style.setProperty('--theme-text-secondary', theme.textSecondary);
    root.style.setProperty('--theme-border', theme.border);
    root.style.setProperty('--theme-highlight', theme.highlight);
  }, [theme]);

  const handleColorChange = (color) => {
    setSelectedColor(color);
  };

  const handleProfileUpdate = (updatedUser) => {
    setUser(prev => ({
      ...prev,
      ...updatedUser
    }));
  };

  const handleLogin = (userData) => {
    setUser(userData);
  };

  const handleNewSession = (sessionId) => {
    setCurrentSessionId(sessionId);
    // If creating a new unsaved conversation, clear localStorage and increment key to force reset
    if (sessionId === null) {
      // Clear unsaved chat from localStorage before creating new conversation
      if (user?.id) {
        try {
          localStorage.removeItem(`unsaved_chat_${user.id}`);
        } catch (error) {
          console.error('Error clearing unsaved chat on new conversation:', error);
        }
      }
      setNewConversationKey(prev => prev + 1);
    }
  };

  const handleSessionChange = (sessionId) => {
    setCurrentSessionId(sessionId);
  };

  const handleSessionSaved = (sessionId) => {
    // When a chat is saved, switch to that session
    setCurrentSessionId(sessionId);
    // Reload sessions list (this will be handled by SessionManager's useEffect)
  };

  const handleLogout = async () => {
    try {
      // Clear unsaved chat from localStorage before logout
      if (user?.id) {
        try {
          localStorage.removeItem(`unsaved_chat_${user.id}`);
        } catch (error) {
          console.error('Error clearing unsaved chat on logout:', error);
        }
      }
      await authHelpers.signOut();
      setUser(null);
      setCurrentSessionId(null);
    } catch (error) {
      console.error('Logout error:', error);
      // Still set user to null even if logout fails
      setUser(null);
      setCurrentSessionId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="app">
        <PilarLoader />
      </div>
    );
  }

  return (
    <div className="app" style={{ '--theme-color': theme.secondary, '--theme-accent': theme.accent }}>
      {user ? (
        <>
          <Header 
            user={user} 
            onLogin={handleLogin} 
            onLogout={handleLogout} 
            theme={theme}
            currentPage={currentPage}
            onPageChange={setCurrentPage}
            onOpenProfile={() => setShowProfileModal(true)}
            onOpenAbout={() => setCurrentPage('about')}
          />
          {currentPage === 'chat' ? (
            <div className="app-with-sessions">
              <SessionManager 
                currentSessionId={currentSessionId}
                onSessionChange={handleSessionChange}
                onNewSession={handleNewSession}
                theme={theme}
                isUnsaved={!currentSessionId && unsavedMessagesCount > 0}
                onSaveClick={() => {
                  if (saveChatRef.current) {
                    saveChatRef.current();
                  }
                }}
              />
              <main className="main-content-with-sessions">
                <ChatInterface 
                  key={newConversationKey}
                  user={user} 
                  sessionId={currentSessionId} 
                  theme={theme}
                  onSessionSaved={handleSessionSaved}
                  onSaveClick={saveChatRef}
                  onMessagesChange={setUnsavedMessagesCount}
                  onCollaIdentified={handleColorChange}
                  onInputFocusChange={setIsInputFocused}
                />
              </main>
            </div>
          ) : currentPage === 'joc-del-mocador' ? (
            <main className="main-content-with-sessions">
              <JocDelMocador 
                theme={theme}
                onBack={() => setCurrentPage('chat')}
                onColorChange={handleColorChange}
                selectedColor={selectedColor}
              />
            </main>
          ) : currentPage === 'about' ? (
            <main className="main-content-with-sessions">
              <AboutPage theme={theme} onBack={() => setCurrentPage('chat')} />
            </main>
          ) : currentPage === 'contact' ? (
            <main className="main-content-with-sessions">
              <ContactPage theme={theme} onBack={() => setCurrentPage('chat')} />
            </main>
          ) : null}
          <ColorSelector 
            selectedColor={selectedColor}
            onColorChange={handleColorChange}
            hideOnMobile={isInputFocused}
          />
          {showProfileModal && (
            <ProfileModal
              user={user}
              onClose={() => setShowProfileModal(false)}
              onProfileUpdate={handleProfileUpdate}
              theme={theme}
              onCollaChange={handleColorChange}
            />
          )}
        </>
      ) : (
        <WelcomePage 
          selectedColor={selectedColor}
          onColorChange={handleColorChange}
          onLogin={handleLogin}
        />
      )}
    </div>
  );
}

export default App;
