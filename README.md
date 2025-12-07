# Xiquet Casteller - AI Assistant Infrastructure

A production-ready AI chat application for Casteller knowledge, built with modern web technologies and containerized deployment.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Supabase      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (Database)    │
│   Port 3001     │    │   Port 8000     │    │   (Auth + DB)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Development Mode (Recommended)
```bash
# Start both services with hot reload
make dev

# Access the application:
# Frontend: http://localhost:3001
# Backend API: http://localhost:8000/docs
```

### Production Mode
```bash
# Start production environment
make prod

# Access the application:
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## 📁 Project Structure

```
castellers/
├── backend/                    # FastAPI backend
│   ├── main.py                # Main API server
│   ├── agent.py               # Xiquet AI agent
│   ├── auth_service.py        # Supabase authentication
│   ├── database_service.py   # Database operations
│   ├── llm_function.py       # LLM provider interface
│   ├── rag_index.py          # RAG search functionality
│   └── requirements.txt       # Python dependencies
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── ChatInterface.js
│   │   │   ├── SessionManager.js
│   │   │   ├── Header.js
│   │   │   └── LoginForm.js
│   │   ├── App.js            # Main app component
│   │   ├── supabaseClient.js # Supabase integration
│   │   └── apiService.js     # API communication
│   └── package.json          # Node dependencies
├── docker/                     # Docker configurations
│   ├── Dockerfile.backend    # Backend container
│   ├── Dockerfile.frontend   # Frontend container
│   └── nginx.conf            # Nginx configuration
├── database_pipeline/          # Database setup
│   └── create_chat_tables.sql # Database schema
├── docker-compose.yml         # Production orchestration
├── docker-compose.dev.yml     # Development overrides
└── Makefile                   # Build automation
```

## 🔧 Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Supabase**: Backend-as-a-Service (Auth + Database)
- **PostgreSQL**: Primary database via Supabase
- **Python**: Core language with async support
- **Uvicorn**: ASGI server with hot reload

### Frontend
- **React**: JavaScript UI library
- **Axios**: HTTP client for API calls
- **Supabase JS**: Client-side Supabase integration
- **CSS3**: Styling with modern features

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration
- **Nginx**: Reverse proxy and static file serving
- **Make**: Build automation

### AI/ML
- **Multiple LLM Providers**: OpenAI, Anthropic, Groq, Gemini, etc.
- **Sentence Transformers**: Embeddings for RAG
- **ChromaDB**: Vector database for embeddings
- **LangChain**: LLM framework integration

## Database Schema

### Tables (Supabase PostgreSQL)

#### `profiles`
- Extends Supabase `auth.users`
- Stores user metadata (username, timestamps)

#### `chat_sessions`
- Individual conversation sessions
- Links to users and contains session metadata
- Auto-updates timestamp on new messages

#### `chat_messages`
- Individual messages with AI responses
- Stores metadata (route used, response time)
- Links to sessions and users

### Security
- **Row Level Security (RLS)**: Users only see their own data
- **JWT Authentication**: Secure token-based auth
- **CORS Protection**: Configured for frontend-backend communication

## Authentication Flow

1. **User Registration/Login**: Handled by Supabase Auth
2. **JWT Token**: Generated and stored in browser
3. **API Requests**: Token sent in Authorization header
4. **Backend Validation**: JWT verified against Supabase secret
5. **Database Access**: User ID extracted from token for RLS

## AI Agent Architecture

### Xiquet Agent (`agent.py`)
- **Multi-route Processing**: Direct, RAG, SQL, Hybrid
- **Context-Aware**: Maintains conversation context
- **Provider Agnostic**: Works with multiple LLM providers
- **Response Metadata**: Tracks route used and performance

### RAG System (`rag_index.py`)
- **Document Embeddings**: Generated with Sentence Transformers
- **Vector Search**: Semantic similarity search
- **Supabase Integration**: Embeddings stored in PostgreSQL
- **Context Retrieval**: Relevant documents for AI context

## 🐳 Docker Configuration

### Development Mode
- **Hot Reload**: Code changes trigger automatic restarts
- **Volume Mounting**: Live code editing
- **Port Mapping**: Frontend on 3001, Backend on 8000
- **Debug Mode**: Enhanced logging and error messages

### Production Mode
- **Optimized Builds**: Multi-stage builds for smaller images
- **Nginx Frontend**: Better performance than dev server
- **Health Checks**: Automatic service monitoring
- **Security**: Non-root users, security headers

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `POST /api/auth/logout` - User logout

### Chat
- `POST /api/chat` - Send message to Xiquet
- `GET /api/chat/history` - Get chat history
- `GET /api/sessions` - Get user sessions
- `POST /api/sessions` - Create new session
- `PUT /api/sessions/{id}` - Update session
- `DELETE /api/sessions/{id}` - Delete session

### User Management
- `GET /api/user/profile` - Get user profile
- `PUT /api/user/profile` - Update user profile

## Available Commands

### Development
```bash
make dev                 # Start development environment
make dev-backend         # Backend only (with hot reload)
make dev-frontend        # Frontend only (with hot reload)
```

### Production
```bash
make prod                # Start production environment
make build               # Build Docker images
make up                  # Start services
make down                # Stop services
```

### Utilities
```bash
make logs                # View all logs
make logs-backend        # Backend logs only
make logs-frontend       # Frontend logs only
make clean               # Clean up Docker resources
make health              # Check service health
```

### Installation
```bash
make install-backend     # Install Python dependencies
make install-frontend    # Install Node dependencies
```

## Access Points

### Development
- **Frontend**: http://localhost:3001
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Production
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🔧 Environment Configuration

### Backend (.env)
```bash
# Supabase Configuration
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=...

# LLM API Keys
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
# ... other providers
```

### Frontend (.env.local)
```bash
REACT_APP_SUPABASE_URL=https://...
REACT_APP_SUPABASE_ANON_KEY=eyJ...
REACT_APP_API_URL=http://localhost:8000
```

## Testing the Application

### 1. Authentication
1. Go to http://localhost:3001 (dev) or http://localhost:3000 (prod)
2. Click "Entrar" (Login)
3. Register a new account or login
4. Verify authentication status

### 2. Chat Functionality
1. **Create Session**: Click "+ Nova conversa"
2. **Ask Questions**: Try "Què és un castell?"
3. **Switch Sessions**: Click on different sessions
4. **Check Persistence**: Refresh page - messages persist

### 3. Session Management
1. **Multiple Sessions**: Create different conversation topics
2. **Delete Sessions**: Click the × button
3. **Session Metadata**: View message counts and dates

## Deployment

### Local Production
```bash
make prod
```

### Cloud Deployment
1. **Build Images**: `make build`
2. **Push to Registry**: Tag and push Docker images
3. **Deploy**: Use docker-compose on server
4. **Environment**: Set production environment variables

### Scaling
- **Horizontal**: Multiple backend instances behind load balancer
- **Database**: Supabase handles scaling automatically
- **CDN**: Frontend can be served via CDN

## Monitoring & Debugging

### Health Checks
```bash
make health              # Check service status
curl http://localhost:8000/api/health  # Backend health
```

### Logs
```bash
make logs                # All services
make logs-backend        # Backend only
make logs-frontend       # Frontend only
```

### Database
- **Supabase Dashboard**: Monitor database performance
- **SQL Editor**: Run queries and check data
- **Auth Dashboard**: Monitor user authentication

## Security Features

- **JWT Authentication**: Secure token-based auth
- **Row Level Security**: Database-level access control
- **CORS Protection**: Configured for frontend-backend
- **Input Validation**: Pydantic models for API validation
- **Non-root Containers**: Security best practices
- **Environment Variables**: Sensitive data protection

## Performance Features

- **Hot Reload**: Fast development iteration
- **Multi-stage Builds**: Optimized production images
- **Nginx Caching**: Static asset optimization
- **Database Indexing**: Optimized queries
- **Connection Pooling**: Efficient database connections
- **Async Processing**: Non-blocking operations

## Development Workflow

1. **Start Development**: `make dev`
2. **Make Changes**: Edit code in your IDE
3. **Auto Reload**: Services restart automatically
4. **Test Changes**: Refresh browser to see updates
5. **Stop Development**: `make down`

## Key Features

✅ **Real-time Chat Interface**
✅ **Supabase Authentication**
✅ **Persistent Chat Sessions**
✅ **Database Storage**
✅ **Docker Containerization**
✅ **Session Management**
✅ **Message History**
✅ **User Profiles**
✅ **Production Ready**
✅ **Hot Reload Development**
✅ **Health Monitoring**
✅ **API Documentation**

---

**Xiquet Casteller** is now a fully functional, production-ready AI chat application with modern infrastructure, persistent storage, and scalable architecture! 
