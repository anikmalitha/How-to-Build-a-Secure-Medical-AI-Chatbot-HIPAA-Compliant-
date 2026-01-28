"""
Token management for PHI de-identification
Handles creation, storage, and retrieval of PHI tokens
"""

import uuid
import hashlib
from datetime import datetime
from typing import Dict, Optional
from .config import PHIConfig


class TokenManager:
    """Manages tokens for PHI replacement and restoration"""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.token_map: Dict[str, Dict] = {}
        self.reverse_map: Dict[str, str] = {}
        self.token_counter = 0
        self.config = PHIConfig()
    
    def generate_token(self, original_value: str, category: str) -> str:
        """Generate a unique token for a PHI value"""
        cache_key = f"{category}:{original_value}"
        if cache_key in self.reverse_map:
            return self.reverse_map[cache_key]
        
        if len(self.token_map) >= self.config.MAX_TOKENS_PER_SESSION:
            self._cleanup_old_tokens()
        
        self.token_counter += 1
        prefix = self.config.TOKEN_PREFIXES.get(category, self.config.TOKEN_PREFIXES['GENERIC'])
        token = f"{prefix}{self.token_counter:03d}{self.config.TOKEN_SUFFIX}"
        
        self.token_map[token] = {
            'original': original_value,
            'category': category,
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        self.reverse_map[cache_key] = token
        
        return token
    
    def get_original(self, token: str) -> Optional[str]:
        """Get the original value for a token"""
        if token in self.token_map:
            return self.token_map[token]['original']
        return None
    
    def get_token_info(self, token: str) -> Optional[Dict]:
        """Get full information about a token"""
        return self.token_map.get(token)
    
    def get_all_tokens(self) -> Dict[str, Dict]:
        """Get all token mappings"""
        return self.token_map.copy()
    
    def clear(self):
        """Clear all token mappings"""
        self.token_map.clear()
        self.reverse_map.clear()
        self.token_counter = 0
    
    def _cleanup_old_tokens(self):
        """Remove oldest tokens when limit is reached"""
        if len(self.token_map) > 0:
            sorted_tokens = sorted(
                self.token_map.items(),
                key=lambda x: x[1]['timestamp']
            )
            tokens_to_remove = len(sorted_tokens) // 10 or 1
            for token, info in sorted_tokens[:tokens_to_remove]:
                cache_key = f"{info['category']}:{info['original']}"
                self.reverse_map.pop(cache_key, None)
                self.token_map.pop(token, None)
    
    def export_mappings(self) -> Dict:
        """Export all mappings for persistence"""
        return {
            'session_id': self.session_id,
            'token_counter': self.token_counter,
            'token_map': self.token_map,
            'reverse_map': self.reverse_map
        }
    
    def import_mappings(self, data: Dict):
        """Import mappings from persistence"""
        self.session_id = data.get('session_id', self.session_id)
        self.token_counter = data.get('token_counter', 0)
        self.token_map = data.get('token_map', {})
        self.reverse_map = data.get('reverse_map', {})


class SecureTokenManager(TokenManager):
    """Enhanced token manager with hash verification"""
    
    def __init__(self, session_id: str = None, encryption_key: str = None):
        super().__init__(session_id)
        self.encryption_key = encryption_key or self._generate_key()
    
    def _generate_key(self) -> str:
        """Generate a session-specific key"""
        return hashlib.sha256(
            f"{self.session_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]
    
    def _hash_value(self, value: str) -> str:
        """Create a secure hash of a value"""
        return hashlib.sha256(
            f"{self.encryption_key}{value}".encode()
        ).hexdigest()[:16]
    
    def generate_token(self, original_value: str, category: str) -> str:
        """Generate a secure token with hash"""
        token = super().generate_token(original_value, category)
        self.token_map[token]['hash'] = self._hash_value(original_value)
        return token
    
    def verify_token(self, token: str) -> bool:
        """Verify token integrity"""
        if token not in self.token_map:
            return False
        info = self.token_map[token]
        expected_hash = self._hash_value(info['original'])
        return info.get('hash') == expected_hash