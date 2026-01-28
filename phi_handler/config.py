"""
Configuration settings for PHI de-identification
"""


class PHIConfig:
    """Configuration class for PHI handling"""
    
    # Token prefixes for different PHI types
    TOKEN_PREFIXES = {
        'NAME': '[NAME_',
        'SSN': '[SSN_',
        'PHONE': '[PHONE_',
        'EMAIL': '[EMAIL_',
        'DATE': '[DATE_',
        'DOB': '[DOB_',
        'ADDRESS': '[ADDR_',
        'CITY': '[CITY_',
        'STATE': '[STATE_',
        'ZIP': '[ZIP_',
        'MRN': '[MRN_',
        'ACCOUNT': '[ACCT_',
        'IP': '[IP_',
        'URL': '[URL_',
        'AGE': '[AGE_',
        'DOCTOR': '[DR_',
        'HOSPITAL': '[HOSP_',
        'MEDICATION': '[MED_',
        'DIAGNOSIS': '[DX_',
        'INSURANCE': '[INS_',
        'POLICY': '[POL_',
        'CREDIT_CARD': '[CC_',
        'DEVICE_ID': '[DEV_',
        'LICENSE': '[LIC_',
        'PASSPORT': '[PASS_',
        'GENERIC': '[PHI_',
    }
    
    # Token suffix
    TOKEN_SUFFIX = ']'
    
    # Whether to preserve context hints
    PRESERVE_CONTEXT = True
    
    # Maximum tokens per session
    MAX_TOKENS_PER_SESSION = 1000
    
    # Enable logging
    ENABLE_LOGGING = True
    
    # Sensitive categories to always de-identify
    ALWAYS_DEIDENTIFY = [
        'SSN', 'CREDIT_CARD', 'ACCOUNT', 'MRN',
        'PASSPORT', 'LICENSE', 'INSURANCE', 'POLICY'
    ]