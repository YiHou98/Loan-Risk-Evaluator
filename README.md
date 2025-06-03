# Loan Risk Evaluator System

## Introduction
A serverless, event-driven AWS pipeline that ingests raw loan applications from S3, cleans and engineers features, computes risk scores via a dedicated service, and exposes scored results through a GraphQL interface. Each module is independently deployable, facilitating targeted testing and future evolution.

---

## Component Breakdown

### 1. Application Simulator
- **Purpose**  
  Periodically reads a CSV of loan applications from S3 and enqueues JSON messages into SQS.
- **Implementation**  
  - **AWS Lambda** (triggered by EventBridge every minute)  
  - **DynamoDB** table to persist byte-offset and line-index for S3 reads  
  - SQS standard queue for message delivery
- **Assumptions**  
  - CSV schema remains stable (column order & names).  
  - ~7,500 daily applications, distributed by hour/day-of-week.
- **Tradeoffs**  
  - **Lambda (S3 + Byte-Range Reads) vs. Database (Aurora/RDS)**: Lambda + S3 is chosen for minimal operational overhead and ultra-low idle cost. Occasional cold starts accepted given low-frequency (once-per-minute).  
  - **Byte-Range S3 Reads**: Reduces data transfer and speeds iteration but adds complexity in managing offsets.

---

### 2. Risk Evaluation Pipeline
- **Purpose**  
  Consumes SQS messages, orchestrates data cleaning, feature engineering, model scoring, and persists results to Aurora.
- **Implementation**  
  - **SQS → Dispatcher Lambda (SqsToStepDispatcher)**  
    - Batch size = 10; batch window = 60s to balance throughput vs. cost.  
    - writes an idempotency key to DynamoDB (TTL=1 hr), then invokes Step Functions per message.
    - Generates a unique application_id (UUID), 
  - **Step Functions** with three sequential Lambdas:  
    1. **CleanAndFeatureEngineer**  
       - Stores raw application JSON (121 fields) into S3,
       - Normalizes fields and engineers features, 
       - Retries up to 2× on data-validation errors before routing to DLQ.  
    2. **CallScoringService**  
       - Invokes the Scoring Component via API Gateway, returns `risk_score`.  
       - Retries up to 3× on transient errors with exponential backoff & jitter; failures → DLQ.  
    3. **PersistScoredApplication**  
       - Writes `application_id`, engineered features, and `risk_score` into Aurora PostgreSQL.  
       - Retries on DB errors up to 3×; persistent failures → DLQ via a final state.
  - **Dead Letter Queue (application-failure-dlq)**  
    - Captures detailed failures (stage, error details, original input).
- **Assumptions**  
  - Near-real-time processing requirement (a few seconds to minutes).  
  - Raw JSON offload to S3 avoids Lambda payload limits.
- **Tradeoffs**  
  - **Step Functions vs. Single Lambda**: Chosen for explicit retry/catch logic per stage and clearer error paths, at the cost of orchestration complexity.  
  - **DynamoDB for Idempotency**: Ensures “exactly-once” Step Functions invocation, though adds provisioned capacity and TTL maintenance.  
  - **Batch Size = 10**: Reduces invocation overhead but may introduce up-to-60 s latency when traffic is low.
  - **Aurora vs. DynamoDB**: Aurora chosen for rich SQL filtering, transactional integrity, and secondary indexes; higher operational cost compared to a fully serverless DB.

---

### 3. Scoring Component
- **Purpose**  
  Exposes a RESTful endpoint to accept cleaned features JSON and return a numerical risk score.
- **Implementation**  
  - **API Gateway** fronting **AWS Lambda**  
  - Mock scoring logic initially (random probability generator); production model can be loaded from S3 into the same handler.
- **Assumptions**  
  - Average of ~5 calls per minute; scoring logic executes in <100 ms.
- **Tradeoffs**  
  - **Lambda + API Gateway vs. ECS/Fargate Container**: Lambda chosen for pay-per-invocation cost-effectiveness. Cold-starts (<200 ms) are acceptable given low QPS.  

---

### 4. Scored Results Access
- **Purpose**  
  Provides downstream consumers with flexible filtering and pagination of scored loan records.
- **Implementation**  
  - **AWS AppSync (GraphQL API)** connected to a **Generic Lambda Resolver**  
  - Lambda executes SQL queries against **Aurora PostgreSQL** (indexes on risk_score, application_date, etc.)
- **Assumptions**  
  - Clients prefer a single endpoint that can filter by risk_score, state, date range, and paginate.  
  - Aurora cluster can handle up to thousands of read queries per day.
- **Tradeoffs**  
  - **AppSync + Lambda vs. Multiple REST Endpoints**: Offers flexible, field-specific queries and built-in subscriptions but adds GraphQL schema complexity and a slight resolver latency overhead.  

---

## Setup Instructions

### Prerequisites
- **AWS Account** with permissions for Lambda, IAM Roles, S3, SQS, DynamoDB, Step Functions, API Gateway, AppSync, and Aurora.  
- **Python 3.12** (for CDK and Lambda runtime).  
- **Node.js** (for any client or local GraphQL testing).

---

### Local Environment Setup
1. **Clone the repository**  
   git clone https://github.com/YiHou98/Loan-Risk-Evaluator.git
   cd Loan-Risk-Evaluator
2. **Client Setup**
    ```bash
    cd client
    npm install
    npm run dev 
4. **AWS Deployment via CDK**
    Note: CDK stacks for deployment are under development and will be added in a future release.
    ```bash
    Install CDK CLI:  npm install -g aws-cdk
    Install Python Dependencies: pip install -r requirements.txt
    Bootstrap Your AWS Environment: cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
    Deploy All Stacks:  cdk deploy --all
