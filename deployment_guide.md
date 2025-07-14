# Support Copilot Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Support Copilot system in different environments, from local development to production AWS deployment.

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Docker Development Environment](#docker-development-environment)
3. [Staging Environment](#staging-environment)
4. [Production AWS Deployment](#production-aws-deployment)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)

## Local Development Setup

### Prerequisites

- Python 3.11 or higher
- MySQL 8.0 or higher
- Redis 6.0 or higher
- Git
- OpenAI API key

### Step 1: Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd support-copilot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Database Setup

```bash
# Start MySQL service
sudo systemctl start mysql  # On Linux
brew services start mysql   # On macOS

# Create database and user
mysql -u root -p << EOF
CREATE DATABASE support_copilot;
CREATE USER 'support_user'@'localhost' IDENTIFIED BY 'support_password';
GRANT ALL PRIVILEGES ON support_copilot.* TO 'support_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# Initialize database schema
mysql -u support_user -p support_copilot < database_schema.sql
```

### Step 3: Redis Setup

```bash
# Start Redis service
sudo systemctl start redis  # On Linux
brew services start redis   # On macOS

# Test Redis connection
redis-cli ping
```

### Step 4: Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration (update with your values)
nano .env
```

Required environment variables:
```bash
OPENAI_API_KEY=your-openai-api-key
DB_PASSWORD=support_password
SECRET_KEY=your-unique-secret-key
```

### Step 5: Run Application

```bash
# Start the application
python app.py

# Test the application
curl http://localhost:5000/health
```

### Step 6: Verify Installation

```bash
# Run tests
pytest test_api.py -v

# Check logs
tail -f logs/support_copilot.log
```

## Docker Development Environment

### Prerequisites

- Docker 20.0 or higher
- Docker Compose 2.0 or higher

### Step 1: Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd support-copilot

# Copy environment file
cp .env.example .env

# Update .env with your OpenAI API key
echo "OPENAI_API_KEY=your-api-key" >> .env
```

### Step 2: Start Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Step 3: Initialize Database

```bash
# Wait for MySQL to be ready
docker-compose exec mysql mysqladmin ping -h localhost

# Database is automatically initialized via docker-entrypoint-initdb.d
# Verify by checking tables
docker-compose exec mysql mysql -u support_user -p support_copilot -e "SHOW TABLES;"
```

### Step 4: Test Application

```bash
# Health check
curl http://localhost:5000/health

# Test authentication
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@company.com", "password": "admin123"}'
```

### Step 5: Access Services

- **API**: http://localhost:5000
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **MySQL**: localhost:3306
- **Redis**: localhost:6379

## Staging Environment

### Prerequisites

- AWS CLI configured
- Terraform (optional)
- Docker
- Access to staging AWS account

### Step 1: Infrastructure Setup

```bash
# Create staging infrastructure
aws cloudformation create-stack \
  --stack-name support-copilot-staging \
  --template-body file://aws_deployment.yml \
  --parameters ParameterKey=Environment,ParameterValue=staging \
               ParameterKey=OpenAIAPIKey,ParameterValue=your-api-key \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### Step 2: Build and Push Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t support-copilot:staging .

# Tag and push
docker tag support-copilot:staging \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/staging-support-copilot:latest

docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/staging-support-copilot:latest
```

### Step 3: Deploy Application

```bash
# Update ECS service
aws ecs update-service \
  --cluster staging-support-copilot-cluster \
  --service staging-support-copilot-service \
  --force-new-deployment \
  --region us-east-1
```

### Step 4: Verify Deployment

```bash
# Get load balancer URL
aws cloudformation describe-stacks \
  --stack-name support-copilot-staging \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text

# Test health endpoint
curl <load-balancer-url>/health
```

## Production AWS Deployment

### Prerequisites

- Production AWS account access
- Domain name and SSL certificate
- Database backup strategy
- Monitoring setup

### Step 1: Pre-deployment Checklist

- [ ] Security review completed
- [ ] Performance testing passed
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] SSL certificates ready
- [ ] DNS configuration planned
- [ ] Rollback plan prepared

### Step 2: Infrastructure Deployment

```bash
# Create production infrastructure
aws cloudformation create-stack \
  --stack-name support-copilot-production \
  --template-body file://aws_deployment.yml \
  --parameters ParameterKey=Environment,ParameterValue=production \
               ParameterKey=OpenAIAPIKey,ParameterValue=your-production-api-key \
               ParameterKey=DBInstanceClass,ParameterValue=db.t3.medium \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### Step 3: Database Migration

```bash
# Create database backup
mysqldump -h staging-db-host -u admin -p support_copilot > backup.sql

# Restore to production (if migrating data)
mysql -h production-db-host -u admin -p support_copilot < backup.sql
```

### Step 4: Application Deployment

```bash
# Build production image
docker build -t support-copilot:production .

# Tag and push to production ECR
docker tag support-copilot:production \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/production-support-copilot:latest

docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/production-support-copilot:latest

# Deploy to production
aws ecs update-service \
  --cluster production-support-copilot-cluster \
  --service production-support-copilot-service \
  --force-new-deployment \
  --region us-east-1
```

### Step 5: DNS and SSL Configuration

```bash
# Create Route 53 record (if using Route 53)
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789 \
  --change-batch file://dns-change.json

# Configure SSL certificate in ALB
aws elbv2 modify-listener \
  --listener-arn <listener-arn> \
  --certificates CertificateArn=<certificate-arn>
```

### Step 6: Production Verification

```bash
# Health check
curl https://api.yourdomain.com/health

# Load test
ab -n 1000 -c 10 https://api.yourdomain.com/health

# Monitor logs
aws logs tail /ecs/production-support-copilot --follow
```

## Post-Deployment Configuration

### Step 1: Monitoring Setup

```bash
# Configure CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "HighResponseTime" \
  --alarm-description "API response time too high" \
  --metric-name ResponseTime \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 300 \
  --threshold 15000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Step 2: Backup Configuration

```bash
# Enable automated RDS backups
aws rds modify-db-instance \
  --db-instance-identifier production-support-copilot-db \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"
```

### Step 3: Security Configuration

```bash
# Enable VPC Flow Logs
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids <vpc-id> \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name VPCFlowLogs
```

### Step 4: Performance Optimization

```bash
# Configure auto-scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/production-support-copilot-cluster/production-support-copilot-service \
  --min-capacity 2 \
  --max-capacity 10
```

## Monitoring and Maintenance

### Daily Monitoring

```bash
# Check application health
curl https://api.yourdomain.com/health

# Monitor key metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name ResponseTime \
  --start-time 2023-01-01T00:00:00Z \
  --end-time 2023-01-01T23:59:59Z \
  --period 3600 \
  --statistics Average
```

### Weekly Maintenance

```bash
# Update dependencies
pip list --outdated

# Review logs for errors
aws logs filter-log-events \
  --log-group-name /ecs/production-support-copilot \
  --filter-pattern "ERROR"

# Database maintenance
mysql -h production-db-host -u admin -p -e "OPTIMIZE TABLE issues, customers, conversations;"
```

### Monthly Tasks

```bash
# Security updates
docker pull python:3.11-slim
docker build -t support-copilot:latest .

# Performance review
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --start-time $(date -d '30 days ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 \
  --statistics Average

# Cost optimization review
aws ce get-cost-and-usage \
  --time-period Start=2023-01-01,End=2023-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptoms**: Application fails to start, database connection timeouts

**Diagnosis**:
```bash
# Check database status
aws rds describe-db-instances \
  --db-instance-identifier production-support-copilot-db

# Test connectivity
telnet <db-endpoint> 3306

# Check security groups
aws ec2 describe-security-groups \
  --group-ids <db-security-group-id>
```

**Solutions**:
- Verify security group rules
- Check database credentials
- Ensure database is in running state
- Verify network connectivity

#### 2. High Response Times

**Symptoms**: API responses > 15 seconds, timeouts

**Diagnosis**:
```bash
# Check ECS service metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=production-support-copilot-service

# Check database performance
aws rds describe-db-log-files \
  --db-instance-identifier production-support-copilot-db
```

**Solutions**:
- Scale ECS service
- Optimize database queries
- Increase cache TTL
- Review AI API usage

#### 3. Memory Issues

**Symptoms**: Container restarts, out of memory errors

**Diagnosis**:
```bash
# Check container metrics
aws logs filter-log-events \
  --log-group-name /ecs/production-support-copilot \
  --filter-pattern "MemoryError"

# Review task definition
aws ecs describe-task-definition \
  --task-definition production-support-copilot-task
```

**Solutions**:
- Increase container memory allocation
- Optimize memory usage in code
- Implement memory monitoring
- Review caching strategy

#### 4. SSL Certificate Issues

**Symptoms**: HTTPS errors, certificate warnings

**Diagnosis**:
```bash
# Check certificate status
aws acm describe-certificate \
  --certificate-arn <certificate-arn>

# Test SSL configuration
openssl s_client -connect api.yourdomain.com:443
```

**Solutions**:
- Renew SSL certificate
- Update ALB listener configuration
- Verify domain validation
- Check DNS configuration

### Emergency Procedures

#### Rollback Deployment

```bash
# Get previous task definition
aws ecs list-task-definitions \
  --family-prefix production-support-copilot-task \
  --status ACTIVE \
  --sort DESC

# Rollback to previous version
aws ecs update-service \
  --cluster production-support-copilot-cluster \
  --service production-support-copilot-service \
  --task-definition production-support-copilot-task:N-1
```

#### Scale Down for Maintenance

```bash
# Scale to zero
aws ecs update-service \
  --cluster production-support-copilot-cluster \
  --service production-support-copilot-service \
  --desired-count 0

# Scale back up
aws ecs update-service \
  --cluster production-support-copilot-cluster \
  --service production-support-copilot-service \
  --desired-count 2
```

#### Database Recovery

```bash
# Create point-in-time recovery
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier production-support-copilot-db \
  --target-db-instance-identifier production-support-copilot-db-recovery \
  --restore-time 2023-01-01T12:00:00Z
```

## Security Considerations

### Production Security Checklist

- [ ] All secrets stored in AWS Secrets Manager
- [ ] Database encryption at rest enabled
- [ ] VPC with private subnets configured
- [ ] Security groups with minimal access
- [ ] WAF rules configured
- [ ] CloudTrail logging enabled
- [ ] Regular security updates applied
- [ ] Access logging configured
- [ ] Backup encryption enabled
- [ ] Network ACLs configured

### Security Monitoring

```bash
# Monitor failed login attempts
aws logs filter-log-events \
  --log-group-name /ecs/production-support-copilot \
  --filter-pattern "Invalid credentials"

# Check for suspicious activity
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRole \
  --start-time 2023-01-01T00:00:00Z \
  --end-time 2023-01-01T23:59:59Z
```

## Performance Optimization

### Database Optimization

```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_issues_customer_created ON issues(customer_id, created_at);
CREATE INDEX idx_conversations_issue_timestamp ON conversations(issue_id, timestamp);

-- Optimize queries
EXPLAIN SELECT * FROM issues WHERE customer_id = 1 ORDER BY created_at DESC LIMIT 10;
```

### Caching Strategy

```python
# Implement intelligent caching
@cache_manager.cache_with_ttl(300)  # 5 minutes
def get_customer_history(customer_id):
    # Expensive database operation
    pass

# Cache invalidation
cache_manager.invalidate_customer_cache(customer_id)
```

### Auto-scaling Configuration

```bash
# Configure target tracking scaling
aws application-autoscaling put-scaling-policy \
  --policy-name cpu-scaling-policy \
  --service-namespace ecs \
  --resource-id service/production-support-copilot-cluster/production-support-copilot-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

This deployment guide provides comprehensive instructions for deploying the Support Copilot system across different environments with proper monitoring, security, and maintenance procedures.