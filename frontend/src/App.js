import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import ChatInterface from './components/ChatInterface';
import Header from './components/Header';
import SessionManager from './components/SessionManager';
import WelcomePage from './components/WelcomePage';
import PassaFaixaGame from './components/PassaFaixaGame/index';
import ColorSelector from './components/ColorSelector';
import { authHelpers } from './supabaseClient';
import { getColorPreference, saveColorPreference, getCurrentTheme } from './colorTheme';

function App() {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [selectedColor, setSelectedColor] = useState(getColorPreference());
  const [theme, setTheme] = useState(getCurrentTheme());
  const [unsavedMessagesCount, setUnsavedMessagesCount] = useState(0);
  const [newConversationKey, setNewConversationKey] = useState(0); // Key to force new conversation
  const [currentPage, setCurrentPage] = useState('chat'); // 'chat' or 'passafaixa'
  const saveChatRef = useRef(null);

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
      } else if (event === 'SIGNED_OUT') {
        setUser(null);
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
        <div className="loading">Carregant Xiquet...</div>
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
              />
            </main>
          </div>
          ) : (
            <main className="main-content-with-sessions">
              <PassaFaixaGame 
                theme={theme}
                onBack={() => setCurrentPage('chat')}
              />
            </main>
          )}
          <ColorSelector 
            selectedColor={selectedColor}
            onColorChange={handleColorChange}
          />
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
