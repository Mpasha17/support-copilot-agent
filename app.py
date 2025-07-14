"""
Support Copilot - Main Application
Flask-based REST API for Issue Lifecycle Management
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from datetime import datetime
import os
from functools import wraps
import jwt
import time

# Import custom modules
from services.issue_analysis_service import IssueAnalysisService
from services.guidance_service import GuidanceService
from services.summarization_service import SummarizationService
from database.db_manager import DatabaseManager
from utils.auth import AuthManager
from utils.cache_manager import CacheManager
from utils.logger import setup_logger

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Enable CORS
CORS(app)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

# Initialize services
db_manager = DatabaseManager()
auth_manager = AuthManager()
cache_manager = CacheManager()
issue_analysis_service = IssueAnalysisService(db_manager, cache_manager)
guidance_service = GuidanceService(db_manager, cache_manager)
summarization_service = SummarizationService(db_manager)

# Setup logging
logger = setup_logger()

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

# Performance monitoring decorator
def monitor_performance(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Log API usage
            db_manager.log_api_usage(
                endpoint=request.endpoint,
                method=request.method,
                response_time_ms=int(response_time),
                status_code=200,
                user_id=getattr(request, 'user_id', None)
            )
            
            # Add performance headers
            if isinstance(result, tuple):
                response, status_code = result
                if isinstance(response, dict):
                    response['response_time_ms'] = int(response_time)
                return response, status_code
            else:
                if isinstance(result, dict):
                    result['response_time_ms'] = int(response_time)
                return result
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            db_manager.log_api_usage(
                endpoint=request.endpoint,
                method=request.method,
                response_time_ms=int(response_time),
                status_code=500,
                user_id=getattr(request, 'user_id', None)
            )
            raise e
    return decorated

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

# Authentication endpoints
@app.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """User authentication endpoint"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = auth_manager.authenticate_user(email, password)
        if user:
            token = auth_manager.generate_token(user['user_id'])
            return jsonify({
                'token': token,
                'user': {
                    'id': user['user_id'],
                    'email': user['email'],
                    'name': user['name']
                }
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 500

# Issue Analysis Endpoints
@app.route('/api/issues/analyze', methods=['POST'])
@token_required
@monitor_performance
@limiter.limit("100 per minute")
def analyze_issue(current_user):
    """
    Analyze a new issue and provide insights
    Expected payload: {
        "customer_id": int,
        "title": str,
        "description": str,
        "category": str,
        "product_area": str
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['customer_id', 'title', 'description', 'category']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Analyze the issue
        analysis_result = issue_analysis_service.analyze_new_issue(
            customer_id=data['customer_id'],
            title=data['title'],
            description=data['description'],
            category=data['category'],
            product_area=data.get('product_area', '')
        )
        
        return jsonify(analysis_result)
        
    except Exception as e:
        logger.error(f"Issue analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze issue'}), 500

@app.route('/api/issues/<int:issue_id>/similar', methods=['GET'])
@token_required
@monitor_performance
def get_similar_issues(current_user, issue_id):
    """Get similar issues for a given issue ID"""
    try:
        limit = request.args.get('limit', 5, type=int)
        similar_issues = issue_analysis_service.find_similar_issues(issue_id, limit)
        
        return jsonify({
            'issue_id': issue_id,
            'similar_issues': similar_issues
        })
        
    except Exception as e:
        logger.error(f"Similar issues error: {str(e)}")
        return jsonify({'error': 'Failed to find similar issues'}), 500

@app.route('/api/customers/<int:customer_id>/history', methods=['GET'])
@token_required
@monitor_performance
def get_customer_history(current_user, customer_id):
    """Get customer issue history"""
    try:
        history = issue_analysis_service.get_customer_history(customer_id)
        return jsonify(history)
        
    except Exception as e:
        logger.error(f"Customer history error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve customer history'}), 500

# Guidance Service Endpoints
@app.route('/api/guidance/template', methods=['POST'])
@token_required
@monitor_performance
@limiter.limit("200 per minute")
def generate_response_template(current_user):
    """
    Generate recommended message template
    Expected payload: {
        "issue_id": int,
        "message_content": str,
        "context": str (optional)
    }
    """
    try:
        data = request.get_json()
        
        if 'issue_id' not in data or 'message_content' not in data:
            return jsonify({'error': 'Missing required fields: issue_id, message_content'}), 400
        
        template = guidance_service.generate_response_template(
            issue_id=data['issue_id'],
            message_content=data['message_content'],
            context=data.get('context', '')
        )
        
        return jsonify(template)
        
    except Exception as e:
        logger.error(f"Template generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate template'}), 500

@app.route('/api/guidance/templates', methods=['GET'])
@token_required
@monitor_performance
def get_templates(current_user):
    """Get available message templates"""
    try:
        category = request.args.get('category')
        severity = request.args.get('severity')
        
        templates = guidance_service.get_available_templates(category, severity)
        return jsonify({'templates': templates})
        
    except Exception as e:
        logger.error(f"Get templates error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve templates'}), 500

# Summarization Endpoints
@app.route('/api/issues/<int:issue_id>/summarize', methods=['POST'])
@token_required
@monitor_performance
def summarize_conversation(current_user, issue_id):
    """Generate conversation summary for an issue"""
    try:
        summary = summarization_service.generate_conversation_summary(issue_id)
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        return jsonify({'error': 'Failed to generate summary'}), 500

# Critical Alerts Endpoints
@app.route('/api/alerts/critical', methods=['GET'])
@token_required
@monitor_performance
def get_critical_alerts(current_user):
    """Get active critical alerts"""
    try:
        alerts = issue_analysis_service.get_critical_alerts()
        return jsonify({'alerts': alerts})
        
    except Exception as e:
        logger.error(f"Critical alerts error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve critical alerts'}), 500

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@token_required
@monitor_performance
def acknowledge_alert(current_user, alert_id):
    """Acknowledge a critical alert"""
    try:
        result = issue_analysis_service.acknowledge_alert(alert_id, current_user)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Alert acknowledgment error: {str(e)}")
        return jsonify({'error': 'Failed to acknowledge alert'}), 500

# Issue Management Endpoints
@app.route('/api/issues', methods=['GET'])
@token_required
@monitor_performance
def get_issues(current_user):
    """Get issues with filtering and pagination"""
    try:
        # Query parameters
        status = request.args.get('status')
        severity = request.args.get('severity')
        customer_id = request.args.get('customer_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        issues = db_manager.get_issues_with_filters(
            status=status,
            severity=severity,
            customer_id=customer_id,
            page=page,
            per_page=per_page
        )
        
        return jsonify(issues)
        
    except Exception as e:
        logger.error(f"Get issues error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve issues'}), 500

@app.route('/api/issues/<int:issue_id>', methods=['GET'])
@token_required
@monitor_performance
def get_issue_details(current_user, issue_id):
    """Get detailed information about a specific issue"""
    try:
        issue_details = db_manager.get_issue_details(issue_id)
        if not issue_details:
            return jsonify({'error': 'Issue not found'}), 404
            
        return jsonify(issue_details)
        
    except Exception as e:
        logger.error(f"Get issue details error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve issue details'}), 500

@app.route('/api/issues/<int:issue_id>/status', methods=['PUT'])
@token_required
@monitor_performance
def update_issue_status(current_user, issue_id):
    """Update issue status"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        result = db_manager.update_issue_status(issue_id, new_status, current_user)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Update issue status error: {str(e)}")
        return jsonify({'error': 'Failed to update issue status'}), 500

# Analytics Endpoints
@app.route('/api/analytics/dashboard', methods=['GET'])
@token_required
@monitor_performance
def get_dashboard_analytics(current_user):
    """Get dashboard analytics data"""
    try:
        analytics = db_manager.get_dashboard_analytics()
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"Dashboard analytics error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve analytics'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': str(e.retry_after)}), 429

if __name__ == '__main__':
    # Initialize database
    db_manager.initialize_database()
    
    # Start the application
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Support Copilot API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)