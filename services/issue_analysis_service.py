"""
Issue Analysis Service
Handles issue intake, analysis, and critical issue detection
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from mistralai import Mistral
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

class IssueAnalysisService:
    def __init__(self, db_manager, cache_manager):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Mistral client
        self.mistral_client = Mistral(
            api_key=os.getenv('MISTRAL_API_KEY')
        )
        
        # Severity keywords for classification
        self.severity_keywords = {
            'Critical': [
                'system down', 'outage', 'cannot access', 'complete failure',
                'data loss', 'security breach', 'urgent', 'emergency',
                'production down', 'service unavailable'
            ],
            'High': [
                'major issue', 'significant problem', 'blocking', 'broken',
                'not working', 'error', 'failure', 'important',
                'affecting multiple users', 'performance issue'
            ],
            'Normal': [
                'question', 'help', 'how to', 'clarification',
                'minor issue', 'improvement', 'suggestion'
            ],
            'Low': [
                'feature request', 'enhancement', 'nice to have',
                'cosmetic', 'documentation', 'typo'
            ]
        }

    def analyze_new_issue(self, customer_id: int, title: str, description: str, 
                         category: str, product_area: str = '') -> Dict:
        """
        Comprehensive analysis of a new issue
        """
        try:
            # Start analysis
            analysis_start = datetime.utcnow()
            
            # 1. Get customer history
            customer_history = self.get_customer_history(customer_id)
            
            # 2. Classify severity
            severity = self._classify_severity(title, description)
            
            # 3. Create the issue record
            issue_id = self._create_issue_record(
                customer_id, title, description, category, severity, product_area
            )
            
            # 4. Find similar issues
            similar_issues = self.find_similar_issues_by_content(title, description)
            
            # 5. Check for critical alerts
            critical_alerts = self._check_critical_conditions(customer_id, severity)
            
            # 6. Generate AI insights
            ai_insights = self._generate_ai_insights(title, description, similar_issues)
            
            # 7. Calculate priority score
            priority_score = self._calculate_priority_score(
                severity, customer_history, similar_issues
            )
            
            # 8. Update issue with analysis results
            self._update_issue_analysis(issue_id, severity, priority_score, ai_insights)
            
            analysis_time = (datetime.utcnow() - analysis_start).total_seconds()
            
            return {
                'issue_id': issue_id,
                'severity': severity,
                'priority_score': priority_score,
                'customer_history': customer_history,
                'similar_issues': similar_issues[:5],  # Top 5 similar issues
                'critical_alerts': critical_alerts,
                'ai_insights': ai_insights,
                'analysis_time_seconds': analysis_time,
                'recommendations': self._generate_recommendations(
                    severity, similar_issues, customer_history
                )
            }
            
        except Exception as e:
            self.logger.error(f"Issue analysis failed: {str(e)}")
            raise

    def _classify_severity(self, title: str, description: str) -> str:
        """
        Classify issue severity based on content analysis
        """
        try:
            # Combine title and description for analysis
            content = f"{title} {description}".lower()
            
            # Score each severity level
            severity_scores = {}
            
            for severity, keywords in self.severity_keywords.items():
                score = 0
                for keyword in keywords:
                    if keyword in content:
                        # Weight based on keyword importance
                        if severity == 'Critical':
                            score += 3
                        elif severity == 'High':
                            score += 2
                        elif severity == 'Normal':
                            score += 1
                        else:  # Low
                            score += 0.5
                
                severity_scores[severity] = score
            
            # Use AI for additional classification if scores are close
            if max(severity_scores.values()) < 2:
                ai_severity = self._ai_classify_severity(title, description)
                if ai_severity:
                    return ai_severity
            
            # Return highest scoring severity
            return max(severity_scores, key=severity_scores.get)
            
        except Exception as e:
            self.logger.error(f"Severity classification failed: {str(e)}")
            return 'Normal'  # Default fallback

    def _ai_classify_severity(self, title: str, description: str) -> Optional[str]:
        """
        Use AI to classify severity when keyword-based classification is uncertain
        """
        try:
            prompt = f"""
            Analyze the following support issue and classify its severity as Critical, High, Normal, or Low.
            
            Title: {title}
            Description: {description}
            
            Severity Guidelines:
            - Critical: System outages, data loss, security breaches, complete service unavailability
            - High: Major functionality broken, significant user impact, blocking issues
            - Normal: Standard issues, questions, minor bugs with workarounds
            - Low: Feature requests, cosmetic issues, documentation updates
            
            Respond with only the severity level: Critical, High, Normal, or Low
            """
            
            response = self.mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            
            severity = response.choices[0].message.content.strip()
            
            # Validate response
            if severity in ['Critical', 'High', 'Normal', 'Low']:
                return severity
            
        except Exception as e:
            self.logger.error(f"AI severity classification failed: {str(e)}")
        
        return None

    def _create_issue_record(self, customer_id: int, title: str, description: str,
                           category: str, severity: str, product_area: str) -> int:
        """
        Create new issue record in database
        """
        try:
            query = """
            INSERT INTO issues (customer_id, title, description, category, severity, product_area)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            issue_id = self.db_manager.execute_query(
                query, (customer_id, title, description, category, severity, product_area),
                fetch_lastrowid=True
            )
            
            self.logger.info(f"Created issue {issue_id} for customer {customer_id}")
            return issue_id
            
        except Exception as e:
            self.logger.error(f"Failed to create issue record: {str(e)}")
            raise

    def find_similar_issues(self, issue_id: int, limit: int = 5) -> List[Dict]:
        """
        Find similar issues for a given issue ID
        """
        try:
            # Get the current issue details
            current_issue = self.db_manager.get_issue_details(issue_id)
            if not current_issue:
                return []
            
            return self.find_similar_issues_by_content(
                current_issue['title'], 
                current_issue['description'],
                limit
            )
            
        except Exception as e:
            self.logger.error(f"Failed to find similar issues: {str(e)}")
            return []

    def find_similar_issues_by_content(self, title: str, description: str, 
                                     limit: int = 5) -> List[Dict]:
        """
        Find similar issues based on content similarity
        """
        try:
            # Get all resolved issues for comparison
            query = """
            SELECT issue_id, title, description, severity, resolution_time_hours
            FROM issues 
            WHERE status = 'Resolved' 
            AND resolution_time_hours IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 1000
            """
            
            resolved_issues = self.db_manager.execute_query(query, fetch_all=True)
            
            if not resolved_issues:
                return []
            
            # Prepare text data for similarity analysis
            current_text = f"{title} {description}"
            issue_texts = [f"{issue['title']} {issue['description']}" 
                          for issue in resolved_issues]
            issue_texts.append(current_text)
            
            # Calculate TF-IDF similarity
            vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=1000,
                ngram_range=(1, 2)
            )
            
            tfidf_matrix = vectorizer.fit_transform(issue_texts)
            
            # Calculate cosine similarity
            similarity_scores = cosine_similarity(
                tfidf_matrix[-1:], tfidf_matrix[:-1]
            ).flatten()
            
            # Get top similar issues
            similar_indices = similarity_scores.argsort()[-limit:][::-1]
            
            similar_issues = []
            for idx in similar_indices:
                if similarity_scores[idx] > 0.1:  # Minimum similarity threshold
                    issue = resolved_issues[idx]
                    similar_issues.append({
                        'issue_id': issue['issue_id'],
                        'title': issue['title'],
                        'description': issue['description'][:200] + '...',
                        'severity': issue['severity'],
                        'similarity_score': float(similarity_scores[idx]),
                        'resolution_time_hours': issue['resolution_time_hours']
                    })
            
            return similar_issues
            
        except Exception as e:
            self.logger.error(f"Similar issues search failed: {str(e)}")
            return []

    def get_customer_history(self, customer_id: int) -> Dict:
        """
        Get comprehensive customer history
        """
        try:
            # Check cache first
            cache_key = f"customer_history_{customer_id}"
            cached_history = self.cache_manager.get(cache_key)
            if cached_history:
                return cached_history
            
            # Get customer basic info
            customer_query = """
            SELECT customer_id, customer_name, email, company, tier, created_at
            FROM customers WHERE customer_id = %s
            """
            customer = self.db_manager.execute_query(customer_query, (customer_id,), fetch_one=True)
            
            if not customer:
                return {}
            
            # Get issue statistics
            stats_query = """
            SELECT 
                COUNT(*) as total_issues,
                COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_issues,
                COUNT(CASE WHEN status IN ('Open', 'In Progress') THEN 1 END) as open_issues,
                COUNT(CASE WHEN severity = 'Critical' THEN 1 END) as critical_issues,
                COUNT(CASE WHEN severity = 'High' THEN 1 END) as high_issues,
                AVG(resolution_time_hours) as avg_resolution_time,
                MAX(created_at) as last_issue_date,
                COUNT(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as issues_last_30_days
            FROM issues 
            WHERE customer_id = %s
            """
            stats = self.db_manager.execute_query(stats_query, (customer_id,), fetch_one=True)
            
            # Get recent issues
            recent_query = """
            SELECT issue_id, title, severity, status, created_at
            FROM issues 
            WHERE customer_id = %s 
            ORDER BY created_at DESC 
            LIMIT 10
            """
            recent_issues = self.db_manager.execute_query(recent_query, (customer_id,), fetch_all=True)
            
            history = {
                'customer_info': dict(customer),
                'statistics': dict(stats) if stats else {},
                'recent_issues': [dict(issue) for issue in recent_issues] if recent_issues else [],
                'risk_level': self._calculate_customer_risk_level(stats)
            }
            
            # Cache for 5 minutes
            self.cache_manager.set(cache_key, history, expire=300)
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get customer history: {str(e)}")
            return {}

    def _calculate_customer_risk_level(self, stats: Dict) -> str:
        """
        Calculate customer risk level based on issue patterns
        """
        if not stats:
            return 'Low'
        
        # Risk factors
        total_issues = stats.get('total_issues', 0)
        critical_issues = stats.get('critical_issues', 0)
        high_issues = stats.get('high_issues', 0)
        issues_last_30_days = stats.get('issues_last_30_days', 0)
        avg_resolution_time = stats.get('avg_resolution_time', 0) or 0
        
        risk_score = 0
        
        # High volume of issues
        if total_issues > 20:
            risk_score += 2
        elif total_issues > 10:
            risk_score += 1
        
        # Critical/High severity issues
        if critical_issues > 0:
            risk_score += 3
        if high_issues > 3:
            risk_score += 2
        
        # Recent activity
        if issues_last_30_days > 5:
            risk_score += 2
        
        # Long resolution times
        if avg_resolution_time > 48:
            risk_score += 2
        
        # Determine risk level
        if risk_score >= 6:
            return 'High'
        elif risk_score >= 3:
            return 'Medium'
        else:
            return 'Low'

    def _check_critical_conditions(self, customer_id: int, severity: str) -> List[Dict]:
        """
        Check for critical conditions that require immediate attention
        """
        alerts = []
        
        try:
            # Check for unattended critical issues > 24 hours
            critical_query = """
            SELECT issue_id, title, created_at, 
                   TIMESTAMPDIFF(HOUR, created_at, NOW()) as hours_open
            FROM issues 
            WHERE customer_id = %s 
            AND severity = 'Critical' 
            AND status IN ('Open', 'In Progress')
            AND created_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """
            
            unattended_critical = self.db_manager.execute_query(
                critical_query, (customer_id,), fetch_all=True
            )
            
            for issue in unattended_critical or []:
                alert = {
                    'type': 'Unattended Critical Issue',
                    'issue_id': issue['issue_id'],
                    'title': issue['title'],
                    'hours_open': issue['hours_open'],
                    'severity': 'Critical',
                    'message': f"Critical issue #{issue['issue_id']} has been unattended for {issue['hours_open']} hours"
                }
                alerts.append(alert)
                
                # Create alert record
                self._create_alert_record(issue['issue_id'], 'Unattended', alert['message'])
            
            # Check for multiple high-severity issues from same customer
            high_severity_query = """
            SELECT COUNT(*) as count
            FROM issues 
            WHERE customer_id = %s 
            AND severity IN ('Critical', 'High')
            AND status IN ('Open', 'In Progress')
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """
            
            high_count = self.db_manager.execute_query(
                high_severity_query, (customer_id,), fetch_one=True
            )
            
            if high_count and high_count['count'] >= 3:
                alert = {
                    'type': 'Multiple High Severity Issues',
                    'customer_id': customer_id,
                    'count': high_count['count'],
                    'severity': 'High',
                    'message': f"Customer has {high_count['count']} high-severity issues in the last 7 days"
                }
                alerts.append(alert)
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Critical conditions check failed: {str(e)}")
            return []

    def _create_alert_record(self, issue_id: int, alert_type: str, message: str):
        """
        Create alert record in database
        """
        try:
            query = """
            INSERT INTO critical_alerts (issue_id, alert_type, alert_message, severity)
            VALUES (%s, %s, %s, 'High')
            """
            self.db_manager.execute_query(query, (issue_id, alert_type, message))
            
        except Exception as e:
            self.logger.error(f"Failed to create alert record: {str(e)}")

    def _generate_ai_insights(self, title: str, description: str, 
                            similar_issues: List[Dict]) -> Dict:
        """
        Generate AI-powered insights for the issue
        """
        try:
            # Prepare context from similar issues
            similar_context = ""
            if similar_issues:
                similar_context = "\n".join([
                    f"- {issue['title']} (resolved in {issue.get('resolution_time_hours', 'N/A')} hours)"
                    for issue in similar_issues[:3]
                ])
            
            prompt = f"""
            Analyze this support issue and provide insights:
            
            Title: {title}
            Description: {description}
            
            Similar resolved issues:
            {similar_context}
            
            Please provide:
            1. Root cause analysis (2-3 sentences)
            2. Recommended resolution approach
            3. Estimated resolution time
            4. Potential escalation triggers
            5. Customer communication strategy
            
            Format as JSON with keys: root_cause, resolution_approach, estimated_time_hours, escalation_triggers, communication_strategy
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )
            
            insights_text = response.choices[0].message.content.strip()
            
            # Try to parse as JSON, fallback to structured text
            try:
                insights = json.loads(insights_text)
            except:
                insights = {
                    'root_cause': 'AI analysis pending',
                    'resolution_approach': insights_text[:200],
                    'estimated_time_hours': 24,
                    'escalation_triggers': ['No response in 4 hours', 'Customer escalation'],
                    'communication_strategy': 'Regular updates every 2 hours'
                }
            
            return insights
            
        except Exception as e:
            self.logger.error(f"AI insights generation failed: {str(e)}")
            return {
                'root_cause': 'Analysis pending',
                'resolution_approach': 'Standard troubleshooting process',
                'estimated_time_hours': 24,
                'escalation_triggers': ['No response in 4 hours'],
                'communication_strategy': 'Regular updates'
            }

    def _calculate_priority_score(self, severity: str, customer_history: Dict, 
                                similar_issues: List[Dict]) -> int:
        """
        Calculate priority score (1-10, where 10 is highest priority)
        """
        score = 5  # Base score
        
        # Severity impact
        severity_scores = {'Critical': 4, 'High': 3, 'Normal': 0, 'Low': -2}
        score += severity_scores.get(severity, 0)
        
        # Customer tier impact
        customer_info = customer_history.get('customer_info', {})
        tier = customer_info.get('tier', 'Basic')
        tier_scores = {'Enterprise': 2, 'Premium': 1, 'Basic': 0}
        score += tier_scores.get(tier, 0)
        
        # Customer risk level impact
        risk_level = customer_history.get('risk_level', 'Low')
        risk_scores = {'High': 2, 'Medium': 1, 'Low': 0}
        score += risk_scores.get(risk_level, 0)
        
        # Similar issues impact (if many similar issues exist, might be easier to resolve)
        if len(similar_issues) > 3:
            score -= 1
        
        # Ensure score is within bounds
        return max(1, min(10, score))

    def _update_issue_analysis(self, issue_id: int, severity: str, 
                             priority_score: int, ai_insights: Dict):
        """
        Update issue record with analysis results
        """
        try:
            query = """
            UPDATE issues 
            SET severity = %s, priority = %s, tags = %s
            WHERE issue_id = %s
            """
            
            tags = json.dumps({
                'ai_analyzed': True,
                'estimated_resolution_hours': ai_insights.get('estimated_time_hours', 24),
                'priority_score': priority_score
            })
            
            self.db_manager.execute_query(
                query, (severity, priority_score, tags, issue_id)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update issue analysis: {str(e)}")

    def _generate_recommendations(self, severity: str, similar_issues: List[Dict], 
                                customer_history: Dict) -> List[str]:
        """
        Generate actionable recommendations
        """
        recommendations = []
        
        # Severity-based recommendations
        if severity == 'Critical':
            recommendations.extend([
                'Immediately assign to senior technical team',
                'Notify customer within 15 minutes',
                'Set up war room if needed',
                'Prepare executive escalation path'
            ])
        elif severity == 'High':
            recommendations.extend([
                'Assign to experienced support engineer',
                'Respond to customer within 1 hour',
                'Monitor progress every 2 hours'
            ])
        
        # Similar issues recommendations
        if similar_issues:
            avg_resolution_time = np.mean([
                issue.get('resolution_time_hours', 24) 
                for issue in similar_issues
            ])
            recommendations.append(
                f'Based on similar issues, expected resolution time: {avg_resolution_time:.1f} hours'
            )
            
            if len(similar_issues) >= 3:
                recommendations.append('Review knowledge base articles from similar resolved issues')
        
        # Customer history recommendations
        risk_level = customer_history.get('risk_level', 'Low')
        if risk_level == 'High':
            recommendations.extend([
                'Consider proactive communication',
                'Involve account manager if available',
                'Document all interactions thoroughly'
            ])
        
        return recommendations

    def get_critical_alerts(self) -> List[Dict]:
        """
        Get all active critical alerts
        """
        try:
            query = """
            SELECT ca.*, i.title, i.severity, c.customer_name, c.company
            FROM critical_alerts ca
            JOIN issues i ON ca.issue_id = i.issue_id
            JOIN customers c ON i.customer_id = c.customer_id
            WHERE ca.status = 'Active'
            ORDER BY ca.created_at DESC
            """
            
            alerts = self.db_manager.execute_query(query, fetch_all=True)
            return [dict(alert) for alert in alerts] if alerts else []
            
        except Exception as e:
            self.logger.error(f"Failed to get critical alerts: {str(e)}")
            return []

    def acknowledge_alert(self, alert_id: int, user_id: int) -> Dict:
        """
        Acknowledge a critical alert
        """
        try:
            query = """
            UPDATE critical_alerts 
            SET status = 'Acknowledged', acknowledged_at = NOW(), acknowledged_by = %s
            WHERE alert_id = %s AND status = 'Active'
            """
            
            rows_affected = self.db_manager.execute_query(
                query, (user_id, alert_id), fetch_rowcount=True
            )
            
            if rows_affected > 0:
                return {'success': True, 'message': 'Alert acknowledged successfully'}
            else:
                return {'success': False, 'message': 'Alert not found or already acknowledged'}
                
        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert: {str(e)}")
            return {'success': False, 'message': 'Failed to acknowledge alert'}