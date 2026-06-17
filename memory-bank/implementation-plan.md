# 企业话术智能检索与统一培训管理系统 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. This plan intentionally contains no implementation code.

**Goal:** Build the MVP described by `memory-bank/design-document.md` using the stack and constraints in `memory-bank/tech-stack.md`.

**Architecture:** Use one Vue 3 SPA for employee and admin pages, one FastAPI monolith for REST APIs and RAG orchestration, MySQL as the authoritative data source, Milvus as the vector index, and DashScope as the model provider. Keep permissions, content versions, index status, and RAG source consistency inside the backend service layer.

**Tech Stack:** Vue 3, TypeScript, Vite, Vue Router, Pinia, Axios, Element Plus, Python 3.13.x, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PyMySQL, MySQL 8.4 LTS, Milvus Standalone, PyMilvus, DashScope, pytest, Vitest, Playwright.

---

## Plan Rules

- Do not write implementation code in this plan.
- Every implementation step below includes a validation test.
- Use automated tests whenever practical.
- Use fake DashScope and fake Milvus clients for unit and API tests.
- Do not call real DashScope in normal automated tests.
- Do not put secrets in repository files.
- Do not introduce LangChain, LangGraph, Celery, Redis, Kubernetes, microservices, or object storage in MVP.
- Before writing any code, read `memory-bank/architecture.md` and `memory-bank/design-document.md` completely.
- After each major milestone, update `memory-bank/architecture.md` if architecture, data flow, or implementation boundary changes.

## Expected Repository Shape

- `backend/`: FastAPI application, tests, migrations, service layer, integrations.
- `frontend/`: Vue 3 application, tests, routes, stores, pages, API clients.
- `infra/`: local Milvus, MySQL, and later Nginx deployment assets.
- `memory-bank/`: architecture and product context.
- `memory-bank/implementation-plan.md`: this implementation plan.

## Phase 0: Preparation And Guardrails

### Task 1: Confirm Context And Protect Existing Work

- [ ] Step 1: Read `AGENTS.md`, `memory-bank/architecture.md`, `memory-bank/design-document.md`, and `memory-bank/tech-stack.md` from start to finish.
  - Validation test: Write a brief implementation note listing the five non-negotiable constraints: MySQL authority, Milvus index-only role, backend permission enforcement, no model free-answer on miss, and no complex middleware in MVP.

- [ ] Step 2: Inspect the current Git worktree and identify tracked changes, untracked files, and files unrelated to the implementation.
  - Validation test: Confirm the implementation note lists which files are safe to modify and which existing untracked files must not be touched unless they are part of the current task.

- [ ] Step 3: Create a milestone checklist for backend, frontend, RAG, E2E, and deployment documentation.
  - Validation test: Confirm every milestone maps to at least one MVP acceptance criterion from `memory-bank/design-document.md`.

### Task 2: Establish Test Strategy Before Scaffolding

- [ ] Step 1: Define backend test categories: unit tests for services, API tests for routes, migration checks, and integration-style tests using fake external clients.
  - Validation test: Confirm the test strategy explicitly covers login, permission filtering, content publishing, versioning, index failure, AI miss handling, and source consistency.

- [ ] Step 2: Define frontend test categories: route guard tests, store tests, API error handling tests, page state tests, and Playwright smoke tests.
  - Validation test: Confirm the test strategy explicitly covers employee login, admin login, restricted admin route access, general-user visibility, full-user visibility, and AI miss UI.

- [ ] Step 3: Define external-service test boundaries for DashScope and Milvus.
  - Validation test: Confirm the plan states that automated tests use fake clients and that a separate manual smoke check is required before real model calls are considered verified.

## Phase 1: Project Scaffold

### Task 3: Create Backend Skeleton

- [ ] Step 1: Create the backend project directory, package metadata, application package, and empty test structure.
  - Validation test: Run backend test discovery and confirm the test runner starts successfully without importing application modules from the wrong path.

- [ ] Step 2: Add a backend health-check behavior at `GET /health`.
  - Validation test: Add an API test requiring the health endpoint to return an OK status and a stable service identifier; run it before implementation to confirm failure, then after implementation to confirm pass.

- [ ] Step 3: Add backend configuration loading for environment variables without requiring real secrets during tests.
  - Validation test: Add a configuration test requiring test defaults to load without real database, Milvus, DashScope, or JWT secrets.

- [ ] Step 4: Add centralized backend error response behavior.
  - Validation test: Add an API test requiring unknown routes and controlled application errors to return consistent JSON error shapes without leaking stack traces.

### Task 4: Create Frontend Skeleton

- [ ] Step 1: Create the Vue 3, TypeScript, and Vite frontend project structure.
  - Validation test: Run the frontend unit test runner and confirm it can discover a minimal placeholder test without requiring a browser.

- [ ] Step 2: Add the frontend application shell with route areas for login, employee app, and admin app.
  - Validation test: Add a route test requiring `/login`, `/app`, and `/admin` to resolve to distinct route records.

- [ ] Step 3: Add global API client setup with base URL configuration.
  - Validation test: Add a unit test requiring the API client to use the configured API base URL and to expose a consistent error path for failed requests.

- [ ] Step 4: Add baseline frontend styling and layout constraints for mobile H5 and PC admin pages.
  - Validation test: Add a component rendering test requiring the application shell to render without horizontal overflow at a mobile viewport width and a desktop viewport width.

### Task 5: Create Local Development Infrastructure

- [ ] Step 1: Create local infrastructure documentation for MySQL and Milvus startup.
  - Validation test: Confirm a new developer can identify the required MySQL host, database name, Milvus host, Milvus port, and where to place local secrets without reading source code.

- [ ] Step 2: Create `.env.example` with all required backend and frontend environment variable names and safe placeholder values.
  - Validation test: Add a repository check that confirms `.env.example` contains no real API key, password, token, or private host.

- [ ] Step 3: Add local startup documentation for backend and frontend.
  - Validation test: Confirm the documentation lists separate startup checks for backend health, frontend route load, MySQL connectivity, and Milvus connectivity.

## Phase 2: Backend Data Model And Migrations

### Task 6: Establish Database Connection And Migration Flow

- [ ] Step 1: Configure SQLAlchemy database session management for MySQL.
  - Validation test: Add a backend test requiring the application to create and close a database session without leaking connections when using a test database URL.

- [ ] Step 2: Configure Alembic migration discovery.
  - Validation test: Add a migration check requiring a fresh test database to apply all migrations from empty state without manual SQL.

- [ ] Step 3: Add a migration rollback verification approach for local development.
  - Validation test: Confirm a migration test can upgrade to the latest migration and downgrade one revision without leaving orphaned migration metadata.

### Task 7: Implement User And Permission Tables

- [ ] Step 1: Define the user table with username, password hash, display name, account type, content level, active flag, and timestamps.
  - Validation test: Add a migration test requiring the user table to contain all required fields and enforce unique usernames.

- [ ] Step 2: Define allowed account types and content levels at the domain layer.
  - Validation test: Add a domain test requiring invalid account types and invalid content levels to be rejected before database write.

- [ ] Step 3: Add seed guidance for one initial admin account without storing a real password in the repository.
  - Validation test: Confirm the seed documentation requires password input through environment or an operator command, not a committed file.

### Task 8: Implement Content, Version, Chunk, And Vector Index Tables

- [ ] Step 1: Define the content table for type, title, category, permission level, status, current version, creator, and timestamps.
  - Validation test: Add a migration test requiring content type, permission level, and status to be constrained to allowed values.

- [ ] Step 2: Define the content version table for version number, title snapshot, summary, body, structured payload, publish time, effective time, expiry time, creator, and creation time.
  - Validation test: Add a database test requiring multiple versions to belong to one content item and requiring version numbers to remain unique per content item.

- [ ] Step 3: Define the content chunk table for chunk type, text, order, token estimate, content hash, permission level, active flag, and timestamps.
  - Validation test: Add a database test requiring chunks to reference both a content item and a content version.

- [ ] Step 4: Define the vector index record table for Milvus collection, Milvus primary key, embedding model, embedding dimension, content hash, indexed time, and active flag.
  - Validation test: Add a database test requiring each active vector index record to reference an existing chunk.

### Task 9: Implement Quiz, Missed Question, And Optional Conversation Tables

- [ ] Step 1: Define the quiz question table with question, options, answer, explanation, related content, permission level, status, and timestamps.
  - Validation test: Add a database test requiring quiz questions to be filterable by permission level and status.

- [ ] Step 2: Confirm no quiz answer record table is created.
  - Validation test: Add a migration inspection test requiring no table exists for persisted quiz attempts, quiz scores, personal ranking, or answer history.

- [ ] Step 3: Define the missed question table with question text, user, account type, content level, asked time, status, and handled time.
  - Validation test: Add a database test requiring a missed question to preserve the user permission snapshot at ask time.

- [ ] Step 4: Decide whether conversation persistence is included in MVP implementation.
  - Validation test: Confirm the decision is recorded in `memory-bank/architecture.md` and that tests match the chosen scope: either no conversation tables or conversation tables with source records.

## Phase 3: Authentication And Authorization

### Task 10: Implement Password Security And Login

- [ ] Step 1: Add password hashing and password verification behavior.
  - Validation test: Add a security test requiring stored password values to differ from raw passwords and requiring the raw password to verify successfully.

- [ ] Step 2: Add login API behavior for username and password.
  - Validation test: Add an API test requiring valid credentials to return user identity, account type, content level, and access token.

- [ ] Step 3: Add failed-login behavior.
  - Validation test: Add an API test requiring wrong password, disabled account, and unknown username to fail without revealing which field was wrong.

- [ ] Step 4: Add token expiration behavior.
  - Validation test: Add a token test requiring expired tokens to be rejected and valid tokens to resolve the expected user.

### Task 11: Implement Backend Permission Dependencies

- [ ] Step 1: Add a current-user dependency for protected APIs.
  - Validation test: Add an API test requiring unauthenticated calls to protected endpoints to fail with an authentication error.

- [ ] Step 2: Add an admin-only dependency.
  - Validation test: Add an API test requiring `full_user` and `general_user` accounts to be rejected from admin routes while `admin` succeeds.

- [ ] Step 3: Add content-level filtering helpers.
  - Validation test: Add a service test requiring `general_user` filters to return only general content and `full_user` filters to return general plus full content.

- [ ] Step 4: Add a no-leak permission error rule.
  - Validation test: Add an API test requiring unauthorized content access to return an error without content title, body, source, or update time.

## Phase 4: Backend Content Management

### Task 12: Implement Admin Content Draft Creation

- [ ] Step 1: Add admin API behavior for creating content drafts.
  - Validation test: Add an API test requiring an admin to create draft content with type, title, category, permission level, and body fields.

- [ ] Step 2: Reject non-admin draft creation.
  - Validation test: Add an API test requiring `full_user` and `general_user` draft creation attempts to fail.

- [ ] Step 3: Validate content type-specific required fields.
  - Validation test: Add API tests requiring standard script items to include scenario fields and latest must-read entries to include update details.

- [ ] Step 4: Ensure drafts are hidden from employee APIs.
  - Validation test: Add API tests requiring draft content to be absent from employee lists and details.

### Task 13: Implement Draft Editing And Listing

- [ ] Step 1: Add admin API behavior for listing content with filters by type, status, permission level, and category.
  - Validation test: Add an API test requiring each filter to narrow results correctly and requiring pagination metadata.

- [ ] Step 2: Add admin API behavior for editing draft content.
  - Validation test: Add an API test requiring draft edits to update fields without creating a published version.

- [ ] Step 3: Prevent unsafe edits to historical versions.
  - Validation test: Add a service test requiring historical version snapshots to remain unchanged after current content edits.

- [ ] Step 4: Add admin content detail behavior.
  - Validation test: Add an API test requiring content detail to include current status, current version reference, index status, and editable fields.

### Task 14: Implement Publish And Versioning

- [ ] Step 1: Add publish behavior that creates a new content version.
  - Validation test: Add a service test requiring the first publish to create version number one and mark the content as published.

- [ ] Step 2: Add republish behavior for existing published content.
  - Validation test: Add a service test requiring republish to create the next version number and keep older versions available only as history.

- [ ] Step 3: Set publish time as the initial effective time.
  - Validation test: Add a service test requiring published time and effective time to be populated consistently for MVP.

- [ ] Step 4: Ensure historical versions do not appear in current employee content APIs.
  - Validation test: Add an API test requiring only the latest current version to appear in employee list and detail responses.

### Task 15: Implement Offline And History Behavior

- [ ] Step 1: Add admin API behavior for taking content offline.
  - Validation test: Add an API test requiring offline content to disappear from employee APIs.

- [ ] Step 2: Ensure offline content is excluded from AI candidate retrieval.
  - Validation test: Add a service test requiring offline content chunks to be excluded before Milvus search or filtered from candidate results.

- [ ] Step 3: Add admin history listing.
  - Validation test: Add an API test requiring admins to view historical versions for a content item.

- [ ] Step 4: Reject non-admin history access.
  - Validation test: Add an API test requiring `full_user` and `general_user` accounts to be denied historical version access.

## Phase 5: Backend Employee Content APIs

### Task 16: Implement Latest Must-Read APIs

- [ ] Step 1: Add employee API behavior for must-read list sorted by publish time descending.
  - Validation test: Add an API test requiring published must-read entries to appear newest first.

- [ ] Step 2: Apply permission filtering to must-read list.
  - Validation test: Add API tests requiring general users to see only general entries and full users to see general plus full entries.

- [ ] Step 3: Add must-read detail behavior.
  - Validation test: Add an API test requiring detail to include title, update body, adjustment points, publish time, effective time, and permission level.

- [ ] Step 4: Prevent invisible must-read detail leaks.
  - Validation test: Add an API test requiring a general user requesting a full must-read detail to receive a no-leak permission error.

### Task 17: Implement Standard Script APIs

- [ ] Step 1: Add employee API behavior for core base scripts.
  - Validation test: Add an API test requiring core base scripts to return summary points, update time, permission level, and detail link data.

- [ ] Step 2: Add employee API behavior for standardized script items.
  - Validation test: Add an API test requiring standardized items to include scenario, recommended wording summary, update time, and permission level.

- [ ] Step 3: Add scenario category filtering.
  - Validation test: Add an API test requiring category filters to return only matching visible script items.

- [ ] Step 4: Add script detail behavior.
  - Validation test: Add an API test requiring detail to include scenario, recommended wording, forbidden wording, notes, update time, and copyable text.

### Task 18: Implement Quiz APIs

- [ ] Step 1: Add admin quiz question management behavior.
  - Validation test: Add API tests requiring admins to create, edit, enable, disable, and list quiz questions.

- [ ] Step 2: Add employee quiz question retrieval.
  - Validation test: Add an API test requiring each quiz session to return between five and ten visible enabled questions when enough questions exist.

- [ ] Step 3: Apply permission filtering to quiz questions.
  - Validation test: Add API tests requiring general users to receive only general questions and full users to receive general plus full questions.

- [ ] Step 4: Add quiz submit behavior without persistence.
  - Validation test: Add an API test requiring submission to return correctness, correct answers, explanations, and related content links while creating no answer record and no score record.

## Phase 6: RAG, Indexing, And AI Safety

### Task 19: Implement Chunk Generation

- [ ] Step 1: Define chunk generation rules for core base scripts.
  - Validation test: Add a service test requiring core base script chunks to preserve parent content ID, version ID, permission level, and active state.

- [ ] Step 2: Define chunk generation rules for standardized script items.
  - Validation test: Add a service test requiring each scenario item to become a business-boundary chunk rather than an arbitrary fixed-length chunk.

- [ ] Step 3: Define chunk generation rules for latest must-read entries.
  - Validation test: Add a service test requiring each must-read entry to produce a chunk tied to its current version.

- [ ] Step 4: Add duplicate-content hash behavior.
  - Validation test: Add a service test requiring unchanged chunk text to produce stable content hash values and changed text to produce different values.

### Task 20: Implement DashScope Integration Boundary

- [ ] Step 1: Add a DashScope client abstraction for chat generation.
  - Validation test: Add a unit test using a fake model response requiring the abstraction to return normalized answer text and usage metadata without exposing provider-specific response shape.

- [ ] Step 2: Add a DashScope embedding abstraction.
  - Validation test: Add a unit test using a fake embedding response requiring the abstraction to return a numeric vector and embedding model name.

- [ ] Step 3: Add model configuration loading.
  - Validation test: Add a configuration test requiring missing API key to fail only in real-provider mode and not in fake-client test mode.

- [ ] Step 4: Add provider error normalization.
  - Validation test: Add a unit test requiring timeout, authentication failure, and malformed provider response to map to controlled internal errors.

### Task 21: Implement Milvus Integration Boundary

- [ ] Step 1: Add a Milvus client abstraction for collection setup.
  - Validation test: Add a unit test using a fake Milvus client requiring collection setup to be called with vector dimension, primary key, and metadata fields.

- [ ] Step 2: Add vector upsert behavior.
  - Validation test: Add a unit test requiring vector upsert to include content ID, version ID, chunk ID, permission level, status, effective time, and expired time metadata.

- [ ] Step 3: Add vector search behavior with metadata filters.
  - Validation test: Add a unit test requiring general-user search filters to exclude full-level vectors before results are returned.

- [ ] Step 4: Add vector deactivation behavior.
  - Validation test: Add a unit test requiring offline or historical version vectors to be marked inactive or removed from effective search scope.

### Task 22: Implement Index Synchronization

- [ ] Step 1: Connect publish behavior to chunk generation and embedding generation.
  - Validation test: Add a service test requiring publish to produce active chunks and call the embedding client for each active chunk.

- [ ] Step 2: Connect embedding output to Milvus upsert and vector index records.
  - Validation test: Add a service test requiring successful indexing to create active vector index records with Milvus primary keys.

- [ ] Step 3: Handle embedding failure after content publish.
  - Validation test: Add a service test requiring content to remain published, index status to become failed, and employee detail APIs to continue returning content.

- [ ] Step 4: Add admin retry index behavior.
  - Validation test: Add an API test requiring retry to change failed index status to synced when fake embedding and fake Milvus clients succeed.

### Task 23: Implement RAG Search And Answer Flow

- [ ] Step 1: Add question embedding flow.
  - Validation test: Add a service test requiring a user question to call the embedding abstraction exactly once and include the user permission level in subsequent search input.

- [ ] Step 2: Add Milvus candidate retrieval with permission and status filters.
  - Validation test: Add a service test requiring general users never receive full-level candidates even when fake Milvus returns mixed results.

- [ ] Step 3: Add similarity threshold miss behavior.
  - Validation test: Add a service test requiring low-score candidates to return the fixed miss message and create a missed question record.

- [ ] Step 4: Add MySQL source backfill for valid candidates.
  - Validation test: Add a service test requiring candidate content to be reloaded from MySQL and requiring missing, offline, historical, or unauthorized sources to be excluded.

- [ ] Step 5: Add answer generation with strict context.
  - Validation test: Add a service test requiring the fake chat client to receive only authorized source text and requiring the returned source list to match the included context.

- [ ] Step 6: Add RAG API endpoint.
  - Validation test: Add API tests for successful answer, no-hit answer, unauthorized token, general-user full-content attempt, and provider-unavailable error.

### Task 24: Implement Missed Question Management

- [ ] Step 1: Add backend behavior to record missed questions.
  - Validation test: Add a service test requiring missed question records to include question text, user ID, account type, content level, asked time, and new status.

- [ ] Step 2: Add admin missed question list API.
  - Validation test: Add an API test requiring admins to list missed questions with text, asked time, user, permission snapshot, and status.

- [ ] Step 3: Add admin mark-handled behavior.
  - Validation test: Add an API test requiring status to change from new to handled and requiring handled time to be set.

- [ ] Step 4: Reject non-admin missed question management.
  - Validation test: Add API tests requiring `full_user` and `general_user` to be denied missed question list and update endpoints.

## Phase 7: Frontend Auth, Routing, And Shared UI

### Task 25: Implement Frontend Auth Store And Route Guards

- [ ] Step 1: Add auth store behavior for token, user identity, account type, content level, and logout.
  - Validation test: Add store tests requiring login state to persist for the session and logout to clear token and user data.

- [ ] Step 2: Add route guard for protected employee routes.
  - Validation test: Add route tests requiring unauthenticated users visiting `/app` routes to redirect to login.

- [ ] Step 3: Add route guard for admin routes.
  - Validation test: Add route tests requiring non-admin users visiting `/admin` routes to be blocked and requiring admin users to enter.

- [ ] Step 4: Add global API unauthorized handling.
  - Validation test: Add API client tests requiring authentication errors to clear local auth state and redirect to login.

### Task 26: Implement Login Page

- [ ] Step 1: Build login form behavior with username and password fields.
  - Validation test: Add component tests requiring empty username or empty password to prevent submission and show validation feedback.

- [ ] Step 2: Connect login page to backend login API.
  - Validation test: Add component tests with mocked API requiring successful login to store user identity and route to the correct default page.

- [ ] Step 3: Add login failure display.
  - Validation test: Add component tests requiring invalid credentials and disabled account responses to show a generic login failure message.

- [ ] Step 4: Verify mobile login layout.
  - Validation test: Add visual or DOM layout test requiring login controls to fit within a mobile viewport without overlapping.

### Task 27: Implement Shared Layouts

- [ ] Step 1: Build employee app layout with AI search entry and three core navigation entries.
  - Validation test: Add component tests requiring latest must-read, standard script, and quiz entries to render for authenticated employee users.

- [ ] Step 2: Build admin layout with content, quiz, users, and missed question navigation.
  - Validation test: Add component tests requiring admin navigation entries to render only for admin users.

- [ ] Step 3: Add global empty, loading, and error states.
  - Validation test: Add component tests requiring standard empty, loading, permission error, service error, and AI unavailable states to render correct text.

- [ ] Step 4: Add copy-to-clipboard feedback behavior.
  - Validation test: Add component tests requiring successful copy actions to show confirmation and failed copy actions to show a recoverable error.

## Phase 8: Frontend Employee Pages

### Task 28: Implement Employee Home Page

- [ ] Step 1: Add home page AI question input.
  - Validation test: Add component tests requiring blank questions to be rejected and nonblank questions to trigger the RAG request path.

- [ ] Step 2: Add home page core entry cards.
  - Validation test: Add component tests requiring exactly three primary entries: latest must-read, standard script, and quiz.

- [ ] Step 3: Add user identity and logout display.
  - Validation test: Add component tests requiring display name and logout action to be visible after login.

### Task 29: Implement Latest Must-Read Pages

- [ ] Step 1: Add must-read list page.
  - Validation test: Add component tests requiring list items to display title, publish time, effective time, and permission level.

- [ ] Step 2: Add must-read list empty state.
  - Validation test: Add component tests requiring the empty text “暂无可查看的最新必读” when API returns no visible entries.

- [ ] Step 3: Add must-read detail page.
  - Validation test: Add component tests requiring title, update body, adjustment points, publish time, effective time, and permission level to render.

- [ ] Step 4: Add must-read permission error handling.
  - Validation test: Add component tests requiring permission errors to show “无权查看该内容” without stale content remaining on screen.

### Task 30: Implement Standard Script Pages

- [ ] Step 1: Add core base script list area.
  - Validation test: Add component tests requiring each base script item to display title, summary points, update time, and permission level.

- [ ] Step 2: Add standardized script item list area.
  - Validation test: Add component tests requiring each script item to display scenario, recommended wording summary, update time, and permission level.

- [ ] Step 3: Add scenario category filter.
  - Validation test: Add component tests requiring category selection to request filtered data and update the visible list.

- [ ] Step 4: Add script detail page.
  - Validation test: Add component tests requiring scenario, recommended wording, forbidden wording, notes, update time, and copy actions to render.

- [ ] Step 5: Add script copy actions.
  - Validation test: Add component tests requiring recommended wording copy and full item copy to use the correct text from the rendered detail.

### Task 31: Implement Quiz Page

- [ ] Step 1: Add quiz question rendering.
  - Validation test: Add component tests requiring five to ten questions to render when API returns that range.

- [ ] Step 2: Add answer selection behavior.
  - Validation test: Add component tests requiring selected answers to be tracked per question without submitting early.

- [ ] Step 3: Add quiz submission behavior.
  - Validation test: Add component tests requiring submit to call the quiz submit API with selected answers and disable duplicate submission while waiting.

- [ ] Step 4: Add quiz result display.
  - Validation test: Add component tests requiring correctness, correct answer, explanation, and related content entry to render after submission.

- [ ] Step 5: Confirm no score history UI exists.
  - Validation test: Add a page test requiring no ranking, score history, personal statistics, or management statistics labels to appear on the quiz page.

### Task 32: Implement AI Answer UI

- [ ] Step 1: Add AI answer result display.
  - Validation test: Add component tests requiring answer text, source list, source update time, and copy button to render after successful RAG response.

- [ ] Step 2: Add AI miss display.
  - Validation test: Add component tests requiring the fixed miss text “当前没有有效标准口径，请联系管理员。” when the backend returns no hit.

- [ ] Step 3: Add AI service unavailable display.
  - Validation test: Add component tests requiring “智能问答暂不可用，请稍后重试” for model or Milvus service errors.

- [ ] Step 4: Add source navigation behavior.
  - Validation test: Add component tests requiring source links to navigate only to accessible content detail routes.

## Phase 9: Frontend Admin Pages

### Task 33: Implement Admin Content List

- [ ] Step 1: Add content list table with filters.
  - Validation test: Add component tests requiring filters for content type, status, permission level, and category to change API query parameters.

- [ ] Step 2: Add content operation entries.
  - Validation test: Add component tests requiring draft edit, publish, offline, history, index status, and retry index actions to appear only where valid for the content status.

- [ ] Step 3: Add pagination.
  - Validation test: Add component tests requiring page changes to request the correct page and preserve active filters.

- [ ] Step 4: Add index status display.
  - Validation test: Add component tests requiring unsynced, syncing, synced, and failed states to render distinct labels.

### Task 34: Implement Admin Content Editor

- [ ] Step 1: Add shared content fields.
  - Validation test: Add component tests requiring title, content type, category, permission level, summary, and body validation.

- [ ] Step 2: Add standard script item fields.
  - Validation test: Add component tests requiring scenario, recommended wording, forbidden wording, and notes fields for standardized script items.

- [ ] Step 3: Add latest must-read fields.
  - Validation test: Add component tests requiring update body and adjustment points fields for latest must-read entries.

- [ ] Step 4: Add draft save behavior.
  - Validation test: Add component tests requiring successful draft save to show confirmation and route back to admin content detail or list.

### Task 35: Implement Publish, Offline, History, And Retry UI

- [ ] Step 1: Add publish confirmation dialog.
  - Validation test: Add component tests requiring title, content type, permission level, visible audience, and replacement warning to appear before publish.

- [ ] Step 2: Add publish result handling.
  - Validation test: Add component tests requiring successful publish to show success and index failure publish to show content-published-but-AI-unavailable notice.

- [ ] Step 3: Add offline confirmation behavior.
  - Validation test: Add component tests requiring offline confirmation before calling the offline API and requiring the list to update after success.

- [ ] Step 4: Add history page.
  - Validation test: Add component tests requiring version number, title, publish time, publisher, permission level, and body snapshot to render.

- [ ] Step 5: Add retry index action.
  - Validation test: Add component tests requiring retry index to be available only when index status is failed and to refresh status after success.

### Task 36: Implement Admin Quiz Management

- [ ] Step 1: Add quiz question list.
  - Validation test: Add component tests requiring question, permission level, related content, status, and update time to render.

- [ ] Step 2: Add quiz editor.
  - Validation test: Add component tests requiring question, options, correct answer, explanation, related content, permission level, and status validation.

- [ ] Step 3: Add enable and disable behavior.
  - Validation test: Add component tests requiring enable and disable actions to update status and refresh list data.

### Task 37: Implement Admin User Management

- [ ] Step 1: Add user list.
  - Validation test: Add component tests requiring username, display name, account type, content level, status, and update time to render.

- [ ] Step 2: Add user create and edit form.
  - Validation test: Add component tests requiring username, display name, account type, content level, and status validation.

- [ ] Step 3: Add password reset behavior.
  - Validation test: Add component tests requiring reset confirmation and requiring returned temporary password or reset instruction to be shown only once.

- [ ] Step 4: Add disable account behavior.
  - Validation test: Add component tests requiring disabled users to appear with disabled state and requiring disabled accounts to fail login in backend API tests.

### Task 38: Implement Admin Missed Question Management

- [ ] Step 1: Add missed question list.
  - Validation test: Add component tests requiring question text, asked time, user, permission snapshot, and status to render.

- [ ] Step 2: Add status filter.
  - Validation test: Add component tests requiring new and handled filters to request the correct API state.

- [ ] Step 3: Add mark-handled action.
  - Validation test: Add component tests requiring mark-handled to update row state and handled time after API success.

- [ ] Step 4: Confirm no statistics dashboard exists.
  - Validation test: Add a page test requiring no chart, aggregate count board, ranking, or analytics panel to appear in missed question management.

## Phase 10: End-To-End Verification

### Task 39: Build Backend Fixture Data For E2E

- [ ] Step 1: Create deterministic test accounts for admin, full user, and general user in the E2E environment.
  - Validation test: Add an E2E setup test requiring all three accounts to log in and return the expected account type and content level.

- [ ] Step 2: Create deterministic content fixtures for general and full permission levels.
  - Validation test: Add an E2E setup test requiring the fixture content to include at least one must-read, one base script, one standardized script item, and one quiz question per relevant permission level.

- [ ] Step 3: Create deterministic fake RAG fixtures for successful hit and miss.
  - Validation test: Add an E2E setup test requiring the fake RAG path to return one successful sourced answer and one no-hit response.

### Task 40: Implement Playwright Smoke Tests

- [ ] Step 1: Add admin login and content publish smoke test.
  - Validation test: The smoke test must create a general-level draft, publish it, and observe it in employee-visible content.

- [ ] Step 2: Add general-user permission isolation smoke test.
  - Validation test: The smoke test must confirm a general user cannot see full-level content in lists, details, AI sources, or quiz questions.

- [ ] Step 3: Add full-user visibility smoke test.
  - Validation test: The smoke test must confirm a full user can see both general-level and full-level content.

- [ ] Step 4: Add AI miss smoke test.
  - Validation test: The smoke test must submit an unanswerable question, observe the fixed miss message, then confirm the admin missed question list contains that question.

- [ ] Step 5: Add quiz no-persistence smoke test.
  - Validation test: The smoke test must submit quiz answers, see explanations, reload the page, and confirm no score history or answer history is shown.

### Task 41: Run MVP Acceptance Checklist

- [ ] Step 1: Verify all backend tests.
  - Validation test: Backend unit, service, API, and migration tests must complete with zero failures.

- [ ] Step 2: Verify all frontend tests.
  - Validation test: Frontend unit and component tests must complete with zero failures.

- [ ] Step 3: Verify all Playwright smoke tests.
  - Validation test: Playwright smoke tests for login, permission isolation, publish, AI miss, and quiz behavior must complete with zero failures.

- [ ] Step 4: Verify MVP acceptance criteria one by one.
  - Validation test: Create a checklist mapping each acceptance criterion from `memory-bank/design-document.md` section 13 to a passing test or documented manual verification.

## Phase 11: Documentation, Deployment Notes, And Memory Updates

### Task 42: Update Documentation For Local Development

- [ ] Step 1: Add backend local setup instructions.
  - Validation test: A developer following only the documentation can identify how to configure database URL, JWT secret, Milvus host, and DashScope settings.

- [ ] Step 2: Add frontend local setup instructions.
  - Validation test: A developer following only the documentation can identify how to configure the API base URL and run frontend tests.

- [ ] Step 3: Add local dependency startup instructions.
  - Validation test: A developer following only the documentation can identify how to start or connect MySQL and Milvus without using production secrets.

- [ ] Step 4: Add test execution instructions.
  - Validation test: Documentation must list backend tests, frontend tests, and Playwright smoke tests as separate verification categories.

### Task 43: Add Deployment Notes For Baota And ECS

- [ ] Step 1: Document frontend deployment as a static HTML project.
  - Validation test: Documentation must state that production frontend output is served as static files and does not require a Node server.

- [ ] Step 2: Document backend deployment as a Python project.
  - Validation test: Documentation must state the backend listens on a local port behind Nginx or Baota reverse proxy.

- [ ] Step 3: Document MySQL deployment options.
  - Validation test: Documentation must state that SQLAlchemy is not an extra database and that the only business database is MySQL.

- [ ] Step 4: Document Milvus deployment as the extra service.
  - Validation test: Documentation must clearly state that Milvus is the main additional runtime service and can be run with Docker.

- [ ] Step 5: Document DashScope configuration.
  - Validation test: Documentation must state that DashScope is an external API configured by environment variables and is never called from the frontend.

### Task 44: Update Memory Bank After Major Milestones

- [ ] Step 1: Update `memory-bank/architecture.md` after backend scaffold and data model are stable.
  - Validation test: Confirm the memory file describes the actual backend directory, chosen dependency manager, migration approach, and test categories.

- [ ] Step 2: Update `memory-bank/architecture.md` after RAG indexing and answer flow are stable.
  - Validation test: Confirm the memory file describes the actual chunking rules, fake-client test strategy, source consistency rule, and index failure behavior.

- [ ] Step 3: Update `memory-bank/architecture.md` after frontend route and page structure are stable.
  - Validation test: Confirm the memory file describes the actual frontend route groups, shared stores, admin pages, employee pages, and test approach.

- [ ] Step 4: Update `memory-bank/architecture.md` after MVP acceptance tests pass.
  - Validation test: Confirm the memory file lists the final MVP runtime shape, known limitations, non-goals, and next-phase extension points.

## Final Handoff Checklist

- [ ] Step 1: Confirm no implementation code appears in this plan.
  - Validation test: Search this file for implementation code blocks and confirm none exist.

- [ ] Step 2: Confirm every plan step has a validation test.
  - Validation test: Search this file for every checkbox step and confirm each one has a directly adjacent “Validation test” line.

- [ ] Step 3: Confirm plan coverage against product design.
  - Validation test: Map login, homepage, latest must-read, standard scripts, quiz, AI Q&A, admin content, versions, indexing, missed questions, permissions, local verification, and deployment notes to tasks in this plan.

- [ ] Step 4: Confirm plan coverage against tech stack.
  - Validation test: Map Vue, TypeScript, Vite, Vue Router, Pinia, Axios, Element Plus, FastAPI, SQLAlchemy, Alembic, MySQL, Milvus, DashScope, pytest, Vitest, and Playwright to tasks in this plan.
