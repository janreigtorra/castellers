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
import CollesCastelleres from './components/CollesCastelleres';
import CollaDetail from './components/CollaDetail';
import CompararDiades from './components/CompararDiades';
import AdminPendingQueriesPage from './components/AdminPendingQueriesPage';
import PilarLoader from './components/PilarLoader';
import AuthCallback from './components/AuthCallback';
import { authHelpers } from './supabaseClient';
import { getColorPreference, saveColorPreference, getCurrentTheme, getUserDefaultColor, getThemeForColor, getThemeActionColor } from './colorTheme';

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
  const [selectedCollaId, setSelectedCollaId] = useState(null);
  const saveChatRef = useRef(null);
  
  // Derive currentPage from URL
  const getPageFromPath = useCallback(() => {
    const path = window.location.pathname;
    if (path === '/auth/callback') return 'auth-callback';
    if (path === '/joc-del-mocador') return 'joc-del-mocador';
    if (path === '/sobre-xiquet-ai') return 'about';
    if (path === '/contacte') return 'contact';
    if (path === '/colles-castelleres') return 'colles-castelleres';
    if (path === '/comparar-diades') return 'comparar-diades';
    if (path === '/admin/consultes-usuaris') return 'admin-pending-queries';
    if (path.startsWith('/colles/')) {
      return 'colla-detail';
    }
    return 'chat';
  }, []);
  
  const [currentPage, setCurrentPageState] = useState(getPageFromPath);
  
  // Extract colla slug from URL when on colla-detail page
  useEffect(() => {
    if (currentPage === 'colla-detail') {
      const path = window.location.pathname;
      if (path.startsWith('/colles/')) {
        const collaSlug = path.replace('/colles/', '');
        setSelectedCollaId(collaSlug);
      }
    } else {
      setSelectedCollaId(null);
    }
  }, [currentPage]);
  
  const setCurrentPage = useCallback((page, collaId = null) => {
    let path = '/';
    if (page === 'joc-del-mocador') path = '/joc-del-mocador';
    else if (page === 'about') path = '/sobre-xiquet-ai';
    else if (page === 'contact') path = '/contacte';
    else if (page === 'colles-castelleres') path = '/colles-castelleres';
    else if (page === 'comparar-diades') path = '/comparar-diades';
    else if (page === 'admin-pending-queries') path = '/admin/consultes-usuaris';
    else if (page === 'colla-detail' && collaId) {
      path = `/colles/${collaId}`;
      setSelectedCollaId(collaId);
    }
    
    window.history.pushState({}, '', path);
    setCurrentPageState(page);
  }, []);
  
  const handleCollaClick = useCallback((collaSlug, collaId) => {
    // Use slug for URL, but keep ID for API calls
    setCurrentPage('colla-detail', collaSlug);
  }, [setCurrentPage]);
  
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
    // Focus rings / CTAs: red when shirt color is white so borders stay visible (login form, etc.)
    root.style.setProperty('--chat-action-color', getThemeActionColor(theme));
  }, [theme]);

  // SEO: document title and meta description per page (resets when leaving colla so tab no longer shows colla name)
  useEffect(() => {
    if (currentPage === 'auth-callback' || currentPage === 'colla-detail') return; // colla-detail sets its own; auth-callback is transient
    const metaDescription = document.querySelector('meta[name="description"]');
    let title = 'Xiquet.cat';
    let description = 'Xiquet - Assistent expert en el món casteller';
    if (currentPage === 'chat') {
      title = 'Xat - Xiquet.cat';
      description = 'Xat amb Xiquet: l\'assistent d\'intel·ligència artificial expert en castells. Fes preguntes sobre colles, diades i castells en català.';
    } else if (currentPage === 'joc-del-mocador') {
      title = 'El Joc del Mocador - Xiquet.cat';
      description = 'Juga al Joc del Mocador amb Xiquet.cat: el joc de preguntes sobre el món casteller. Posar les mans al mocador i demostra el que saps.';
    } else if (currentPage === 'about') {
      title = 'Sobre Xiquet.cat';
      description = 'Coneix Xiquet: l\'assistent IA expert en el món casteller. Informació sobre el projecte i les dades castelleres.';
    } else if (currentPage === 'contact') {
      title = 'Contacte - Xiquet.cat';
      description = 'Contacta amb l\'equip de Xiquet.cat. Suggeriments, errors o col·laboracions sobre el món casteller.';
    } else if (currentPage === 'colles-castelleres') {
      title = 'Colles Castelleres - Xiquet.cat';
      description = 'Descobreix totes les colles castelleres de Catalunya amb informació detallada sobre les seves millors diades i castells.';
    } else if (currentPage === 'comparar-diades') {
      title = 'Comparar Diades - Xiquet.cat';
      description = 'Compara diades castelleres: resultats, castells i estadístiques entre diferents actuacions.';
    } else if (currentPage === 'admin-pending-queries') {
      title = 'Seguiment consultes - Xiquet.cat';
      description = 'Panell d\'administració per al seguiment de consultes d\'usuaris.';
    }
    document.title = title;
    if (metaDescription) metaDescription.setAttribute('content', description);
  }, [currentPage]);

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

  // Handle auth callback route separately (before checking user)
  if (currentPage === 'auth-callback') {
    return <AuthCallback onAuthSuccess={handleLogin} />;
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
                  onOpenProfile={() => setShowProfileModal(true)}
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
          ) : currentPage === 'colles-castelleres' ? (
            <main className="main-content-with-sessions">
              <CollesCastelleres 
                theme={theme} 
                onBack={() => setCurrentPage('chat')}
                onCollaClick={handleCollaClick}
              />
            </main>
          ) : currentPage === 'colla-detail' ? (
            <main className="main-content-with-sessions">
              <CollaDetail 
                collaId={selectedCollaId}
                theme={theme} 
                onBack={() => setCurrentPage('colles-castelleres')}
              />
            </main>
          ) : currentPage === 'comparar-diades' ? (
            <main className="main-content-with-sessions">
              <CompararDiades 
                theme={theme} 
                onBack={() => setCurrentPage('chat')}
              />
            </main>
          ) : currentPage === 'admin-pending-queries' ? (
            <main className="main-content-with-sessions">
              <AdminPendingQueriesPage
                theme={theme}
                onBack={() => setCurrentPage('chat')}
              />
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
        <>
          <Header
            user={null}
            onLogin={handleLogin}
            onLogout={() => {}}
            theme={theme}
            currentPage={currentPage}
            onPageChange={setCurrentPage}
            onOpenAbout={() => setCurrentPage('about')}
          />
          <div className="app-guest-main">
            {currentPage === 'colles-castelleres' ? (
              <CollesCastelleres
                theme={theme}
                onBack={() => setCurrentPage('chat')}
                onCollaClick={handleCollaClick}
              />
            ) : currentPage === 'comparar-diades' ? (
              <CompararDiades
                theme={theme}
                onBack={() => setCurrentPage('chat')}
              />
            ) : currentPage === 'about' ? (
              <AboutPage theme={theme} onBack={() => setCurrentPage('chat')} />
            ) : currentPage === 'contact' ? (
              <ContactPage theme={theme} onBack={() => setCurrentPage('chat')} />
            ) : currentPage === 'colla-detail' ? (
              <CollaDetail
                collaId={selectedCollaId}
                theme={theme}
                onBack={() => setCurrentPage('colles-castelleres')}
              />
            ) : (
              <WelcomePage
                selectedColor={selectedColor}
                onColorChange={handleColorChange}
                onLogin={handleLogin}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default App;
