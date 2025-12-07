import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiService } from '../apiService';

const ChatInterface = ({ user, sessionId, theme, onSessionSaved, onSaveClick, onMessagesChange }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveTitle, setSaveTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [thinkingFrame, setThinkingFrame] = useState(1); // For animation: 1 or 2
  const [expandedTables, setExpandedTables] = useState(new Set()); // Track expanded tables
  const messagesEndRef = useRef(null);
  const previousSessionIdRef = useRef(null); // Track previous sessionId to detect new conversation
  const tableCounterRef = useRef(0); // Table counter for generating unique IDs
  const tableInstanceMapRef = useRef(new Map()); // Map to track table instances and their IDs

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

  const sendMessage = async (e) => {
    e.preventDefault();
    
    if (!inputMessage.trim() || isLoading) return;

    const messageContent = inputMessage.trim();
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
    setInputMessage('');
    setIsLoading(true);
    setError('');
    // Note: scroll will be handled by useEffect when messages.length changes

    try {
      const response = await apiService.sendMessage(messageContent, sessionId);

      // Replace temporary user message and add assistant response
      // The backend saves both user message and response in one row
      // We need to create proper message objects matching the database structure
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
        isUser: false
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
      setError(error.response?.data?.detail || 'Error enviant el missatge');
      console.error('Error sending message:', error);
      // Remove the user message if sending failed
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
    } finally {
      setIsLoading(false);
    }
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
      
      const shouldCollapse = rowCount > 2;
      
      const toggleExpanded = () => {
        const newExpanded = new Set(expandedTables);
        if (isExpanded) {
          newExpanded.delete(tableId);
        } else {
          newExpanded.add(tableId);
        }
        setExpandedTables(newExpanded);
      };

      // Clone and modify children to show only first 2 rows in tbody
      const modifiedChildren = shouldCollapse && !isExpanded && tbodyElement
        ? React.Children.map(children, (child) => {
            if (child && typeof child === 'object' && 'type' in child) {
              if (child.type === 'tbody' || (child.props && child.props.children && child.type !== 'thead')) {
                const tbodyRows = React.Children.toArray(child.props?.children || []);
                const visibleRows = tbodyRows.slice(0, 2);
                return React.cloneElement(child, {
                  children: visibleRows
                });
              }
            }
            return child;
          })
        : children;

      return (
        <div className="collapsible-table-wrapper">
          <table {...props}>
            {modifiedChildren}
          </table>
          {shouldCollapse && (
            <button 
              className="table-toggle-button" 
              onClick={toggleExpanded}
              type="button"
              aria-label={isExpanded ? 'Mostrar menys' : `Mostrar totes les ${rowCount} files`}
              style={{ 
                background: buttonBackgroundColor,
                '--button-hover-color': buttonHoverColor
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = buttonHoverColor;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = buttonBackgroundColor;
              }}
            >
              <svg 
                width="16" 
                height="16" 
                viewBox="0 0 16 16" 
                fill="none" 
                xmlns="http://www.w3.org/2000/svg"
                className={isExpanded ? 'table-toggle-icon expanded' : 'table-toggle-icon'}
                style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
              >
                <path 
                  d="M4 6L8 10L12 6" 
                  stroke="currentColor" 
                  strokeWidth="2" 
                  strokeLinecap="round" 
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>
      );
    };
  }, [expandedTables, setExpandedTables, theme]);

  // Markdown components configuration
  const markdownComponents = {
    table: CollapsibleTable,
  };

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
      return theme?.image || '/xiquet_images/basic_white.png';
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
      {/* Fixed Xiquet icon at bottom left */}
      {messages.length > 0 && (
        <div className="xiquet-fixed-icon">
          <img 
            src={getXiquetIcon()} 
            alt="Xiquet" 
            className={isLoading ? 'thinking' : 'idle'}
          />
          {isLoading && (
            <div className="xiquet-thinking-bubble">
              <span className="spinner"></span> Pensant...
            </div>
          )}
        </div>
      )}
      <div className="chat-messages" style={{ background: chatBackgroundColor }}>
        {messages.length === 0 && (
          <div className="welcome-message">
            <img 
              src={theme?.image || '/xiquet_images/basic_white.png'} 
              alt="Xiquet" 
              className="welcome-xiquet-icon-large"
            />
            <div className="welcome-text-container">
              <p className="welcome-text-main">Hola! Sóc el Xiquet, l'agent d'Intel·ligència Artificial expert en el món casteller.</p>
              <p className="welcome-text-sub">Fes-me qualsevol pregunta sobre castells!</p>
            </div>
          </div>
        )}
        
        {messages.map((message) => (
          <div key={message.id} className={`message-wrapper ${message.isUser ? 'user' : 'assistant'}`}>
            {message.isUser ? (
              <div className={`message ${message.isUser ? 'user' : 'assistant'}`} style={{ background: inputBackgroundColor, borderColor: messageBorderColor }}>
                <div className="message-content">
                  {message.content}
                </div>
              </div>
            ) : (
              <div className="assistant-response">
                <div className="assistant-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.response}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        ))}
        
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
