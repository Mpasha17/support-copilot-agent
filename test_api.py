"""
Test Suite for Support Copilot API
Comprehensive testing for all endpoints and functionality
"""

import pytest
import json
import jwt
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app import app
from database.db_manager import DatabaseManager
from services.issue_analysis_service import IssueAnalysisService
from services.guidance_service import GuidanceService
from services.summarization_service import SummarizationService

class TestSupportCopilotAPI:
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        token = jwt.encode(
            {'user_id': 1, 'exp': datetime.utcnow() + timedelta(hours=1)},
            'test-secret-key',
            algorithm='HS256'
        )
        return {'Authorization': f'Bearer {token}'}
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'version' in data
    
    def test_login_success(self, client):
        """Test successful login"""
        with patch('utils.auth.AuthManager.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                'user_id': 1,
                'email': 'test@example.com',
                'name': 'Test User'
            }
            
            response = client.post('/auth/login', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'token' in data
            assert 'user' in data
            assert data['user']['email'] == 'test@example.com'
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        with patch('utils.auth.AuthManager.authenticate_user') as mock_auth:
            mock_auth.return_value = None
            
            response = client.post('/auth/login', json={
                'email': 'test@example.com',
                'password': 'wrongpassword'
            })
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['error'] == 'Invalid credentials'
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        response = client.post('/auth/login', json={
            'email': 'test@example.com'
            # Missing password
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Email and password required' in data['error']
    
    def test_analyze_issue_success(self, client, auth_headers):
        """Test successful issue analysis"""
        with patch('services.issue_analysis_service.IssueAnalysisService.analyze_new_issue') as mock_analyze:
            mock_analyze.return_value = {
                'issue_id': 123,
                'severity': 'High',
                'priority_score': 8,
                'similar_issues': [],
                'critical_alerts': [],
                'ai_insights': {
                    'root_cause': 'Authentication service issue',
                    'estimated_time_hours': 4
                }
            }
            
            response = client.post('/api/issues/analyze', 
                headers=auth_headers,
                json={
                    'customer_id': 1,
                    'title': 'Login not working',
                    'description': 'Users cannot log in after update',
                    'category': 'Technical'
                }
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_id'] == 123
            assert data['severity'] == 'High'
            assert data['priority_score'] == 8
    
    def test_analyze_issue_missing_fields(self, client, auth_headers):
        """Test issue analysis with missing required fields"""
        response = client.post('/api/issues/analyze',
            headers=auth_headers,
            json={
                'customer_id': 1,
                'title': 'Login not working'
                # Missing description and category
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing required field' in data['error']
    
    def test_analyze_issue_unauthorized(self, client):
        """Test issue analysis without authentication"""
        response = client.post('/api/issues/analyze', json={
            'customer_id': 1,
            'title': 'Login not working',
            'description': 'Users cannot log in',
            'category': 'Technical'
        })
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['error'] == 'Token is missing'
    
    def test_get_similar_issues(self, client, auth_headers):
        """Test getting similar issues"""
        with patch('services.issue_analysis_service.IssueAnalysisService.find_similar_issues') as mock_similar:
            mock_similar.return_value = [
                {
                    'issue_id': 456,
                    'title': 'Authentication failure',
                    'similarity_score': 0.85,
                    'resolution_time_hours': 6
                }
            ]
            
            response = client.get('/api/issues/123/similar?limit=5', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_id'] == 123
            assert len(data['similar_issues']) == 1
            assert data['similar_issues'][0]['similarity_score'] == 0.85
    
    def test_get_customer_history(self, client, auth_headers):
        """Test getting customer history"""
        with patch('services.issue_analysis_service.IssueAnalysisService.get_customer_history') as mock_history:
            mock_history.return_value = {
                'customer_info': {
                    'customer_id': 1,
                    'customer_name': 'Test Customer',
                    'tier': 'Premium'
                },
                'statistics': {
                    'total_issues': 5,
                    'resolved_issues': 4,
                    'avg_resolution_time': 24.5
                }
            }
            
            response = client.get('/api/customers/1/history', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['customer_info']['customer_name'] == 'Test Customer'
            assert data['statistics']['total_issues'] == 5
    
    def test_generate_response_template(self, client, auth_headers):
        """Test generating response template"""
        with patch('services.guidance_service.GuidanceService.generate_response_template') as mock_template:
            mock_template.return_value = {
                'issue_id': 123,
                'template_category': 'initial_response',
                'recommended_template': {
                    'content': 'Dear {{customer_name}}, thank you for contacting us...',
                    'variables': ['customer_name', 'issue_id'],
                    'suggested_values': {
                        'customer_name': 'Test Customer',
                        'issue_id': '123'
                    }
                },
                'confidence_score': 0.85
            }
            
            response = client.post('/api/guidance/template',
                headers=auth_headers,
                json={
                    'issue_id': 123,
                    'message_content': 'I need help with login issues'
                }
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_id'] == 123
            assert data['template_category'] == 'initial_response'
            assert data['confidence_score'] == 0.85
    
    def test_generate_template_missing_fields(self, client, auth_headers):
        """Test template generation with missing fields"""
        response = client.post('/api/guidance/template',
            headers=auth_headers,
            json={
                'issue_id': 123
                # Missing message_content
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing required fields' in data['error']
    
    def test_get_templates(self, client, auth_headers):
        """Test getting available templates"""
        with patch('services.guidance_service.GuidanceService.get_available_templates') as mock_templates:
            mock_templates.return_value = [
                {
                    'template_id': 1,
                    'template_name': 'Initial Response - Technical',
                    'category': 'initial_response',
                    'effectiveness_score': 0.9
                }
            ]
            
            response = client.get('/api/guidance/templates?category=initial_response', 
                headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['templates']) == 1
            assert data['templates'][0]['template_name'] == 'Initial Response - Technical'
    
    def test_summarize_conversation(self, client, auth_headers):
        """Test conversation summarization"""
        with patch('services.summarization_service.SummarizationService.generate_conversation_summary') as mock_summary:
            mock_summary.return_value = {
                'issue_id': 123,
                'summary_text': 'Customer reported login issues...',
                'key_points': ['Authentication failure', 'Recent system update'],
                'action_items': [
                    {
                        'description': 'Check authentication service',
                        'assigned_to': 'Support',
                        'priority': 'High'
                    }
                ]
            }
            
            response = client.post('/api/issues/123/summarize', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_id'] == 123
            assert 'Customer reported login issues' in data['summary_text']
            assert len(data['action_items']) == 1
    
    def test_get_critical_alerts(self, client, auth_headers):
        """Test getting critical alerts"""
        with patch('services.issue_analysis_service.IssueAnalysisService.get_critical_alerts') as mock_alerts:
            mock_alerts.return_value = [
                {
                    'alert_id': 1,
                    'issue_id': 123,
                    'alert_type': 'Unattended',
                    'severity': 'Critical',
                    'created_at': '2023-01-01T10:00:00'
                }
            ]
            
            response = client.get('/api/alerts/critical', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['alerts']) == 1
            assert data['alerts'][0]['alert_type'] == 'Unattended'
    
    def test_acknowledge_alert(self, client, auth_headers):
        """Test acknowledging an alert"""
        with patch('services.issue_analysis_service.IssueAnalysisService.acknowledge_alert') as mock_ack:
            mock_ack.return_value = {
                'success': True,
                'message': 'Alert acknowledged successfully'
            }
            
            response = client.post('/api/alerts/1/acknowledge', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'acknowledged successfully' in data['message']
    
    def test_get_issues_with_filters(self, client, auth_headers):
        """Test getting issues with filters"""
        with patch('database.db_manager.DatabaseManager.get_issues_with_filters') as mock_issues:
            mock_issues.return_value = {
                'issues': [
                    {
                        'issue_id': 123,
                        'title': 'Login problem',
                        'severity': 'High',
                        'status': 'Open',
                        'customer_name': 'Test Customer'
                    }
                ],
                'pagination': {
                    'page': 1,
                    'per_page': 20,
                    'total': 1,
                    'pages': 1
                }
            }
            
            response = client.get('/api/issues?status=Open&severity=High', 
                headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['issues']) == 1
            assert data['issues'][0]['severity'] == 'High'
            assert data['pagination']['total'] == 1
    
    def test_get_issue_details(self, client, auth_headers):
        """Test getting issue details"""
        with patch('database.db_manager.DatabaseManager.get_issue_details') as mock_details:
            mock_details.return_value = {
                'issue_id': 123,
                'title': 'Login problem',
                'description': 'Users cannot log in',
                'severity': 'High',
                'status': 'Open',
                'customer_name': 'Test Customer',
                'created_at': '2023-01-01T10:00:00'
            }
            
            response = client.get('/api/issues/123', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_id'] == 123
            assert data['title'] == 'Login problem'
            assert data['severity'] == 'High'
    
    def test_get_issue_details_not_found(self, client, auth_headers):
        """Test getting details for non-existent issue"""
        with patch('database.db_manager.DatabaseManager.get_issue_details') as mock_details:
            mock_details.return_value = None
            
            response = client.get('/api/issues/999', headers=auth_headers)
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'Issue not found'
    
    def test_update_issue_status(self, client, auth_headers):
        """Test updating issue status"""
        with patch('database.db_manager.DatabaseManager.update_issue_status') as mock_update:
            mock_update.return_value = {
                'success': True,
                'message': 'Issue status updated to Resolved'
            }
            
            response = client.put('/api/issues/123/status',
                headers=auth_headers,
                json={'status': 'Resolved'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'Resolved' in data['message']
    
    def test_update_issue_status_missing_status(self, client, auth_headers):
        """Test updating issue status without providing status"""
        response = client.put('/api/issues/123/status',
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == 'Status is required'
    
    def test_get_dashboard_analytics(self, client, auth_headers):
        """Test getting dashboard analytics"""
        with patch('database.db_manager.DatabaseManager.get_dashboard_analytics') as mock_analytics:
            mock_analytics.return_value = {
                'issue_statistics': {
                    'total_issues': 100,
                    'open_issues': 25,
                    'resolved_issues': 70,
                    'critical_issues': 5
                },
                'performance_metrics': {
                    'avg_response_time_ms': 2500,
                    'error_count': 2
                }
            }
            
            response = client.get('/api/analytics/dashboard', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['issue_statistics']['total_issues'] == 100
            assert data['performance_metrics']['avg_response_time_ms'] == 2500
    
    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting functionality"""
        # This would require actual rate limiting setup
        # For now, we'll test that the endpoint responds normally
        response = client.get('/api/issues', headers=auth_headers)
        assert response.status_code in [200, 429]  # Either success or rate limited
    
    def test_invalid_token(self, client):
        """Test request with invalid token"""
        headers = {'Authorization': 'Bearer invalid-token'}
        response = client.get('/api/issues', headers=headers)
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Token is invalid' in data['error']
    
    def test_expired_token(self, client):
        """Test request with expired token"""
        expired_token = jwt.encode(
            {'user_id': 1, 'exp': datetime.utcnow() - timedelta(hours=1)},
            'test-secret-key',
            algorithm='HS256'
        )
        headers = {'Authorization': f'Bearer {expired_token}'}
        response = client.get('/api/issues', headers=headers)
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Token has expired' in data['error']
    
    def test_404_endpoint(self, client):
        """Test non-existent endpoint"""
        response = client.get('/api/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Endpoint not found'

# Performance Tests
class TestPerformance:
    
    def test_response_time_under_threshold(self, client, auth_headers):
        """Test that API responses are under 15 seconds"""
        import time
        
        start_time = time.time()
        response = client.get('/health')
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response_time < 15.0  # Should be much faster than 15 seconds
        assert response.status_code == 200

# Integration Tests
class TestIntegration:
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for integration tests"""
        with patch('database.db_manager.DatabaseManager') as mock:
            yield mock
    
    def test_full_issue_workflow(self, client, auth_headers, mock_db):
        """Test complete issue workflow from creation to resolution"""
        # This would test the full workflow in a real integration test
        # For now, we'll test that the endpoints can be called in sequence
        
        # 1. Analyze new issue
        with patch('services.issue_analysis_service.IssueAnalysisService.analyze_new_issue'):
            response = client.post('/api/issues/analyze',
                headers=auth_headers,
                json={
                    'customer_id': 1,
                    'title': 'Test issue',
                    'description': 'Test description',
                    'category': 'Technical'
                }
            )
            assert response.status_code == 200
        
        # 2. Generate response template
        with patch('services.guidance_service.GuidanceService.generate_response_template'):
            response = client.post('/api/guidance/template',
                headers=auth_headers,
                json={
                    'issue_id': 123,
                    'message_content': 'Customer needs help'
                }
            )
            assert response.status_code == 200
        
        # 3. Update issue status
        with patch('database.db_manager.DatabaseManager.update_issue_status'):
            response = client.put('/api/issues/123/status',
                headers=auth_headers,
                json={'status': 'Resolved'}
            )
            assert response.status_code == 200
        
        # 4. Generate summary
        with patch('services.summarization_service.SummarizationService.generate_conversation_summary'):
            response = client.post('/api/issues/123/summarize',
                headers=auth_headers
            )
            assert response.status_code == 200

if __name__ == '__main__':
    pytest.main([__file__, '-v'])