"""
main.py
FastAPI backend for Xiquet Casteller Agent
Wraps the existing agent.py functionality with REST API endpoints
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import os
import asyncio
import json
from dotenv import load_dotenv

# Import our existing agent and Supabase auth
from agent import Xiquet
from auth_service import supabase_auth
from database_service import chat_db
from passafaixa.main import generate_question
from passafaixa.db_pool import init_connection_pool, close_connection_pool

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Xiquet Casteller API",
    description="API for the Xiquet AI knowledge system",
    version="1.0.0"
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Initialize database connection pool on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool and preload ML models when the app starts"""
    # Initialize connection pool
    try:
        init_connection_pool(min_conn=2, max_conn=10)
    except Exception as e:
        print(f"Warning: Failed to initialize connection pool: {e}")
        print("Question generation will use direct connections (slower)")
    
    # Pre-load RAG model to avoid delay on first request
    try:
        from database_pipeline.rag_index_supabase import preload_rag_model
        preload_rag_model()
    except Exception as e:
        print(f"Warning: Failed to preload RAG model: {e}")
        print("RAG model will be loaded on first request (slower)")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection pool when the app shuts down"""
    try:
        close_connection_pool()
    except Exception as e:
        print(f"Warning: Error closing connection pool: {e}")

# Pydantic models for API requests and responses
class ChatMessage(BaseModel):
    content: str
    session_id: Optional[str] = None

class TableData(BaseModel):
    title: str
    columns: List[str]
    rows: List[List[str]]

class CastellEntity(BaseModel):
    castell_code: str
    status: Optional[str] = None

class IdentifiedEntities(BaseModel):
    colles: List[str] = []
    castells: List[CastellEntity] = []
    anys: List[int] = []
    llocs: List[str] = []
    diades: List[str] = []

class ChatResponse(BaseModel):
    id: str
    content: str
    response: str
    route_used: str
    timestamp: datetime
    response_time_ms: int
    session_id: Optional[str] = None
    table_data: Optional[TableData] = None
    identified_entities: Optional[IdentifiedEntities] = None

class SaveChatRequest(BaseModel):
    title: str
    messages: List[dict]  # List of message objects with content, response, route_used, etc.

class ChatSession(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

class UserProfile(BaseModel):
    id: str
    username: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime

# Simple in-memory storage for demo (replace with Supabase later)
chat_sessions = {}
chat_messages = {}
users = {}

# Dependency to get current user from Supabase JWT
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current user from Supabase JWT token. Requires valid authentication."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in."
        )
    
    try:
        # Verify JWT token with Supabase
        user_data = supabase_auth.verify_jwt_token(credentials.credentials)
        return user_data
    except HTTPException:
        # Re-raise HTTP exceptions (like 401)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )

# API Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Xiquet Casteller API is running!", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "agent_status": "ready"
    }

def _get_friendly_error_message(error: Exception) -> str:
    """
    Convert technical errors to user-friendly Catalan messages.
    Never expose technical details to the UI.
    """
    error_str = str(error).lower()
    
    # Rate limit errors
    if "rate limit" in error_str or "429" in error_str:
        return "No puc respondre la pregunta perquè he arribat al límit de peticions. Si us plau, torna-ho a intentar en uns moments."
    
    # API key errors
    if "api key" in error_str or "authentication" in error_str:
        return "No puc respondre la pregunta perquè hi ha un problema amb la configuració del servei."
    
    # Network/timeout errors
    if "timeout" in error_str or "connection" in error_str or "network" in error_str:
        return "No puc respondre la pregunta perquè hi ha un problema de connexió. Si us plau, torna-ho a intentar."
    
    # Provider errors
    if "llm call failed" in error_str or "provider" in error_str:
        return "No puc respondre la pregunta perquè el servei d'intel·ligència artificial no està disponible temporalment. Si us plau, torna-ho a intentar."
    
    # Database errors
    if "database" in error_str or "sql" in error_str:
        return "No puc respondre la pregunta perquè hi ha un problema accedint a la base de dades."
    
    # Generic fallback
    return "No puc respondre la pregunta en aquest moment. Si us plau, torna-ho a intentar més tard."

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_xiquet(
    message: ChatMessage,
    current_user: dict = Depends(get_current_user)
):
    """
    Main chat endpoint - sends message to Xiquet agent
    """
    try:
        import traceback
        from datetime import datetime
        start_time = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"[TIMING] Request started at {start_time.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"[TIMING] Question: {message.content[:100]}...")
        print(f"{'='*60}\n")
        
        # Initialize Xiquet agent
        init_start = datetime.now()
        xiquet = Xiquet()
        init_time = (datetime.now() - init_start).total_seconds() * 1000
        print(f"[TIMING] Agent initialization: {init_time:.2f}ms")
        
        # Process the question - MUST use asyncio.to_thread to avoid blocking event loop!
        # This allows other async requests (like /api/chat/route) to run in parallel
        process_start = datetime.now()
        response_text = await asyncio.to_thread(xiquet.process_question, message.content)
        process_time = (datetime.now() - process_start).total_seconds() * 1000
        
        end_time = datetime.now()
        response_time = int((end_time - start_time).total_seconds() * 1000)
        
        print(f"\n{'='*60}")
        print(f"[TIMING] Total request time: {response_time}ms")
        print(f"[TIMING] Process question time: {process_time:.2f}ms")
        print(f"[TIMING] Request completed at {end_time.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"{'='*60}\n")
        
        # Get the route used from the agent's last response
        # The response object is stored in xiquet.response after decide_route
        route_used = 'unknown'
        if hasattr(xiquet, 'response') and xiquet.response:
            route_used = getattr(xiquet.response, 'tools', 'unknown')
        # Ensure route_used is a valid string
        if not route_used or route_used not in ['direct', 'rag', 'sql', 'hybrid']:
            route_used = 'unknown'
        
        # Only save to database if session_id is provided
        # If no session_id, return response without saving (unsaved chat)
        session_id = message.session_id
        message_id = None
        
        if session_id:
            # Store message in database only if session exists
            message_id = chat_db.create_message(
                session_id=session_id,
                user_id=current_user["id"],
                content=message.content,
                response=response_text,
                route_used=route_used,
                response_time_ms=response_time
            )
        
        # Create response - use a temporary ID if no session_id
        if not message_id:
            message_id = f"temp_{uuid.uuid4()}"
        
        # Get table data if available (for SQL queries)
        table_data = None
        if hasattr(xiquet, 'table_data') and xiquet.table_data:
            table_data = TableData(**xiquet.table_data)
        
        # Get identified entities from the agent
        identified_entities = None
        if hasattr(xiquet, 'response') and xiquet.response:
            castells_list = []
            if xiquet.castells:
                for c in xiquet.castells:
                    if hasattr(c, 'castell_code'):
                        castells_list.append(CastellEntity(
                            castell_code=c.castell_code,
                            status=c.status if hasattr(c, 'status') else None
                        ))
            
            identified_entities = IdentifiedEntities(
                colles=xiquet.colles_castelleres or [],
                castells=castells_list,
                anys=xiquet.anys or [],
                llocs=xiquet.llocs or [],
                diades=xiquet.diades or []
            )
        
        chat_response = ChatResponse(
            id=message_id,
            content=message.content,
            response=response_text,
            route_used=route_used,
            timestamp=datetime.now(),
            response_time_ms=response_time,
            session_id=session_id,
            table_data=table_data,
            identified_entities=identified_entities
        )
        
        return chat_response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in chat endpoint: {str(e)}")
        print(f"Traceback: {error_details}")
        
        # Get friendly error message
        friendly_message = _get_friendly_error_message(e)
        
        # Return a valid response with the friendly error message instead of raising HTTPException
        # This ensures the UI always receives a proper response
        try:
            session_id = message.session_id if hasattr(message, 'session_id') else None
            content = message.content if hasattr(message, 'content') else ""
        except:
            session_id = None
            content = ""
        
        message_id = f"temp_{uuid.uuid4()}"
        
        error_response = ChatResponse(
            id=message_id,
            content=content,
            response=friendly_message,
            route_used='error',
            timestamp=datetime.now(),
            response_time_ms=0,
            session_id=session_id
        )
        
        return error_response

class RouteResponse(BaseModel):
    route_used: str
    identified_entities: IdentifiedEntities

@app.post("/api/chat/route", response_model=RouteResponse)
async def get_chat_route(
    message: ChatMessage,
    current_user: dict = Depends(get_current_user)
):
    """
    Quick endpoint that ONLY runs decide_route and returns identified entities.
    Use this to get entities immediately, then call /api/chat for the full response.
    """
    try:
        from datetime import datetime
        start_time = datetime.now()
        
        print(f"\n[ROUTE] Getting route for: {message.content[:100]}...")
        
        # Initialize Xiquet agent and run decide_route
        xiquet = Xiquet()
        route_response = await asyncio.to_thread(xiquet.decide_route, message.content)
        
        route_time = (datetime.now() - start_time).total_seconds() * 1000
        print(f"[ROUTE] decide_route() completed in {route_time:.2f}ms")
        
        # Build identified entities
        castells_list = []
        if xiquet.castells:
            for c in xiquet.castells:
                if hasattr(c, 'castell_code'):
                    castells_list.append(CastellEntity(
                        castell_code=c.castell_code,
                        status=c.status if hasattr(c, 'status') else None
                    ))
        
        identified_entities = IdentifiedEntities(
            colles=xiquet.colles_castelleres or [],
            castells=castells_list,
            anys=xiquet.anys or [],
            llocs=xiquet.llocs or [],
            diades=xiquet.diades or []
        )
        
        route_used = route_response.tools if route_response else 'unknown'
        
        return RouteResponse(
            route_used=route_used,
            identified_entities=identified_entities
        )
        
    except Exception as e:
        import traceback
        print(f"ERROR in route endpoint: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Get chat history for current user
    """
    try:
        if session_id:
            # Get messages for specific session
            messages = chat_db.get_session_messages(session_id, current_user["id"], limit)
        else:
            # Get all user messages
            messages = chat_db.get_user_messages(current_user["id"], limit)
        
        return messages
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in get_chat_history: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error getting chat history: {str(e)}")

@app.post("/api/sessions")
async def create_chat_session(
    title: str = "New Chat",
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new chat session
    """
    try:
        session_id = chat_db.create_session(current_user["id"], title)
        return {"id": session_id, "title": title, "created_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@app.post("/api/sessions/save")
async def save_chat_session(
    request: SaveChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Save an unsaved chat as a new session with messages
    """
    try:
        # Create new session
        session_id = chat_db.create_session(current_user["id"], request.title)
        
        # Save all messages to the session
        # Only save assistant messages (they contain both user question and assistant response)
        for msg in request.messages:
            # Skip user messages - they're duplicated in assistant messages
            if msg.get("isUser", False):
                continue
            
            # Extract message data from assistant messages
            content = msg.get("content", "")  # User's question
            response = msg.get("response", "")  # Assistant's response
            route_used = msg.get("route_used", "") or "unknown"
            response_time_ms = msg.get("response_time_ms", 0)
            
            # Only save if we have both content and response (complete message pair)
            if content and response:
                chat_db.create_message(
                    session_id=session_id,
                    user_id=current_user["id"],
                    content=content,
                    response=response,
                    route_used=route_used,
                    response_time_ms=response_time_ms
                )
        
        return {"id": session_id, "title": request.title, "created_at": datetime.now().isoformat()}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in save_chat_session: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error saving chat: {str(e)}")

@app.get("/api/sessions")
async def get_chat_sessions(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all chat sessions for current user
    """
    try:
        sessions = chat_db.get_user_sessions(current_user["id"])
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sessions: {str(e)}")

@app.put("/api/sessions/{session_id}")
async def update_chat_session(
    session_id: str,
    title: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Update chat session title
    """
    try:
        success = chat_db.update_session_title(session_id, current_user["id"], title)
        if success:
            return {"message": "Session updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")

@app.delete("/api/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete chat session
    """
    try:
        success = chat_db.delete_session(session_id, current_user["id"])
        if success:
            return {"message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")

@app.get("/api/user/profile")
async def get_user_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user profile
    """
    try:
        profile = chat_db.get_user_profile(current_user["id"])
        if profile:
            return UserProfile(
                id=profile["id"],
                username=profile["username"],
                email=current_user.get("email"),
                created_at=datetime.fromisoformat(profile["created_at"])
            )
        else:
            return UserProfile(
                id=current_user["id"],
                username=current_user.get("username"),
                email=current_user.get("email"),
                created_at=datetime.now()
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user profile: {str(e)}")

@app.put("/api/user/profile")
async def update_user_profile(
    username: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Update current user profile
    """
    try:
        success = chat_db.update_user_profile(current_user["id"], username)
        if success:
            return {"message": "Profile updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Profile not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

# Authentication endpoints with Supabase
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """
    Login endpoint with Supabase Auth
    """
    try:
        result = await supabase_auth.sign_in(request.email, request.password)
        return {
            "access_token": result["session"].access_token,
            "token_type": "bearer",
            "user": result["user"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """
    Register endpoint with Supabase Auth
    """
    try:
        result = await supabase_auth.sign_up(request.email, request.password, request.username)
        return {
            "access_token": result["session"].access_token if result["session"] else None,
            "token_type": "bearer",
            "user": result["user"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint
    """
    try:
        await supabase_auth.sign_out("")
        return {"message": "Logged out successfully"}
    except Exception as e:
        return {"message": f"Logout completed with warning: {str(e)}"}

# PassaFaixa game endpoints
async def generate_single_question_with_retry(selected_colles: List[str] = None, selected_years: List[int] = None, max_retries: int = 10):
    """
    Generate a single question with retry logic.
    Runs in a thread pool to allow parallel execution.
    
    Args:
        selected_colles: Optional list of colla names to filter questions.
        selected_years: Optional list of years to filter questions.
        max_retries: Maximum number of retry attempts.
    """
    for retry in range(max_retries):
        try:
            # Run the synchronous generate_question in a thread pool
            question = await asyncio.to_thread(generate_question, selected_colles, selected_years)
            if question and not question.is_error:
                return question.model_dump()
        except Exception as e:
            print(f"Error generating question (retry {retry + 1}/{max_retries}): {e}")
            if retry == max_retries - 1:
                return None
    return None

@app.get("/api/passafaixa/questions")
async def get_game_questions(
    num_questions: int = 10,
    colles: Optional[str] = None,
    years: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate questions for the PassaFaixa trivia game in parallel.
    Returns a list of questions with shuffled answers.
    
    Uses parallel generation with batching to optimize performance while
    respecting database connection pool limits.
    
    Args:
        num_questions: Number of questions to generate.
        colles: Comma-separated list of colla names to filter questions.
                If provided, only generates questions about these colles.
        years: Comma-separated list of years to filter questions.
               If provided, only generates questions about these years.
    """
    try:
        # Parse selected_colles from comma-separated string
        selected_colles = None
        if colles:
            selected_colles = [c.strip() for c in colles.split(",") if c.strip()]
            if len(selected_colles) == 0:
                selected_colles = None
        
        # Parse selected_years from comma-separated string
        selected_years = None
        if years:
            try:
                selected_years = [int(y.strip()) for y in years.split(",") if y.strip()]
                if len(selected_years) == 0:
                    selected_years = None
            except ValueError:
                selected_years = None
        
        questions = []
        seen_question_texts = set()  # Track seen questions to avoid duplicates
        max_concurrent = min(10, num_questions + 10)  # Limit concurrent tasks to avoid overwhelming the pool
        batch_size = max_concurrent
        max_attempts = 5  # Maximum number of batch attempts to prevent infinite loops
        attempt = 0
        
        # Generate questions in batches to respect connection pool limits
        while len(questions) < num_questions and attempt < max_attempts:
            attempt += 1
            # Calculate how many more we need
            remaining = num_questions - len(questions)
            
            # Generate a batch (generate extra to account for errors and duplicates)
            batch_to_generate = min(batch_size, remaining + 5)
            
            # Create tasks for parallel generation
            tasks = [generate_single_question_with_retry(selected_colles, selected_years) for _ in range(batch_to_generate)]
            
            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None, exceptions, errors, and duplicates
            for result in results:
                if result is None:
                    continue
                if isinstance(result, Exception):
                    print(f"Exception in question generation: {result}")
                    continue
                if isinstance(result, dict):
                    # Check for duplicate question text
                    question_text = result.get("question", "")
                    if question_text and question_text not in seen_question_texts:
                        seen_question_texts.add(question_text)
                        questions.append(result)
                        if len(questions) >= num_questions:
                            break
            
            # Safety check to prevent infinite loop
            if len(questions) >= num_questions * 2:
                print(f"Warning: Generated {len(questions)} questions but only needed {num_questions}")
                break
        
        # Return only the requested number of questions
        return {"questions": questions[:num_questions]}
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in get_game_questions: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error generating questions: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
