"""
Logger Configuration
Centralized logging setup for the Support Copilot application
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime

def setup_logger(name: str = None, level: str = None) -> logging.Logger:
    """
    Setup centralized logger with file and console handlers
    """
    
    # Get logger name
    logger_name = name or 'support_copilot'
    logger = logging.getLogger(logger_name)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Set log level
    log_level = level or os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler for detailed logs
    log_dir = os.getenv('LOG_DIR', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'support_copilot.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_log_file = os.path.join(log_dir, 'support_copilot_errors.log')
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Performance log handler
    perf_log_file = os.path.join(log_dir, 'support_copilot_performance.log')
    perf_handler = logging.handlers.RotatingFileHandler(
        perf_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    perf_handler.setLevel(logging.INFO)
    perf_formatter = logging.Formatter(
        '%(asctime)s - PERFORMANCE - %(message)s'
    )
    perf_handler.setFormatter(perf_formatter)
    
    # Create performance logger
    perf_logger = logging.getLogger(f'{logger_name}.performance')
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    
    return logger

def get_performance_logger() -> logging.Logger:
    """Get performance logger"""
    return logging.getLogger('support_copilot.performance')

def log_api_call(endpoint: str, method: str, response_time: float, status_code: int, user_id: int = None):
    """Log API call performance"""
    perf_logger = get_performance_logger()
    perf_logger.info(
        f"API_CALL - Endpoint: {endpoint} - Method: {method} - "
        f"ResponseTime: {response_time:.3f}s - Status: {status_code} - User: {user_id}"
    )

def log_database_query(query_type: str, execution_time: float, affected_rows: int = None):
    """Log database query performance"""
    perf_logger = get_performance_logger()
    perf_logger.info(
        f"DB_QUERY - Type: {query_type} - ExecutionTime: {execution_time:.3f}s - "
        f"AffectedRows: {affected_rows or 'N/A'}"
    )

def log_ai_operation(operation: str, model: str, tokens_used: int, response_time: float):
    """Log AI operation performance"""
    perf_logger = get_performance_logger()
    perf_logger.info(
        f"AI_OPERATION - Operation: {operation} - Model: {model} - "
        f"Tokens: {tokens_used} - ResponseTime: {response_time:.3f}s"
    )

class ContextFilter(logging.Filter):
    """Add context information to log records"""
    
    def __init__(self, context: dict = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record):
        for key, value in self.context.items():
            setattr(record, key, value)
        return True

def add_context_to_logger(logger: logging.Logger, context: dict):
    """Add context filter to logger"""
    context_filter = ContextFilter(context)
    logger.addFilter(context_filter)

# Custom log levels
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")

def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)

logging.Logger.trace = trace