"""
database_service.py
Database service for chat persistence using Supabase
"""

import os
import psycopg2
from psycopg2.extras import Json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
import uuid
import json

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
                      response_time_ms: int = None,
                      table_data: dict = None, identified_entities: dict = None) -> str:
        """Create a new chat message"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            message_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO public.chat_messages 
                (id, session_id, user_id, content, response, route_used, response_time_ms, table_data, identified_entities)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (message_id, session_id, user_id, content, response, route_used, response_time_ms, 
                  Json(table_data) if table_data else None, 
                  Json(identified_entities) if identified_entities else None))
            
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
                SELECT id, content, response, route_used, response_time_ms, created_at, table_data, identified_entities
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
                table_data = row[6]  # JSONB - already parsed by psycopg2
                identified_entities = row[7]  # JSONB - already parsed by psycopg2
                
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
                        "isUser": False,
                        "table_data": table_data,
                        "identified_entities": identified_entities
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

    # ============================================================
    # PENDING MESSAGES - Progressive Response Pattern
    # ============================================================
    
    def create_pending_message(self, user_id: str, content: str, session_id: str = None) -> str:
        """
        Create a pending message record when a chat request starts.
        Returns the message_id that frontend will use for polling.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            message_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO public.pending_messages 
                (id, user_id, session_id, content, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING id
            """, (message_id, user_id, session_id, content))
            
            result = cur.fetchone()
            conn.commit()
            return result[0]
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating pending message: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_pending_entities(self, message_id: str, route_used: str, 
                                identified_entities: dict) -> bool:
        """
        Update pending message with entities after decide_route completes.
        This is the FIRST update - allows frontend to show chips immediately.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE public.pending_messages 
                SET status = 'entities_ready',
                    route_used = %s,
                    identified_entities = %s
                WHERE id = %s
            """, (route_used, Json(identified_entities) if identified_entities else None, message_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating pending entities: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_pending_complete(self, message_id: str, response: str, 
                                table_data: dict = None, response_time_ms: int = None) -> bool:
        """
        Update pending message with final response.
        This is the SECOND update - frontend can now show the full response.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE public.pending_messages 
                SET status = 'complete',
                    response = %s,
                    table_data = %s,
                    response_time_ms = %s
                WHERE id = %s
            """, (response, Json(table_data) if table_data else None, response_time_ms, message_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating pending complete: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_pending_error(self, message_id: str, error_message: str) -> bool:
        """
        Update pending message with error status.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE public.pending_messages 
                SET status = 'error',
                    error_message = %s
                WHERE id = %s
            """, (error_message, message_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error updating pending error: {e}")
        finally:
            cur.close()
            conn.close()
    
    def get_pending_message(self, message_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current state of a pending message for polling.
        Returns None if message doesn't exist or doesn't belong to user.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, content, status, route_used, identified_entities, 
                       response, table_data, response_time_ms, error_message, created_at
                FROM public.pending_messages
                WHERE id = %s AND user_id = %s
            """, (message_id, user_id))
            
            row = cur.fetchone()
            if row:
                return {
                    "id": str(row[0]),
                    "content": row[1],
                    "status": row[2],
                    "route_used": row[3],
                    "identified_entities": row[4],  # JSONB - already parsed
                    "response": row[5],
                    "table_data": row[6],  # JSONB - already parsed
                    "response_time_ms": row[7],
                    "error_message": row[8],
                    "created_at": row[9].isoformat() if row[9] else None
                }
            return None
            
        except Exception as e:
            raise Exception(f"Error getting pending message: {e}")
        finally:
            cur.close()
            conn.close()
    
    def delete_pending_message(self, message_id: str, user_id: str) -> bool:
        """
        Delete a pending message (cleanup after frontend receives complete response).
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                DELETE FROM public.pending_messages 
                WHERE id = %s AND user_id = %s
            """, (message_id, user_id))
            
            conn.commit()
            return cur.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error deleting pending message: {e}")
        finally:
            cur.close()
            conn.close()
    
    def move_pending_to_chat_messages(self, message_id: str, user_id: str) -> Optional[str]:
        """
        Move a completed pending message to the permanent chat_messages table.
        Only moves if session_id is set (saved conversation).
        Returns the new message_id in chat_messages, or None if not saved.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # Get the pending message
            cur.execute("""
                SELECT session_id, content, response, route_used, response_time_ms, 
                       table_data, identified_entities
                FROM public.pending_messages
                WHERE id = %s AND user_id = %s AND status = 'complete'
            """, (message_id, user_id))
            
            row = cur.fetchone()
            if not row or not row[0]:  # No session_id means unsaved chat
                return None
            
            session_id, content, response, route_used, response_time_ms, table_data, identified_entities = row
            
            # Insert into chat_messages
            new_message_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO public.chat_messages 
                (id, session_id, user_id, content, response, route_used, response_time_ms, table_data, identified_entities)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (new_message_id, session_id, user_id, content, response, route_used, 
                  response_time_ms, Json(table_data) if table_data else None, 
                  Json(identified_entities) if identified_entities else None))
            
            result = cur.fetchone()
            
            # Delete from pending_messages
            cur.execute("""
                DELETE FROM public.pending_messages WHERE id = %s
            """, (message_id,))
            
            conn.commit()
            return result[0] if result else None
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error moving pending to chat messages: {e}")
        finally:
            cur.close()
            conn.close()

# Create global instance
chat_db = ChatDatabaseService()
