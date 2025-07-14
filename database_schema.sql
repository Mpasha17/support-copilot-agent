-- Support Copilot Database Schema
-- MySQL Database Design

-- Create database
CREATE DATABASE IF NOT EXISTS support_copilot;
USE support_copilot;

-- Customers table
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    company VARCHAR(255),
    phone VARCHAR(20),
    tier ENUM('Basic', 'Premium', 'Enterprise') DEFAULT 'Basic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_company (company)
);

-- Issues table
CREATE TABLE issues (
    issue_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    category ENUM('Technical', 'Billing', 'General', 'Feature Request', 'Bug Report') NOT NULL,
    severity ENUM('Low', 'Normal', 'High', 'Critical') DEFAULT 'Normal',
    status ENUM('Open', 'In Progress', 'Resolved', 'Closed', 'Escalated') DEFAULT 'Open',
    priority INT DEFAULT 3, -- 1=Highest, 5=Lowest
    assigned_to INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    resolution_time_hours DECIMAL(10,2),
    product_area VARCHAR(255),
    tags JSON,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_status (status),
    INDEX idx_severity (severity),
    INDEX idx_created_at (created_at),
    INDEX idx_assigned_to (assigned_to),
    INDEX idx_product_area (product_area)
);

-- Conversations table
CREATE TABLE conversations (
    conversation_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    message_type ENUM('Customer', 'Support', 'System') NOT NULL,
    message_content TEXT NOT NULL,
    sender_id INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_template_used BOOLEAN DEFAULT FALSE,
    template_id INT,
    sentiment_score DECIMAL(3,2), -- -1 to 1
    confidence_score DECIMAL(3,2), -- 0 to 1
    FOREIGN KEY (issue_id) REFERENCES issues(issue_id) ON DELETE CASCADE,
    INDEX idx_issue_id (issue_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_message_type (message_type)
);

-- Message templates table
CREATE TABLE message_templates (
    template_id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    severity ENUM('Low', 'Normal', 'High', 'Critical'),
    template_content TEXT NOT NULL,
    variables JSON, -- Placeholder variables
    usage_count INT DEFAULT 0,
    effectiveness_score DECIMAL(3,2) DEFAULT 0.5,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_category (category),
    INDEX idx_severity (severity),
    INDEX idx_effectiveness (effectiveness_score)
);

-- Issue resolutions table
CREATE TABLE issue_resolutions (
    resolution_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    resolution_summary TEXT NOT NULL,
    resolution_steps JSON,
    resolved_by INT,
    resolution_category VARCHAR(100),
    customer_satisfaction INT, -- 1-5 rating
    resolution_effectiveness DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES issues(issue_id),
    INDEX idx_issue_id (issue_id),
    INDEX idx_resolution_category (resolution_category),
    INDEX idx_customer_satisfaction (customer_satisfaction)
);

-- Similar issues mapping table
CREATE TABLE similar_issues (
    mapping_id INT PRIMARY KEY AUTO_INCREMENT,
    source_issue_id INT NOT NULL,
    similar_issue_id INT NOT NULL,
    similarity_score DECIMAL(3,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_issue_id) REFERENCES issues(issue_id),
    FOREIGN KEY (similar_issue_id) REFERENCES issues(issue_id),
    INDEX idx_source_issue (source_issue_id),
    INDEX idx_similarity_score (similarity_score)
);

-- Issue summaries table
CREATE TABLE issue_summaries (
    summary_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    summary_text TEXT NOT NULL,
    key_points JSON,
    action_items JSON,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by ENUM('AI', 'Human') DEFAULT 'AI',
    FOREIGN KEY (issue_id) REFERENCES issues(issue_id),
    INDEX idx_issue_id (issue_id)
);

-- Support executives table
CREATE TABLE support_executives (
    executive_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    specialization VARCHAR(255),
    current_workload INT DEFAULT 0,
    max_capacity INT DEFAULT 10,
    performance_rating DECIMAL(3,2) DEFAULT 3.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_email (email),
    INDEX idx_specialization (specialization)
);

-- Critical alerts table
CREATE TABLE critical_alerts (
    alert_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_id INT NOT NULL,
    alert_type ENUM('Unattended', 'Escalation', 'SLA_Breach', 'Customer_Escalation') NOT NULL,
    alert_message TEXT NOT NULL,
    severity ENUM('Medium', 'High', 'Critical') DEFAULT 'High',
    status ENUM('Active', 'Acknowledged', 'Resolved') DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP NULL,
    acknowledged_by INT,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (issue_id) REFERENCES issues(issue_id),
    INDEX idx_issue_id (issue_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- API usage tracking table
CREATE TABLE api_usage (
    usage_id INT PRIMARY KEY AUTO_INCREMENT,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    response_time_ms INT NOT NULL,
    status_code INT NOT NULL,
    user_id INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_size INT,
    response_size INT,
    INDEX idx_endpoint (endpoint),
    INDEX idx_timestamp (timestamp),
    INDEX idx_response_time (response_time_ms)
);

-- Insert sample data for testing

-- Sample customers
INSERT INTO customers (customer_name, email, company, tier) VALUES
('John Doe', 'john.doe@techcorp.com', 'TechCorp Inc', 'Enterprise'),
('Jane Smith', 'jane.smith@startup.io', 'Startup Solutions', 'Premium'),
('Bob Johnson', 'bob.johnson@smallbiz.com', 'Small Business LLC', 'Basic'),
('Alice Brown', 'alice.brown@enterprise.com', 'Enterprise Systems', 'Enterprise'),
('Charlie Wilson', 'charlie.wilson@midsize.com', 'MidSize Company', 'Premium');

-- Sample support executives
INSERT INTO support_executives (name, email, specialization) VALUES
('Sarah Connor', 'sarah.connor@company.com', 'Technical Issues'),
('Mike Ross', 'mike.ross@company.com', 'Billing Support'),
('Rachel Green', 'rachel.green@company.com', 'General Support'),
('Ross Geller', 'ross.geller@company.com', 'Technical Issues'),
('Monica Bing', 'monica.bing@company.com', 'Enterprise Support');

-- Sample message templates
INSERT INTO message_templates (template_name, category, severity, template_content, variables) VALUES
('Initial Response - Technical', 'Technical', 'Normal', 
'Hello {{customer_name}}, thank you for contacting our support team. I understand you are experiencing {{issue_type}}. I will investigate this issue and get back to you within {{response_time}} hours.', 
'{"customer_name": "string", "issue_type": "string", "response_time": "number"}'),

('Escalation Notice', 'General', 'High', 
'Dear {{customer_name}}, your issue #{{issue_id}} has been escalated to our senior technical team. We are treating this with high priority and will provide an update within {{update_time}} hours.', 
'{"customer_name": "string", "issue_id": "string", "update_time": "number"}'),

('Resolution Confirmation', 'General', 'Normal', 
'Hi {{customer_name}}, I am pleased to inform you that your issue #{{issue_id}} has been resolved. {{resolution_summary}} Please let us know if you need any further assistance.', 
'{"customer_name": "string", "issue_id": "string", "resolution_summary": "string"}');

-- Sample issues
INSERT INTO issues (customer_id, title, description, category, severity, status, product_area) VALUES
(1, 'Login Authentication Failure', 'Users cannot log in to the system after the recent update', 'Technical', 'High', 'Open', 'Authentication'),
(2, 'Billing Discrepancy', 'Invoice shows incorrect charges for premium features', 'Billing', 'Normal', 'In Progress', 'Billing'),
(3, 'Feature Request - Dark Mode', 'Request to add dark mode theme to the application', 'Feature Request', 'Low', 'Open', 'UI/UX'),
(1, 'API Rate Limiting Issues', 'API calls are being throttled unexpectedly', 'Technical', 'Critical', 'Escalated', 'API'),
(4, 'Data Export Functionality', 'Cannot export data in CSV format', 'Technical', 'Normal', 'Open', 'Data Management');

-- Create indexes for performance optimization
CREATE INDEX idx_issues_customer_created ON issues(customer_id, created_at);
CREATE INDEX idx_conversations_issue_timestamp ON conversations(issue_id, timestamp);
CREATE INDEX idx_critical_alerts_status_created ON critical_alerts(status, created_at);

-- Create views for common queries
CREATE VIEW active_issues AS
SELECT 
    i.issue_id,
    i.title,
    i.severity,
    i.status,
    c.customer_name,
    c.company,
    i.created_at,
    TIMESTAMPDIFF(HOUR, i.created_at, NOW()) as hours_open
FROM issues i
JOIN customers c ON i.customer_id = c.customer_id
WHERE i.status IN ('Open', 'In Progress', 'Escalated');

CREATE VIEW customer_issue_history AS
SELECT 
    c.customer_id,
    c.customer_name,
    c.company,
    COUNT(i.issue_id) as total_issues,
    COUNT(CASE WHEN i.status = 'Resolved' THEN 1 END) as resolved_issues,
    AVG(i.resolution_time_hours) as avg_resolution_time,
    MAX(i.created_at) as last_issue_date
FROM customers c
LEFT JOIN issues i ON c.customer_id = i.customer_id
GROUP BY c.customer_id, c.customer_name, c.company;