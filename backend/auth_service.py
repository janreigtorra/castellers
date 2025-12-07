"""
supabase_auth.py
Supabase authentication utilities for the backend
"""

import os
import jwt
from typing import Optional, Dict, Any
from supabase import create_client, Client
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")  # Use ANON_KEY from your .env
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseAuth:
    """Supabase authentication handler"""
    
    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token using Supabase client and extract user information
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Use Supabase client to verify the token by calling get_user
            # This method verifies the token automatically
            response = supabase.auth.get_user(token)
            
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "username": response.user.user_metadata.get("username") if response.user.user_metadata else None,
                    "role": response.user.role if hasattr(response.user, 'role') else None
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found in token"
                )
            
        except Exception as e:
            error_msg = str(e)
            print(f"[AUTH] Error verifying token with Supabase client: {error_msg}")
            
            # If Supabase client method fails, try manual JWT decode as fallback
            # This is useful if the JWT_SECRET is configured correctly
            try:
                if not SUPABASE_JWT_SECRET:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="JWT secret not configured and Supabase client verification failed"
                    )
                
                # Remove 'Bearer ' prefix if present
                if token.startswith('Bearer '):
                    token = token[7:]
                
                # Decode JWT token manually (without verification first to get payload)
                # Then verify with the secret
                payload = jwt.decode(
                    token, 
                    SUPABASE_JWT_SECRET, 
                    algorithms=["HS256"],
                    options={"verify_exp": False, "verify_signature": True}  # Verify signature but not exp
                )
                
                return {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "username": payload.get("user_metadata", {}).get("username") if isinstance(payload.get("user_metadata"), dict) else None,
                    "role": payload.get("role"),
                    "aud": payload.get("aud")
                }
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            except jwt.InvalidTokenError as jwt_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token signature: {str(jwt_error)}"
                )
            except Exception as fallback_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token verification failed: {str(fallback_error)}"
                )
    
    @staticmethod
    async def sign_up(email: str, password: str, username: str = None) -> Dict[str, Any]:
        """
        Register a new user with Supabase Auth
        """
        try:
            user_metadata = {}
            if username:
                user_metadata["username"] = username
            
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata
                }
            })
            
            if response.user:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "username": username,
                        "email_confirmed": response.user.email_confirmed_at is not None
                    },
                    "session": response.session
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user"
                )
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}"
            )
    
    @staticmethod
    async def sign_in(email: str, password: str) -> Dict[str, Any]:
        """
        Sign in user with Supabase Auth
        """
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "username": response.user.user_metadata.get("username"),
                        "email_confirmed": response.user.email_confirmed_at is not None
                    },
                    "session": response.session
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Login failed: {str(e)}"
            )
    
    @staticmethod
    async def sign_out(token: str) -> bool:
        """
        Sign out user
        """
        try:
            supabase.auth.sign_out()
            return True
        except Exception as e:
            print(f"Sign out error: {e}")
            return False
    
    @staticmethod
    async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from Supabase
        """
        try:
            # Get user from auth
            response = supabase.auth.get_user()
            if response.user and response.user.id == user_id:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "username": response.user.user_metadata.get("username"),
                    "created_at": response.user.created_at,
                    "last_sign_in": response.user.last_sign_in_at,
                    "email_confirmed": response.user.email_confirmed_at is not None
                }
            return None
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    @staticmethod
    async def update_user_profile(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update user profile
        """
        try:
            response = supabase.auth.update_user({
                "data": updates
            })
            
            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "username": response.user.user_metadata.get("username"),
                    "updated_at": response.user.updated_at
                }
            return None
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return None

# Create global auth instance
supabase_auth = SupabaseAuth()
