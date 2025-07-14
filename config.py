"""
Configuration Management
Centralized configuration for different environments
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Application Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    DEBUG = False
    TESTING = False
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_NAME = os.getenv('DB_NAME', 'support_copilot')
    
    # Database URL
    DATABASE_URL = f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('JWT_EXPIRY_HOURS', 24)))
    
    # Mistral AI Configuration
    MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
    MISTRAL_MODEL = os.getenv('MISTRAL_MODEL', 'mistral-small-latest')
    MISTRAL_MAX_TOKENS = int(os.getenv('MISTRAL_MAX_TOKENS', 1000))
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    
    # S3 Configuration
    S3_BUCKET = os.getenv('S3_BUCKET', 'support-copilot-files')
    
    # Performance Settings
    MAX_RESPONSE_TIME_SECONDS = int(os.getenv('MAX_RESPONSE_TIME_SECONDS', 15))
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 100))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = os.getenv('LOG_DIR', 'logs')
    
    # Cache Settings
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 3600))
    CACHE_CUSTOMER_TIMEOUT = int(os.getenv('CACHE_CUSTOMER_TIMEOUT', 300))
    CACHE_ISSUE_TIMEOUT = int(os.getenv('CACHE_ISSUE_TIMEOUT', 1800))
    
    # Email Configuration (for notifications)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    
    # Monitoring Configuration
    ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'True').lower() == 'true'
    METRICS_PORT = int(os.getenv('METRICS_PORT', 8080))
    
    # Security Settings
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')
    
    # Feature Flags
    ENABLE_AI_ANALYSIS = os.getenv('ENABLE_AI_ANALYSIS', 'True').lower() == 'true'
    ENABLE_SIMILARITY_SEARCH = os.getenv('ENABLE_SIMILARITY_SEARCH', 'True').lower() == 'true'
    ENABLE_AUTO_SUMMARIZATION = os.getenv('ENABLE_AUTO_SUMMARIZATION', 'True').lower() == 'true'

class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    
    # Use local database for development
    DB_HOST = 'localhost'
    DB_NAME = 'support_copilot_dev'
    
    # Relaxed rate limiting for development
    RATE_LIMIT_PER_MINUTE = 1000

class TestingConfig(Config):
    """Testing environment configuration"""
    TESTING = True
    DEBUG = True
    
    # Use test database
    DB_NAME = 'support_copilot_test'
    
    # Use in-memory cache for testing
    REDIS_HOST = None
    
    # Disable external API calls in tests
    ENABLE_AI_ANALYSIS = False

class StagingConfig(Config):
    """Staging environment configuration"""
    DEBUG = False
    
    # Use staging database
    DB_NAME = 'support_copilot_staging'
    
    # Moderate rate limiting
    RATE_LIMIT_PER_MINUTE = 500

class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    
    # Production database settings
    DB_HOST = os.getenv('PROD_DB_HOST', 'prod-db-host')
    DB_NAME = 'support_copilot_prod'
    
    # Production Redis settings
    REDIS_HOST = os.getenv('PROD_REDIS_HOST', 'prod-redis-host')
    
    # Strict rate limiting
    RATE_LIMIT_PER_MINUTE = 100
    
    # Enhanced security
    CORS_ORIGINS = os.getenv('PROD_CORS_ORIGINS', 'https://yourdomain.com').split(',')
    ALLOWED_HOSTS = os.getenv('PROD_ALLOWED_HOSTS', 'yourdomain.com').split(',')

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(env_name: str = None) -> Config:
    """Get configuration based on environment"""
    env_name = env_name or os.getenv('FLASK_ENV', 'default')
    return config_map.get(env_name, DevelopmentConfig)

# Application-specific constants
class Constants:
    """Application constants"""
    
    # Issue Severity Levels
    SEVERITY_LEVELS = ['Low', 'Normal', 'High', 'Critical']
    
    # Issue Status Options
    STATUS_OPTIONS = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated']
    
    # Issue Categories
    CATEGORIES = ['Technical', 'Billing', 'General', 'Feature Request', 'Bug Report']
    
    # Customer Tiers
    CUSTOMER_TIERS = ['Basic', 'Premium', 'Enterprise']
    
    # Alert Types
    ALERT_TYPES = ['Unattended', 'Escalation', 'SLA_Breach', 'Customer_Escalation']
    
    # Template Categories
    TEMPLATE_CATEGORIES = [
        'initial_response', 'status_update', 'escalation', 
        'resolution', 'clarification'
    ]
    
    # Response Time SLAs (in hours)
    SLA_RESPONSE_TIMES = {
        'Critical': 1,
        'High': 4,
        'Normal': 24,
        'Low': 48
    }
    
    # Resolution Time SLAs (in hours)
    SLA_RESOLUTION_TIMES = {
        'Critical': 4,
        'High': 24,
        'Normal': 72,
        'Low': 168
    }
    
    # Customer Tier Priorities
    TIER_PRIORITIES = {
        'Enterprise': 1,
        'Premium': 2,
        'Basic': 3
    }
    
    # AI Model Settings
    AI_MODELS = {
        'classification': 'mistral-small-latest',
        'summarization': 'mistral-medium-latest',
        'template_generation': 'mistral-medium-latest',
        'similarity': 'mistral-embed'
    }
    
    # Cache Keys
    CACHE_KEYS = {
        'customer_history': 'customer:{customer_id}',
        'issue_analysis': 'issue_analysis:{issue_id}',
        'similar_issues': 'similar_issues:{issue_id}',
        'templates': 'templates:{category}:{severity}',
        'dashboard_stats': 'dashboard:stats',
        'performance_metrics': 'performance:metrics'
    }
    
    # File Upload Settings
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
    
    # Pagination Settings
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Search Settings
    MIN_SIMILARITY_SCORE = 0.1
    MAX_SIMILAR_ISSUES = 10
    
    # Performance Thresholds
    SLOW_QUERY_THRESHOLD = 1.0  # seconds
    SLOW_API_THRESHOLD = 5.0    # seconds
    
    # Monitoring Intervals
    HEALTH_CHECK_INTERVAL = 60  # seconds
    METRICS_COLLECTION_INTERVAL = 300  # seconds