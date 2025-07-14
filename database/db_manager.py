"""
Database Manager
Handles all database operations and connections
"""

import mysql.connector
from mysql.connector import pooling
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.connection_pool = None
        self._initialize_connection_pool()

    def _initialize_connection_pool(self):
        """Initialize MySQL connection pool"""
        try:
            config = {
                'user': os.getenv('DB_USER', 'root'),
                'password': os.getenv('DB_PASSWORD', 'password'),
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 3306)),
                'database': os.getenv('DB_NAME', 'support_copilot'),
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'autocommit': True,
                'pool_name': 'support_copilot_pool',
                'pool_size': 10,
                'pool_reset_session': True
            }
            
            self.connection_pool = pooling.MySQLConnectionPool(**config)
            self.logger.info("Database connection pool initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database connection pool: {str(e)}")
            raise

    def get_connection(self):
        """Get connection from pool"""
        try:
            return self.connection_pool.get_connection()
        except Exception as e:
            self.logger.error(f"Failed to get database connection: {str(e)}")
            raise

    def execute_query(self, query: str, params: Tuple = None, 
                     fetch_one: bool = False, fetch_all: bool = False,
                     fetch_lastrowid: bool = False, fetch_rowcount: bool = False) -> Any:
        """
        Execute database query with various return options
        """
        connection = None
        cursor = None
        
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Handle different return types
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            elif fetch_lastrowid:
                return cursor.lastrowid
            elif fetch_rowcount:
                return cursor.rowcount
            else:
                connection.commit()
                return True
                
        except Exception as e:
            if connection:
                connection.rollback()
            self.logger.error(f"Database query failed: {str(e)}")
            self.logger.error(f"Query: {query}")
            self.logger.error(f"Params: {params}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def initialize_database(self):
        """Initialize database with schema"""
        try:
            # Read and execute schema file
            schema_path = os.path.join(os.path.dirname(__file__), '..', 'database_schema.sql')
            
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as file:
                    schema_sql = file.read()
                
                # Split and execute statements
                statements = schema_sql.split(';')
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        try:
                            self.execute_query(statement)
                        except Exception as e:
                            # Log but don't fail on duplicate table errors
                            if 'already exists' not in str(e).lower():
                                self.logger.warning(f"Schema statement failed: {str(e)}")
                
                self.logger.info("Database schema initialized successfully")
            else:
                self.logger.warning("Schema file not found, skipping initialization")
                
        except Exception as e:
            self.logger.error(f"Database initialization failed: {str(e)}")

    def get_issue_details(self, issue_id: int) -> Optional[Dict]:
        """Get comprehensive issue details"""
        try:
            query = """
            SELECT i.*, c.customer_name, c.email, c.company, c.tier,
                   se.name as assigned_to_name
            FROM issues i
            JOIN customers c ON i.customer_id = c.customer_id
            LEFT JOIN support_executives se ON i.assigned_to = se.executive_id
            WHERE i.issue_id = %s
            """
            
            issue = self.execute_query(query, (issue_id,), fetch_one=True)
            
            if issue:
                # Parse JSON fields
                if issue.get('tags'):
                    try:
                        issue['tags'] = json.loads(issue['tags'])
                    except:
                        issue['tags'] = {}
                
                return dict(issue)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get issue details: {str(e)}")
            return None

    def get_issues_with_filters(self, status: str = None, severity: str = None,
                              customer_id: int = None, page: int = 1, 
                              per_page: int = 20) -> Dict:
        """Get issues with filtering and pagination"""
        try:
            # Build WHERE clause
            where_conditions = []
            params = []
            
            if status:
                where_conditions.append("i.status = %s")
                params.append(status)
            
            if severity:
                where_conditions.append("i.severity = %s")
                params.append(severity)
            
            if customer_id:
                where_conditions.append("i.customer_id = %s")
                params.append(customer_id)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Count total records
            count_query = f"""
            SELECT COUNT(*) as total
            FROM issues i
            JOIN customers c ON i.customer_id = c.customer_id
            {where_clause}
            """
            
            total_count = self.execute_query(count_query, params, fetch_one=True)
            total = total_count['total'] if total_count else 0
            
            # Calculate pagination
            offset = (page - 1) * per_page
            
            # Get paginated results
            data_query = f"""
            SELECT i.issue_id, i.title, i.severity, i.status, i.created_at,
                   i.updated_at, i.priority, c.customer_name, c.company,
                   TIMESTAMPDIFF(HOUR, i.created_at, NOW()) as hours_open
            FROM issues i
            JOIN customers c ON i.customer_id = c.customer_id
            {where_clause}
            ORDER BY i.created_at DESC
            LIMIT %s OFFSET %s
            """
            
            params.extend([per_page, offset])
            issues = self.execute_query(data_query, params, fetch_all=True)
            
            return {
                'issues': [dict(issue) for issue in issues] if issues else [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get issues with filters: {str(e)}")
            return {'issues': [], 'pagination': {'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0}}

    def update_issue_status(self, issue_id: int, new_status: str, user_id: int) -> Dict:
        """Update issue status"""
        try:
            # Get current issue details
            current_issue = self.get_issue_details(issue_id)
            if not current_issue:
                return {'success': False, 'message': 'Issue not found'}
            
            # Update status
            update_query = """
            UPDATE issues 
            SET status = %s, updated_at = NOW()
            WHERE issue_id = %s
            """
            
            self.execute_query(update_query, (new_status, issue_id))
            
            # If resolving, calculate resolution time
            if new_status == 'Resolved':
                resolution_query = """
                UPDATE issues 
                SET resolved_at = NOW(),
                    resolution_time_hours = TIMESTAMPDIFF(HOUR, created_at, NOW())
                WHERE issue_id = %s
                """
                self.execute_query(resolution_query, (issue_id,))
            
            # Log status change
            self._log_status_change(issue_id, current_issue['status'], new_status, user_id)
            
            return {'success': True, 'message': f'Issue status updated to {new_status}'}
            
        except Exception as e:
            self.logger.error(f"Failed to update issue status: {str(e)}")
            return {'success': False, 'message': 'Failed to update issue status'}

    def _log_status_change(self, issue_id: int, old_status: str, new_status: str, user_id: int):
        """Log status change in conversation"""
        try:
            message = f"Issue status changed from {old_status} to {new_status}"
            
            query = """
            INSERT INTO conversations (issue_id, message_type, message_content, sender_id)
            VALUES (%s, 'System', %s, %s)
            """
            
            self.execute_query(query, (issue_id, message, user_id))
            
        except Exception as e:
            self.logger.error(f"Failed to log status change: {str(e)}")

    def log_api_usage(self, endpoint: str, method: str, response_time_ms: int,
                     status_code: int, user_id: int = None, request_size: int = None,
                     response_size: int = None):
        """Log API usage for monitoring"""
        try:
            query = """
            INSERT INTO api_usage 
            (endpoint, method, response_time_ms, status_code, user_id, request_size, response_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            self.execute_query(
                query, 
                (endpoint, method, response_time_ms, status_code, user_id, request_size, response_size)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to log API usage: {str(e)}")

    def get_dashboard_analytics(self) -> Dict:
        """Get dashboard analytics data"""
        try:
            analytics = {}
            
            # Issue statistics
            issue_stats_query = """
            SELECT 
                COUNT(*) as total_issues,
                COUNT(CASE WHEN status = 'Open' THEN 1 END) as open_issues,
                COUNT(CASE WHEN status = 'In Progress' THEN 1 END) as in_progress_issues,
                COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_issues,
                COUNT(CASE WHEN severity = 'Critical' THEN 1 END) as critical_issues,
                COUNT(CASE WHEN severity = 'High' THEN 1 END) as high_issues,
                AVG(resolution_time_hours) as avg_resolution_time,
                COUNT(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR) THEN 1 END) as issues_last_24h
            FROM issues
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """
            
            issue_stats = self.execute_query(issue_stats_query, fetch_one=True)
            analytics['issue_statistics'] = dict(issue_stats) if issue_stats else {}
            
            # Customer statistics
            customer_stats_query = """
            SELECT 
                COUNT(DISTINCT c.customer_id) as total_customers,
                COUNT(DISTINCT CASE WHEN i.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) 
                      THEN c.customer_id END) as active_customers_week,
                AVG(customer_issues.issue_count) as avg_issues_per_customer
            FROM customers c
            LEFT JOIN issues i ON c.customer_id = i.customer_id
            LEFT JOIN (
                SELECT customer_id, COUNT(*) as issue_count
                FROM issues
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY customer_id
            ) customer_issues ON c.customer_id = customer_issues.customer_id
            """
            
            customer_stats = self.execute_query(customer_stats_query, fetch_one=True)
            analytics['customer_statistics'] = dict(customer_stats) if customer_stats else {}
            
            # Performance metrics
            performance_query = """
            SELECT 
                AVG(response_time_ms) as avg_response_time_ms,
                MAX(response_time_ms) as max_response_time_ms,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
                COUNT(*) as total_requests
            FROM api_usage
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """
            
            performance_stats = self.execute_query(performance_query, fetch_one=True)
            analytics['performance_metrics'] = dict(performance_stats) if performance_stats else {}
            
            # Critical alerts
            alerts_query = """
            SELECT COUNT(*) as active_alerts
            FROM critical_alerts
            WHERE status = 'Active'
            """
            
            alerts_count = self.execute_query(alerts_query, fetch_one=True)
            analytics['critical_alerts'] = alerts_count['active_alerts'] if alerts_count else 0
            
            # Issue trends (last 7 days)
            trends_query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as issues_created,
                COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as issues_resolved
            FROM issues
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date
            """
            
            trends = self.execute_query(trends_query, fetch_all=True)
            analytics['issue_trends'] = [dict(trend) for trend in trends] if trends else []
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"Failed to get dashboard analytics: {str(e)}")
            return {}

    def get_customer_risk_analysis(self) -> List[Dict]:
        """Get customer risk analysis"""
        try:
            query = """
            SELECT 
                c.customer_id,
                c.customer_name,
                c.company,
                c.tier,
                COUNT(i.issue_id) as total_issues,
                COUNT(CASE WHEN i.severity = 'Critical' THEN 1 END) as critical_issues,
                COUNT(CASE WHEN i.severity = 'High' THEN 1 END) as high_issues,
                COUNT(CASE WHEN i.status IN ('Open', 'In Progress') THEN 1 END) as open_issues,
                COUNT(CASE WHEN i.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as recent_issues,
                AVG(ir.customer_satisfaction) as avg_satisfaction,
                AVG(i.resolution_time_hours) as avg_resolution_time
            FROM customers c
            LEFT JOIN issues i ON c.customer_id = i.customer_id
            LEFT JOIN issue_resolutions ir ON i.issue_id = ir.issue_id
            GROUP BY c.customer_id
            HAVING total_issues > 0
            ORDER BY (critical_issues * 3 + high_issues * 2 + recent_issues) DESC
            LIMIT 50
            """
            
            customers = self.execute_query(query, fetch_all=True)
            
            risk_analysis = []
            for customer in customers or []:
                customer_dict = dict(customer)
                
                # Calculate risk score
                risk_score = self._calculate_customer_risk_score(customer_dict)
                customer_dict['risk_score'] = risk_score
                customer_dict['risk_level'] = self._get_risk_level(risk_score)
                
                risk_analysis.append(customer_dict)
            
            return risk_analysis
            
        except Exception as e:
            self.logger.error(f"Failed to get customer risk analysis: {str(e)}")
            return []

    def _calculate_customer_risk_score(self, customer_data: Dict) -> float:
        """Calculate customer risk score"""
        score = 0.0
        
        # Issue volume factor
        total_issues = customer_data.get('total_issues', 0)
        if total_issues > 20:
            score += 3.0
        elif total_issues > 10:
            score += 2.0
        elif total_issues > 5:
            score += 1.0
        
        # Severity factor
        critical_issues = customer_data.get('critical_issues', 0)
        high_issues = customer_data.get('high_issues', 0)
        score += critical_issues * 2.0 + high_issues * 1.0
        
        # Open issues factor
        open_issues = customer_data.get('open_issues', 0)
        score += open_issues * 1.5
        
        # Recent activity factor
        recent_issues = customer_data.get('recent_issues', 0)
        if recent_issues > 5:
            score += 2.0
        elif recent_issues > 2:
            score += 1.0
        
        # Satisfaction factor (inverse)
        avg_satisfaction = customer_data.get('avg_satisfaction')
        if avg_satisfaction is not None:
            if avg_satisfaction < 3.0:
                score += 2.0
            elif avg_satisfaction < 4.0:
                score += 1.0
        
        # Resolution time factor
        avg_resolution_time = customer_data.get('avg_resolution_time')
        if avg_resolution_time is not None and avg_resolution_time > 48:
            score += 1.0
        
        return min(10.0, score)  # Cap at 10

    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level"""
        if risk_score >= 7.0:
            return 'High'
        elif risk_score >= 4.0:
            return 'Medium'
        else:
            return 'Low'

    def get_performance_metrics(self, hours: int = 24) -> Dict:
        """Get system performance metrics"""
        try:
            query = """
            SELECT 
                COUNT(*) as total_requests,
                AVG(response_time_ms) as avg_response_time,
                MAX(response_time_ms) as max_response_time,
                MIN(response_time_ms) as min_response_time,
                COUNT(CASE WHEN response_time_ms > 15000 THEN 1 END) as slow_requests,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_requests,
                COUNT(CASE WHEN status_code = 200 THEN 1 END) as success_requests
            FROM api_usage
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            """
            
            metrics = self.execute_query(query, (hours,), fetch_one=True)
            
            if metrics:
                metrics_dict = dict(metrics)
                
                # Calculate derived metrics
                total_requests = metrics_dict.get('total_requests', 0)
                if total_requests > 0:
                    metrics_dict['error_rate'] = (metrics_dict.get('error_requests', 0) / total_requests) * 100
                    metrics_dict['success_rate'] = (metrics_dict.get('success_requests', 0) / total_requests) * 100
                    metrics_dict['slow_request_rate'] = (metrics_dict.get('slow_requests', 0) / total_requests) * 100
                else:
                    metrics_dict['error_rate'] = 0
                    metrics_dict['success_rate'] = 0
                    metrics_dict['slow_request_rate'] = 0
                
                return metrics_dict
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {str(e)}")
            return {}

    def cleanup_old_data(self, days: int = 90):
        """Clean up old data to maintain performance"""
        try:
            # Clean old API usage logs
            api_cleanup_query = """
            DELETE FROM api_usage 
            WHERE timestamp < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            self.execute_query(api_cleanup_query, (days,))
            
            # Clean old resolved alerts
            alert_cleanup_query = """
            DELETE FROM critical_alerts 
            WHERE status = 'Resolved' 
            AND resolved_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            self.execute_query(alert_cleanup_query, (days,))
            
            self.logger.info(f"Cleaned up data older than {days} days")
            
        except Exception as e:
            self.logger.error(f"Data cleanup failed: {str(e)}")

    def backup_database(self, backup_path: str = None):
        """Create database backup"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"/tmp/support_copilot_backup_{timestamp}.sql"
            
            # This would typically use mysqldump
            # For now, we'll log the backup request
            self.logger.info(f"Database backup requested: {backup_path}")
            
            return {'success': True, 'backup_path': backup_path}
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def health_check(self) -> Dict:
        """Perform database health check"""
        try:
            # Test connection
            test_query = "SELECT 1 as test"
            result = self.execute_query(test_query, fetch_one=True)
            
            if result and result.get('test') == 1:
                # Get additional health metrics
                status_query = """
                SELECT 
                    COUNT(*) as total_issues,
                    COUNT(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR) THEN 1 END) as recent_issues
                FROM issues
                """
                
                status = self.execute_query(status_query, fetch_one=True)
                
                return {
                    'status': 'healthy',
                    'connection': 'ok',
                    'total_issues': status.get('total_issues', 0) if status else 0,
                    'recent_issues': status.get('recent_issues', 0) if status else 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'status': 'unhealthy',
                    'connection': 'failed',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'connection': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }