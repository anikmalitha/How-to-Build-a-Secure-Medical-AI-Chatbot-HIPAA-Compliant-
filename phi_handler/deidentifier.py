"""
Main PHI De-identification and Re-identification logic
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from .patterns import PHIPatterns
from .tokenizer import TokenManager, SecureTokenManager
from .config import PHIConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PHIDeidentifier:
    """Main class for de-identifying and re-identifying PHI in text"""
    
    def __init__(self, session_id: str = None, use_secure_tokens: bool = False):
        """
        Initialize the PHI Deidentifier
        
        Args:
            session_id: Unique session identifier
            use_secure_tokens: Whether to use encrypted token storage
        """
        self.config = PHIConfig()
        
        if use_secure_tokens:
            self.token_manager = SecureTokenManager(session_id)
        else:
            self.token_manager = TokenManager(session_id)
        
        self.compiled_patterns = PHIPatterns.compile_patterns()
        
        self.stats = {
            'total_deidentified': 0,
            'total_reidentified': 0,
            'by_category': {}
        }
    
    def deidentify(self, text: str, categories: List[str] = None) -> Tuple[str, Dict]:
        """
        De-identify PHI in the given text
        
        Args:
            text: Input text containing potential PHI
            categories: Optional list of PHI categories to process
        
        Returns:
            Tuple of (deidentified_text, found_phi_mapping)
        """
        if not text:
            return text, {}
        
        deidentified_text = text
        found_phi = {}
        
        if categories is None:
            categories = list(self.compiled_patterns.keys())
        
        # Process in order of specificity
        priority_order = [
            'SSN', 'CREDIT_CARD', 'MRN', 'ACCOUNT', 'INSURANCE',
            'DOB', 'EMAIL', 'PHONE', 'IP', 'URL',
            'DATE', 'ADDRESS', 'ZIP', 'AGE',
            'DOCTOR', 'HOSPITAL', 'NAME', 'LICENSE'
        ]
        
        ordered_categories = [c for c in priority_order if c in categories]
        ordered_categories += [c for c in categories if c not in ordered_categories]
        
        for category in ordered_categories:
            if category not in self.compiled_patterns:
                continue
            
            patterns = self.compiled_patterns[category]
            
            for pattern in patterns:
                matches = list(pattern.finditer(deidentified_text))
                
                for match in reversed(matches):
                    original_value = match.group(0)
                    
                    # Skip already tokenized values
                    if original_value.startswith('[') and original_value.endswith(']'):
                        continue
                    
                    token = self.token_manager.generate_token(original_value, category)
                    
                    start, end = match.span()
                    deidentified_text = (
                        deidentified_text[:start] +
                        token +
                        deidentified_text[end:]
                    )
                    
                    if category not in found_phi:
                        found_phi[category] = []
                    found_phi[category].append({
                        'original': original_value,
                        'token': token,
                        'position': start
                    })
                    
                    self.stats['total_deidentified'] += 1
                    self.stats['by_category'][category] = \
                        self.stats['by_category'].get(category, 0) + 1
        
        if self.config.ENABLE_LOGGING and found_phi:
            logger.info(f"De-identified {sum(len(v) for v in found_phi.values())} PHI items")
        
        return deidentified_text, found_phi
    
    def reidentify(self, text: str) -> str:
        """
        Re-identify (restore) PHI in the given text
        
        Args:
            text: Text containing tokens to be replaced
        
        Returns:
            Text with tokens replaced by original PHI values
        """
        if not text:
            return text
        
        reidentified_text = text
        
        # Find all tokens in the text
        token_pattern = re.compile(r'\[[A-Z_]+_\d{3}\]')
        matches = list(token_pattern.finditer(text))
        
        for match in reversed(matches):
            token = match.group(0)
            original = self.token_manager.get_original(token)
            
            if original:
                start, end = match.span()
                reidentified_text = (
                    reidentified_text[:start] +
                    original +
                    reidentified_text[end:]
                )
                self.stats['total_reidentified'] += 1
            else:
                logger.warning(f"Token not found in mapping: {token}")
        
        return reidentified_text
    
    def deidentify_with_context(self, text: str) -> Tuple[str, Dict, str]:
        """
        De-identify text while preserving context hints
        
        Returns:
            Tuple of (deidentified_text, found_phi, context_hints)
        """
        deidentified_text, found_phi = self.deidentify(text)
        
        context_hints = []
        for category, items in found_phi.items():
            count = len(items)
            hints_map = {
                'NAME': f"[{count} name(s)]",
                'DATE': f"[{count} date(s)]",
                'DOB': f"[{count} date of birth]",
                'PHONE': f"[{count} phone(s)]",
                'EMAIL': f"[{count} email(s)]",
                'ADDRESS': f"[{count} address(es)]",
                'AGE': f"[{count} age(s)]",
                'SSN': f"[{count} ID(s)]",
                'MRN': f"[{count} medical record(s)]",
            }
            if category in hints_map:
                context_hints.append(hints_map[category])
        
        context_string = " ".join(context_hints) if context_hints else ""
        
        return deidentified_text, found_phi, context_string
    
    def get_statistics(self) -> Dict:
        """Get de-identification statistics"""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'total_deidentified': 0,
            'total_reidentified': 0,
            'by_category': {}
        }
    
    def clear_session(self):
        """Clear all session data including tokens"""
        self.token_manager.clear()
        self.reset_statistics()
    
    def get_token_mapping(self) -> Dict:
        """Get current token mappings"""
        return self.token_manager.get_all_tokens()
    
    def export_session(self) -> Dict:
        """Export session data for persistence"""
        return {
            'token_mappings': self.token_manager.export_mappings(),
            'statistics': self.stats
        }
    
    def import_session(self, data: Dict):
        """Import session data from persistence"""
        if 'token_mappings' in data:
            self.token_manager.import_mappings(data['token_mappings'])
        if 'statistics' in data:
            self.stats = data['statistics']