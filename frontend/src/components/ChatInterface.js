import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiService } from '../apiService';
import { COLOR_THEMES } from '../colorTheme';
import WelcomeMessage from './WelcomeMessage';
import CastellLoader from './CastellLoader';
import PilarLoader from './PilarLoader';

// Hook to detect mobile screen
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(() => {
    return typeof window !== 'undefined' && window.innerWidth <= 768;
  });

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return isMobile;
};

// Mapping from colles_fundacio.json color_code to colorTheme.js keys
const COLOR_CODE_TO_THEME = {
  'darkgreen': 'darkgreen',
  'skyblue': 'bluesky',
  'turquese': 'turquese',
  'lightgreen': 'lightgreen',
  'yellow': 'yellow',
  'darkblue': 'darkblue',
  'lila': 'lila',
  'granate': 'granate',
  'blue': 'blue',
  'red': 'red',
  'green': 'green',
  'brown': 'brown',
  'gray': 'gray',
  'rosat': 'rosat',
  'malva': 'malva',
  'orange': 'orange',
  'white': 'white',
  'darkturquesa': 'darkturquesa',
  'ralles': 'ralles'
};

// Colles to color_code mapping (loaded from colles_fundacio.json data)
const COLLES_COLORS = {
  "Al·lots de Llevant": "darkgreen",
  "Angelets de Vallespir": "skyblue",
  "Arreplegats de la Zona Universitària": "turquese",
  "Bergants del Campus de Terrassa": "lightgreen",
  "Bordegassos de Vilanova": "yellow",
  "Brivalls de Cornudella": "darkblue",
  "Capgrossos de Mataró": "darkblue",
  "Castellers d'Altafulla": "lila",
  "La Global": "darkblue",
  "Castellers d'Andorra": "granate",
  "Castellers d'Esparreguera": "granate",
  "Castellers d'Esplugues": "blue",
  "Castellers de Badalona": "yellow",
  "Castellers de Barcelona": "red",
  "Castellers de Berga": "darkblue",
  "Castellers de Caldes de Montbui": "darkgreen",
  "Castellers de Castellar del Vallès": "granate",
  "Castellers de Castelldefels": "yellow",
  "Castellers de Cerdanyola": "green",
  "Castellers de Cornellà": "lila",
  "Castellers de Terrassa": "darkturquesa",
  "Castellers de la Sagrada Família": "green",
  "Castellers de la Vila de Gràcia": "darkblue",
  "Castellers de les Gavarres": "brown",
  "Castellers de les Roquetes": "gray",
  "Castellers de Lleida": "granate",
  "Castellers de Mallorca": "granate",
  "Castellers de Mediona": "darkblue",
  "Castellers de Mollet": "lightgreen",
  "Castellers de Montcada i Reixac": "orange",
  "Castellers de Rubí": "red",
  "Castellers de Sabadell": "darkgreen",
  "Castellers de Sant Adrià": "granate",
  "Castellers de Sant Cugat": "darkgreen",
  "Castellers de Tortosa": "granate",
  "Castellers de Sant Feliu": "rosat",
  "Castellers de Sant Vicenç dels Horts": "orange",
  "Castellers de Santa Coloma": "skyblue",
  "Castellers de Santpedor": "yellow",
  "Castellers de Sants": "gray",
  "Castellers de Sarrià": "granate",
  "Castellers de Solsona": "yellow",
  "Castellers del Poble Sec": "skyblue",
  "Castellers de Viladecans": "lightgreen",
  "Castellers de Vilafranca": "turquese",
  "Castellers del Baix Montseny": "blue",
  "Castellers del Foix de Cubelles": "white",
  "Castellers del Pallars": "white",
  "Castellers del Prat de Llobregat": "blue",
  "Castellers del Riberal": "green",
  "Colla Castellera de Figueres": "lila",
  "Colla Castellera de Gavà": "blue",
  "Colla Castellera Els Encantats de Begues": "darkgreen",
  "Colla Castellera de l'Alt Maresme i la Selva Marítima": "red",
  "Colla Castellera de l'Esquerra de l'Eixample": "lila",
  "Colla Castellera de la Gavarresa": "granate",
  "Colla Castellera de Madrid": "red",
  "Colla Castellera Jove de Barcelona": "granate",
  "Colla Castellera La Bisbal del Penedès": "orange",
  "Colla Castellera Nyerros de la Plana": "gray",
  "Colla Castellera Sant Pere i Sant Pau": "green",
  "Colla Jove de Castellers de Sitges": "granate",
  "Colla Jove de l'Hospitalet": "green",
  "Colla Jove Xiquets de Tarragona": "malva",
  "Colla Jove Xiquets de Vilafranca": "darkblue",
  "Colla Joves Xiquets de Valls": "red",
  "Colla Vella dels Xiquets de Valls": "rosat",
  "Engrescats de URL": "yellow",
  "Esperxats de l'Estany": "darkturquesa",
  "Ganàpies de la UAB": "blue",
  "Laietans de Gramenet": "green",
  "Llunàtics UPC Vilanova": "blue",
  "Los Xics Caleros": "skyblue",
  "Manyacs de Parets": "malva",
  "Margeners de Guissona": "brown",
  "Marrecs de Salt": "blue",
  "Matossers de Molins de Rei": "brown",
  "Minyons de l'Arboç": "red",
  "Minyons de Santa Cristina d'Aro": "lightgreen",
  "Tirallongues de Manresa": "gray",
  "Minyons de Terrassa": "malva",
  "Moixiganguers d'Igualada": "lila",
  "Nens del Vendrell": "red",
  "Nois de la Torre": "skyblue",
  "Torraires de Montblanc": "granate",
  "Passerells del TCM": "malva",
  "Pataquers de la URV": "orange",
  "Penjats del Campus de Manresa": "red",
  "Sagals d'Osona": "orange",
  "Salats de Súria": "rosat",
  "Trempats de la UPF": "brown",
  "Vailets de Gelida": "lightgreen",
  "Vailets de l'Empordà": "skyblue",
  "Xerrics d'Olot": "granate",
  "Xicots de Vilafranca": "red",
  "Xics de Granollers": "granate",
  "Xiqüelos i Xiqüeles del Delta": "blue",
  "Xiquets d'Alcover": "white",
  "Xiquets de Cambrils": "granate",
  "Xiquets de Reus": "brown",
  "Xiquets de Tarragona": "ralles",
  "Xiquets de Vila-seca": "skyblue",
  "Xiquets del Serrallo": "darkblue",
  "Xoriguers de la UdG": "blue",
  "Pallagos del Conflent": "granate",
  "Emboirats de la Universitat de Vic": "red",
  "Colla Castellera de Cerdanya": "white",
  "Xiquets de Montblanc": "white",
  "Xiquets de Torredembarra": "white",
  "Descargolats de l'EEBE": "white",
  "Grillats del Campus del Baix Llobregat": "white",
  "Marracos de la Universitat de Lleida": "gray"
};

// SVG Icons for entity chips
const CollaIcon = ({ color = "currentColor" }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {/* Center person (front) */}
    <circle cx="12" cy="7" r="3" />
    <path d="M7 21v-2a5 5 0 0 1 10 0v2" />
    {/* Left person (back) */}
    <circle cx="5" cy="8" r="2" />
    <path d="M1 21v-1a4 4 0 0 1 4-4" />
    {/* Right person (back) */}
    <circle cx="19" cy="8" r="2" />
    <path d="M23 21v-1a4 4 0 0 0-4-4" />
  </svg>
);

const CastellIcon = ({ color = "currentColor" }) => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {/* Base */}
    <circle cx="8" cy="18" r="2" />
    <circle cx="16" cy="18" r="2" />
    <line x1="8" y1="16" x2="8" y2="14" />
    <line x1="16" y1="16" x2="16" y2="14" />

    {/* Segon pis */}
    <circle cx="12" cy="13" r="2" />
    <line x1="12" y1="11" x2="12" y2="9" />

    {/* Enxaneta */}
    <circle cx="12" cy="7" r="1.5" />
  </svg>
);


const CalendarIcon = ({ color = "currentColor" }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4" />
    <path d="M8 2v4" />
    <path d="M3 10h18" />
    <path d="M8 14h.01" />
    <path d="M12 14h.01" />
    <path d="M16 14h.01" />
    <path d="M8 18h.01" />
    <path d="M12 18h.01" />
  </svg>
);

const LocationIcon = ({ color = "currentColor" }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
    <circle cx="12" cy="9" r="2.5" />
  </svg>
);

const DiadaIcon = ({ color = "currentColor" }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
  </svg>
);

// Gamma icon (layers/levels)
const GammaIcon = ({ color = "currentColor" }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="4" rx="1" />
    <rect x="5" y="9" width="14" height="4" rx="1" />
    <rect x="7" y="15" width="10" height="4" rx="1" />
  </svg>
);

// Helper to check if there are any entities to display
const hasEntities = (entities) => {
  if (!entities) return false;
  return (
    (entities.colles && entities.colles.length > 0) ||
    (entities.castells && entities.castells.length > 0) ||
    (entities.anys && entities.anys.length > 0) ||
    (entities.llocs && entities.llocs.length > 0) ||
    (entities.diades && entities.diades.length > 0) ||
    (entities.gamma)
  );
};

const ChatInterface = ({ user, sessionId, theme, onSessionSaved, onSaveClick, onMessagesChange, onCollaIdentified }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveTitle, setSaveTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [thinkingFrame, setThinkingFrame] = useState(1); // For animation: 1 or 2
  const [expandedTables, setExpandedTables] = useState(new Set()); // Track expanded tables
  const [identifiedEntities, setIdentifiedEntities] = useState(null); // Track entities identified by the agent
  const messagesEndRef = useRef(null);
  const previousSessionIdRef = useRef(null); // Track previous sessionId to detect new conversation
  const tableCounterRef = useRef(0); // Table counter for generating unique IDs
  const tableInstanceMapRef = useRef(new Map()); // Map to track table instances and their IDs
  const [thinkingDots, setThinkingDots] = useState('');
  const isMobile = useIsMobile();

  // Helper functions for localStorage persistence
  const getUnsavedChatKey = useCallback(() => {
    return user ? `unsaved_chat_${user.id}` : null;
  }, [user]);

  const saveUnsavedChatToStorage = useCallback((messagesToSave) => {
    const key = getUnsavedChatKey();
    if (key && !sessionId) {
      try {
        localStorage.setItem(key, JSON.stringify(messagesToSave));
      } catch (error) {
        console.error('Error saving unsaved chat to localStorage:', error);
      }
    }
  }, [getUnsavedChatKey, sessionId]);

  const loadUnsavedChatFromStorage = useCallback(() => {
    const key = getUnsavedChatKey();
    if (key && !sessionId) {
      try {
        const saved = localStorage.getItem(key);
        if (saved) {
          return JSON.parse(saved);
        }
      } catch (error) {
        console.error('Error loading unsaved chat from localStorage:', error);
      }
    }
    return null;
  }, [getUnsavedChatKey, sessionId]);

  const clearUnsavedChatFromStorage = useCallback(() => {
    const key = getUnsavedChatKey();
    if (key) {
      try {
        localStorage.removeItem(key);
      } catch (error) {
        console.error('Error clearing unsaved chat from localStorage:', error);
      }
    }
  }, [getUnsavedChatKey]);

  // Expose save dialog trigger to parent via ref
  useEffect(() => {
    if (onSaveClick && typeof onSaveClick === 'object') {
      // If it's a ref object, set the current function
      onSaveClick.current = () => {
        if (messages.length > 0) {
          setShowSaveDialog(true);
        }
      };
    }
  }, [onSaveClick, messages]);

  // Notify parent of complete conversation count (messages with answers)
  // Only count assistant messages (which have responses) as complete conversations
  useEffect(() => {
    if (onMessagesChange && !sessionId) {
      // Count only messages that have responses (complete conversations)
      const completeConversations = messages.filter(msg => 
        !msg.isUser && msg.response && msg.response.trim().length > 0
      ).length;
      onMessagesChange(completeConversations);
    } else if (onMessagesChange) {
      onMessagesChange(0);
    }
  }, [messages, sessionId, onMessagesChange]);

  // Persist unsaved messages to localStorage whenever they change
  useEffect(() => {
    if (!sessionId && user) {
      saveUnsavedChatToStorage(messages);
    }
  }, [messages, sessionId, user, saveUnsavedChatToStorage]);

  // Scroll to bottom - optionally force scroll regardless of user position
  const scrollToBottom = (force = false) => {
    if (!messagesEndRef.current) return;
    
    const messagesContainer = messagesEndRef.current.parentElement;
    if (!messagesContainer) return;

    const scrollHeight = messagesContainer.scrollHeight;
    const clientHeight = messagesContainer.clientHeight;
    const currentScrollTop = messagesContainer.scrollTop;
    
    // Check if scroll is needed (content exceeds container height)
    const needsScroll = scrollHeight > clientHeight;
    if (!needsScroll) {
      return; // Content fits, no scroll needed
    }

    // If force is true, always scroll to bottom (for new messages after thinking)
    if (force) {
      messagesContainer.scrollTop = scrollHeight - clientHeight;
      return;
    }

    // Calculate distance from bottom
    const distanceFromBottom = scrollHeight - currentScrollTop - clientHeight;
    
    // Only scroll if user is already near the bottom (within 200px)
    // This prevents scrolling when user is reading old messages
    if (distanceFromBottom < 200) {
      messagesContainer.scrollTop = scrollHeight - clientHeight;
    }
  };

  // Track previous loading state to detect when loading completes (new message arrived)
  const prevLoadingRef = useRef(isLoading);

  // Only scroll when messages are added AND loading is false (response received)
  // This prevents scrolling when "Xiquet està pensant..." appears
  useEffect(() => {
    // Don't scroll during loading - wait for the response
    if (isLoading) {
      prevLoadingRef.current = isLoading;
      return;
    }
    
    // Only scroll if we have messages
    if (messages.length === 0) {
      prevLoadingRef.current = isLoading;
      return;
    }

    // If loading just completed (was true, now false), force scroll to show new message
    const justFinishedLoading = prevLoadingRef.current === true && isLoading === false;
    
    // Scroll after a delay to ensure DOM is updated
    const timeoutId = setTimeout(() => {
      scrollToBottom(justFinishedLoading);
    }, 200);
    
    prevLoadingRef.current = isLoading;
    return () => clearTimeout(timeoutId);
  }, [messages.length, isLoading]); // Scroll when messages change AND loading is done

  // Animate thinking images when loading
  // Frame 1 shows for 1 second, then Frame 2 shows for 0.5 seconds
  useEffect(() => {
    if (!isLoading) {
      setThinkingFrame(1);
      return;
    }

    setThinkingFrame(1);
    let timeout1, timeout2;
    let isActive = true;

    const animate = () => {
      if (!isActive) return;
      
      // Frame 1 for 1 second
      timeout1 = setTimeout(() => {
        if (!isActive) return;
        setThinkingFrame(2);
        
        // Frame 2 for 0.5 seconds
        timeout2 = setTimeout(() => {
          if (!isActive) return;
          setThinkingFrame(1);
          animate(); // Continue animation loop
        }, 500); // 0.5 seconds for frame 2
      }, 1000); // 1 second for frame 1
    };

    animate();

    return () => {
      isActive = false;
      if (timeout1) clearTimeout(timeout1);
      if (timeout2) clearTimeout(timeout2);
    };
  }, [isLoading]);

  // Load chat history on component mount or session change
  useEffect(() => {
    const loadHistory = async () => {
      try {
        // Detect if this is a new conversation (sessionId changed from non-null to null)
        const isNewConversation = previousSessionIdRef.current !== null && sessionId === null;
        
        if (sessionId) {
          // Clear unsaved chat from storage when switching to a saved session
          clearUnsavedChatFromStorage();
          const history = await apiService.getChatHistory(sessionId);
          console.log('[ChatInterface] Loaded history:', history.length, 'messages');
          // Backend returns messages in correct order (oldest first)
          // User message comes before assistant response for each pair
          // Sort by timestamp to ensure correct order (oldest first, newest last)
          const sortedHistory = [...history].sort((a, b) => {
            const timeA = new Date(a.timestamp).getTime();
            const timeB = new Date(b.timestamp).getTime();
            if (timeA !== timeB) return timeA - timeB;
            // If same timestamp, user message should come before assistant
            if (a.isUser && !b.isUser) return -1;
            if (!a.isUser && b.isUser) return 1;
            return 0;
          });
          setMessages(sortedHistory);
          // Scroll to bottom after loading history
          setTimeout(() => scrollToBottom(true), 200);
        } else {
          // No session
          if (isNewConversation) {
            // This is a new conversation - clear everything
            console.log('[ChatInterface] New conversation - clearing messages and localStorage');
            clearUnsavedChatFromStorage();
            setMessages([]);
            setInputMessage(''); // Clear input field
            setError(''); // Clear any errors
          } else {
            // First load or returning to unsaved chat - try to load from localStorage
            const savedMessages = loadUnsavedChatFromStorage();
            if (savedMessages && savedMessages.length > 0) {
              console.log('[ChatInterface] Restored unsaved chat from localStorage:', savedMessages.length, 'messages');
              setMessages(savedMessages);
              // Scroll to bottom after loading from localStorage
              setTimeout(() => scrollToBottom(true), 200);
            } else {
              // No saved messages - start fresh
              setMessages([]);
            }
          }
        }
        
        // Update previous sessionId ref
        previousSessionIdRef.current = sessionId;
      } catch (error) {
        console.error('Error loading chat history:', error);
      }
    };

    if (user) {
      loadHistory();
    }
  }, [user, sessionId, clearUnsavedChatFromStorage, loadUnsavedChatFromStorage]);

  // Core function to send a message (used by both form submit and question chips)
  // Uses the NEW polling-based approach for progressive updates
  const sendMessageContent = async (messageContent) => {
    if (!messageContent.trim() || isLoading) return;
    const tempId = `temp_${Date.now()}`;
    
    const userMessage = {
      id: `${tempId}_user`,
      content: messageContent,
      response: '',
      route_used: '',
      timestamp: new Date().toISOString(),
      response_time_ms: 0,
      isUser: true
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError('');
    setIdentifiedEntities(null); // Clear previous entities
    // Note: scroll will be handled by useEffect when messages.length changes

    try {
      // Callback to handle entities as soon as they arrive (FAST ~500-1000ms)
      // This is called BEFORE the full response is ready
      const handleEntitiesReceived = (entities, routeUsed) => {
        console.log('[ChatInterface] 🎯 ENTITIES RECEIVED (fast path)!', entities);
        console.log('[ChatInterface] Setting identifiedEntities state NOW');
        
        // Force immediate state update - chips will appear!
        setIdentifiedEntities(entities);
        
        // If a colla was identified, change the app color theme
        if (entities.colles && entities.colles.length > 0) {
          const firstColla = entities.colles[0];
          console.log('[ChatInterface] Colla identified:', firstColla);
          const colorCode = COLLES_COLORS[firstColla];
          if (colorCode && onCollaIdentified) {
            const themeKey = COLOR_CODE_TO_THEME[colorCode];
            if (themeKey && COLOR_THEMES[themeKey]) {
              console.log('[ChatInterface] Changing theme to:', themeKey);
              onCollaIdentified(themeKey);
            }
          }
        }
      };

      // Build previous context from the last assistant message (for follow-up questions)
      // This enables context without requiring session_id / database storage
      let previousContext = null;
      const assistantMessages = messages.filter(msg => !msg.isUser && msg.response);
      if (assistantMessages.length > 0) {
        const lastAssistant = assistantMessages[assistantMessages.length - 1];
        const entities = lastAssistant.identified_entities || {};
        previousContext = {
          question: lastAssistant.content,
          response: lastAssistant.response?.substring(0, 300), // Truncate response
          route: lastAssistant.route_used || null,
          sql_query_type: entities.sql_query_type || null,
          entities: {
            colles: entities.colles || [],
            castells: (entities.castells || []).map(c => typeof c === 'string' ? c : c.castell_code),
            anys: entities.anys || [],
            llocs: entities.llocs || [],
            diades: entities.diades || []
          }
        };
        console.log('[ChatInterface] 📋 Sending previous context:', previousContext);
      }

      // Use NEW polling-based approach:
      // 1. Backend starts processing, returns message_id immediately
      // 2. Frontend polls /api/chat/status every 300ms
      // 3. handleEntitiesReceived is called as soon as entities are ready (FAST)
      // 4. Promise resolves when full response is ready (SLOW)
      const response = await apiService.sendMessageWithPolling(
        messageContent, 
        sessionId, 
        handleEntitiesReceived,
        previousContext
      );

      console.log('[ChatInterface] ✅ Full response received');

      // Replace temporary user message and add assistant response
      const userMessageFromDb = {
        id: `${response.id}_user`,
        content: messageContent,
        response: '',
        route_used: '',
        timestamp: response.timestamp,
        response_time_ms: 0,
        isUser: true
      };

      const assistantMessage = {
        id: response.id,
        content: messageContent,
        response: response.response,
        route_used: response.route_used || '',
        timestamp: response.timestamp,
        response_time_ms: response.response_time_ms || 0,
        isUser: false,
        table_data: response.table_data || null,  // Table data from SQL queries
        identified_entities: response.identified_entities || null  // Store entities with the message
      };

      // Replace temporary message with real messages from database
      setMessages(prev => {
        // Remove temporary message
        const filtered = prev.filter(msg => msg.id !== userMessage.id);
        // Add real user message and assistant response
        const updated = [...filtered, userMessageFromDb, assistantMessage];
        // Sort by timestamp to ensure correct order (oldest first, newest last)
        return updated.sort((a, b) => {
          const timeA = new Date(a.timestamp).getTime();
          const timeB = new Date(b.timestamp).getTime();
          if (timeA !== timeB) return timeA - timeB;
          // If same timestamp, user message should come before assistant
          if (a.isUser && !b.isUser) return -1;
          if (!a.isUser && b.isUser) return 1;
          return 0;
        });
      });
      // Note: scroll will be handled by useEffect when messages.length changes

    } catch (error) {
      setError(error.response?.data?.detail || error.message || 'Error enviant el missatge');
      console.error('Error sending message:', error);
      // Remove the user message if sending failed
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
    } finally {
      setIsLoading(false);
    }
  };

  // Form submit handler
  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;
    const messageContent = inputMessage.trim();
    setInputMessage('');
    await sendMessageContent(messageContent);
  };

  // Handler for clicking on question chips in the welcome screen
  const handleQuestionClick = (question) => {
    sendMessageContent(question);
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('ca-ES', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getRouteDisplayName = (route) => {
    const routeNames = {
      'direct': 'Resposta directa',
      'rag': 'Cerca semàntica',
      'sql': 'Consulta de dades',
      'hybrid': 'Combinat',
      'unknown': 'Desconegut'
    };
    return routeNames[route] || route;
  };

  const handleSaveChat = async (e) => {
    e.preventDefault();
    if (!saveTitle.trim() || isSaving) return;

    // Filter out loading/temporary user messages that don't have responses yet
    const completeMessages = messages.filter(msg => {
      // Include messages that have a response (assistant messages)
      // or user messages that are part of a complete pair
      if (!msg.isUser && msg.response) return true;
      if (msg.isUser) {
        // Check if there's a corresponding assistant message
        const hasResponse = messages.some(m => !m.isUser && m.content === msg.content);
        return hasResponse;
      }
      return false;
    });

    if (completeMessages.length === 0) {
      setError('No hi ha missatges per guardar');
      return;
    }

    setIsSaving(true);
    try {
      const savedSession = await apiService.saveChatSession(saveTitle.trim(), completeMessages);
      // Clear unsaved chat from storage after successful save
      clearUnsavedChatFromStorage();
      setShowSaveDialog(false);
      setSaveTitle('');
      // Notify parent to switch to the saved session
      if (onSessionSaved) {
        onSessionSaved(savedSession.id);
      }
    } catch (error) {
      setError(error.response?.data?.detail || 'Error guardant la conversa');
      console.error('Error saving chat:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // Check if chat is unsaved (no sessionId and has messages)
  const isUnsaved = !sessionId && messages.length > 0;
  
  // Check if we have complete conversations (messages with answers)
  const hasCompleteConversations = messages.some(msg => !msg.isUser && msg.response && msg.response.trim().length > 0);

  // DataTable component for displaying SQL query results
  const DataTable = ({ tableData }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    
    if (!tableData || !tableData.rows || tableData.rows.length === 0) {
      return null;
    }
    
    const { title, columns, rows } = tableData;
    // On mobile, show only 1 row; on desktop show 3
    const collapsedRowCount = isMobile ? 1 : 3;
    const shouldCollapse = rows.length > collapsedRowCount;
    const displayedRows = shouldCollapse && !isExpanded ? rows.slice(0, collapsedRowCount) : rows;
    
    // Determine button colors based on theme
    const isWhiteTheme = theme?.secondary && 
      (theme.secondary.toLowerCase() === '#ffffff' || 
       theme.secondary.toLowerCase() === '#fff' ||
       theme.secondary.toLowerCase() === 'white');
    const buttonBgColor = isWhiteTheme ? '#808080' : (theme?.secondary || '#d0282c');
    const buttonHoverColor = isWhiteTheme ? '#666666' : (theme?.accent || '#b02226');
    
    return (
      <div className="data-table-container">
        {/* {title && <div className="data-table-title">Referencia a la base de dades: {title}</div>} */}
        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((col, idx) => (
                  <th key={idx} title={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayedRows.map((row, rowIdx) => (
                <tr key={rowIdx}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx}>{cell}</td>
                  ))}
                </tr>
              ))}
              {shouldCollapse && (
                <tr 
                  className="table-expand-row"
                  onClick={() => setIsExpanded(!isExpanded)}
                  style={{ 
                    '--row-bg-color': buttonBgColor,
                    '--row-hover-color': buttonHoverColor
                  }}
                >
                  <td colSpan={columns.length}>
                    <svg 
                      width="16" 
                      height="16" 
                      viewBox="0 0 16 16" 
                      fill="none" 
                      xmlns="http://www.w3.org/2000/svg"
                      style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
                    >
                      <path 
                        d="M4 6L8 10L12 6" 
                        stroke="white" 
                        strokeWidth="2" 
                        strokeLinecap="round" 
                        strokeLinejoin="round"
                      />
                    </svg>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // Collapsible table component for tables with more than 2 rows
  // Must be defined before any early returns to satisfy React Hooks rules
  const CollapsibleTable = React.useMemo(() => {
    return ({ children, ...props }) => {
      // Access theme from closure
      // Generate a stable ID based on table structure
      // Create a simple hash from children structure
      const childrenArrayForId = React.Children.toArray(children);
      const tableSignature = childrenArrayForId.length + '_' + 
        (childrenArrayForId[0]?.type?.toString() || '') + '_' +
        (childrenArrayForId[childrenArrayForId.length - 1]?.type?.toString() || '');
      
      // Check if we already have an ID for this table signature
      let tableId = tableInstanceMapRef.current.get(tableSignature);
      if (!tableId) {
        tableId = `table_${tableCounterRef.current++}`;
        tableInstanceMapRef.current.set(tableSignature, tableId);
        // Limit map size to prevent memory leaks
        if (tableInstanceMapRef.current.size > 100) {
          const firstKey = tableInstanceMapRef.current.keys().next().value;
          tableInstanceMapRef.current.delete(firstKey);
        }
      }
      
      const isExpanded = expandedTables.has(tableId);
      
      // Determine button background color (gray if theme color is white)
      const isWhiteColor = theme?.secondary && 
        (theme.secondary.toLowerCase() === '#ffffff' || 
         theme.secondary.toLowerCase() === '#fff' ||
         theme.secondary.toLowerCase() === 'white');
      const buttonBackgroundColor = isWhiteColor ? '#808080' : (theme?.secondary || '#d0282c');
      const buttonHoverColor = isWhiteColor ? '#666666' : (theme?.accent || '#b02226');
      
      // Count tbody rows (excluding thead)
      const childrenArrayForCount = React.Children.toArray(children);
      let tbodyElement = null;
      let rowCount = 0;
      
      // Find tbody element
      childrenArrayForCount.forEach(child => {
        if (child && typeof child === 'object' && 'type' in child) {
          if (child.type === 'tbody' || (child.props && child.props.children && child.type !== 'thead')) {
            tbodyElement = child;
          }
        }
      });
      
      // Count rows in tbody
      if (tbodyElement && tbodyElement.props && tbodyElement.props.children) {
        const tbodyRows = React.Children.toArray(tbodyElement.props.children);
        rowCount = tbodyRows.filter(row => {
          const rowType = row?.type || row?.props?.mdxType;
          return rowType === 'tr';
        }).length;
      }
      
      // On mobile, show only 1 row; on desktop show 2
      const collapsedRowCount = isMobile ? 1 : 2;
      const shouldCollapse = rowCount > collapsedRowCount;
      
      const toggleExpanded = () => {
        const newExpanded = new Set(expandedTables);
        if (isExpanded) {
          newExpanded.delete(tableId);
        } else {
          newExpanded.add(tableId);
        }
        setExpandedTables(newExpanded);
      };

      // Count columns for the expand row
      let columnCount = 1;
      const theadElement = childrenArrayForCount.find(child => 
        child && typeof child === 'object' && 'type' in child && child.type === 'thead'
      );
      if (theadElement && theadElement.props && theadElement.props.children) {
        const headerRow = React.Children.toArray(theadElement.props.children)[0];
        if (headerRow && headerRow.props && headerRow.props.children) {
          columnCount = React.Children.count(headerRow.props.children);
        }
      }

      // Create the expand/collapse row
      const expandRow = shouldCollapse ? (
        <tr 
          className="table-expand-row"
          onClick={toggleExpanded}
          style={{ 
            '--row-bg-color': buttonBackgroundColor,
            '--row-hover-color': buttonHoverColor,
            cursor: 'pointer'
          }}
        >
          <td colSpan={columnCount} style={{ textAlign: 'center', padding: '6px 0' }}>
            <svg 
              width="16" 
              height="16" 
              viewBox="0 0 16 16" 
              fill="none" 
              xmlns="http://www.w3.org/2000/svg"
              style={{ 
                transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s ease'
              }}
            >
              <path 
                d="M4 6L8 10L12 6" 
                stroke="white" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
          </td>
        </tr>
      ) : null;

      // Clone and modify children to show only first N rows in tbody + expand row
      const modifiedChildren = React.Children.map(children, (child) => {
        if (child && typeof child === 'object' && 'type' in child) {
          if (child.type === 'tbody' || (child.props && child.props.children && child.type !== 'thead')) {
            const tbodyRows = React.Children.toArray(child.props?.children || []);
            const visibleRows = shouldCollapse && !isExpanded 
              ? tbodyRows.slice(0, collapsedRowCount) 
              : tbodyRows;
            return React.cloneElement(child, {
              children: [...visibleRows, expandRow]
            });
          }
        }
        return child;
      });

      return (
        <div className="collapsible-table-wrapper">
          <table {...props}>
            {modifiedChildren}
          </table>
        </div>
      );
    };
  }, [expandedTables, setExpandedTables, theme, isMobile]);

  // Markdown components configuration
  const markdownComponents = {
    table: CollapsibleTable,
    th: ({ children, ...props }) => {
      // Add title attribute for hover tooltip on mobile
      const textContent = typeof children === 'string' ? children : 
        (React.Children.toArray(children).map(child => 
          typeof child === 'string' ? child : child?.props?.children || ''
        ).join(''));
      return <th {...props} title={textContent} data-title={textContent}>{children}</th>;
    },
  };
  useEffect(() => {
    if (!isLoading) {
      setThinkingDots('');
      return;
    }
  
    let dots = 0;
    const interval = setInterval(() => {
      dots = (dots + 1) % 4; // 0,1,2,3
      setThinkingDots('.'.repeat(dots));
    }, 400); // velocitat (ms)
  
    return () => clearInterval(interval);
  }, [isLoading]);
  

  if (!user) {
    return null; // This should not happen as App.js handles this case
  }

  // Convert hex color to rgba with opacity for background
  const hexToRgba = (hex, opacity) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  };

  const chatBackgroundColor = 'white';
  const inputBackgroundColor = theme?.secondary ? hexToRgba(theme.secondary, 0.10) : 'rgba(208, 40, 44, 0.05)';
  
  // Helper to check if a color is white (or very close to white)
  const isWhiteColor = (hex) => {
    if (!hex) return false;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    // Consider it white if all RGB values are above 240 (very light)
    return r > 240 && g > 240 && b > 240;
  };
  
  // Border color: theme color if not white, gray if white
  const messageBorderColor = theme?.secondary 
    ? (isWhiteColor(theme.secondary) ? '#808080' : theme.secondary)
    : '#808080';

  // Determine Xiquet icon state
  const getXiquetIcon = () => {
    if (isLoading) {
      // Show animated thinking images
      return `/xiquet_images/think_${thinkingFrame}.png`;
    } else {
      return theme?.image || '/xiquet_images/colors/basic_white.png';
    }
  };

  const getXiquetSize = () => {
    if (messages.length === 0) {
      return '400px'; // Much bigger when no messages
    } else {
      return '120px'; // Same size for thinking and responses
    }
  };



  return (
    <div className="chat-container" style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}>
      {/* Fixed Xiquet icon at bottom left - only on desktop */}
      {messages.length > 0 && !isMobile && (
        <div className="xiquet-fixed-icon">
          <img 
            src={getXiquetIcon()} 
            alt="Xiquet" 
            className={isLoading ? 'thinking' : 'idle'}
          />
          {isLoading && (
            // <div className="xiquet-thinking-bubble">
            //   <span className="spinner"></span> Pensant{thinkingDots}
            // </div>
            <div className="xiquet-thinking-bubble">
              <CastellLoader isMobile={isMobile} />
            </div>
          )}
        </div>
      )}
      <div className="chat-messages" style={{ background: chatBackgroundColor }}>
        {messages.length === 0 && (
          <WelcomeMessage 
            theme={theme} 
            onQuestionClick={handleQuestionClick}
          />
        )}
        
        {messages.map((message, index) => {
          // Each completed message uses its own stored entities (not the shared identifiedEntities state)
          // This prevents old chips from changing when a new question is asked
          const entitiesToShow = message.identified_entities;
          
          return (
          <div key={message.id} className={`message-wrapper ${message.isUser ? 'user' : 'assistant'}`}>
            {message.isUser ? (
              <div className={`message ${message.isUser ? 'user' : 'assistant'}`} style={{ background: inputBackgroundColor, borderColor: messageBorderColor }}>
                <div className="message-content">
                  {message.content}
                </div>
              </div>
            ) : (
              <div className="assistant-response">
                  {/* Show chips - uses identifiedEntities for most recent to avoid reload */}
                  {/* Don't show chips for RAG route since entities aren't used in RAG queries */}
                  {hasEntities(entitiesToShow) && (() => {
                    // Get theme color from first colla if available
                    const firstColla = entitiesToShow.colles?.[0];
                    const colorCode = firstColla ? COLLES_COLORS[firstColla] : null;
                    const themeKey = colorCode ? COLOR_CODE_TO_THEME[colorCode] : null;
                    const selectedThemeColor = themeKey && COLOR_THEMES[themeKey] ? COLOR_THEMES[themeKey].secondary : null;
                    
                    // Style for non-colla chips when a color is selected
                    const themedChipStyle = selectedThemeColor ? {
                      backgroundColor: 'white',
                      color: selectedThemeColor,
                      border: `2px solid ${selectedThemeColor}`
                    } : {};
                    const themedIconColor = selectedThemeColor || 'white';
                    
                    return (
                    <div className="response-entities-chips">
                      {entitiesToShow.colles && entitiesToShow.colles.map((colla, idx) => {
                        const collaColorCode = COLLES_COLORS[colla];
                        const collaThemeKey = collaColorCode ? COLOR_CODE_TO_THEME[collaColorCode] : null;
                        const themeColor = collaThemeKey && COLOR_THEMES[collaThemeKey] ? COLOR_THEMES[collaThemeKey].secondary : '#666';
                        const textColor = collaColorCode === 'white' ? '#333' : 'white';
                        return (
                          <span 
                            key={`colla-${idx}`} 
                            className="entity-chip entity-chip-colla"
                            style={{ backgroundColor: themeColor, color: textColor }}
                          >
                            <CollaIcon color={textColor} /> {colla}
                          </span>
                        );
                      })}
                      {entitiesToShow.castells && entitiesToShow.castells.map((castell, idx) => (
                        <span key={`castell-${idx}`} className="entity-chip entity-chip-castell" style={themedChipStyle}>
                          <CastellIcon color={themedIconColor} /> {castell.castell_code}{castell.status ? ` (${castell.status})` : ''}
                        </span>
                      ))}
                      {entitiesToShow.anys && entitiesToShow.anys.map((any, idx) => (
                        <span key={`any-${idx}`} className="entity-chip entity-chip-any" style={themedChipStyle}>
                          <CalendarIcon color={themedIconColor} /> {any}
                        </span>
                      ))}
                      {entitiesToShow.llocs && entitiesToShow.llocs.map((lloc, idx) => (
                        <span key={`lloc-${idx}`} className="entity-chip entity-chip-lloc" style={themedChipStyle}>
                          <LocationIcon color={themedIconColor} /> {lloc}
                        </span>
                      ))}
                      {entitiesToShow.diades && entitiesToShow.diades.map((diada, idx) => (
                        <span key={`diada-${idx}`} className="entity-chip entity-chip-diada" style={themedChipStyle}>
                          <DiadaIcon color={themedIconColor} /> {diada}
                        </span>
                      ))}
                      {entitiesToShow.gamma && (
                        <span className="entity-chip entity-chip-gamma" style={themedChipStyle}>
                          <GammaIcon color={themedIconColor} /> {entitiesToShow.gamma}
                        </span>
                      )}
                    </div>
                  );})()}
                <div className="assistant-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.response}</ReactMarkdown>
                  {/* Display table data from SQL queries */}
                  {message.table_data && <DataTable tableData={message.table_data} />}
                </div>
              </div>
            )}
          </div>
          );
        })}
        
        {/* Loading state - shows entity chips while waiting for response */}
        {isLoading && hasEntities(identifiedEntities) && (() => {
          // Get theme color from first colla if available
          const firstColla = identifiedEntities.colles?.[0];
          const colorCode = firstColla ? COLLES_COLORS[firstColla] : null;
          const themeKey = colorCode ? COLOR_CODE_TO_THEME[colorCode] : null;
          const selectedThemeColor = themeKey && COLOR_THEMES[themeKey] ? COLOR_THEMES[themeKey].secondary : null;
          
          // Style for non-colla chips when a color is selected
          const themedChipStyle = selectedThemeColor ? {
            backgroundColor: 'white',
            color: selectedThemeColor,
            border: `2px solid ${selectedThemeColor}`
          } : {};
          const themedIconColor = selectedThemeColor || 'white';
          
          return (
          <div className="message-wrapper assistant">
            <div className="assistant-response">
              <div className="response-entities-chips">
                {identifiedEntities.colles && identifiedEntities.colles.map((colla, idx) => {
                  const collaColorCode = COLLES_COLORS[colla];
                  const collaThemeKey = collaColorCode ? COLOR_CODE_TO_THEME[collaColorCode] : null;
                  const themeColor = collaThemeKey && COLOR_THEMES[collaThemeKey] ? COLOR_THEMES[collaThemeKey].secondary : '#666';
                  const textColor = collaColorCode === 'white' ? '#333' : 'white';
                  return (
                    <span 
                      key={`colla-${idx}`} 
                      className="entity-chip entity-chip-colla"
                      style={{ backgroundColor: themeColor, color: textColor }}
                    >
                      <CollaIcon color={textColor} /> {colla}
                    </span>
                  );
                })}
                {identifiedEntities.castells && identifiedEntities.castells.map((castell, idx) => (
                  <span key={`castell-${idx}`} className="entity-chip entity-chip-castell" style={themedChipStyle}>
                    <CastellIcon color={themedIconColor} /> {castell.castell_code}{castell.status ? ` (${castell.status})` : ''}
                  </span>
                ))}
                {identifiedEntities.anys && identifiedEntities.anys.map((any, idx) => (
                  <span key={`any-${idx}`} className="entity-chip entity-chip-any" style={themedChipStyle}>
                    <CalendarIcon color={themedIconColor} /> {any}
                  </span>
                ))}
                {identifiedEntities.llocs && identifiedEntities.llocs.map((lloc, idx) => (
                  <span key={`lloc-${idx}`} className="entity-chip entity-chip-lloc" style={themedChipStyle}>
                    <LocationIcon color={themedIconColor} /> {lloc}
                  </span>
                ))}
                {identifiedEntities.diades && identifiedEntities.diades.map((diada, idx) => (
                  <span key={`diada-${idx}`} className="entity-chip entity-chip-diada" style={themedChipStyle}>
                    <DiadaIcon color={themedIconColor} /> {diada}
                  </span>
                ))}
                {identifiedEntities.gamma && (
                  <span className="entity-chip entity-chip-gamma" style={themedChipStyle}>
                    <GammaIcon color={themedIconColor} /> {identifiedEntities.gamma}
                  </span>
                )}
              </div>
            </div>
          </div>
        );})()}
        
        {/* Mobile loading indicator - shows inline when loading */}
        {isLoading && isMobile && (
          <div className="message-wrapper assistant mobile-loading">
            <div className="assistant-response">
              <PilarLoader />
            </div>
          </div>
        )}
        
        {error && (
          <div className="error">
            {error}
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      <div className="chat-input">
        <form onSubmit={sendMessage} className="input-group">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Fes una pregunta sobre castells..."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !inputMessage.trim()}>
            Enviar
          </button>
        </form>
      </div>

      {showSaveDialog && (
        <div className="save-dialog-overlay" onClick={() => setShowSaveDialog(false)}>
          <div className="save-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Guardar conversa</h3>
            <form onSubmit={handleSaveChat}>
              <input
                type="text"
                value={saveTitle}
                onChange={(e) => setSaveTitle(e.target.value)}
                placeholder="Nom de la conversa..."
                autoFocus
                disabled={isSaving}
              />
              <div className="save-dialog-actions">
                <button type="submit" disabled={isSaving || !saveTitle.trim()}>
                  {isSaving ? 'Guardant...' : 'Guardar'}
                </button>
                <button 
                  type="button" 
                  onClick={() => {
                    setShowSaveDialog(false);
                    setSaveTitle('');
                  }}
                  disabled={isSaving}
                >
                  Cancel·lar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
