"""
Summarization Service
Handles conversation summarization and knowledge base updates
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from mistralai import Mistral
import os
from collections import Counter

class SummarizationService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Mistral client
        self.mistral_client = Mistral(
            api_key=os.getenv('MISTRAL_API_KEY')
        )

    def generate_conversation_summary(self, issue_id: int) -> Dict:
        """
        Generate comprehensive conversation summary for an issue
        """
        try:
            # Get issue details
            issue_details = self.db_manager.get_issue_details(issue_id)
            if not issue_details:
                raise ValueError(f"Issue {issue_id} not found")
            
            # Get full conversation history
            conversation_history = self._get_full_conversation(issue_id)
            
            if not conversation_history:
                return {
                    'issue_id': issue_id,
                    'summary': 'No conversation history available',
                    'key_points': [],
                    'action_items': [],
                    'resolution_summary': None
                }
            
            # Generate AI-powered summary
            ai_summary = self._generate_ai_summary(issue_details, conversation_history)
            
            # Extract key metrics
            conversation_metrics = self._calculate_conversation_metrics(conversation_history)
            
            # Generate action items
            action_items = self._extract_action_items(conversation_history, issue_details)
            
            # Create resolution summary if issue is resolved
            resolution_summary = None
            if issue_details.get('status') == 'Resolved':
                resolution_summary = self._generate_resolution_summary(
                    issue_details, conversation_history
                )
            
            # Save summary to database
            summary_data = {
                'issue_id': issue_id,
                'summary_text': ai_summary['summary'],
                'key_points': ai_summary['key_points'],
                'action_items': action_items,
                'conversation_metrics': conversation_metrics,
                'resolution_summary': resolution_summary,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            self._save_summary_to_db(summary_data)
            
            # Update knowledge base if resolved
            if resolution_summary:
                self._update_knowledge_base(issue_details, summary_data)
            
            return summary_data
            
        except Exception as e:
            self.logger.error(f"Conversation summarization failed: {str(e)}")
            raise

    def _get_full_conversation(self, issue_id: int) -> List[Dict]:
        """
        Get complete conversation history for an issue
        """
        try:
            query = """
            SELECT c.*, se.name as sender_name
            FROM conversations c
            LEFT JOIN support_executives se ON c.sender_id = se.executive_id
            WHERE c.issue_id = %s
            ORDER BY c.timestamp ASC
            """
            
            conversations = self.db_manager.execute_query(
                query, (issue_id,), fetch_all=True
            )
            
            return [dict(conv) for conv in conversations] if conversations else []
            
        except Exception as e:
            self.logger.error(f"Failed to get conversation history: {str(e)}")
            return []

    def _generate_ai_summary(self, issue_details: Dict, conversation_history: List[Dict]) -> Dict:
        """
        Generate AI-powered conversation summary
        """
        try:
            # Prepare conversation text
            conversation_text = self._format_conversation_for_ai(conversation_history)
            
            prompt = f"""
            Summarize this customer support conversation:
            
            Issue Details:
            - Title: {issue_details.get('title', '')}
            - Category: {issue_details.get('category', '')}
            - Severity: {issue_details.get('severity', '')}
            - Status: {issue_details.get('status', '')}
            
            Conversation:
            {conversation_text}
            
            Please provide:
            1. A concise summary (2-3 paragraphs) of the entire conversation
            2. Key points discussed (bullet points)
            3. Customer concerns and requests
            4. Support actions taken
            5. Current status and next steps
            
            Format as JSON with keys: summary, key_points, customer_concerns, support_actions, current_status
            """
            
            response = self.mistral_client.chat.complete(
                model="mistral-medium-latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.2
            )
            
            try:
                summary_data = json.loads(response.choices[0].message.content.strip())
            except json.JSONDecodeError:
                # Fallback to text summary
                summary_text = response.choices[0].message.content.strip()
                summary_data = {
                    'summary': summary_text[:500],
                    'key_points': ['AI summary generated'],
                    'customer_concerns': ['See full summary'],
                    'support_actions': ['Various support actions taken'],
                    'current_status': issue_details.get('status', 'Unknown')
                }
            
            return summary_data
            
        except Exception as e:
            self.logger.error(f"AI summary generation failed: {str(e)}")
            return {
                'summary': 'Summary generation failed',
                'key_points': [],
                'customer_concerns': [],
                'support_actions': [],
                'current_status': issue_details.get('status', 'Unknown')
            }

    def _format_conversation_for_ai(self, conversation_history: List[Dict]) -> str:
        """
        Format conversation history for AI processing
        """
        formatted_conversation = []
        
        for msg in conversation_history:
            timestamp = msg.get('timestamp', '').strftime('%Y-%m-%d %H:%M') if msg.get('timestamp') else 'Unknown'
            sender = msg.get('sender_name') or msg.get('message_type', 'Unknown')
            content = msg.get('message_content', '')
            
            formatted_conversation.append(f"[{timestamp}] {sender}: {content}")
        
        return '\n'.join(formatted_conversation)

    def _calculate_conversation_metrics(self, conversation_history: List[Dict]) -> Dict:
        """
        Calculate metrics about the conversation
        """
        try:
            if not conversation_history:
                return {}
            
            # Basic metrics
            total_messages = len(conversation_history)
            customer_messages = len([msg for msg in conversation_history 
                                   if msg.get('message_type') == 'Customer'])
            support_messages = len([msg for msg in conversation_history 
                                  if msg.get('message_type') == 'Support'])
            
            # Time metrics
            first_message = conversation_history[0].get('timestamp')
            last_message = conversation_history[-1].get('timestamp')
            
            conversation_duration = None
            if first_message and last_message:
                duration = last_message - first_message
                conversation_duration = duration.total_seconds() / 3600  # Hours
            
            # Response time analysis
            response_times = self._calculate_response_times(conversation_history)
            
            # Sentiment analysis
            sentiment_scores = [msg.get('sentiment_score') for msg in conversation_history 
                              if msg.get('sentiment_score') is not None]
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
            
            return {
                'total_messages': total_messages,
                'customer_messages': customer_messages,
                'support_messages': support_messages,
                'conversation_duration_hours': conversation_duration,
                'avg_response_time_hours': response_times.get('avg_response_time'),
                'max_response_time_hours': response_times.get('max_response_time'),
                'avg_sentiment_score': avg_sentiment,
                'first_message_time': first_message.isoformat() if first_message else None,
                'last_message_time': last_message.isoformat() if last_message else None
            }
            
        except Exception as e:
            self.logger.error(f"Metrics calculation failed: {str(e)}")
            return {}

    def _calculate_response_times(self, conversation_history: List[Dict]) -> Dict:
        """
        Calculate response time metrics
        """
        try:
            response_times = []
            
            for i in range(1, len(conversation_history)):
                prev_msg = conversation_history[i-1]
                curr_msg = conversation_history[i]
                
                # Calculate response time from customer to support
                if (prev_msg.get('message_type') == 'Customer' and 
                    curr_msg.get('message_type') == 'Support'):
                    
                    prev_time = prev_msg.get('timestamp')
                    curr_time = curr_msg.get('timestamp')
                    
                    if prev_time and curr_time:
                        response_time = (curr_time - prev_time).total_seconds() / 3600
                        response_times.append(response_time)
            
            if response_times:
                return {
                    'avg_response_time': sum(response_times) / len(response_times),
                    'max_response_time': max(response_times),
                    'min_response_time': min(response_times)
                }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Response time calculation failed: {str(e)}")
            return {}

    def _extract_action_items(self, conversation_history: List[Dict], 
                            issue_details: Dict) -> List[Dict]:
        """
        Extract action items from conversation
        """
        try:
            # Use AI to extract action items
            conversation_text = self._format_conversation_for_ai(conversation_history)
            
            prompt = f"""
            Extract action items from this support conversation:
            
            {conversation_text}
            
            Identify:
            1. Pending actions for support team
            2. Pending actions for customer
            3. Follow-up items
            4. Escalation requirements
            
            For each action item, provide:
            - Description
            - Assigned to (Support/Customer/System)
            - Priority (High/Medium/Low)
            - Due date estimate
            
            Format as JSON array with objects containing: description, assigned_to, priority, due_estimate
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.2
            )
            
            try:
                action_items = json.loads(response.choices[0].message.content.strip())
                if not isinstance(action_items, list):
                    action_items = []
            except json.JSONDecodeError:
                action_items = []
            
            # Add default action items based on issue status
            status = issue_details.get('status', '')
            if status in ['Open', 'In Progress']:
                action_items.append({
                    'description': 'Continue working on issue resolution',
                    'assigned_to': 'Support',
                    'priority': 'High' if issue_details.get('severity') in ['Critical', 'High'] else 'Medium',
                    'due_estimate': '24 hours'
                })
            
            return action_items
            
        except Exception as e:
            self.logger.error(f"Action items extraction failed: {str(e)}")
            return []

    def _generate_resolution_summary(self, issue_details: Dict, 
                                   conversation_history: List[Dict]) -> Dict:
        """
        Generate resolution summary for resolved issues
        """
        try:
            # Get resolution details
            resolution_query = """
            SELECT * FROM issue_resolutions WHERE issue_id = %s
            """
            resolution = self.db_manager.execute_query(
                resolution_query, (issue_details['issue_id'],), fetch_one=True
            )
            
            conversation_text = self._format_conversation_for_ai(conversation_history)
            
            prompt = f"""
            Generate a resolution summary for this resolved support issue:
            
            Issue: {issue_details.get('title', '')}
            Category: {issue_details.get('category', '')}
            Severity: {issue_details.get('severity', '')}
            
            Conversation:
            {conversation_text}
            
            Please provide:
            1. Root cause of the issue
            2. Solution implemented
            3. Steps taken to resolve
            4. Prevention measures suggested
            5. Customer satisfaction indicators
            
            Format as JSON with keys: root_cause, solution, resolution_steps, prevention_measures, satisfaction_indicators
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.2
            )
            
            try:
                resolution_summary = json.loads(response.choices[0].message.content.strip())
            except json.JSONDecodeError:
                resolution_summary = {
                    'root_cause': 'Analysis pending',
                    'solution': response.choices[0].message.content.strip()[:200],
                    'resolution_steps': ['See conversation history'],
                    'prevention_measures': ['To be determined'],
                    'satisfaction_indicators': ['Resolution completed']
                }
            
            # Add resolution metrics
            if resolution:
                resolution_summary.update({
                    'resolution_time_hours': resolution.get('resolution_time_hours'),
                    'customer_satisfaction': resolution.get('customer_satisfaction'),
                    'resolved_by': resolution.get('resolved_by'),
                    'resolution_category': resolution.get('resolution_category')
                })
            
            return resolution_summary
            
        except Exception as e:
            self.logger.error(f"Resolution summary generation failed: {str(e)}")
            return {}

    def _save_summary_to_db(self, summary_data: Dict):
        """
        Save conversation summary to database
        """
        try:
            query = """
            INSERT INTO issue_summaries (issue_id, summary_text, key_points, action_items)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            summary_text = VALUES(summary_text),
            key_points = VALUES(key_points),
            action_items = VALUES(action_items),
            generated_at = NOW()
            """
            
            self.db_manager.execute_query(
                query,
                (
                    summary_data['issue_id'],
                    summary_data['summary_text'],
                    json.dumps(summary_data['key_points']),
                    json.dumps(summary_data['action_items'])
                )
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save summary to database: {str(e)}")

    def _update_knowledge_base(self, issue_details: Dict, summary_data: Dict):
        """
        Update knowledge base with resolved issue information
        """
        try:
            # Create knowledge base entry
            kb_entry = {
                'title': issue_details.get('title', ''),
                'category': issue_details.get('category', ''),
                'severity': issue_details.get('severity', ''),
                'summary': summary_data.get('summary_text', ''),
                'resolution': summary_data.get('resolution_summary', {}),
                'tags': self._generate_kb_tags(issue_details, summary_data),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Here you would typically save to a knowledge base system
            # For now, we'll log it
            self.logger.info(f"Knowledge base entry created for issue {issue_details['issue_id']}")
            
            # Update similar issues mapping
            self._update_similar_issues_mapping(issue_details['issue_id'], summary_data)
            
        except Exception as e:
            self.logger.error(f"Knowledge base update failed: {str(e)}")

    def _generate_kb_tags(self, issue_details: Dict, summary_data: Dict) -> List[str]:
        """
        Generate tags for knowledge base entry
        """
        tags = []
        
        # Add category and severity tags
        tags.append(issue_details.get('category', '').lower())
        tags.append(issue_details.get('severity', '').lower())
        
        # Extract keywords from title and summary
        title = issue_details.get('title', '').lower()
        summary = summary_data.get('summary_text', '').lower()
        
        # Common technical keywords
        tech_keywords = [
            'login', 'authentication', 'password', 'api', 'database', 'server',
            'network', 'connection', 'timeout', 'error', 'bug', 'performance',
            'security', 'backup', 'restore', 'integration', 'sync', 'export'
        ]
        
        for keyword in tech_keywords:
            if keyword in title or keyword in summary:
                tags.append(keyword)
        
        # Add product area if available
        product_area = issue_details.get('product_area', '')
        if product_area:
            tags.append(product_area.lower())
        
        return list(set(tags))  # Remove duplicates

    def _update_similar_issues_mapping(self, issue_id: int, summary_data: Dict):
        """
        Update similar issues mapping for future reference
        """
        try:
            # This would typically involve vector similarity calculations
            # For now, we'll create a simple mapping based on category and tags
            
            # Find issues with similar characteristics
            similar_query = """
            SELECT issue_id, title, category, severity
            FROM issues
            WHERE category = (SELECT category FROM issues WHERE issue_id = %s)
            AND issue_id != %s
            AND status = 'Resolved'
            LIMIT 10
            """
            
            similar_issues = self.db_manager.execute_query(
                similar_query, (issue_id, issue_id), fetch_all=True
            )
            
            # Create similarity mappings
            for similar_issue in similar_issues or []:
                similarity_score = self._calculate_simple_similarity(
                    issue_id, similar_issue['issue_id']
                )
                
                if similarity_score > 0.3:  # Minimum threshold
                    mapping_query = """
                    INSERT IGNORE INTO similar_issues 
                    (source_issue_id, similar_issue_id, similarity_score)
                    VALUES (%s, %s, %s)
                    """
                    self.db_manager.execute_query(
                        mapping_query, (issue_id, similar_issue['issue_id'], similarity_score)
                    )
            
        except Exception as e:
            self.logger.error(f"Similar issues mapping update failed: {str(e)}")

    def _calculate_simple_similarity(self, issue_id1: int, issue_id2: int) -> float:
        """
        Calculate simple similarity score between two issues
        """
        try:
            # Get issue details for both issues
            query = """
            SELECT issue_id, title, description, category, severity, product_area
            FROM issues WHERE issue_id IN (%s, %s)
            """
            
            issues = self.db_manager.execute_query(
                query, (issue_id1, issue_id2), fetch_all=True
            )
            
            if len(issues) != 2:
                return 0.0
            
            issue1, issue2 = issues[0], issues[1]
            
            similarity_score = 0.0
            
            # Category match
            if issue1['category'] == issue2['category']:
                similarity_score += 0.3
            
            # Severity match
            if issue1['severity'] == issue2['severity']:
                similarity_score += 0.2
            
            # Product area match
            if issue1['product_area'] == issue2['product_area']:
                similarity_score += 0.2
            
            # Title similarity (simple word overlap)
            title1_words = set(issue1['title'].lower().split())
            title2_words = set(issue2['title'].lower().split())
            
            if title1_words and title2_words:
                word_overlap = len(title1_words.intersection(title2_words))
                total_words = len(title1_words.union(title2_words))
                similarity_score += 0.3 * (word_overlap / total_words)
            
            return min(1.0, similarity_score)
            
        except Exception as e:
            self.logger.error(f"Similarity calculation failed: {str(e)}")
            return 0.0

    def get_issue_summary(self, issue_id: int) -> Optional[Dict]:
        """
        Get existing summary for an issue
        """
        try:
            query = """
            SELECT * FROM issue_summaries WHERE issue_id = %s
            ORDER BY generated_at DESC LIMIT 1
            """
            
            summary = self.db_manager.execute_query(query, (issue_id,), fetch_one=True)
            
            if summary:
                summary_dict = dict(summary)
                # Parse JSON fields
                if summary_dict.get('key_points'):
                    summary_dict['key_points'] = json.loads(summary_dict['key_points'])
                if summary_dict.get('action_items'):
                    summary_dict['action_items'] = json.loads(summary_dict['action_items'])
                
                return summary_dict
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get issue summary: {str(e)}")
            return None

    def batch_summarize_resolved_issues(self, limit: int = 50) -> Dict:
        """
        Batch process summaries for recently resolved issues
        """
        try:
            # Get recently resolved issues without summaries
            query = """
            SELECT i.issue_id
            FROM issues i
            LEFT JOIN issue_summaries s ON i.issue_id = s.issue_id
            WHERE i.status = 'Resolved'
            AND i.resolved_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            AND s.issue_id IS NULL
            ORDER BY i.resolved_at DESC
            LIMIT %s
            """
            
            issues = self.db_manager.execute_query(query, (limit,), fetch_all=True)
            
            results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            for issue in issues or []:
                try:
                    self.generate_conversation_summary(issue['issue_id'])
                    results['successful'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'issue_id': issue['issue_id'],
                        'error': str(e)
                    })
                
                results['processed'] += 1
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch summarization failed: {str(e)}")
            return {'processed': 0, 'successful': 0, 'failed': 1, 'errors': [str(e)]}