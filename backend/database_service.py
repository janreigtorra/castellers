"""
database_service.py
Database service for chat persistence using Supabase
"""

import os
import psycopg2
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
import uuid

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

class ChatDatabaseService:
    """Service for managing chat data in Supabase"""
    
    def __init__(self):
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL must be set in environment variables")
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(DATABASE_URL)
    
    def create_session(self, user_id: str, title: str = "New Chat") -> str:
        """Create a new chat session"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            session_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO public.chat_sessions (id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (session_id, user_id, title))
            
            result = cur.fetchone()
            conn.commit()
            return result[0]
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating session: {e}")
        finally:
            cur.close()
            conn.close()
    
    def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, title, created_at, updated_at,
                       (SELECT COUNT(*) FROM public.chat_messages WHERE session_id = cs.id) as message_count
                FROM public.chat_sessions cs
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
            """, (user_id, limit))
            
            sessions = []
            for row in cur.fetchall():
                sessions.append({
                    "id": str(row[0]),
                    "title": row[1],
                    "created_at": row[2].isoformat(),
                    "updated_at": row[3].isoformat(),
                    "message_count": row[4]
                })
            
            return sessions
            
        except Exception as e:
            raise Exception(f"Error getting sessions: {e}")
        finally:
            cur.close()
            conn.close()
    
    def create_message(self, session_id: str, user_id: str, content: str, 
                      response: str = None, route_used: str = None, 
                      response_time_ms: int = None) -> str:
        """Create a new chat message"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            message_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO public.chat_messages 
                (id, session_id, user_id, content, response, route_used, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (message_id, session_id, user_id, content, response, route_used, response_time_ms))
            
            result = cur.fetchone()
            conn.commit()
            return result[0]
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating message: {e}")
        finally:
            cur.close()
            conn.close()
    
    def get_session_messages(self, session_id: str, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages for a specific session"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, content, response, route_used, response_time_ms, created_at
                FROM public.chat_messages
                WHERE session_id = %s AND user_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (session_id, user_id, limit))
            
            messages = []
            for row in cur.fetchall():
                message_id = str(row[0])
                content = row[1]  # User's question
                response = row[2]  # Assistant's response
                route_used = row[3]
                response_time_ms = row[4]
                timestamp = row[5].isoformat()
                
                # Return two messages: one for user question, one for assistant response
                if content:  # User question
                    messages.append({
                        "id": f"{message_id}_user",
                        "content": content,
                        "response": "",
                        "route_used": "",
                        "response_time_ms": 0,
                        "timestamp": timestamp,
                        "isUser": True
                    })
                if response:  # Assistant response
                    messages.append({
                        "id": message_id,
                        "content": content,
                        "response": response,
                        "route_used": route_used or "",
                        "response_time_ms": response_time_ms or 0,
                        "timestamp": timestamp,
                        "isUser": False
                    })
            
            return messages
            
        except Exception as e:
            raise Exception(f"Error getting messages: {e}")
        finally:
            cur.close()
            conn.close()
    
    def get_user_messages(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages for a user across all sessions"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, session_id, content, response, route_used, response_time_ms, created_at
                FROM public.chat_messages
                WHERE user_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (user_id, limit))
            
            messages = []
            for row in cur.fetchall():
                message_id = str(row[0])
                session_id = str(row[1])
                content = row[2]  # User's question
                response = row[3]  # Assistant's response
                route_used = row[4]
                response_time_ms = row[5]
                timestamp = row[6].isoformat()
                
                # Return two messages: one for user question, one for assistant response
                if content:  # User question
                    messages.append({
                        "id": f"{message_id}_user",
                        "session_id": session_id,
                        "content": content,
                        "response": "",
                        "route_used": "",
                        "response_time_ms": 0,
                        "timestamp": timestamp,
                        "isUser": True
                    })
                if response:  # Assistant response
                    messages.append({
                        "id": message_id,
                        "session_id": session_id,
                        "content": content,
                        "response": response,
                        "route_used": route_used or "",
                        "response_time_ms": response_time_ms or 0,
                        "timestamp": timestamp,
                        "isUser": False
                    })
            
            return messages
            
        except Exception as e:
            raise Exception(f"Error getting user messages: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_session_title(self, session_id: str, user_id: str, title: str) -> bool:
        """Update session title"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE public.chat_sessions 
                SET title = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (title, session_id, user_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating session title: {e}")
        finally:
            cur.close()
            conn.close()
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session and all its messages"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                DELETE FROM public.chat_sessions 
                WHERE id = %s AND user_id = %s
            """, (session_id, user_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error deleting session: {e}")
        finally:
            cur.close()
            conn.close()
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, username, created_at, updated_at
                FROM public.profiles
                WHERE id = %s
            """, (user_id,))
            
            row = cur.fetchone()
            if row:
                return {
                    "id": str(row[0]),
                    "username": row[1],
                    "created_at": row[2].isoformat(),
                    "updated_at": row[3].isoformat()
                }
            return None
            
        except Exception as e:
            raise Exception(f"Error getting user profile: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_user_profile(self, user_id: str, username: str = None) -> bool:
        """Update user profile"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            if username:
                cur.execute("""
                    UPDATE public.profiles 
                    SET username = %s, updated_at = NOW()
                    WHERE id = %s
                """, (username, user_id))
            else:
                cur.execute("""
                    UPDATE public.profiles 
                    SET updated_at = NOW()
                    WHERE id = %s
                """, (user_id,))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating user profile: {e}")
        finally:
            cur.close()
            conn.close()

# Create global instance
chat_db = ChatDatabaseService()
