# JurisLab – Product Requirements Document (PRD)

## 1. Overview

**Product name:** JurisLab  
**Tagline:** Multi‑Agent Legal Simulation & Document Intelligence Platform  
**Vision:** A professional platform that turns real fact patterns and legal documents into structured, interactive multi‑agent simulations and high‑quality document reviews, generating reusable case studies and teachable insights for legal professionals, educators, students, and aid organizations.  
**Positioning:** Enterprise‑grade tool for legal education, training, scenario exploration, and document analysis—not a substitute for licensed legal advice.

---

## 2. Goals and Non‑Goals

### 2.1 Goals

- Enable users to:
  - Upload and scan legal documents (contracts, notices, policies, statutes, case law excerpts).
  - Run multi‑agent simulations where AI agents role‑play legal participants (plaintiff, defendant, judge, informer, etc.).
  - Obtain structured document reviews (clause extraction, risk/obligation highlighting, plain‑language explanations).
  - Interact with agents in real time (human‑in‑the‑loop).
  - Generate structured case studies, argument maps, and learning notes.
- Provide:
  - Geo‑specific legal reasoning grounded in ingested legal documents and rules.
  - AI‑augmented analytics on simulations, document reviews, and knowledge usage.
  - A professional, secure, multi‑role web application with modular access by role.

### 2.2 Non‑Goals

- Providing binding legal advice or representing users in real proceedings.
- Guaranteeing jurisdiction‑specific legal correctness without human review.
- Replacing licensed attorneys, judges, or legal aid services.
- Providing fallback or degraded modes for LLM failures; the system assumes LLM availability as configured.

---

## 3. Modules

JurisLab is organized into three core modules, each with its own feature set and role‑based access controls.

### 3.1 JurisLab Sim (Simulation Module)

- Multi‑agent courtroom / dispute simulation.
- Scenario management, agent orchestration, human‑in‑the‑loop controls.
- Case study generation and learning outputs.

### 3.2 JurisLab Review (Document Intelligence Module)

- Document ingestion, scanning, and chunking.
- Clause and entity extraction (parties, dates, obligations, penalties, termination, dispute resolution, etc.).
- Risk/obligation highlighting and plain‑language explanations.
- Q&A grounded in uploaded documents.

### 3.3 JurisLab Hub (Knowledge & Analytics Module)

- Knowledge base of ingested legal documents (statutes, regulations, case law, templates).
- Semantic + keyword search, filters by jurisdiction/domain/type.
- AI‑augmented insights:
  - Usage analytics.
  - Trend analysis across simulations and reviews.
  - Teaching packs and curated collections.

---

## 4. Target Users and Roles

### 4.1 User Roles (Platform‑Level)

- **Platform Admin**
  - Manages global settings, integrations, observability, and platform‑wide policies.
- **Organization Admin**
  - Manages users, roles, and module access within an organization (law firm, law school, legal aid org).
- **Billing / Ops Admin** (optional)
  - Manages subscriptions, quotas, and usage reports.

### 4.2 Module‑Level Roles

Access to specific modules is granted per user via module‑level roles.

#### 4.2.1 JurisLab Sim Roles

- **Sim Educator / Trainer**
  - Creates and curates scenarios.
  - Reviews and publishes case studies.
  - Manages simulation templates for teaching.
- **Sim Professional**
  - Runs simulations for training/internal knowledge.
  - Exports case studies for internal use.
- **Sim Student / Trainee**
  - Observes or participates in simulations assigned by educators.
  - Accesses published case studies and learning materials.
- **Sim Researcher**
  - Analyzes aggregated, anonymized simulation data.

#### 4.2.2 JurisLab Review Roles

- **Review Lead (Senior Lawyer / Paralegal Lead)**
  - Configures review templates and risk schemas.
  - Approves final review outputs for client‑facing use (with disclaimers).
- **Review Analyst (Lawyer / Paralegal)**
  - Uploads documents, runs reviews, annotates outputs.
  - Uses clause extraction and risk highlights to support client work.
- **Review Viewer (Client / Internal Stakeholder)**
  - Views finalized review reports and summaries (read‑only).

#### 4.2.3 JurisLab Hub Roles

- **Knowledge Curator**
  - Ingests and organizes legal documents.
  - Defines jurisdiction/domain metadata and tags.
  - Curates collections and teaching packs.
- **Knowledge Consumer**
  - Searches and reads documents and AI‑augmented views.
  - Accesses linked simulations and reviews.
- **Knowledge Analyst**
  - Uses analytics dashboards and AI insights on knowledge usage.

A single user can hold multiple module‑level roles (e.g., Sim Educator + Review Analyst + Knowledge Curator).

---

## 5. Core Capabilities by Module

### 5.1 JurisLab Sim

- **Scenario Management**
  - Create/edit/version scenarios with:
    - Jurisdiction, domain, fact pattern, parties, timeline.
    - Associated legal documents (from JurisLab Hub or direct upload).
  - Configure simulation parameters:
    - Active agent roles (Plaintiff, Defendant, Judge, Informer, Witness).
    - Phases (opening, arguments, judge questions, settlement, outcome).
    - Turn limits, focus areas (e.g., contract interpretation, procedural issues).

- **Multi‑Agent Simulation Engine**
  - Agents implemented with **LangChain / LangGraph**.
  - Tool calling for:
    - Retrieval from knowledge base.
    - Citation of specific rules/clauses.
    - Logging and telemetry.
  - Communication via:
    - **A2A protocol** (structured message passing).
    - **MCP v2.x** for tool permissions, IAM, and audit.
  - Human‑in‑the‑loop:
    - Pause/resume simulation.
    - Inject additional facts/documents.
    - Ask agents to clarify/rephrase.
    - Steer focus (e.g., "focus on termination clause").

- **Case Study and Learning Outputs**
  - Automatic generation at simulation end:
    - Summary, facts, issues, arguments (by side), outcome, reasoning.
    - Legal principles highlighted (general, jurisdiction‑aware).
    - "What a real lawyer would do next" checklist.
    - Reflection questions.
  - Export:
    - In‑app Markdown viewer.
    - Download as `.md` and `.pdf`.

### 5.2 JurisLab Review

- **Document Ingestion and Scanning**
  - Upload formats: PDF, DOCX, TXT, MD.
  - OCR for scanned PDFs (via Document AI or equivalent).
  - Chunking and indexing for retrieval.

- **Clause and Entity Extraction**
  - Detect and label:
    - Parties, effective dates, termination clauses, renewal terms.
    - Payment terms, penalties, indemnities, liability caps.
    - Dispute resolution (arbitration, jurisdiction, venue).
    - Confidentiality, IP ownership, non‑compete, non‑solicit.
  - Map clauses to risk categories and obligations.

- **Risk and Obligation Highlighting**
  - Color‑coded risk levels (high/medium/low).
  - Obligation load summary (number and severity of duties).
  - Balance score (one‑sidedness between parties).

- **Plain‑Language Explanations and Q&A**
  - "In simple terms" explanations for complex clauses.
  - Q&A grounded in the uploaded document:
    - "What happens if I terminate early?"
    - "What are my notice obligations?"
  - Clear disclaimers: informational only, not legal advice.

- **Review Reports**
  - Structured report including:
    - Executive summary.
    - Key clauses and risks.
    - Obligations checklist.
    - Suggested questions for a lawyer.
  - Export as Markdown and PDF.

### 5.3 JurisLab Hub

- **Knowledge Base**
  - Ingest and index:
    - Statutes, regulations, procedural rules.
    - Case law summaries and headnotes.
    - Standard forms and templates.
  - Metadata:
    - Jurisdiction, domain, document type, effective dates, version.

- **Search and Browse**
  - Hybrid search (semantic + keyword).
  - Filters by jurisdiction, domain, type, date.
  - Document detail view:
    - Full text.
    - Metadata.
    - Linked scenarios, simulations, and reviews.

- **AI‑Augmented Insights**
  - Summaries of document clusters.
  - Trend analysis:
    - Common issues, frequent clauses, typical outcomes (based on simulations/reviews).
  - Teaching packs:
    - Auto‑assembled from related simulations, reviews, and documents.

- **Analytics Dashboards**
  - Usage metrics:
    - Simulations run (by scenario, role, jurisdiction).
    - Reviews performed (by document type, domain).
    - Top searched topics and documents.
  - Agent telemetry:
    - Turn counts, tool calls, retrieval hits.
  - AI‑augmented insights:
    - Suggested new scenarios or missing legal content.
    - Quality signals (citation coverage, grounding scores).

---

## 6. Functional Requirements

### 6.1 Authentication and Authorization

- **P1**
  - Support **Keycloak** or **form‑based auth**.
  - Role‑based access control at:
    - Platform level (Platform Admin, Organization Admin).
    - Module level (Sim, Review, Hub roles).
  - Secure session management and password policies.
- **P2**
  - SSO integration (Google, Microsoft) for enterprise deployments.
  - Fine‑grained permissions for scenario, document, and report access.

### 6.2 User Interface

- **P1**
  - Web app built with **React + Vite**.
  - **Left‑side navigation menu** with top‑level items:
    - Dashboard
    - Sim (JurisLab Sim)
    - Review (JurisLab Review)
    - Hub (JurisLab Hub)
    - Analytics
    - Settings (role‑based visibility)
  - **User profile** displayed at **left bottom** of the menu.
  - Support **dark and light themes** with toggle.
  - Markdown viewer for generated case studies, review reports, and notes.
- **P2**
  - Responsive design for tablets.
  - Customizable dashboard widgets.

### 6.3 Scenario and Document Management

- **P1**
  - Create/edit scenarios (Sim module) with:
    - Title, description, jurisdiction, domain.
    - Fact pattern editor (rich text + structured fields).
    - Document upload and linkage to Hub/Review.
  - Versioning for scenarios and documents.
  - Tagging by legal topics and keywords.
- **P2**
  - Template library for common scenario types.
  - Bulk import/export of scenarios and documents.

### 6.4 Simulation Execution

- **P1**
  - Start simulation from a scenario (Sim module).
  - Select active agent roles (minimum: Plaintiff, Defendant, Judge; optional: Informer, Witness).
  - Real‑time chat‑like interface showing:
    - Agent messages with role labels.
    - Citations to legal documents and clauses.
    - Controls: pause, resume, inject fact, request clarification.
  - Enforce turn‑taking and procedural rules via Orchestrator Agent.
- **P2**
  - Multiple concurrent simulations per user (subject to quota).
  - Save/load simulation state for later continuation.

### 6.5 Document Review Execution

- **P1**
  - Upload documents (Review module).
  - Run automated review:
    - Clause extraction.
    - Risk/obligation highlighting.
    - Plain‑language summaries.
  - Interactive view:
    - Highlighted text with side panel explanations.
    - Q&A grounded in the document.
  - Generate review report with:
    - Executive summary.
    - Key risks and obligations.
    - Suggested questions for a lawyer.
- **P2**
  - Customizable review templates by document type.
  - Collaborative annotations on review reports (for teams).

### 6.6 Case Study and Report Generation

- **P1**
  - Automatic generation at simulation end (Sim) and review completion (Review).
  - Markdown format with structured sections.
  - In‑app Markdown viewer with:
    - Syntax highlighting.
    - Copy and download options.
- **P2**
  - Customizable templates for case study and report structure.
  - Collaborative annotations on case studies and reports (for educators/teams).

### 6.7 Knowledge Hub

- **P1**
  - Browse and search legal documents.
  - Filters: jurisdiction, domain, document type, date.
  - Document detail view with:
    - Full text.
    - Metadata.
    - Linked scenarios, simulations, and reviews.
- **P2**
  - Curated collections (e.g., "Tenant Rights – Maharashtra").
  - User‑contributed annotations (moderated).

### 6.8 Analytics and Insights

- **P1**
  - Basic usage dashboards:
    - Simulations run, by scenario and role.
    - Reviews performed, by document type.
    - Top searched legal topics.
    - Most exported case studies and reports.
  - Agent telemetry:
    - Number of turns, tool calls, retrieval queries.
- **P2**
  - AI‑augmented insights:
    - Suggested new scenarios based on usage patterns.
    - Gap analysis in knowledge base coverage.
    - Quality metrics for simulations and reviews (grounding, citation density).

---

## 7. Technical Requirements

### 7.1 Architecture Overview

- **Frontend**
  - React + Vite.
  - State management: Redux Toolkit or Zustand.
  - UI components: Material UI or Ant Design.
  - Theme support: dark/light via CSS variables or theme provider.
- **Backend**
  - Python (FastAPI or similar) for API and agent orchestration.
  - LangChain / LangGraph for agent definitions and workflows.
  - MCP v2.x integration for tool governance and IAM.
  - A2A protocol for agent‑to‑agent messaging (structured JSON over HTTP/gRPC).
- **Data Stores**
  - Relational DB: **PostgreSQL** (preferred) or **SQLite** for local/dev.
  - Vector store: **Google Vertex AI Vector Search** or **Qdrant**.
  - Object storage: **Google Cloud Storage** (or local filesystem in dev) for documents.
- **LLM Access**
  - **GCP Model Garden** (Vertex AI models) as primary.
  - **Ollama** for local/open‑source models (dev, offline, cost‑sensitive).
  - Configurable model selection per scenario, review, or environment.
  - **No fallback mechanism for LLMs**: if configured LLM endpoints are unavailable, the affected operations (simulation, review, insights) must fail explicitly with clear error messages; no silent degradation or substitution.
- **Deployment**
  - Agents and backend deployable on:
    - **GCP Agent Studio** (or equivalent managed agent runtime).
    - **Kubernetes** (GKE or self‑managed).
  - Containerized services (Docker).
  - CI/CD pipelines for automated build and deploy.

### 7.2 Security and Compliance

- **P1**
  - TLS for all external communications.
  - Encrypted storage for sensitive data (at rest).
  - Role‑based access control enforced on all APIs and UI routes.
  - Audit logs for:
    - Logins.
    - Scenario, document, and review changes.
    - Simulation runs and exports.
- **P2**
  - Data residency controls (geo‑specific storage).
  - PII detection and redaction in uploaded documents.

### 7.3 Observability and Telemetry

- **P1**
  - Structured logging (JSON) with correlation IDs per simulation/review.
  - Metrics:
    - Request latency, error rates.
    - Agent turn counts, tool call counts.
    - Vector search latency and hit rates.
  - Tracing for agent workflows (LangChain callbacks + OpenTelemetry).
- **P2**
  - Centralized observability stack (e.g., Cloud Monitoring, Prometheus + Grafana).
  - Alerting on error spikes and performance degradation.

### 7.4 Code Quality and Engineering Standards

- **P1**
  - Strict code quality requirements:
    - Type hints and static typing (e.g., mypy/pyright for Python; TypeScript for frontend).
    - Linting and formatting enforced in CI (e.g., ruff/black for Python, ESLint/Prettier for frontend).
    - Minimum test coverage thresholds (e.g., ≥80% for core modules).
  - Security practices:
    - No secrets in code; use secret manager / environment variables.
    - Regular dependency vulnerability scanning.
    - Input validation and output encoding to prevent injection attacks.
  - UI guidelines:
    - Consistent component library and design tokens.
    - Accessibility baseline (WCAG 2.1 AA considerations for color contrast, keyboard navigation).
    - Clear error states and messages for users.
- **P2**
  - Formal code review process with security checklist.
  - Performance budgets for key UI paths (e.g., time‑to‑interactive, simulation message latency).

---

## 8. Agent Specifications

All agents must:

- Be defined as LangChain / LangGraph nodes.
- Use tool calling for retrieval and logging.
- Communicate via A2A messages with:
  - `from_agent`, `to_agent`, `message_type`, `payload`, `citation_refs`.
- Respect MCP v2.x policies for tool access.
- Log all actions to telemetry.

### 8.1 Orchestrator Agent (Sim Module)

**Responsibilities:**

- Initialize simulation from scenario.
- Manage turn order and phase transitions.
- Enforce procedural rules and time/turn limits.
- Trigger case study generation at end.

**Tools:**

- Scenario loader.
- Simulation state manager.
- Case study generator.

**Acceptance Criteria:**

- Given a valid scenario, the Orchestrator can:
  - Start a simulation and sequence at least Plaintiff, Defendant, and Judge agents.
  - Enforce turn‑taking without deadlocks.
  - Transition through phases (opening → arguments → judge questions → outcome).
  - Trigger case study generation upon completion.

### 8.2 Plaintiff Agent (Sim Module)

**Responsibilities:**

- Represent the plaintiff's position based on facts and documents.
- Make claims, cite legal provisions, and respond to counter‑arguments.

**Tools:**

- Knowledge base retriever (jurisdiction‑aware).
- Citation formatter.
- Fact validator (checks claims against provided facts).

**Acceptance Criteria:**

- Given a scenario and knowledge base:
  - Produces opening statement with at least one cited legal provision.
  - Responds to defendant arguments with relevant citations.
  - Does not invent facts outside the provided scenario.

### 8.3 Defendant Agent (Sim Module)

**Responsibilities:**

- Represent the defendant's position.
- Counter plaintiff claims, raise defenses, cite applicable rules.

**Tools:**

- Same as Plaintiff Agent.

**Acceptance Criteria:**

- Mirrors Plaintiff Agent criteria from the defense perspective.
- Clearly distinguishes between contested and admitted facts.

### 8.4 Judge / Arbitrator Agent (Sim Module)

**Responsibilities:**

- Maintain procedural order.
- Ask clarifying questions.
- Summarize key issues.
- Provide outcome and reasoning (non‑binding, educational).

**Tools:**

- Knowledge base retriever.
- Issue extractor.
- Outcome template generator.

**Acceptance Criteria:**

- Asks at least one clarifying question during simulation.
- Produces an outcome section with:
  - Summary of key issues.
  - Reasoning referencing legal principles.
  - Clear disclaimer that output is educational, not legal advice.

### 8.5 Informer / Legal Aid Agent (Sim & Review Modules)

**Responsibilities:**

- Explain legal terms, procedures, and rights in plain language.
- Provide "what this means for you" style explanations.

**Tools:**

- Terminology explainer.
- Plain‑language rewriter.
- Resource linker (to legal aid orgs, official guides).

**Acceptance Criteria:**

- Can take a complex clause or rule and produce a clear, plain‑language explanation.
- Provides at least one actionable suggestion or question for a real lawyer.

### 8.6 Review Analyst Agent (Review Module)

**Responsibilities:**

- Analyze uploaded documents.
- Extract clauses, entities, and obligations.
- Assign risk levels and generate summaries.

**Tools:**

- Document parser and chunker.
- Clause/entity extractor.
- Risk scorer.
- Summary generator.

**Acceptance Criteria:**

- Given a legal document:
  - Identifies key clauses (termination, payment, dispute resolution, etc.).
  - Produces a structured review report with risk highlights.
  - Grounds all statements in the document text with citations.

### 8.7 Witness / Expert Agent (Optional, Sim Module)

**Responsibilities:**

- Provide domain‑specific context (e.g., technical, medical, financial) as configured.
- Answer agent questions within defined expertise.

**Acceptance Criteria:**

- Responds only within configured expertise domain.
- Cites provided expert documents when answering.

---

## 9. Data Model (High‑Level)

### 9.1 Core Entities

- `User`
  - id, email, role, profile, auth_provider_id
- `Organization`
  - id, name, settings, subscription_tier
- `UserRole`
  - id, user_id, organization_id, platform_role, module_roles (JSON)
- `Scenario`
  - id, title, description, jurisdiction, domain, created_by, versions
- `ScenarioVersion`
  - id, scenario_id, fact_pattern, parameters, created_at
- `LegalDocument`
  - id, title, type, jurisdiction, domain, text, metadata, vector_id
- `Simulation`
  - id, scenario_version_id, status, started_by, started_at, ended_at
- `SimulationTurn`
  - id, simulation_id, turn_number, agent_role, message, citations, metadata
- `CaseStudy`
  - id, simulation_id, markdown_content, generated_at
- `DocumentReview`
  - id, document_id, reviewer_id, markdown_report, generated_at
- `AnalyticsEvent`
  - id, event_type, user_id, module, simulation_id, review_id, timestamp, payload

---

## 10. Dos and Don'ts

### 10.1 Dos

- Clearly label all outputs as **educational and informational**, not legal advice.
- Ground agent statements and review findings in:
  - Provided facts.
  - Ingested legal documents and rules.
- Log all agent actions and citations for auditability.
- Allow human users to:
  - Pause, inspect, and modify simulation inputs.
  - Annotate and export case studies and review reports.
- Design for extensibility:
  - New agent roles.
  - Additional jurisdictions and domains.
  - New modules over time.

### 10.2 Don'ts

- Do not claim that the system provides binding legal advice or representation.
- Do not allow agents to invent statutes, case law, or facts not in the knowledge base or scenario.
- Do not expose raw internal prompts or chain‑of‑thought to end users.
- Do not store sensitive personal data longer than necessary; implement retention policies.
- Do not implement silent fallbacks for LLM failures; fail explicitly with clear messages.

---

## 11. Deployment Instructions

### 11.1 Prerequisites

- GCP project with:
  - Vertex AI enabled.
  - Cloud Storage bucket.
  - (Optional) Vertex AI Vector Search or Qdrant cluster.
- Kubernetes cluster (GKE or other) or access to GCP Agent Studio.
- Docker and kubectl installed locally.
- Node.js 20+ and Python 3.11+ for local development.

### 11.2 Backend Deployment

1. **Containerize backend**
   - Build Docker image for the FastAPI + LangGraph service.
2. **Configure environment**
   - Set env vars for:
     - DB connection (PostgreSQL).
     - Vector store (Vertex AI or Qdrant).
     - LLM endpoints (GCP Model Garden, Ollama).
     - Auth (Keycloak URL, realm, client).
     - MCP and A2A endpoints.
3. **Deploy to Kubernetes / Agent Studio**
   - Apply Kubernetes manifests or Agent Studio configuration.
   - Ensure services for:
     - API.
     - Agent runtime.
     - Telemetry (logging, metrics).

### 11.3 Frontend Deployment

1. **Build React app**
   - `npm install`
   - `npm run build` (Vite).
2. **Serve via**:
   - Static hosting (Cloud Storage + CDN) or
   - Containerized NGINX service on Kubernetes.
3. **Configure**
   - API base URL.
   - Auth provider settings.
   - Theme defaults.

### 11.4 Database and Vector Store Setup

- Run migrations for PostgreSQL schema (users, organizations, roles, scenarios, simulations, reviews, etc.).
- Initialize vector index:
  - Create index in Vertex AI Vector Search or Qdrant.
  - Configure dimension, metric, and metadata fields.
- Ingest initial legal documents:
  - Use a batch ingestion script to:
    - Parse documents.
    - Chunk text.
    - Generate embeddings.
    - Store in vector DB with metadata.

### 11.5 Auth Setup

- **Keycloak**
  - Create realm and clients for web app and backend.
  - Define roles matching platform and module roles.
  - Configure OIDC in frontend and resource server in backend.
- **Form‑based auth**
  - Implement secure password hashing (e.g., bcrypt).
  - Session or JWT‑based authentication with refresh tokens.
  - Enforce role checks on all API endpoints and UI routes.

---

## 12. Acceptance Criteria (System‑Level)

The application is considered acceptable for initial production use when:

- **Authentication and Authorization**
  - Users can log in with assigned roles.
  - Module access is correctly restricted by module‑level roles.
- **JurisLab Sim**
  - Users can create, edit, and version scenarios.
  - A simulation can be started from a scenario.
  - At least Plaintiff, Defendant, and Judge agents participate.
  - Human user can pause, inject facts, and resume.
  - All agent messages include citations where applicable.
  - At simulation end, a case study in Markdown is generated and viewable/downloadable.
- **JurisLab Review**
  - Users can upload legal documents.
  - Automated review produces:
    - Clause extraction.
    - Risk/obligation highlights.
    - Plain‑language summaries.
  - A structured review report in Markdown is generated and viewable/downloadable.
- **JurisLab Hub**
  - Users can search and filter legal documents.
  - Document detail views show text, metadata, and linked simulations/reviews.
- **Analytics**
  - Dashboards show basic usage metrics for Sim, Review, and Hub.
  - Agent telemetry (turns, tool calls) is visible.
- **Security and Logging**
  - All API endpoints enforce authentication and authorization.
  - Audit logs capture key actions.
  - No critical security vulnerabilities in a standard scan.
- **Code Quality and UI**
  - Linting, formatting, and type checks pass in CI.
  - Minimum test coverage thresholds met.
  - UI follows defined component library and accessibility baseline.
  - Dark/light theme toggle works across all modules.

---

## 13. Future Enhancements (Post‑P1)

- Multi‑jurisdiction comparative simulations and reviews.
- Advanced AI‑augmented insights (trend detection, gap analysis).
- Collaborative features for educators and legal teams (shared libraries, annotations).
- Integration with external legal research and CLM APIs.
- Mobile‑optimized views for field use by legal aid workers.

---

## 14. Glossary

- **A2A Protocol:** Structured agent‑to‑agent communication format (messages, metadata, citations).
- **MCP v2.x:** Model/Tool Control Plane for governing tool access, permissions, and audit.
- **Orchestrator Agent:** Central agent managing simulation flow and rules.
- **Knowledge Hub:** Central repository of ingested legal documents and AI‑augmented views.
- **Case Study:** Structured, Markdown‑based output summarizing a simulation and its learnings.
- **Review Report:** Structured, Markdown‑based output summarizing document analysis, risks, and obligations.

---

## 15. Quality, Safety, Evaluation, and Delivery Standards

### 15.1 Product Quality Gates

The platform must meet the following quality gates before a release is considered ready:

- Functional workflows must be validated end to end:
  - Ingest legal document → index with metadata → retrieve grounded passages → review → generate Markdown report.
  - Create scenario → attach jurisdictional sources → run multi-agent simulation → generate case study.
- All generated legal content must include an educational/informational disclaimer and source citations when source material is available.
- The UI must provide clear loading, empty, validation, permission-denied, and LLM-unavailable states.
- Any unavailable configured LLM endpoint must cause an explicit, observable failure for the affected operation. The system must not silently use a different model, fabricate output, or degrade to an uncited generic response.

### 15.2 Agent Evaluation Strategy

Agent evaluation is a first-class engineering requirement, not a post-release activity.

- **Primary OSS evaluation framework:** **DeepEval** must be used for Python/pytest-native regression tests, including LLM-as-a-judge and deterministic assertions.
- **Tracing and production evaluation:** **Arize Phoenix** with OpenInference/OpenTelemetry instrumentation must be self-hosted or deployed in the approved observability environment to inspect traces, retrievals, tool calls, and agent trajectories.
- **Security and prompt/tool regression:** **promptfoo** must be used for prompt-injection, jailbreak, PII, policy, and output-regression test suites.
- Evaluation datasets must contain only approved, licensed, public, synthetic, or properly anonymized legal materials. No simulated data shall be presented as a real legal authority or real case record.

#### 15.2.1 Required Evaluation Suites

- **Retrieval evaluation**
  - Context precision, context recall, citation correctness, source attribution, and jurisdiction metadata filtering.
  - Negative tests: irrelevant jurisdiction, outdated document version, missing authority, conflicting source excerpts.
- **Document review evaluation**
  - Clause extraction precision/recall against reviewed fixtures.
  - Correct identification of parties, dates, obligations, termination, liability, indemnity, dispute resolution, confidentiality, and IP clauses where present.
  - Groundedness: every highlighted risk must cite the relevant document span.
  - Abstention: where a clause cannot be found or interpreted from source material, the output must say so.
- **Simulation evaluation**
  - Agent role adherence: Plaintiff, Defendant, Judge, Informer, and Witness stay within their assigned mandate.
  - Fact fidelity: no agent introduces unsupported facts.
  - Procedural integrity: Orchestrator maintains valid phase and turn transitions; Judge does not act as counsel.
  - Trajectory quality: tool selection, retrieval use, citations, and termination are evaluated across the complete LangGraph trace.
  - Human-intervention behavior: injected facts are acknowledged, attributed, and reflected only after validation.
- **Safety and policy evaluation**
  - Prompt-injection resistance in uploaded documents and user messages.
  - PII detection/redaction behavior.
  - Unauthorized tool-call attempts.
  - Disallowed claims of legal representation, guaranteed outcomes, or binding legal advice.
  - Cross-tenant and cross-role data-access attempts.
- **Reliability and performance evaluation**
  - API error handling, explicit LLM endpoint failure behavior, vector retrieval latency, document processing limits, and concurrent simulation load.

#### 15.2.2 Release Thresholds

- 100% pass rate for deterministic security, authorization, policy, and agent-state-machine tests.
- 100% pass rate for required citation-presence tests when an answer makes a legal assertion derived from the knowledge base.
- No critical or high-severity unresolved findings from dependency, secret, static-analysis, or dynamic security scans.
- Document-review and retrieval quality thresholds must be versioned per supported document type and jurisdiction, reviewed by a qualified legal-domain reviewer before release.
- Evaluation results, model identifiers, prompt versions, knowledge-base version, and policy version must be stored with each release artifact.

### 15.3 Guardrail Architecture

Guardrails must be enforced at input, retrieval, tool, agent, output, and audit layers.

- **Input guardrails**
  - Validate file type, size, malware scan status, and document extraction success.
  - Detect prompt-injection content embedded in uploaded documents and isolate it from executable system instructions.
  - Detect and classify PII/sensitive data; apply configured redaction, access restrictions, or consent requirements.
  - Validate jurisdiction, legal domain, user role, and scenario ownership before processing.
- **Retrieval guardrails**
  - Filter by organization/tenant, document permissions, jurisdiction, domain, effective date, and source status.
  - Prefer official legal rules, authoritative sources, and curated legal documents.
  - Label unverified, secondary, expired, or jurisdictionally mismatched sources clearly; do not present them as controlling authority.
- **Agent guardrails**
  - Agent prompts must require source grounding, role adherence, uncertainty disclosure, and educational-not-advice language.
  - Agents must not reveal system prompts, credentials, hidden tool output, chain-of-thought, or data outside the user's authorization scope.
  - Agents must not invent facts, statutes, cases, citations, court outcomes, or legal professionals.
  - Agents must ask a clarifying question or abstain when material facts, jurisdiction, authority, or document content are insufficient.
- **Output guardrails**
  - Validate output schemas with Pydantic/JSON Schema.
  - Run citation validation: cited source IDs must exist, be authorized, and match the claimed jurisdiction/document.
  - Apply PII leakage detection and prohibited-content detection before display/export.
  - Display disclaimers in simulation views, review reports, case studies, and exported Markdown/PDF artifacts.
- **Human oversight guardrails**
  - Mark outputs as draft unless a permitted Review Lead or Sim Educator publishes/approves them.
  - Require human review for any externally shareable report configuration.
  - Preserve immutable audit records of source material, agent actions, policy decisions, and user interventions.

### 15.4 OPA Policy Enforcement

**Open Policy Agent (OPA)** is the policy decision point for authorization and agent governance. Policies must be written in Rego, versioned with code, tested in CI, and evaluated at runtime.

OPA must enforce at minimum:

- **RBAC and module authorization**
  - Platform roles and module-level permissions for Sim, Review, and Hub.
  - Organization/tenant isolation for every API, document, embedding, simulation, report, and analytics request.
- **Document and knowledge access**
  - Users and agents may retrieve only documents authorized for their organization, module role, jurisdiction, and classification.
- **MCP tool authorization**
  - Every MCP v2.x tool call must be authorized by OPA before execution.
  - Policies must constrain agent role, allowed tool, action, document scope, data classification, rate limit, and purpose.
  - Default-deny behavior: an unrecognized agent, tool, resource, or policy decision is denied.
- **A2A message authorization**
  - A2A messages must be schema-validated and authorized according to sender role, recipient role, simulation membership, and phase.
  - Agents may not send messages or evidence outside the active scenario/simulation scope.
- **Export and publication control**
  - Case studies and review reports may be exported or published only by users with the corresponding role and only after required disclaimer/citation checks pass.
- **Policy decision logging**
  - Every allow/deny decision must emit an audit event with correlation ID, actor, resource, policy version, decision, and reason code.

### 15.5 Security Requirements

- Apply OWASP ASVS-aligned controls appropriate to the deployment tier.
- Use Keycloak OIDC/OAuth2 or secure form-based authentication with strong password hashing, short-lived access tokens, refresh-token rotation, CSRF protections where applicable, and secure cookie settings.
- Use least-privilege service accounts and workload identity for GCP/Kubernetes workloads.
- Keep credentials in Secret Manager/Kubernetes Secrets; never commit secrets, production documents, model outputs containing sensitive information, or `.env` files to source control.
- Encrypt data in transit and at rest; use signed URLs with expiry for document access.
- Validate, sanitize, and virus-scan uploads; do not execute uploaded content.
- Rate-limit authentication, upload, simulation, review, and export endpoints.
- Maintain dependency lockfiles, generate an SBOM, run SCA/SAST/secret scanning in CI, and address critical/high findings before release.
- Use content-security policy, secure headers, server-side authorization checks, and audit logging.

### 15.6 Accessibility and UI Quality Requirements

- Meet WCAG 2.1 AA as the baseline:
  - Keyboard-accessible navigation, dialogs, document highlights, simulation controls, and Markdown viewer.
  - Visible focus states, semantic landmarks, accessible labels, and screen-reader compatible status updates.
  - Minimum color contrast requirements in both light and dark themes; risk levels cannot rely on color alone.
- The left navigation must remain understandable and usable at standard desktop widths and responsive tablet widths.
- User profile controls must remain at the lower left navigation area, with accessible account/logout controls.
- The interface must distinguish source text, generated analysis, citations, agent messages, user injections, warnings, and errors.
- Markdown rendering must be sanitized to prevent XSS and must support accessible tables, headings, links, and code blocks.

### 15.7 Codebase and Repository Standards

- Use a monorepo or clearly separated frontend/backend structure with a single default branch for the development lifecycle.
- Keep the repository source-focused and lightweight:
  - Do not commit build outputs, model weights, node modules, virtual environments, generated telemetry, large PDFs, datasets, or secrets.
  - Store documents and large artifacts in object storage; include only small, approved test fixtures where necessary.
  - Enforce repository size limits through CI checks.
- Include the following developer artifacts:
  - `README.md` describing product scope, supported workflows, setup, architecture, assumptions, and limitations.
  - `.env.example` with no real secrets.
  - Architecture diagram/source (e.g., Mermaid Markdown).
  - API contract (OpenAPI generated from FastAPI).
  - Threat model and security notes.
  - Evaluation guide and reproducible eval commands.
  - Contribution, code-style, and testing instructions.
- CI must run on every pull request/merge and include:
  - Formatting, linting, type checking, unit/integration tests, coverage reporting.
  - OPA/Rego policy tests.
  - DeepEval and promptfoo evaluation suites.
  - Dependency, secret, and static security scans.
  - Frontend accessibility checks and production build validation.

### 15.8 Delivery Acceptance Criteria

The release is acceptable only when:

- A developer can follow the README to configure the selected LLM provider (GCP Model Garden or Ollama), database, vector store, authentication provider, and storage without relying on undocumented steps.
- The default development setup runs with SQLite and Qdrant or a documented local equivalent; production configuration supports PostgreSQL, Google Cloud Storage, and Vertex AI Vector Search or Qdrant.
- The product demonstrates both primary workflows using approved legal documents tied to an explicit scenario and jurisdiction:
  - JurisLab Review: ingest → analyze → cited review report.
  - JurisLab Sim: scenario → authorized A2A/MCP agent interaction → cited case study.
- Policy-denied requests are blocked and logged; unauthorized MCP calls never reach the tool implementation.
- Eval, security, and accessibility checks are reproducible locally and in CI.
- The application provides clear disclosure of scope, uncertainty, and its non-advice status at relevant decision points.
