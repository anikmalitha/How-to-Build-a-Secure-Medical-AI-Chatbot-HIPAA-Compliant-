"""
Regex patterns for identifying PHI (Protected Health Information)
Covers HIPAA identifiers and common medical data patterns
"""

import re


class PHIPatterns:
    """Collection of regex patterns for PHI detection"""
    
    # Social Security Number patterns
    SSN_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',
        r'\b\d{3}\s\d{2}\s\d{4}\b',
        r'\b\d{9}\b(?=.*(?:ssn|social|security))',
    ]
    
    # Phone number patterns (US and Bangladesh)
    PHONE_PATTERNS = [
        r'\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b',
        r'\b\(\d{3}\)\s?\d{3}[-.\s]?\d{4}\b',
        r'\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',
        r'\b01\d{9}\b',  # Bangladesh: 01XXXXXXXXX
        r'\b\+880\d{10}\b',  # Bangladesh with country code
        r'\b\+91\d{10}\b',  # India
    ]
    
    # Email patterns
    EMAIL_PATTERNS = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ]
    
    # Date patterns
    DATE_PATTERNS = [
        r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
        r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
    ]
    
    # Date of Birth with context
    DOB_PATTERNS = [
        r'(?:born|birth|dob|date of birth|birthday)[:\s]+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
        r'(?:born|birth|dob|date of birth|birthday)[:\s]+\d{4}[-/]\d{1,2}[-/]\d{1,2}',
        r'(?:born on|born in|birthday on)[:\s]+[\w\s,]+\d{4}',
    ]
    
    # Age patterns
    AGE_PATTERNS = [
        r'\b\d{1,3}\s*(?:years?\s*old|yrs?\s*old|y/?o)\b',
        r'\bage[:\s]+\d{1,3}\b',
        r'\b(?:i am|i\'m|he is|she is|patient is|aged)\s+\d{1,3}\b',
    ]
    
    # Address patterns
    ADDRESS_PATTERNS = [
        r'\b\d{1,5}\s+[\w\s]{1,30}(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct|circle|cir|place|pl)\b',
        r'\b(?:house|flat|apt|apartment|unit|suite|ste)[\s#]+\d+[a-z]?\b',
        r'\b(?:road|sector|block)\s+\d+[a-z]?\b',  # Bangladesh/South Asian format
    ]
    
    # ZIP/Postal code patterns
    ZIP_PATTERNS = [
        r'\b\d{5}(?:-\d{4})?\b',
        r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b',
        r'\b\d{4}\b(?=.*(?:zip|postal|code|pin))',
        r'\b\d{6}\b(?=.*(?:postal|pin|code))',  # India PIN code
    ]
    
    # Medical Record Number patterns
    MRN_PATTERNS = [
        r'(?:mrn|medical record|patient id|patient number|chart|reg(?:istration)?)[:\s#]*[A-Z0-9]{4,12}\b',
        r'\b[A-Z]{2,3}\d{6,10}\b',
        r'(?:patient|reg|id)[:\s#]*\d{6,12}\b',
    ]
    
    # Account/Member number patterns
    ACCOUNT_PATTERNS = [
        r'(?:account|acct|member|id)[:\s#]*\d{6,15}\b',
        r'\b[A-Z]{1,3}\d{8,12}\b',
    ]
    
    # Credit Card patterns
    CREDIT_CARD_PATTERNS = [
        r'\b(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        r'\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b',
    ]
    
    # IP Address patterns
    IP_PATTERNS = [
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        r'\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b',
    ]
    
    # URL patterns
    URL_PATTERNS = [
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        r'www\.[^\s<>"{}|\\^`\[\]]+',
    ]
    
    # Insurance/Policy patterns
    INSURANCE_PATTERNS = [
        r'(?:insurance|policy|group)[:\s#]*[A-Z0-9]{5,15}\b',
        r'\b[A-Z]{2,4}\d{6,12}\b(?=.*(?:insurance|policy|coverage))',
    ]
    
    # License/Passport patterns
    LICENSE_PATTERNS = [
        r'(?:license|licence|dl|driving)[:\s#]*[A-Z0-9]{6,12}\b',
        r'(?:passport)[:\s#]*[A-Z0-9]{6,12}\b',
        r'(?:nid|national id)[:\s#]*\d{10,17}\b',  # National ID
    ]
    
    # Name patterns (with context clues)
    NAME_PATTERNS = [
        r'(?:my name is|i am|i\'m|this is|patient|mr\.?|mrs\.?|ms\.?|dr\.?|miss)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
        r'(?:name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
        r'(?:patient name|full name)[:\s]+[\w\s]+',
    ]
    
    # Doctor/Hospital patterns
    DOCTOR_PATTERNS = [
        r'(?:dr\.?|doctor|physician)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'(?:consultant|specialist)[:\s]+[\w\s\.]+',
    ]
    
    HOSPITAL_PATTERNS = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:hospital|medical center|clinic|healthcare|diagnostic)',
        r'(?:admitted to|visited|at)\s+[\w\s]+(?:hospital|clinic|center)',
    ]
    
    @classmethod
    def get_all_patterns(cls):
        """Return all patterns organized by category"""
        return {
            'SSN': cls.SSN_PATTERNS,
            'PHONE': cls.PHONE_PATTERNS,
            'EMAIL': cls.EMAIL_PATTERNS,
            'DATE': cls.DATE_PATTERNS,
            'DOB': cls.DOB_PATTERNS,
            'AGE': cls.AGE_PATTERNS,
            'ADDRESS': cls.ADDRESS_PATTERNS,
            'ZIP': cls.ZIP_PATTERNS,
            'MRN': cls.MRN_PATTERNS,
            'ACCOUNT': cls.ACCOUNT_PATTERNS,
            'CREDIT_CARD': cls.CREDIT_CARD_PATTERNS,
            'IP': cls.IP_PATTERNS,
            'URL': cls.URL_PATTERNS,
            'INSURANCE': cls.INSURANCE_PATTERNS,
            'LICENSE': cls.LICENSE_PATTERNS,
            'NAME': cls.NAME_PATTERNS,
            'DOCTOR': cls.DOCTOR_PATTERNS,
            'HOSPITAL': cls.HOSPITAL_PATTERNS,
        }
    
    @classmethod
    def compile_patterns(cls):
        """Compile all patterns for efficiency"""
        compiled = {}
        for category, patterns in cls.get_all_patterns().items():
            compiled[category] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return compiled