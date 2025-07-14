"""
Authentication Manager
Handles user authentication and JWT token management
"""

import jwt
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import os

class AuthManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')
        self.token_expiry_hours = int(os.getenv('TOKEN_EXPIRY_HOURS', 24))
        
        # In a real implementation, this would connect to a user database
        # For demo purposes, we'll use a simple in-memory store
        self.users = {
            'admin@company.com': {
                'user_id': 1,
                'email': 'admin@company.com',
                'name': 'System Administrator',
                'password_hash': self._hash_password('admin123'),
                'role': 'admin'
            },
            'support@company.com': {
                'user_id': 2,
                'email': 'support@company.com',
                'name': 'Support Manager',
                'password_hash': self._hash_password('support123'),
                'role': 'support'
            }
        }

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user with email and password"""
        try:
            user = self.users.get(email)
            if user and self._verify_password(password, user['password_hash']):
                return {
                    'user_id': user['user_id'],
                    'email': user['email'],
                    'name': user['name'],
                    'role': user['role']
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return None

    def generate_token(self, user_id: int) -> str:
        """Generate JWT token for user"""
        try:
            payload = {
                'user_id': user_id,
                'exp': datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            return token
            
        except Exception as e:
            self.logger.error(f"Token generation failed: {str(e)}")
            raise

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return user info"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None
        except Exception as e:
            self.logger.error(f"Token verification failed: {str(e)}")
            return None

    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh JWT token"""
        try:
            payload = self.verify_token(token)
            if payload:
                return self.generate_token(payload['user_id'])
            return None
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {str(e)}")
            return None

    def create_user(self, email: str, password: str, name: str, role: str = 'support') -> Dict:
        """Create new user (for demo purposes)"""
        try:
            if email in self.users:
                return {'success': False, 'message': 'User already exists'}
            
            user_id = len(self.users) + 1
            password_hash = self._hash_password(password)
            
            self.users[email] = {
                'user_id': user_id,
                'email': email,
                'name': name,
                'password_hash': password_hash,
                'role': role
            }
            
            return {'success': True, 'user_id': user_id}
            
        except Exception as e:
            self.logger.error(f"User creation failed: {str(e)}")
            return {'success': False, 'message': 'Failed to create user'}

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        for user_data in self.users.values():
            if user_data['user_id'] == user_id:
                return {
                    'user_id': user_data['user_id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'role': user_data['role']
                }
        return None