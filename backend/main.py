"""
main.py
FastAPI backend for Xiquet Casteller Agent
Wraps the existing agent.py functionality with REST API endpoints
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Union
import uuid
from datetime import datetime, timezone
import os
import asyncio
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import stripe

# Import our existing agent and Supabase auth
from xiquet.agent import Xiquet, MAX_QUESTIONS_BASIC, TIME_BASIC
from auth_service import supabase_auth
from database_service import chat_db
from joc_del_mocador.main import generate_question
from joc_del_mocador.db_pool import init_connection_pool, close_connection_pool

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID")  # Price ID for 1.99€/month subscription
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://xiquet.vercel.app")

# Initialize FastAPI app
app = FastAPI(
    title="Xiquet Casteller API",
    description="API for the Xiquet AI knowledge system",
    version="1.0.0"
)

# CORS origins - configurable via environment variable
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://xiquet.vercel.app",
    "https://xiquet-frontend.vercel.app",
    "https://castellers.vercel.app",
    "https://castellers-t9nc.vercel.app",  # Production Vercel deployment
]
# Merge default + custom origins
ALL_ORIGINS = list(set(DEFAULT_ORIGINS + [o.strip() for o in CORS_ORIGINS if o.strip()]))

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALL_ORIGINS,
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
    
    # Pre-warm entity cache to avoid slow first queries
    # This loads colles, castells, anys, llocs, diades from DB
    try:
        from xiquet.utility_functions import warm_entity_cache
        await asyncio.to_thread(warm_entity_cache)
    except Exception as e:
        print(f"Warning: Failed to warm entity cache: {e}")
        print("Entity cache will be populated on first query (slower)")
    
    # Pre-load RAG models to avoid delay on first request
    try:
        from database_pipeline.rag_index_supabase import preload_rag_model
        preload_rag_model()
    except Exception as e:
        print(f"Warning: Failed to preload RAG model: {e}")
    
    # Pre-load multilingual model for castellers_info_chunks
    try:
        from database_pipeline.load_castellers_info_chunks import preload_multilingual_model
        preload_multilingual_model()
    except Exception as e:
        print(f"Warning: Failed to preload multilingual model: {e}")
        print("Multilingual model will be loaded on first RAG request")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection pool when the app shuts down"""
    try:
        close_connection_pool()
    except Exception as e:
        print(f"Warning: Error closing connection pool: {e}")

# Pydantic models for API requests and responses
class PreviousContext(BaseModel):
    """Context from the previous message for follow-up questions"""
    question: Optional[str] = None
    response: Optional[str] = None
    route: Optional[str] = None
    sql_query_type: Optional[str] = None
    entities: Optional[dict] = None  # {colles: [], castells: [], anys: [], llocs: [], diades: []}

class PreSelectedEntities(BaseModel):
    """Pre-selected entities from the frontend UI"""
    colles: List[str] = []
    castells: List[str] = []  # List of castell codes
    anys: List[str] = []  # List of years as strings

class ChatMessage(BaseModel):
    content: str
    session_id: Optional[str] = None
    previous_context: Optional[PreviousContext] = None  # Context from frontend for follow-up questions
    pre_selected_entities: Optional[PreSelectedEntities] = None  # Pre-selected entities from UI

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
    gamma: Optional[str] = None  # Gamma de castells (e.g., "castells de 6", "gamma extra")
    sql_query_type: Optional[str] = None  # Tipus de consulta SQL (millor_castell, etc.)

class ChatResponse(BaseModel):
    id: str
    content: str
    response: str
    route_used: str
    timestamp: datetime
    response_time_ms: int
    session_id: Optional[str] = None
    table_data: Optional[Union[TableData, List[TableData]]] = None  # Can be single table or list of tables (for custom queries)
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
    subscription: str = 'basic'
    role: str = 'user'
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

@app.get("/api/chat/routes")
async def list_chat_routes():
    """Debug endpoint to verify chat routes are registered"""
    return {
        "routes": [
            "POST /api/chat",
            "POST /api/chat/route",
            "POST /api/chat/start",
            "GET /api/chat/status/{message_id}",
            "GET /api/chat/history",
            "DELETE /api/chat/pending/{message_id}"
        ]
    }

@app.get("/api/entities/options")
async def get_entity_options(current_user: dict = Depends(get_current_user)):
    """
    Get all available entity options for frontend dropdowns.
    Returns colles, castells, anys, and diades.
    """
    try:
        from xiquet.utility_functions import (
            get_all_colla_options,
            get_all_castell_options,
            get_all_any_options,
            get_all_diada_options
        )
        
        return {
            "colles": get_all_colla_options(),
            "castells": get_all_castell_options(),
            "anys": get_all_any_options(),
            "diades": get_all_diada_options()
        }
    except Exception as e:
        print(f"Error fetching entity options: {e}")
        raise HTTPException(status_code=500, detail="Error obtenint les opcions d'entitats")

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
        
        # Check user subscription and rate limit for basic users ONLY
        # Premium users bypass rate limiting completely
        user_profile = chat_db.get_user_profile(current_user["id"])
        subscription = user_profile.get("subscription", "basic") if user_profile else "basic"
        print(f"[RATE_LIMIT] User {current_user['id']} subscription: {subscription}")
        
        # Only check rate limit for basic subscription users
        # Premium users have unlimited messages
        if subscription == "basic":
            is_allowed, question_count = chat_db.check_rate_limit(
                current_user["id"], 
                MAX_QUESTIONS_BASIC, 
                TIME_BASIC
            )
            
            print(f"[RATE_LIMIT] Check result: {question_count}/{MAX_QUESTIONS_BASIC} messages, allowed: {is_allowed}")
            
            if not is_allowed:
                # Rate limit exceeded - return message explaining limit and upgrade link
                upgrade_message = f"""Has arribat al límit de {MAX_QUESTIONS_BASIC} preguntes per hora amb el **pla bàsic**.

Per continuar fent preguntes il·limitades, pots [actualitzar al pla premium per només 1,99€/mes](/profile).

Aquesta subscripció permet fer tantes preguntes com vulguis al Xiquet.

**Per què hauria de pagar?**

Fer servir models d'intel·ligència artificial no és gratis. Cada pregunta que es fa al Xiquet té un cost real de computació i d'ús dels models d'IA. Xiquet.cat no està finançat per cap empresa ni inversor, i fins ara tot el projecte s'ha pagat directament de la meva butxaca.

Aquesta subscripció ajuda a cobrir els costos de funcionament (servidors, ús dels models d'IA, manteniment i millores) i permet que el projecte pugui continuar existint i creixent. Si decideixes subscriure't, no només obtens accés il·limitat al Xiquet, sinó que també estàs ajudant a mantenir viu aquest projecte fet amb passió pel món casteller."""
                
                # Return error response with upgrade message
                message_id = f"temp_{uuid.uuid4()}"
                error_response = ChatResponse(
                    id=message_id,
                    content=message.content,
                    response=upgrade_message,
                    route_used='rate_limit',
                    timestamp=datetime.now(timezone.utc),
                    response_time_ms=0,
                    session_id=message.session_id
                )
                return error_response
        
        # Get previous message context if session_id is provided
        previous_question = None
        previous_response = None
        previous_route = None
        previous_sql_query_type = None
        previous_entities = None
        if message.session_id:
            try:
                session_messages = chat_db.get_session_messages(
                    message.session_id, 
                    current_user["id"],
                    limit=10  # Get last 10 messages
                )
                # Get the last message (most recent) as context
                if session_messages and len(session_messages) > 0:
                    last_msg = session_messages[-1]  # Most recent message
                    previous_question = last_msg.get("content")
                    previous_response = last_msg.get("response")
                    previous_route = last_msg.get("route_used")
                    
                    # Extract sql_query_type and entities from identified_entities
                    prev_entities = last_msg.get("identified_entities") or {}
                    previous_sql_query_type = prev_entities.get("sql_query_type")
                    previous_entities = {
                        "colles": prev_entities.get("colles", []),
                        "castells": prev_entities.get("castells", []),
                        "anys": prev_entities.get("anys", []),
                        "llocs": prev_entities.get("llocs", []),
                        "diades": prev_entities.get("diades", []),
                    }
                    
                    print(f"[CONTEXT] Previous: q='{previous_question[:50] if previous_question else 'None'}...', route={previous_route}, sql_type={previous_sql_query_type}")
            except Exception as e:
                print(f"[WARNING] Could not get previous context: {e}")
        
        # Initialize Xiquet agent with previous context
        init_start = datetime.now()
        xiquet = Xiquet(
            previous_question=previous_question,
            previous_response=previous_response,
            previous_route=previous_route,
            previous_sql_query_type=previous_sql_query_type,
            previous_entities=previous_entities
        )
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
        
        # Get table data if available (for SQL queries)
        table_data = None
        if hasattr(xiquet, 'table_data') and xiquet.table_data:
            # For custom queries, table_data is a list of tables
            # For other queries, it's a single table dict
            if isinstance(xiquet.table_data, list):
                # List of tables (custom queries)
                table_data = [TableData(**table) for table in xiquet.table_data]
            else:
                # Single table (other queries)
                table_data = TableData(**xiquet.table_data)
        
        # Get identified entities from the agent
        identified_entities = None
        if hasattr(xiquet, 'response') and xiquet.response:
            castells_list = []
            if xiquet.castells:
                for c in xiquet.castells:
                    if isinstance(c, str):
                        castells_list.append(CastellEntity(castell_code=c))
                    elif isinstance(c, dict) and 'castell_code' in c:
                        castells_list.append(CastellEntity(**c))
                    elif hasattr(c, 'castell_code'):
                        castells_list.append(CastellEntity(
                            castell_code=c.castell_code,
                            status=getattr(c, 'status', None)
                        ))
            
            colles_list = []
            if xiquet.colles_castelleres:
                for col in xiquet.colles_castelleres:
                    if isinstance(col, str):
                        colles_list.append(col)
                    elif isinstance(col, dict) and 'name' in col:
                        colles_list.append(col['name'])
                    else:
                        colles_list.append(str(col))
            
            # Get sql_query_type from response
            sql_query_type = getattr(xiquet.response, 'sql_query_type', None)
            
            identified_entities = IdentifiedEntities(
                castells=castells_list,
                colles=colles_list,
                anys=xiquet.anys if xiquet.anys else [],
                llocs=xiquet.llocs if xiquet.llocs else [],
                diades=xiquet.diades if xiquet.diades else [],
                gamma=xiquet.gamma,
                sql_query_type=sql_query_type
            )
        
        if session_id:
            # Store message in database only if session exists
            # Convert table_data and identified_entities to dicts for JSON storage
            table_data_dict = table_data.dict() if table_data else None
            identified_entities_dict = identified_entities.dict() if identified_entities else None
            
            message_id = chat_db.create_message(
                session_id=session_id,
                user_id=current_user["id"],
                content=message.content,
                response=response_text,
                route_used=route_used,
                response_time_ms=response_time,
                table_data=table_data_dict,
                identified_entities=identified_entities_dict
            )
        
        # Create response - use a temporary ID if no session_id
        if not message_id:
            message_id = f"temp_{uuid.uuid4()}"
        
        chat_response = ChatResponse(
            id=message_id,
            content=message.content,
            response=response_text,
            route_used=route_used,
            timestamp=datetime.now(timezone.utc),
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
            timestamp=datetime.now(timezone.utc),
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
        
        # Get previous message context if session_id is provided
        previous_question = None
        previous_response = None
        previous_route = None
        previous_sql_query_type = None
        previous_entities = None
        if message.session_id:
            try:
                session_messages = chat_db.get_session_messages(
                    message.session_id, 
                    current_user["id"],
                    limit=10
                )
                if session_messages and len(session_messages) > 0:
                    last_msg = session_messages[-1]
                    previous_question = last_msg.get("content")
                    previous_response = last_msg.get("response")
                    previous_route = last_msg.get("route_used")
                    
                    # Extract sql_query_type and entities from identified_entities
                    prev_entities = last_msg.get("identified_entities") or {}
                    previous_sql_query_type = prev_entities.get("sql_query_type")
                    previous_entities = {
                        "colles": prev_entities.get("colles", []),
                        "castells": prev_entities.get("castells", []),
                        "anys": prev_entities.get("anys", []),
                        "llocs": prev_entities.get("llocs", []),
                        "diades": prev_entities.get("diades", []),
                    }
                    
                    print(f"[ROUTE CONTEXT] Previous: q='{previous_question[:50] if previous_question else 'None'}...', route={previous_route}, sql_type={previous_sql_query_type}")
            except Exception as e:
                print(f"[WARNING] Could not get previous context for route: {e}")
        
        # Initialize Xiquet agent with previous context and run decide_route
        xiquet = Xiquet(
            previous_question=previous_question,
            previous_response=previous_response,
            previous_route=previous_route,
            previous_sql_query_type=previous_sql_query_type,
            previous_entities=previous_entities
        )
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
            diades=xiquet.diades or [],
            gamma=xiquet.gamma
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


# ============================================================
# PROGRESSIVE RESPONSE PATTERN - Two-phase chat with polling
# ============================================================

class StartChatResponse(BaseModel):
    message_id: str
    status: str

class MessageStatusResponse(BaseModel):
    message_id: str
    status: str  # pending, entities_ready, complete, error
    route_used: Optional[str] = None
    identified_entities: Optional[IdentifiedEntities] = None
    response: Optional[str] = None
    table_data: Optional[Union[TableData, List[TableData]]] = None  # Can be single table or list of tables (for custom queries)
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None


def _process_message_background(
    message_id: str, 
    question: str, 
    user_id: str, 
    session_id: Optional[str],
    frontend_context: Optional[dict] = None,  # Context passed from frontend
    pre_selected_entities: Optional[dict] = None  # Pre-selected entities from UI
):
    """
    Background task to process a message in two phases:
    1. Run decide_route() -> save entities to DB (fast, ~500-1000ms)
    2. Run handle_sql/rag() -> save response to DB (slow, ~2-5s)
    
    This runs in a separate thread via BackgroundTasks.
    
    Args:
        frontend_context: Optional dict with previous message context from frontend:
            {question, response, route, sql_query_type, entities}
    """
    import traceback
    from datetime import datetime
    
    start_time = datetime.now()
    xiquet = None
    
    try:
        print(f"\n[BACKGROUND] Starting processing for message_id: {message_id}")
        print(f"[BACKGROUND] Question: {question[:100]}...")
        
        # Get previous message context - prefer frontend_context, fallback to DB
        previous_question = None
        previous_response = None
        previous_route = None
        previous_sql_query_type = None
        previous_entities = None
        
        # OPTION 1: Use context passed from frontend (for unsaved chats)
        if frontend_context:
            previous_question = frontend_context.get("question")
            previous_response = frontend_context.get("response")
            previous_route = frontend_context.get("route")
            previous_sql_query_type = frontend_context.get("sql_query_type")
            previous_entities = frontend_context.get("entities") or {}
            print(f"[BACKGROUND CONTEXT] From frontend: q='{previous_question[:50] if previous_question else 'None'}...', route={previous_route}, sql_type={previous_sql_query_type}")
        
        # OPTION 2: Get from database (for saved sessions)
        elif session_id:
            try:
                session_messages = chat_db.get_session_messages(
                    session_id, 
                    user_id,
                    limit=10
                )
                if session_messages and len(session_messages) > 0:
                    last_msg = session_messages[-1]
                    previous_question = last_msg.get("content")
                    previous_response = last_msg.get("response")
                    previous_route = last_msg.get("route_used")
                    
                    # Extract sql_query_type and entities from identified_entities
                    prev_entities = last_msg.get("identified_entities") or {}
                    previous_sql_query_type = prev_entities.get("sql_query_type")
                    previous_entities = {
                        "colles": prev_entities.get("colles", []),
                        "castells": prev_entities.get("castells", []),
                        "anys": prev_entities.get("anys", []),
                        "llocs": prev_entities.get("llocs", []),
                        "diades": prev_entities.get("diades", []),
                    }
                    
                    print(f"[BACKGROUND CONTEXT] From DB: q='{previous_question[:50] if previous_question else 'None'}...', route={previous_route}, sql_type={previous_sql_query_type}")
                else:
                    print(f"[BACKGROUND CONTEXT] No previous messages found in session {session_id}")
            except Exception as e:
                print(f"[WARNING] Could not get previous context from DB: {e}")
        else:
            print(f"[BACKGROUND CONTEXT] No context available (no frontend_context and no session_id)")
        
        # Initialize Xiquet agent with previous context and pre-selected entities
        xiquet = Xiquet(
            previous_question=previous_question,
            previous_response=previous_response,
            previous_route=previous_route,
            previous_sql_query_type=previous_sql_query_type,
            previous_entities=previous_entities,
            pre_selected_entities=pre_selected_entities
        )
        
        # ============================================================
        # PHASE 1: Route decision (FAST) - Save entities immediately
        # ============================================================
        route_start = datetime.now()
        route_response = xiquet.decide_route(question)
        route_time = (datetime.now() - route_start).total_seconds() * 1000
        print(f"[BACKGROUND] Phase 1 - decide_route(): {route_time:.2f}ms")
        
        # Store route_response in xiquet so handle methods can access it
        xiquet.response = route_response
        
        # Build entities dict
        castells_list = []
        if xiquet.castells:
            for c in xiquet.castells:
                if hasattr(c, 'castell_code'):
                    castells_list.append({
                        "castell_code": c.castell_code,
                        "status": c.status if hasattr(c, 'status') else None
                    })
        
        # Get sql_query_type from route_response
        sql_query_type = getattr(route_response, 'sql_query_type', None) if route_response else None
        
        entities_dict = {
            "colles": xiquet.colles_castelleres or [],
            "castells": castells_list,
            "anys": xiquet.anys or [],
            "llocs": xiquet.llocs or [],
            "diades": xiquet.diades or [],
            "gamma": xiquet.gamma,
            "sql_query_type": sql_query_type
        }
        
        route_used = route_response.tools if route_response else 'unknown'
        
        # SAVE ENTITIES TO DATABASE - Frontend can now poll and see chips!
        chat_db.update_pending_entities(message_id, route_used, entities_dict)
        print(f"[BACKGROUND] Entities saved to DB - status='entities_ready'")
        
        # ============================================================
        # PHASE 2: Generate response (SLOW) - Save when complete
        # ============================================================
        response_start = datetime.now()
        
        if route_response.tools == "direct":
            response_text = xiquet.handle_direct()
        elif route_response.tools == "rag":
            response_text = xiquet.handle_rag()
        elif route_response.tools == "sql":
            response_text = xiquet.handle_sql()
        elif route_response.tools == "hybrid":
            response_text = xiquet.handle_hybrid()
        else:
            response_text = "No estic segur de com respondre això, però ho estic intentant!"
        
        response_time = (datetime.now() - response_start).total_seconds() * 1000
        total_time = int((datetime.now() - start_time).total_seconds() * 1000)
        print(f"[BACKGROUND] Phase 2 - handle_{route_response.tools}(): {response_time:.2f}ms")
        print(f"[BACKGROUND] Total time: {total_time}ms")
        
        # Get table data if available
        table_data_dict = None
        if hasattr(xiquet, 'table_data') and xiquet.table_data:
            table_data_dict = xiquet.table_data
        
        # SAVE RESPONSE TO DATABASE - Frontend can now poll and see full response!
        chat_db.update_pending_complete(message_id, response_text, table_data_dict, total_time)
        print(f"[BACKGROUND] Response saved to DB - status='complete'")
        
        # If session_id is provided, also save to permanent chat_messages table
        print(f"[BACKGROUND] Session ID for history: {session_id or 'NONE'}")
        if session_id:
            saved_id = chat_db.move_pending_to_chat_messages(message_id, user_id)
            if saved_id:
                print(f"[BACKGROUND] Message moved to chat_messages: {saved_id}")
            else:
                print(f"[BACKGROUND] WARNING: Failed to move message to chat_messages!")
        else:
            # For unsaved chats (no session_id), keep the pending_message for rate limiting
            # It will be counted in rate limit checks and can be cleaned up later (after 1 hour)
            print(f"[BACKGROUND] No session_id - message stays in pending_messages for rate limiting")
        
    except Exception as e:
        error_msg = _get_friendly_error_message(e)
        print(f"[BACKGROUND] ERROR: {str(e)}")
        print(f"[BACKGROUND] Traceback: {traceback.format_exc()}")
        
        # Save error status to database
        try:
            chat_db.update_pending_error(message_id, error_msg)
        except Exception as db_error:
            print(f"[BACKGROUND] Failed to save error to DB: {db_error}")


@app.post("/api/chat/start", response_model=StartChatResponse)
async def start_chat(
    message: ChatMessage,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Start processing a chat message in the background.
    Returns immediately with a message_id for polling.
    
    Frontend should:
    1. Call this endpoint to start processing
    2. Poll /api/chat/status/{message_id} every 300-500ms
    3. Show entity chips when status='entities_ready'
    4. Show response when status='complete'
    """
    try:
        # Check user subscription
        # Premium users bypass rate limiting completely
        user_profile = chat_db.get_user_profile(current_user["id"])
        subscription = user_profile.get("subscription", "basic") if user_profile else "basic"
        print(f"[RATE_LIMIT] User {current_user['id']} subscription: {subscription}")
        
        # Create pending message record FIRST (so it gets counted in rate limit check)
        message_id = chat_db.create_pending_message(
            user_id=current_user["id"],
            content=message.content,
            session_id=message.session_id
        )
        
        # Only check rate limit for basic subscription users
        # Premium users have unlimited messages - skip rate limit check
        if subscription == "basic":
            is_allowed, question_count = chat_db.check_rate_limit(
                current_user["id"], 
                MAX_QUESTIONS_BASIC, 
                TIME_BASIC
            )
            
            if not is_allowed:
                # Rate limit exceeded - mark pending message as error
                upgrade_message = f"""Has arribat al límit de {MAX_QUESTIONS_BASIC} preguntes per hora amb el **pla bàsic**.

Per continuar fent preguntes il·limitades, pots [actualitzar al pla premium per només 1,99€/mes](/profile). Aquesta subscripció permet fer tantes preguntes com vulguis al Xiquet.

**Per què hauria de pagar?**

Fer servir models d'intel·ligència artificial no és gratis. Cada pregunta que es fa al Xiquet té un cost real de computació i d'ús dels models d'IA. Xiquet.cat no està finançat per cap empresa ni inversor, i fins ara tot el projecte s'ha pagat directament de la meva butxaca.

Aquesta subscripció ajuda a cobrir els costos de funcionament (servidors, ús dels models d'IA, manteniment i millores) i permet que el projecte pugui continuar existint i creixent. Si decideixes subscriure't, no només obtens accés il·limitat al Xiquet, sinó que també estàs ajudant a mantenir viu aquest projecte fet amb passió pel món casteller."""
                
                # Update pending message with error status
                chat_db.update_pending_error(message_id, upgrade_message)
                
                return StartChatResponse(
                    message_id=message_id,
                    status="error"
                )
        
        print(f"\n[START] Created pending message: {message_id}")
        print(f"[START] Question: {message.content[:100]}...")
        print(f"[START] Session ID: {message.session_id or 'NONE'}")
        print(f"[START] Has frontend context: {message.previous_context is not None}")
        
        # Convert PreviousContext to dict for background task
        frontend_context = None
        if message.previous_context:
            frontend_context = {
                "question": message.previous_context.question,
                "response": message.previous_context.response,
                "route": message.previous_context.route,
                "sql_query_type": message.previous_context.sql_query_type,
                "entities": message.previous_context.entities
            }
        
        # Convert pre-selected entities to dict
        pre_selected_entities = None
        if message.pre_selected_entities:
            pre_selected_entities = {
                "colles": message.pre_selected_entities.colles or [],
                "castells": message.pre_selected_entities.castells or [],
                "anys": message.pre_selected_entities.anys or []
            }
            print(f"[START] Pre-selected entities: {pre_selected_entities}")
        
        # Start background processing
        background_tasks.add_task(
            _process_message_background,
            message_id,
            message.content,
            current_user["id"],
            message.session_id,
            frontend_context,
            pre_selected_entities
        )
        
        # Return immediately with message_id
        return StartChatResponse(
            message_id=message_id,
            status="pending"
        )
        
    except Exception as e:
        import traceback
        print(f"ERROR in start_chat: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/status/{message_id}", response_model=MessageStatusResponse)
async def get_message_status(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Poll for message status during processing.
    
    Returns:
    - status='pending': Still waiting for decide_route to complete
    - status='entities_ready': Entities available, response still processing
    - status='complete': Full response available
    - status='error': Processing failed
    """
    try:
        # Get pending message from database
        pending = chat_db.get_pending_message(message_id, current_user["id"])
        
        if not pending:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Build response
        identified_entities = None
        if pending.get("identified_entities"):
            entities = pending["identified_entities"]
            castells_list = []
            if entities.get("castells"):
                for c in entities["castells"]:
                    if isinstance(c, dict) and "castell_code" in c:
                        castells_list.append(CastellEntity(**c))
            
            identified_entities = IdentifiedEntities(
                colles=entities.get("colles", []),
                castells=castells_list,
                anys=entities.get("anys", []),
                llocs=entities.get("llocs", []),
                diades=entities.get("diades", []),
                gamma=entities.get("gamma"),
                sql_query_type=entities.get("sql_query_type")  # Include sql_query_type!
            )
        
        table_data = None
        if pending.get("table_data"):
            # For custom queries, table_data is a list of tables
            # For other queries, it's a single table dict
            pending_table = pending["table_data"]
            if isinstance(pending_table, list):
                # List of tables (custom queries)
                table_data = [TableData(**table) for table in pending_table]
            else:
                # Single table (other queries)
                table_data = TableData(**pending_table)
        
        return MessageStatusResponse(
            message_id=message_id,
            status=pending["status"],
            route_used=pending.get("route_used"),
            identified_entities=identified_entities,
            response=pending.get("response"),
            table_data=table_data,
            response_time_ms=pending.get("response_time_ms"),
            error_message=pending.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_message_status: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/chat/pending/{message_id}")
async def delete_pending_message(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a pending message (cleanup after frontend receives complete response).
    Optional - pending messages auto-cleanup after 5 minutes.
    """
    try:
        success = chat_db.delete_pending_message(message_id, current_user["id"])
        if success:
            return {"message": "Pending message deleted"}
        else:
            raise HTTPException(status_code=404, detail="Message not found")
    except HTTPException:
        raise
    except Exception as e:
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
        return {"id": session_id, "title": title, "created_at": datetime.now(timezone.utc).isoformat()}
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
            table_data = msg.get("table_data")  # Table data from SQL queries
            identified_entities = msg.get("identified_entities")  # Entities identified by the agent
            
            # Only save if we have both content and response (complete message pair)
            if content and response:
                chat_db.create_message(
                    session_id=session_id,
                    user_id=current_user["id"],
                    content=content,
                    response=response,
                    route_used=route_used,
                    response_time_ms=response_time_ms,
                    table_data=table_data,
                    identified_entities=identified_entities
                )
        
        return {"id": session_id, "title": request.title, "created_at": datetime.now(timezone.utc).isoformat()}
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
                subscription=profile.get("subscription", "basic"),
                role=profile.get("role", "user"),
                created_at=datetime.fromisoformat(profile["created_at"])
            )
        else:
            # If profile doesn't exist, create it with defaults
            try:
                chat_db.create_user_profile(current_user["id"], current_user.get("username"))
                profile = chat_db.get_user_profile(current_user["id"])
                if profile:
                    return UserProfile(
                        id=profile["id"],
                        username=profile["username"],
                        email=current_user.get("email"),
                        subscription=profile.get("subscription", "basic"),
                        role=profile.get("role", "user"),
                        created_at=datetime.fromisoformat(profile["created_at"])
                    )
            except Exception:
                pass
            
            return UserProfile(
                id=current_user["id"],
                username=current_user.get("username"),
                email=current_user.get("email"),
                subscription="basic",
                role="user",
                created_at=datetime.now(timezone.utc)
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

# ============================================================
# STRIPE SUBSCRIPTION ENDPOINTS
# ============================================================

@app.post("/api/subscription/create-checkout")
async def create_checkout_session(
    current_user: dict = Depends(get_current_user)
):
    """
    Create a Stripe checkout session for premium subscription upgrade
    """
    try:
        if not PREMIUM_PRICE_ID:
            raise HTTPException(
                status_code=500, 
                detail="Stripe price ID not configured. Please contact support."
            )
        
        # Get or create Stripe customer
        user_profile = chat_db.get_user_profile(current_user["id"])
        stripe_customer_id = user_profile.get("stripe_customer_id") if user_profile else None
        
        if not stripe_customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=current_user.get("email"),
                metadata={
                    "user_id": current_user["id"],
                    "username": current_user.get("username", "")
                }
            )
            stripe_customer_id = customer.id
            
            # Save customer ID to database
            chat_db.update_subscription(
                current_user["id"], 
                "basic", 
                stripe_customer_id
            )
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": PREMIUM_PRICE_ID,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/profile?success=true",
            cancel_url=f"{FRONTEND_URL}/profile?canceled=true",
            metadata={
                "user_id": current_user["id"]
            }
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating checkout session: {str(e)}"
        )

@app.post("/api/subscription/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for subscription updates
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        if not STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=500,
                detail="Stripe webhook secret not configured"
            )
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")
        
        # Handle the event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = session.get("metadata", {}).get("user_id")
            
            if user_id:
                # Get subscription details
                subscription_id = session.get("subscription")
                if subscription_id:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    customer_id = subscription.customer
                    
                    # Update user subscription to premium
                    chat_db.update_subscription(
                        user_id,
                        "premium",
                        customer_id
                    )
                    print(f"[STRIPE] User {user_id} upgraded to premium")
        
        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription.customer
            
            # Find user by customer_id
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get("user_id")
            
            if user_id:
                if subscription.status == "active":
                    chat_db.update_subscription(user_id, "premium", customer_id)
                    print(f"[STRIPE] User {user_id} subscription active")
                elif subscription.status in ["canceled", "unpaid", "past_due"]:
                    chat_db.update_subscription(user_id, "basic", customer_id)
                    print(f"[STRIPE] User {user_id} subscription downgraded to basic")
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            customer_id = subscription.customer
            
            # Find user by customer_id
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get("user_id")
            
            if user_id:
                chat_db.update_subscription(user_id, "basic", customer_id)
                print(f"[STRIPE] User {user_id} subscription canceled")
        
        return {"status": "success"}
        
    except Exception as e:
        print(f"[STRIPE WEBHOOK ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")

@app.get("/api/subscription/status")
async def get_subscription_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current subscription status and Stripe customer info
    """
    try:
        user_profile = chat_db.get_user_profile(current_user["id"])
        if not user_profile:
            return {
                "subscription": "basic",
                "stripe_customer_id": None,
                "stripe_subscription": None
            }
        
        subscription = user_profile.get("subscription", "basic")
        stripe_customer_id = user_profile.get("stripe_customer_id")
        
        stripe_subscription = None
        if stripe_customer_id and subscription == "premium":
            try:
                # Get active subscriptions for this customer
                subscriptions = stripe.Subscription.list(
                    customer=stripe_customer_id,
                    status="active",
                    limit=1
                )
                if subscriptions.data:
                    stripe_subscription = {
                        "id": subscriptions.data[0].id,
                        "status": subscriptions.data[0].status,
                        "current_period_end": subscriptions.data[0].current_period_end,
                        "cancel_at_period_end": subscriptions.data[0].cancel_at_period_end
                    }
            except Exception as e:
                print(f"[STRIPE] Error fetching subscription: {e}")
        
        return {
            "subscription": subscription,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription": stripe_subscription
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting subscription status: {str(e)}"
        )

# Admin helper function
async def require_admin(current_user: dict = Depends(get_current_user)):
    """Check if current user is admin"""
    try:
        profile = chat_db.get_user_profile(current_user["id"])
        if not profile or profile.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return current_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking admin status: {str(e)}")

# Admin endpoints
@app.get("/api/admin/last-event-date")
async def get_last_event_date(
    admin_user: dict = Depends(require_admin)
):
    """Get the last event date from the database"""
    try:
        import psycopg2
        from datetime import datetime
        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Since dates are stored as TEXT in DD/MM/YYYY format, we need to parse them properly
        # to find the chronologically latest date, not just the lexicographically maximum string
        cur.execute("""
            SELECT date 
            FROM events 
            WHERE date IS NOT NULL 
              AND date ~ '^\\d{2}/\\d{2}/\\d{4}$'
            ORDER BY 
              CAST(SPLIT_PART(date, '/', 3) AS INTEGER) DESC,
              CAST(SPLIT_PART(date, '/', 2) AS INTEGER) DESC,
              CAST(SPLIT_PART(date, '/', 1) AS INTEGER) DESC
            LIMIT 1
        """)
        result = cur.fetchone()
        
        conn.close()
        
        last_date = result[0] if result and result[0] else None
        return {"last_event_date": last_date}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting last event date: {str(e)}")

class ScrapeEventsRequest(BaseModel):
    date_start: str
    date_end: str

@app.post("/api/admin/scrape-events")
async def scrape_events(
    request: ScrapeEventsRequest,
    admin_user: dict = Depends(require_admin)
):
    """Trigger event scraping with date range"""
    try:
        import subprocess
        import sys
        from pathlib import Path
        import traceback
        
        # Get the script path - script is now in backend/database_pipeline/
        # main.py is at /app/backend/main.py, so parent = /app/backend
        script_path = Path(__file__).parent / "database_pipeline" / "scrapping_events.py"
        
        # If not found, try with resolved path
        if not script_path.exists():
            script_path = script_path.resolve()
        
        # Verify script exists
        if not script_path.exists():
            cwd = Path.cwd()
            tried_path = Path(__file__).parent / "database_pipeline" / "scrapping_events.py"
            raise HTTPException(
                status_code=500,
                detail=f"Script not found at: {tried_path}. Current working directory: {cwd}. File location: {Path(__file__)}"
            )
        
        # Verify script is readable
        if not os.access(script_path, os.R_OK):
            raise HTTPException(
                status_code=500,
                detail=f"Script is not readable: {script_path}"
            )
        
        script_abs_path = script_path.resolve()
        # Determine project root - script is in backend/database_pipeline/, so parent.parent = backend, parent.parent.parent = project root
        # But in Docker, we want to use backend as the working directory
        project_root = Path(__file__).parent  # backend/ directory
        
        print(f"[ADMIN] Running scraping script: {script_abs_path}")
        print(f"[ADMIN] Script exists: {script_path.exists()}")
        print(f"[ADMIN] Date range: {request.date_start} to {request.date_end}")
        print(f"[ADMIN] Python executable: {sys.executable}")
        print(f"[ADMIN] Current working directory: {Path.cwd()}")
        print(f"[ADMIN] Project root: {project_root}")
        import sys
        sys.stdout.flush()
        
        # Run the script with date parameters
        # Use absolute paths and set working directory to project root
        result = subprocess.run(
            [sys.executable, str(script_abs_path), request.date_start, request.date_end],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=str(project_root),  # Set working directory to project root
            env=dict(os.environ, PYTHONPATH=str(project_root))  # Add project root to PYTHONPATH
        )
        
        print(f"[ADMIN] Script return code: {result.returncode}")
        if result.stdout:
            print(f"[ADMIN] Script stdout (first 500 chars): {result.stdout[:500]}")
        if result.stderr:
            print(f"[ADMIN] Script stderr: {result.stderr}")
        
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            print(f"[ADMIN] Scraping failed with error: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Scraping failed: {error_msg}"
            )
        
        # Parse output to extract statistics for NEW events only
        output = result.stdout
        stats = {}
        
        # Try to extract statistics from output - look for "New Events Statistics" section
        import re
        # Match patterns from "New Events Statistics" section
        # Look for "Total new events" first
        total_new_match = re.search(r'Total new events:\s*(\d+)', output)
        if total_new_match:
            stats['total_events'] = int(total_new_match.group(1))
        
        # Look for statistics in the "New Events Statistics" section
        # Find the section and extract from there
        new_events_section = re.search(r'New Events Statistics.*?Total new events:\s*(\d+).*?Events with results:\s*(\d+).*?Total castells:\s*(\d+).*?Unique colles:\s*(\d+).*?Unique cities:\s*(\d+)', output, re.DOTALL)
        if new_events_section:
            stats['total_events'] = int(new_events_section.group(1))
            stats['events_with_results'] = int(new_events_section.group(2))
            stats['total_castells'] = int(new_events_section.group(3))
            stats['unique_colles'] = int(new_events_section.group(4))
            stats['unique_cities'] = int(new_events_section.group(5))
        else:
            # Fallback to individual matches if section not found
            events_with_results_match = re.search(r'Events with results:\s*(\d+)', output)
            if events_with_results_match:
                stats['events_with_results'] = int(events_with_results_match.group(1))
            
            total_castells_match = re.search(r'Total castells:\s*(\d+)', output)
            if total_castells_match:
                stats['total_castells'] = int(total_castells_match.group(1))
            
            unique_colles_match = re.search(r'Unique colles:\s*(\d+)', output)
            if unique_colles_match:
                stats['unique_colles'] = int(unique_colles_match.group(1))
            
            unique_cities_match = re.search(r'Unique cities:\s*(\d+)', output)
            if unique_cities_match:
                stats['unique_cities'] = int(unique_cities_match.group(1))
        
        return {
            "message": "Scraping completed successfully",
            "output": output,
            **stats
        }
    except subprocess.TimeoutExpired as e:
        error_msg = "Scraping timed out after 10 minutes"
        print(f"[ADMIN] {error_msg}")
        import sys
        sys.stdout.flush()
        raise HTTPException(status_code=500, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        error_msg = f"Error scraping events: {str(e)}"
        print(f"[ADMIN] {error_msg}")
        print(f"[ADMIN] Traceback:\n{error_trace}")
        import sys
        sys.stdout.flush()
        # Include traceback in detail for debugging (can be removed in production)
        raise HTTPException(
            status_code=500, 
            detail=f"{error_msg}\n\nTraceback:\n{error_trace[:1000]}"  # Limit traceback length
        )

class UpdateDatabaseRequest(BaseModel):
    from_date: str

@app.post("/api/admin/update-database")
async def update_database(
    request: UpdateDatabaseRequest,
    admin_user: dict = Depends(require_admin)
):
    """Trigger database update with FROM_DATE"""
    try:
        import subprocess
        import sys
        from pathlib import Path
        
        # Get the script path
        script_path = Path(__file__).parent / "database_pipeline" / "update_database_new_events.py"
        
        # Run the script with FROM_DATE parameter
        result = subprocess.run(
            [sys.executable, str(script_path), request.from_date],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Database update failed: {result.stderr}"
            )
        
        # Parse output to extract statistics
        output = result.stdout
        stats = {}
        
        # Try to extract statistics from output
        import re
        events_inserted_match = re.search(r'Actuacions updated:\s*(\d+)\s+new events inserted', output)
        if events_inserted_match:
            stats['events_inserted'] = int(events_inserted_match.group(1))
        
        event_colles_match = re.search(r'Event-colles relationships:\s*(\d+)\s+inserted', output)
        if event_colles_match:
            stats['event_colles_inserted'] = int(event_colles_match.group(1))
        
        castells_match = re.search(r'Castells:\s*(\d+)\s+inserted', output)
        if castells_match:
            stats['castells_inserted'] = int(castells_match.group(1))
        
        return {
            "message": "Database update completed successfully",
            "output": output,
            **stats
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Database update timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating database: {str(e)}")

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
        
        # Create user profile in database with default subscription and role
        if result["user"]:
            try:
                chat_db.create_user_profile(result["user"]["id"], request.username)
            except Exception as profile_error:
                # Log the error but don't fail registration if profile creation fails
                print(f"Warning: Failed to create user profile: {profile_error}")
        
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

# Contact form endpoint
class ContactMessage(BaseModel):
    name: str
    email: str
    message: str

@app.post("/api/contact")
async def send_contact_message(
    contact: ContactMessage,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a contact form message via email.
    """
    try:
        # Email configuration
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SMTP_EMAIL", "xiquet.cat.ai@gmail.com")
        sender_password = os.getenv("SMTP_PASSWORD")
        recipient_email = "xiquet.cat.ai@gmail.com"
        
        if not sender_password:
            # If no SMTP password configured, just log the message
            print(f"[Contact Form] From: {contact.name} <{contact.email}>")
            print(f"[Contact Form] Message: {contact.message}")
            return {"message": "Missatge rebut correctament (mode desenvolupament)"}
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"[Xiquet CAT Contact] Missatge de {contact.name}"
        
        # Email body
        body = f"""
Nou missatge del formulari de contacte de Xiquet AI:

Nom: {contact.name}
Correu: {contact.email}
Usuari connectat: {current_user.get('username', 'Desconegut')} ({current_user.get('email', 'N/A')})

Missatge:
{contact.message}

---
Enviat des de xiquet.cat.ai
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {"message": "Missatge enviat correctament"}
        
    except Exception as e:
        print(f"Error sending contact email: {e}")
        raise HTTPException(status_code=500, detail="Error enviant el missatge. Si us plau, torna-ho a intentar.")

# Feedback endpoint for chat responses
class FeedbackMessage(BaseModel):
    name: str
    email: str
    feedback: str
    user_question: str
    xiquet_answer: str

@app.post("/api/feedback")
async def send_feedback(
    feedback: FeedbackMessage,
    current_user: dict = Depends(get_current_user)
):
    """
    Send feedback about a chat response via email.
    Includes the user's question and Xiquet's answer for context.
    """
    try:
        # Email configuration
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SMTP_EMAIL", "xiquet.cat.ai@gmail.com")
        sender_password = os.getenv("SMTP_PASSWORD")
        recipient_email = "xiquet.cat.ai@gmail.com"
        
        if not sender_password:
            # If no SMTP password configured, just log the message
            print(f"[Feedback] From: {feedback.name} <{feedback.email}>")
            print(f"[Feedback] Question: {feedback.user_question}")
            print(f"[Feedback] Answer: {feedback.xiquet_answer}")
            print(f"[Feedback] Feedback: {feedback.feedback}")
            return {"message": "Feedback rebut correctament (mode desenvolupament)"}
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"[Xiquet AI Feedback] Comentari de {feedback.name}"
        
        # Email body with chat context
        body = f"""
Nou feedback sobre una resposta de Xiquet AI:

Nom: {feedback.name}
Correu: {feedback.email}
Usuari connectat: {current_user.get('username', 'Desconegut')} ({current_user.get('email', 'N/A')})

---
PREGUNTA DE L'USUARI:
{feedback.user_question}

---
RESPOSTA DE XIQUET:
{feedback.xiquet_answer}

---
FEEDBACK DE L'USUARI:
{feedback.feedback}

---
Enviat des de xiquet.cat.ai
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {"message": "Feedback enviat correctament"}
        
    except Exception as e:
        print(f"Error sending feedback email: {e}")
        raise HTTPException(status_code=500, detail="Error enviant el feedback. Si us plau, torna-ho a intentar.")

# El Joc del Mocador game endpoints
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

@app.get("/api/joc-del-mocador/questions")
async def get_game_questions(
    num_questions: int = 10,
    colles: Optional[str] = None,
    years: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate questions for El Joc del Mocador trivia game in parallel.
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
