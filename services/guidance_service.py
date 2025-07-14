"""
Guidance Service
Generates recommended message templates and provides support guidance
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from mistralai import Mistral
import os
from jinja2 import Template

class GuidanceService:
    def __init__(self, db_manager, cache_manager):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize Mistral client
        self.mistral_client = Mistral(
            api_key=os.getenv('MISTRAL_API_KEY')
        )
        
        # Template categories and their characteristics
        self.template_categories = {
            'initial_response': {
                'description': 'First response to customer issue',
                'tone': 'professional, empathetic, reassuring',
                'required_elements': ['acknowledgment', 'next_steps', 'timeline']
            },
            'status_update': {
                'description': 'Progress update on ongoing issue',
                'tone': 'informative, transparent, professional',
                'required_elements': ['current_status', 'progress_made', 'next_steps']
            },
            'escalation': {
                'description': 'Issue escalation notification',
                'tone': 'urgent, professional, apologetic',
                'required_elements': ['escalation_reason', 'new_timeline', 'contact_info']
            },
            'resolution': {
                'description': 'Issue resolution confirmation',
                'tone': 'positive, helpful, professional',
                'required_elements': ['resolution_summary', 'verification_request', 'follow_up']
            },
            'clarification': {
                'description': 'Request for additional information',
                'tone': 'helpful, specific, professional',
                'required_elements': ['information_needed', 'reason', 'urgency']
            }
        }

    def generate_response_template(self, issue_id: int, message_content: str, 
                                 context: str = '') -> Dict:
        """
        Generate a recommended message template based on issue context and customer message
        """
        try:
            # Get issue details
            issue_details = self.db_manager.get_issue_details(issue_id)
            if not issue_details:
                raise ValueError(f"Issue {issue_id} not found")
            
            # Get customer history
            customer_history = self._get_customer_context(issue_details['customer_id'])
            
            # Get conversation history
            conversation_history = self._get_conversation_history(issue_id)
            
            # Analyze message intent
            message_intent = self._analyze_message_intent(message_content)
            
            # Determine template category
            template_category = self._determine_template_category(
                message_intent, issue_details, conversation_history
            )
            
            # Generate personalized template
            template = self._generate_ai_template(
                issue_details, customer_history, message_content, 
                template_category, context
            )
            
            # Get alternative templates
            alternatives = self._get_alternative_templates(
                template_category, issue_details['severity']
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_template_confidence(
                template, issue_details, message_intent
            )
            
            return {
                'issue_id': issue_id,
                'template_category': template_category,
                'recommended_template': template,
                'alternatives': alternatives,
                'confidence_score': confidence_score,
                'message_intent': message_intent,
                'customization_suggestions': self._get_customization_suggestions(
                    template, issue_details
                ),
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Template generation failed: {str(e)}")
            raise

    def _get_customer_context(self, customer_id: int) -> Dict:
        """
        Get relevant customer context for template personalization
        """
        try:
            query = """
            SELECT c.customer_name, c.company, c.tier,
                   COUNT(i.issue_id) as total_issues,
                   AVG(CASE WHEN ir.customer_satisfaction IS NOT NULL 
                       THEN ir.customer_satisfaction END) as avg_satisfaction
            FROM customers c
            LEFT JOIN issues i ON c.customer_id = i.customer_id
            LEFT JOIN issue_resolutions ir ON i.issue_id = ir.issue_id
            WHERE c.customer_id = %s
            GROUP BY c.customer_id
            """
            
            context = self.db_manager.execute_query(
                query, (customer_id,), fetch_one=True
            )
            
            return dict(context) if context else {}
            
        except Exception as e:
            self.logger.error(f"Failed to get customer context: {str(e)}")
            return {}

    def _get_conversation_history(self, issue_id: int) -> List[Dict]:
        """
        Get conversation history for context
        """
        try:
            query = """
            SELECT message_type, message_content, timestamp, sentiment_score
            FROM conversations
            WHERE issue_id = %s
            ORDER BY timestamp ASC
            LIMIT 10
            """
            
            history = self.db_manager.execute_query(
                query, (issue_id,), fetch_all=True
            )
            
            return [dict(msg) for msg in history] if history else []
            
        except Exception as e:
            self.logger.error(f"Failed to get conversation history: {str(e)}")
            return []

    def _analyze_message_intent(self, message_content: str) -> Dict:
        """
        Analyze customer message to understand intent and sentiment
        """
        try:
            prompt = f"""
            Analyze this customer support message and identify:
            1. Primary intent (question, complaint, request, escalation, appreciation)
            2. Urgency level (low, medium, high, critical)
            3. Sentiment (positive, neutral, negative, frustrated, angry)
            4. Key topics mentioned
            5. Specific requests or questions
            
            Message: "{message_content}"
            
            Respond in JSON format with keys: intent, urgency, sentiment, topics, requests
            """
            
            response = self.mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2
            )
            
            try:
                analysis = json.loads(response.choices[0].message.content.strip())
            except json.JSONDecodeError:
                # Fallback analysis
                analysis = {
                    'intent': 'question',
                    'urgency': 'medium',
                    'sentiment': 'neutral',
                    'topics': ['general inquiry'],
                    'requests': ['assistance']
                }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Message intent analysis failed: {str(e)}")
            return {
                'intent': 'question',
                'urgency': 'medium',
                'sentiment': 'neutral',
                'topics': [],
                'requests': []
            }

    def _determine_template_category(self, message_intent: Dict, issue_details: Dict, 
                                   conversation_history: List[Dict]) -> str:
        """
        Determine the appropriate template category based on context
        """
        try:
            # Check if this is the first response
            if not conversation_history or len(conversation_history) <= 1:
                return 'initial_response'
            
            # Check intent
            intent = message_intent.get('intent', '').lower()
            urgency = message_intent.get('urgency', '').lower()
            
            # Escalation scenarios
            if intent in ['escalation', 'complaint'] or urgency == 'critical':
                return 'escalation'
            
            # Resolution scenarios
            if issue_details.get('status') == 'Resolved':
                return 'resolution'
            
            # Clarification scenarios
            if intent in ['question'] and 'clarification' in message_intent.get('requests', []):
                return 'clarification'
            
            # Default to status update
            return 'status_update'
            
        except Exception as e:
            self.logger.error(f"Template category determination failed: {str(e)}")
            return 'status_update'

    def _generate_ai_template(self, issue_details: Dict, customer_history: Dict,
                            message_content: str, template_category: str, 
                            context: str) -> Dict:
        """
        Generate AI-powered personalized template
        """
        try:
            # Get category specifications
            category_spec = self.template_categories.get(template_category, {})
            
            # Build context for AI
            ai_context = f"""
            Generate a professional support response template for:
            
            Customer: {customer_history.get('customer_name', 'Valued Customer')}
            Company: {customer_history.get('company', 'N/A')}
            Tier: {customer_history.get('tier', 'Basic')}
            
            Issue Details:
            - Title: {issue_details.get('title', '')}
            - Severity: {issue_details.get('severity', 'Normal')}
            - Category: {issue_details.get('category', '')}
            - Status: {issue_details.get('status', 'Open')}
            
            Customer Message: "{message_content}"
            
            Template Category: {template_category}
            Required Tone: {category_spec.get('tone', 'professional')}
            Required Elements: {', '.join(category_spec.get('required_elements', []))}
            
            Additional Context: {context}
            
            Generate a response that:
            1. Addresses the customer's specific message
            2. Maintains appropriate tone and professionalism
            3. Includes all required elements for this category
            4. Uses placeholders {{variable_name}} for customizable parts
            5. Is concise but comprehensive
            
            Provide the template content and a list of variables used.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": ai_context}],
                max_tokens=800,
                temperature=0.3
            )
            
            template_content = response.choices[0].message.content.strip()
            
            # Extract variables from template
            variables = self._extract_template_variables(template_content)
            
            # Generate suggested values for variables
            suggested_values = self._generate_variable_suggestions(
                variables, issue_details, customer_history
            )
            
            return {
                'content': template_content,
                'variables': variables,
                'suggested_values': suggested_values,
                'category': template_category,
                'tone': category_spec.get('tone', 'professional')
            }
            
        except Exception as e:
            self.logger.error(f"AI template generation failed: {str(e)}")
            # Return fallback template
            return self._get_fallback_template(template_category, issue_details)

    def _extract_template_variables(self, template_content: str) -> List[str]:
        """
        Extract variable placeholders from template content
        """
        import re
        variables = re.findall(r'\{\{(\w+)\}\}', template_content)
        return list(set(variables))

    def _generate_variable_suggestions(self, variables: List[str], 
                                     issue_details: Dict, customer_history: Dict) -> Dict:
        """
        Generate suggested values for template variables
        """
        suggestions = {}
        
        for var in variables:
            if var == 'customer_name':
                suggestions[var] = customer_history.get('customer_name', 'Valued Customer')
            elif var == 'issue_id':
                suggestions[var] = str(issue_details.get('issue_id', ''))
            elif var == 'issue_title':
                suggestions[var] = issue_details.get('title', '')
            elif var == 'severity':
                suggestions[var] = issue_details.get('severity', 'Normal')
            elif var == 'response_time':
                severity = issue_details.get('severity', 'Normal')
                time_map = {'Critical': '1', 'High': '4', 'Normal': '24', 'Low': '48'}
                suggestions[var] = time_map.get(severity, '24')
            elif var == 'company':
                suggestions[var] = customer_history.get('company', '')
            elif var == 'support_agent':
                suggestions[var] = '[Your Name]'
            else:
                suggestions[var] = f'[{var.replace("_", " ").title()}]'
        
        return suggestions

    def _get_fallback_template(self, category: str, issue_details: Dict) -> Dict:
        """
        Get fallback template when AI generation fails
        """
        fallback_templates = {
            'initial_response': {
                'content': """Dear {{customer_name}},

Thank you for contacting our support team regarding "{{issue_title}}". We have received your request and assigned it ticket number #{{issue_id}}.

We understand the importance of resolving this {{severity}} priority issue promptly. Our team is currently investigating and we will provide you with an update within {{response_time}} hours.

If you have any additional information that might help us resolve this issue faster, please don't hesitate to share it.

Best regards,
{{support_agent}}
Support Team""",
                'variables': ['customer_name', 'issue_title', 'issue_id', 'severity', 'response_time', 'support_agent']
            },
            'status_update': {
                'content': """Hello {{customer_name}},

I wanted to provide you with an update on your support ticket #{{issue_id}}.

Current Status: {{current_status}}

We have made progress on your issue and our team is continuing to work on a resolution. We expect to have this resolved within {{estimated_time}} hours.

Thank you for your patience as we work to resolve this matter.

Best regards,
{{support_agent}}""",
                'variables': ['customer_name', 'issue_id', 'current_status', 'estimated_time', 'support_agent']
            }
        }
        
        template = fallback_templates.get(category, fallback_templates['initial_response'])
        suggestions = self._generate_variable_suggestions(
            template['variables'], issue_details, {}
        )
        
        return {
            'content': template['content'],
            'variables': template['variables'],
            'suggested_values': suggestions,
            'category': category,
            'tone': 'professional'
        }

    def _get_alternative_templates(self, category: str, severity: str) -> List[Dict]:
        """
        Get alternative template options
        """
        try:
            query = """
            SELECT template_id, template_name, template_content, effectiveness_score
            FROM message_templates
            WHERE category = %s AND (severity = %s OR severity IS NULL)
            AND is_active = TRUE
            ORDER BY effectiveness_score DESC, usage_count DESC
            LIMIT 3
            """
            
            templates = self.db_manager.execute_query(
                query, (category, severity), fetch_all=True
            )
            
            alternatives = []
            for template in templates or []:
                alternatives.append({
                    'template_id': template['template_id'],
                    'name': template['template_name'],
                    'content': template['template_content'],
                    'effectiveness_score': float(template['effectiveness_score'])
                })
            
            return alternatives
            
        except Exception as e:
            self.logger.error(f"Failed to get alternative templates: {str(e)}")
            return []

    def _calculate_template_confidence(self, template: Dict, issue_details: Dict, 
                                     message_intent: Dict) -> float:
        """
        Calculate confidence score for the generated template
        """
        try:
            confidence = 0.7  # Base confidence
            
            # Adjust based on issue severity match
            severity = issue_details.get('severity', 'Normal')
            if severity in ['Critical', 'High']:
                confidence += 0.1
            
            # Adjust based on message intent clarity
            intent_confidence = {
                'question': 0.9,
                'complaint': 0.8,
                'request': 0.85,
                'escalation': 0.75,
                'appreciation': 0.95
            }
            intent = message_intent.get('intent', 'question')
            confidence *= intent_confidence.get(intent, 0.8)
            
            # Adjust based on template completeness
            if len(template.get('variables', [])) > 0:
                confidence += 0.05
            
            return min(1.0, confidence)
            
        except Exception as e:
            self.logger.error(f"Confidence calculation failed: {str(e)}")
            return 0.7

    def _get_customization_suggestions(self, template: Dict, issue_details: Dict) -> List[str]:
        """
        Get suggestions for customizing the template
        """
        suggestions = []
        
        severity = issue_details.get('severity', 'Normal')
        category = issue_details.get('category', '')
        
        if severity == 'Critical':
            suggestions.append("Consider adding executive contact information for escalation")
            suggestions.append("Include specific timeline commitments")
        
        if severity == 'High':
            suggestions.append("Emphasize urgency and priority handling")
        
        if category == 'Technical':
            suggestions.append("Include technical details if available")
            suggestions.append("Mention specific troubleshooting steps taken")
        
        if category == 'Billing':
            suggestions.append("Reference specific billing periods or amounts")
            suggestions.append("Include account manager contact if applicable")
        
        suggestions.append("Personalize greeting based on customer relationship")
        suggestions.append("Add specific next steps with clear timelines")
        
        return suggestions

    def get_available_templates(self, category: str = None, severity: str = None) -> List[Dict]:
        """
        Get available message templates with optional filtering
        """
        try:
            query = """
            SELECT template_id, template_name, category, severity, template_content,
                   usage_count, effectiveness_score, created_at
            FROM message_templates
            WHERE is_active = TRUE
            """
            params = []
            
            if category:
                query += " AND category = %s"
                params.append(category)
            
            if severity:
                query += " AND (severity = %s OR severity IS NULL)"
                params.append(severity)
            
            query += " ORDER BY effectiveness_score DESC, usage_count DESC"
            
            templates = self.db_manager.execute_query(query, params, fetch_all=True)
            
            return [dict(template) for template in templates] if templates else []
            
        except Exception as e:
            self.logger.error(f"Failed to get available templates: {str(e)}")
            return []

    def save_template_usage(self, template_id: int, issue_id: int, 
                          effectiveness_rating: float = None):
        """
        Record template usage and effectiveness
        """
        try:
            # Update usage count
            update_query = """
            UPDATE message_templates 
            SET usage_count = usage_count + 1
            WHERE template_id = %s
            """
            self.db_manager.execute_query(update_query, (template_id,))
            
            # Update effectiveness if provided
            if effectiveness_rating is not None:
                effectiveness_query = """
                UPDATE message_templates 
                SET effectiveness_score = (effectiveness_score + %s) / 2
                WHERE template_id = %s
                """
                self.db_manager.execute_query(
                    effectiveness_query, (effectiveness_rating, template_id)
                )
            
            # Record in conversation
            conversation_query = """
            UPDATE conversations 
            SET is_template_used = TRUE, template_id = %s
            WHERE issue_id = %s AND message_type = 'Support'
            ORDER BY timestamp DESC LIMIT 1
            """
            self.db_manager.execute_query(conversation_query, (template_id, issue_id))
            
        except Exception as e:
            self.logger.error(f"Failed to save template usage: {str(e)}")

    def create_custom_template(self, name: str, category: str, content: str,
                             severity: str = None, variables: List[str] = None) -> int:
        """
        Create a new custom template
        """
        try:
            query = """
            INSERT INTO message_templates 
            (template_name, category, severity, template_content, variables)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            variables_json = json.dumps(variables) if variables else None
            
            template_id = self.db_manager.execute_query(
                query, (name, category, severity, content, variables_json),
                fetch_lastrowid=True
            )
            
            self.logger.info(f"Created custom template {template_id}")
            return template_id
            
        except Exception as e:
            self.logger.error(f"Failed to create custom template: {str(e)}")
            raise

    def render_template(self, template_content: str, variables: Dict) -> str:
        """
        Render template with provided variables
        """
        try:
            template = Template(template_content)
            return template.render(**variables)
            
        except Exception as e:
            self.logger.error(f"Template rendering failed: {str(e)}")
            return template_content  # Return original if rendering fails