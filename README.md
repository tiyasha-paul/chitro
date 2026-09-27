# Chitro

**AI Content Operations & Multi-Platform Command Center**

Chitro is an AI-assisted content operations platform designed to take a structured campaign brief through end-to-end execution: platform-specific generation, deterministic rule validation, human-in-the-loop review and approval, scheduling, mock publishing, metric snapshot recording, cross-platform performance analysis, evidence-backed reporting, and closed-loop campaign learning.

Rather than treating generative AI as an unconstrained chat interface, Chitro embeds large language models into a stateful, auditable pipeline governed by deterministic safety gates, strict state machine transitions, and verifiable quantitative citations.

---

## Architectural & Technology Summary

- **Frontend**: Next.js 16 (React 19, TypeScript, Tailwind CSS v4, Vanilla CSS design tokens). Editorial design aesthetic inspired by Aetherfield/Redo with custom typography and responsive grid layouts.
- **Backend**: FastAPI (Python 3.12) structured with distinct domain, service, validation, and adapter layers.
- **Persistence**: PostgreSQL via SQLAlchemy 2.0 (fully async using `asyncpg` driver) and Pydantic v2 validation.
- **AI Integration**: Google Gemini API via the official `google-genai` SDK, leveraging structured JSON schemas (`response_schema`), native Bengali and English language prompts, and an abstract provider interface.
- **Security & Multi-Tenancy**: Bearer JWT authentication (HS256 with salted `scrypt` password hashing), role-based workspace memberships (`owner`, `member`), and tenant-isolated data queries via `X-Workspace-ID`.
- **Validation**: Independent, deterministic rules engine enforcing platform character limits, hashtag taxonomy, call-to-action presence, aspect ratios, and media constraints prior to human review or publishing.
- **Publishing Abstraction**: Extensible `ChannelAdapter` protocol with mock implementations simulating realistic external publishing and network failure modes without calling external APIs.
- **Evidence-Backed Reporting**: Authoritative report generation engine that validates quantitative AI claims against exact recorded metric snapshots, rejecting hallucinated figures at the API boundary.

---


## Core Workflow & Post Lifecycle

Every piece of content created in Chitro traverses an explicit 9-stage operational lifecycle:

```
Brief → Generate → Validate → Human Review → Approve → Schedule → Publish → Measure → Learn → Next Brief
```

### Post State Machine

Content lifecycle states are strictly enforced by a finite state machine in `app/domain/state_machine.py`. Illegal state transitions raise an `InvalidStateTransitionError`, resulting in an HTTP `409 Conflict` response.

```
       ┌───────────┐
       │   DRAFT   │
       └─────┬─────┘
             │ (generation requested)
             ▼
       ┌───────────┐
 ┌────►│ GENERATED │◄────────────────────────┐
 │     └─────┬─────┘                         │
 │           │ (deterministic validation)    │
 │     ┌─────┴──────────────┐                │ (regenerate with feedback)
 │     ▼                    ▼                │
 │ ┌───────────┐  ┌───────────────────┐      │
 │ │ VALIDATED │  │ VALIDATION_FAILED │──────┤
 │ └─────┬─────┘  └───────────────────┘      │
 │       │ (transition)                      │
 │       ▼                                   │
 │ ┌──────────────────┐                      │
 │ │ PENDING_APPROVAL │                      │
 │ └─────┬──────┬─────┘                      │
 │       │      │ (human reject)             │
 │       │      ▼                            │
 │       │ ┌──────────┐                      │
 │       │ │ REJECTED │──────────────────────┘
 │       │ └──────────┘
 │       │ (human approve)
 │       ▼
 │ ┌──────────┐
 │ │ APPROVED │
 │ └─────┬────┘
 │       │ (schedule for future OR direct publish)
 │       ▼
 │ ┌───────────┐
 │ │ SCHEDULED │
 │ └─────┬─────┘
 │       │ (channel adapter execution)
 │       ▼
 │ ┌───────────┐
 │ │ PUBLISHED │ [Terminal State]
 │ └───────────┘
```

#### Valid Transition Matrix

| Source Status | Allowed Target Statuses | Trigger / Precondition |
| :--- | :--- | :--- |
| `DRAFT` | `GENERATED` | Post record initialized and brief submitted to LLM provider. |
| `GENERATED` | `VALIDATED`, `VALIDATION_FAILED` | Deterministic platform rules engine evaluates generated output. |
| `VALIDATION_FAILED` | `GENERATED` | Regeneration requested after adjusting prompt or rules. |
| `VALIDATED` | `PENDING_APPROVAL` | Automatic progression upon zero validation errors. |
| `PENDING_APPROVAL` | `APPROVED`, `REJECTED` | Explicit human operator review action (rejection requires feedback text). |
| `APPROVED` | `SCHEDULED` | Future execution timestamp assigned (`scheduled_at > now`). |
| `REJECTED` | `GENERATED` | Regeneration triggered; preserves history and injects feedback into prompt. |
| `SCHEDULED` | `PUBLISHED` | Target publishing adapter successfully executes publication payload. |
| `PUBLISHED` | *None (Terminal)* | Content is immutable. Subsequent publish calls return existing entity idempotently. |

---

## System Architecture

The following diagram illustrates the component boundaries, service relationships, and data flow across the Chitro platform:

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Layer (Next.js 16 / React 19)"]
        UI["Web Browser Client"]
        Shell["AppShell & Auth Session"]
        CampUI["Campaign & Brief Wizard"]
        PostUI["Post Card & Workflow Timeline"]
        ReportUI["Evidence-Checked Weekly Report UI"]
        UI --> Shell
        Shell --> CampUI
        Shell --> PostUI
        Shell --> ReportUI
    end

    subgraph APILayer["FastAPI Application Layer"]
        RouterAuth["/api/auth (Login, Register, Me)"]
        RouterWorkspaces["/api/workspaces (Members, Roles)"]
        RouterCampaigns["/api/campaigns (Briefs, List, Detail)"]
        RouterPosts["/api/posts (Lifecycle, Schedule, Publish, Metrics)"]
        AuthMiddleware["JWT Bearer & X-Workspace-ID Auth Guard"]
    end

    subgraph ServiceLayer["Domain & Service Orchestration Layer"]
        AuthSvc["AuthService (scrypt, JWT)"]
        WorkSvc["WorkspaceService (Tenant Isolation)"]
        CampSvc["CampaignService"]
        FlowSvc["ContentWorkflowService (State Machine)"]
        ApprSvc["ApprovalService"]
        PubSvc["PublishingService"]
        AnSvc["AnalyticsService (Metric Snapshots & Insights)"]
        RepSvc["ReportingService (Citation Verifier)"]
    end

    subgraph SafetyAndValidation["Deterministic Validation Engine"]
        Engine["ValidationEngine"]
        IGSpec["InstagramSpec (2200 char, 5-30 tags, 1:1/4:5/9:16/16:9)"]
        XSpec["XSpec (280 char, 0-2 tags)"]
        MediaVal["MediaSpec Validator (MIME, Aspect Ratio, Bytes)"]
        Engine --> IGSpec
        Engine --> XSpec
        Engine --> MediaVal
    end

    subgraph AILayer["AI Abstraction & Intelligence"]
        LLMBase["LLMProvider (Protocol)"]
        GeminiProv["GeminiProvider (google-genai Client)"]
        MockLLM["MockReportingLLMProvider (Test Harness)"]
        StratIG["InstagramStrategy"]
        StratX["XStrategy"]
        LLMBase --> GeminiProv
        LLMBase --> MockLLM
    end

    subgraph ChannelAdapters["Publishing Infrastructure"]
        ChannelProto["ChannelAdapter (Protocol)"]
        MockIGAdapter["MockInstagramAdapter"]
        ChannelProto --> MockIGAdapter
    end

    subgraph StorageLayer["Persistence Layer (PostgreSQL / SQLAlchemy Async)"]
        DB[(PostgreSQL Database)]
        Models["Models: User, Workspace, Member, Campaign, PlatformPost, MetricSnapshot, Insight"]
        DB --- Models
    end

    %% Client to API
    CampUI -->|HTTPS / JSON + Bearer + X-Workspace-ID| RouterCampaigns
    PostUI -->|HTTPS / JSON + Bearer + X-Workspace-ID| RouterPosts
    Shell -->|HTTPS / JSON| RouterAuth
    Shell -->|HTTPS / JSON| RouterWorkspaces
    ReportUI -->|HTTPS / JSON| RouterCampaigns

    %% API to Services
    RouterAuth --> AuthSvc
    RouterWorkspaces --> WorkSvc
    RouterCampaigns --> AuthMiddleware
    RouterPosts --> AuthMiddleware
    AuthMiddleware --> CampSvc
    AuthMiddleware --> FlowSvc
    AuthMiddleware --> ApprSvc
    AuthMiddleware --> PubSvc
    AuthMiddleware --> AnSvc
    AuthMiddleware --> RepSvc

    %% Service connections
    FlowSvc --> AILayer
    FlowSvc --> SafetyAndValidation
    FlowSvc --> StorageLayer
    PubSvc --> ChannelAdapters
    PubSvc --> SafetyAndValidation
    PubSvc --> StorageLayer
    AnSvc --> StorageLayer
    RepSvc --> AILayer
    RepSvc --> StorageLayer
    CampSvc --> StorageLayer
    AuthSvc --> StorageLayer
    WorkSvc --> StorageLayer

    %% Feedback loop
    AnSvc -.->|Saves Insights & Evidence| CampSvc
    CampSvc -.->|Injects Previous Insights| FlowSvc
```

---

## Backend Architecture

The backend application in `backend/app/` adheres to clean architecture principles, separating protocol definitions, domain state rules, service orchestration, and protocol transport:

```
backend/app/
├── adapters/               # External channel publishing protocols and adapters
│   ├── channel.py          # ChannelAdapter protocol, PublishPayload, PublishResult
│   └── mock_instagram.py   # MockInstagramAdapter with simulated endpoints & failure flags
├── ai/                     # LLM abstraction, platform strategies, and prompts
│   ├── gemini.py           # GeminiProvider leveraging google-genai SDK
│   ├── platform_strategy.py# InstagramStrategy and XStrategy content constraints
│   ├── prompts.py          # System instructions, language mandates, report prompts
│   └── provider.py         # LLMProvider abstract base class and exceptions
├── api/                    # FastAPI route definitions and dependency injection
│   ├── auth.py             # User registration, login, and token issuing
│   ├── campaigns.py        # Campaign CRUD, generation trigger, comparison, reporting
│   ├── deps.py             # DB sessions, user auth, workspace scoping, service providers
│   ├── posts.py            # Workflow actions: approve, reject, regenerate, schedule, publish
│   └── workspaces.py       # Workspace membership and team management
├── domain/                 # Core business models, enums, exceptions, and state machine
│   ├── enums.py            # Platform, Language, PostStatus definitions
│   ├── exceptions.py       # Domain-specific errors (ResourceNotFound, CitationValidation, etc.)
│   ├── models.py           # SQLAlchemy declarative models
│   └── state_machine.py    # Deterministic post lifecycle transition enforcement
├── schemas/                # Pydantic request/response validation schemas
│   ├── analytics.py        # Snapshot ingestion, metric comparisons, insight payloads
│   ├── auth.py             # Login, register, and token schemas
│   ├── briefs.py           # Structured content brief input schema
│   ├── campaigns.py        # Campaign representation schemas
│   ├── content.py          # Generated content schemas (GeneratedInstagramPost, MediaDirection)
│   ├── media.py            # Concrete media asset specification (MediaAssetSpec)
│   ├── posts.py            # Post lifecycle requests and responses
│   ├── reports.py          # Evidence-backed report schemas, claims, and citations
│   └── workspaces.py       # Workspace membership and summary schemas
├── services/               # Stateless domain business logic
│   ├── analytics.py        # Metric aggregation, normalized comparison, insight synthesis
│   ├── approval.py         # Human approval and rejection handling
│   ├── auth.py             # Password hashing (scrypt) and JWT token encoding/decoding
│   ├── campaign.py         # Campaign lifecycle and previous insight attachment
│   ├── generation.py       # Prompt building and structured LLM invocation
│   ├── publishing.py       # Pre-publish validation, scheduling, and channel distribution
│   ├── reporting.py        # Weekly report context assembly, generation, citation verification
│   ├── validation.py       # Bridge to ValidationEngine
│   ├── workflow.py         # Multi-step generation and regeneration coordinator
│   └── workspace.py        # Member addition/removal and role constraints
├── validation/             # Deterministic platform specifications and media validators
│   ├── engine.py           # ValidationEngine registry and coordinator
│   ├── instagram.py        # InstagramSpec platform rules (character, hashtag, aspect ratios)
│   ├── media.py            # Concrete media metadata, aspect ratio fraction matching
│   ├── platform_spec.py    # PlatformSpec base class, ValidationErrorDetail, ValidationResult
│   └── x.py                # XSpec concise social copy rules (280 chars, 0-2 tags)
├── config.py               # Pydantic Settings configuration from environment
├── database.py             # Async SQLAlchemy engine, session maker, table initialization
└── main.py                 # FastAPI application factory, CORS, and exception handlers
```

---

## AI Generation Architecture

Chitro integrates with Google Gemini via the modern `google-genai` SDK (`google.genai.Client`).

### Structured Output Enforcement

The application uses Gemini's native JSON mode and schema enforcement (`response_mime_type="application/json"` and `response_schema=output_schema`). Responses are deterministically parsed and validated through Pydantic models:

```python
# app/ai/gemini.py
config = genai_types.GenerateContentConfig(
    system_instruction=system_instruction,
    temperature=temperature,
    response_mime_type="application/json",
    response_schema=output_schema,
)
response = await self._client.aio.models.generate_content(
    model=self._model,
    contents=prompt,
    config=config,
)
```

### Media Implementation Boundary

> **Current Implementation Boundary**: Chitro generates **structured textual content and creative visual direction** (`MediaDirection`: visual description, style suggestion, mood, recommended aspect ratio). The application also defines and validates concrete media asset metadata (`GeneratedMediaAsset` / `MediaAssetSpec`). 
> 
> Chitro **does not currently generate binary pixel data (JPEG/PNG) or video files (MP4)** via generative image/video diffusion models. Instead, during mock execution, Chitro synthesizes deterministic asset metadata and mock asset URLs (`mock://generated/{post_id}.jpg`) for downstream media validation and mock distribution. Binary asset generation is a designated roadmap milestone.

### Native Language Handling

Chitro enforces strict language purity at the system instruction level in `app/ai/prompts.py`:

- **Bengali (`bn`)**: Explicit system instructions mandate that the hook, caption, call-to-action, hashtags, and visual direction be written entirely in native Bengali script (বাংলা লিপি). English transliteration or mixed scripts are forbidden unless representing technical terms or global brand names.
- **English (`en`)**: Clear, professional English copy structured for audience engagement.

### Closed-Loop Insight Injection

When generating content for a campaign, Chitro inspects `Campaign.previous_insights`. If prior insights exist from a linked campaign, they are formatted into the prompt under `## Previous Campaign Insights`, ensuring the model does not repeat past mistakes.

Similarly, when a post is rejected by a human reviewer, the mandatory `rejection_reason` is passed into the regeneration prompt under `## Previous Rejection Feedback` so the new generation directly addresses the feedback.

---

## Platform-Specific Content Rules

Chitro avoids uniform cross-posting by implementing distinct `PlatformStrategy` and `PlatformSpec` classes for each supported channel:

### 1. Instagram (`Platform.INSTAGRAM`)
- **Caption Constraints**: 150 to 2,200 characters.
- **Hashtag Taxonomy**: 5 to 30 hashtags, each strictly prefixed with `#` and containing no interior whitespace.
- **Structure**: Mandatory opening hook, narrative body, clear call-to-action, and trailing hashtag block.
- **Media Specs**: Aspect ratios limited to `1:1` (square), `4:5` (portrait), `9:16` (story/reel), or `16:9` (landscape).
- **Tone**: Visual-first, conversational, and emotionally resonant.

### 2. X (`Platform.X`)
- **Caption Constraints**: 1 to 280 characters.
- **Hashtag Taxonomy**: 0 to 2 focused hashtags.
- **Structure**: Concise hook, concise context, and low-friction direct CTA.
- **Tone**: Immediate, punchy, and conversational. Long-form Instagram captions are rejected.

---

## Validation & Safety Gates

A core architectural principle of Chitro is that **AI outputs must never be trusted implicitly**. Model output passes through a decoupled, deterministic validation engine (`ValidationEngine`) implemented in pure Python before it can enter human review or the publishing pipeline.

```
       Generated Output (from LLM)
                  │
                  ▼
      ┌─────────────────────────┐
      │ Deterministic Engine    │
      │ - Caption length check  │
      │ - Hook & CTA presence   │
      │ - Hashtag format/count  │
      │ - Media direction rules │
      │ - Aspect ratio fraction │
      │ - File size / MIME type │
      └───────────┬─────────────┘
                  │
        Pass ─────┴───── Fail
         │                │
         ▼                ▼
   PENDING_APPROVAL   VALIDATION_FAILED
  (Queued for human) (Errors recorded in JSON)
```

### Defense-in-Depth Validation Layers

1. **Post Generation**: After the LLM produces a post, `ValidationEngine.validate()` and `validate_media_asset()` evaluate the content. If errors occur, the post is transitioned to `VALIDATION_FAILED`, the exact errors are persisted to `platform_posts.validation_errors`, and execution halts.
2. **Scheduling Boundary**: Before a post can transition from `APPROVED` to `SCHEDULED`, `PublishingService.schedule_post()` calls `ensure_valid_media_asset()`, ensuring corrupted or modified media specifications cannot be scheduled.
3. **Publishing Boundary**: Before delivering the payload to the channel adapter, `PublishingService.publish_post()` and `MockInstagramAdapter.publish()` re-verify media specifications, guaranteeing that even direct publish requests cannot bypass validation.

### Mathematical Aspect Ratio Validation

Aspect ratio validation does not rely on string matching alone. The validator converts pixel dimensions into exact rational fractions via Python's `fractions.Fraction`:

```python
# app/validation/media.py
actual_ratio = Fraction(media.width, media.height)
allowed_ratios = {
    ratio: Fraction(*(int(part) for part in ratio.split(":")))
    for ratio in spec.allowed_aspect_ratios
}
if actual_ratio not in allowed_ratios.values():
    errors.append(ValidationErrorDetail(
        field="media_spec.width",
        code="UNSUPPORTED_ASPECT_RATIO",
        message="Asset dimensions do not produce an allowed aspect ratio.",
        actual=f"{media.width}:{media.height}",
        expected=sorted(spec.allowed_aspect_ratios)
    ))
```

This guarantees that assets with non-standard dimensions (e.g., `1080x1350` for `4:5`) are accepted accurately while invalid ratios are rejected with structured error payloads.

---

## Human Approval Gate

Chitro enforces an explicit human review gate between content validation and distribution. The system architecture makes it impossible for generated content to publish autonomously.

1. **Gatekeeping**: A post that passes validation sits in `PENDING_APPROVAL`.
2. **Human Decision**:
   - **Approve** (`POST /api/posts/{id}/approve`): Transitions the post to `APPROVED`. It can now be scheduled or published.
   - **Reject** (`POST /api/posts/{id}/reject`): Requires a non-empty human review reason (`reason`). Transitions the post to `REJECTED` and records `rejection_reason`.
3. **Audit History & Regeneration** (`POST /api/posts/{id}/regenerate`):
   - Only posts in `REJECTED` or `VALIDATION_FAILED` can be regenerated.
   - The current content, attempt number, status, and rejection reason are appended to the post's `generation_history` JSON array.
   - The attempt counter (`generation_attempt`) increments.
   - The human feedback is passed directly into the generation prompt under `## Previous Rejection Feedback` to steer the subsequent attempt.

---

## Publishing Architecture

The publishing layer is decoupled from domain logic via the `ChannelAdapter` protocol defined in `app/adapters/channel.py`:

```python
@runtime_checkable
class ChannelAdapter(Protocol):
    async def publish(self, payload: PublishPayload) -> PublishResult:
        ...
```

### Mock Publishing Implementation

Chitro currently features `MockInstagramAdapter` (`app/adapters/mock_instagram.py`):
- Operates entirely in memory without making external network calls.
- Validates concrete media specifications before simulating publication.
- Synthesizes a deterministic external ID (e.g., `mock_ig_a1b2c3d4e5f6`) and mock public URL (`https://mock-instagram.chitro.local/p/{external_id}`).
- Returns structured metadata (caption character count, media format, hashtag count).
- Supports fault-injection testing via `simulate_failure=True`, enabling automated verification of transactional rollbacks and network timeout handling.

This design enables real platform adapters (e.g., Meta Graph API, X API v2) to be added in the future by implementing the `ChannelAdapter` protocol without altering workflow or campaign code.

---

## Authentication & Multi-Tenancy

Chitro implements strict workspace-scoped multi-tenancy:

### Security Primitives
- **Password Security**: Passwords are never stored in plaintext. They are hashed using `scrypt` with unique 16-byte random salts (`hash_password()` in `app/services/auth.py`).
- **Token Format**: Short-lived JSON Web Tokens signed with HMAC-SHA256 (`HS256`) containing the user's UUID in the `sub` claim and an absolute UTC expiry timestamp in `exp`.
- **Zero-Cookie API**: Authentication relies strictly on `Authorization: Bearer <token>` headers.

### Workspace Isolation & Role Access
- **Automatic Provisioning**: Registering a new account automatically creates a personal `Workspace` and assigns the user as `owner` in `WorkspaceMember`.
- **Context Routing**: API calls identify the target workspace via the `X-Workspace-ID` header.
- **Tenant Isolation**: Dependency injection functions (`get_selected_workspace` and `get_selected_workspace_post`) verify that the calling user possesses an active membership in the selected workspace.
- **Defensive Resource Hiding**: Querying a campaign or post belonging to another workspace returns an HTTP `404 Not Found` rather than a `403 Forbidden`, preventing resource ID enumeration across workspaces.
- **Ownership Protection**: A workspace owner cannot be removed if they are the sole owner of that workspace (`SoleOwnerRemovalError` -> `409 Conflict`).

---

## Analytics & Cross-Platform Insights

Chitro provides normalized performance measurement across distinct platform posts.

### Metric Snapshot Ingestion

Performance data is recorded as discrete point-in-time snapshots (`MetricSnapshot`) via `POST /api/posts/{id}/metrics`:
- **Captured Metrics**: `impressions`, `reach`, `likes`, `comments`, `shares`, `saves`, `clicks`, `engagement_rate`.
- **Publication Guard**: Snapshots can only be recorded for posts in the `PUBLISHED` state. Attempting to record metrics on draft, approved, or scheduled posts raises a `PostNotPublishedError` (`409 Conflict`).
- **Normalized Engagement Rate**: If `engagement_rate` is omitted in the payload but `reach > 0`, the service automatically computes a normalized rate:
  $$\text{Engagement Rate} = \frac{\text{likes} + \text{comments} + \text{shares} + \text{saves}}{\text{reach}}$$

### Like-for-Like Cross-Platform Comparison

The comparison endpoint (`GET /api/campaigns/{id}/analytics/comparison`) aggregates the latest metric snapshots across Instagram and X posts within the same campaign. It provides side-by-side reach and engagement rates without fabricating subjective "winner" claims.

### Verifiable Insight Generation

`POST /api/campaigns/{id}/insights/generate` analyzes recorded metric snapshots and synthesizes structured `Insight` models:
1. **Single Post Snapshots**: Identifies engagement rate and reach milestones for individual posts.
2. **Multi-Snapshot Evolution**: Detects velocity and percentage growth when multiple snapshots exist across time.
3. **Cross-Platform Comparisons**: Contrasts engagement rates between platforms when comparable posts are published.
4. **Strict Traceability**: Every insight record contains an `evidence` JSON array with exact references:
   ```json
   {
     "post_id": "7b8e1f2a-...",
     "metric_field": "engagement_rate",
     "value": 0.045,
     "snapshot_id": "9c3d4e5f-..."
   }
   ```
5. **Persistence**: Generated insights are saved to the `insights` table and appended to `Campaign.previous_insights`.

---

## Evidence-Backed Reporting & Citation Validation

A recurring failure mode in generative AI applications is the hallucination of marketing claims (e.g., an LLM claiming "engagement grew by 45%" when data shows 12%). Chitro eliminates this through **deterministic citation verification** (`ReportingService.validate_citations()` in `app/services/reporting.py`).

### Dual-Layer Prompt Contract

The reporting prompt explicitly partitions narrative synthesis from quantitative facts:
- `executive_summary` & `section.summary`: Restricted to high-level qualitative observations. Specific numerical metrics or counts are forbidden in summary prose.
- `claims[]`: Every specific factual or quantitative assertion must be isolated in the `claims` array, paired with explicit citations.

### Citation Verification Rules

When Gemini returns a `PerformanceReport`, Chitro verifies each citation against the authoritative database context before persisting or returning the report:

1. **Post Verification**: `citation.post_id` must match a published post in the campaign.
2. **Snapshot Verification**: `citation.snapshot_id` must exist and belong to the cited post.
3. **Metric Field Verification**: `citation.metric_field` must exist on the snapshot with a non-null value.
4. **Exact Quantitative Value Match**:
   - **Count Metrics** (`likes`, `reach`, `impressions`, `comments`, `shares`, `saves`, `clicks`): The numerical value asserted in `claim.value` must match the recorded database metric within floating-point tolerance ($10^{-5}$). Count metrics cannot be scaled or stated as percentages.
   - **Rate / Ratio Metrics** (`engagement_rate`): Permits either ratio format (e.g., `0.052`) or percentage format (e.g., `5.2`).
5. **Recommendation Grounding**: Every item in `recommendations[]` must cite a valid `claim_id` established in the report.

If any citation fails verification, Chitro raises a `CitationValidationError`, causing the endpoint to return an HTTP `502 Bad Gateway` error rather than delivering an unverified report to stakeholders.

---

## The Learning Loop

Chitro bridges the gap between campaign measurement and subsequent creative production through a persistent feedback loop:

```
[Campaign A: Active / Published]
               │
               ▼
[Record Metric Snapshots over Time]
               │
               ▼
[Generate Evidence-Backed Insights]
  - Saved to `insights` table
  - Stored on `campaigns.previous_insights`
               │
               ▼
[New Campaign Brief Wizard (Campaign B)]
  - User selects Campaign A as learning source
  - `POST /api/campaigns` with `previous_insights: <campaign_a_id>`
               │
               ▼
[Content Generation for Campaign B]
  - `build_generation_prompt()` extracts Campaign A insights
  - Prompt section: "## Previous Campaign Insights"
  - Gemini generates copy conditioned on past performance
```

This ensures marketing teams institutionalize learnings directly within the model's generation context without manual prompt engineering.

---

## Database Schema & Data Models

Chitro uses PostgreSQL with SQLAlchemy 2.0 async declarative models (`app/domain/models.py`):

```
┌──────────────────┐       1:N       ┌────────────────────────┐
│      users       ├────────────────►│   workspace_members    │
└──────────────────┘                 └───────────┬────────────┘
                                                 │ N:1
                                                 ▼
                                     ┌────────────────────────┐
                                     │       workspaces       │
                                     └───────────┬────────────┘
                                                 │ 1:N
                                                 ▼
┌──────────────────┐       1:N       ┌────────────────────────┐
│     insights     │◄────────────────┤       campaigns        │
└──────────────────┘                 └───────────┬────────────┘
                                                 │ 1:N
                                                 ▼
┌──────────────────┐       1:N       ┌────────────────────────┐
│ metric_snapshots │◄────────────────┤     platform_posts     │
└──────────────────┘                 └────────────────────────┘
```

### Entity Specifications

- **`users`**: Platform user accounts. Stores `id` (UUID), `email` (unique index), `display_name`, `password_hash` (scrypt), and `created_at`.
- **`workspaces`**: Tenancy boundaries. Stores `id` (UUID), `name`, and `created_at`.
- **`workspace_members`**: Membership mapping with unique constraint on `(workspace_id, user_id)`. Stores `role` (`owner`, `member`).
- **`campaigns`**: High-level marketing initiatives scoped to a workspace. Stores `name`, `objective`, `target_audience`, `brief_context`, `brief_payload` (JSON), `previous_insights` (JSON), and `workspace_id` (foreign key).
- **`platform_posts`**: Platform-specific content deliverables. Stores `campaign_id` (foreign key), `platform` (`instagram`, `x`), `language` (`bn`, `en`), `status` (PostStatus enum string), `caption`, `hook`, `media_spec` (JSON), `hashtags` (JSON array), `cta`, `validation_errors` (JSON array), `rejection_reason`, `generation_attempt` (integer), `generation_history` (JSON array), `scheduled_at`, `published_at`, `published_post_id`, and `publish_result` (JSON).
- **`metric_snapshots`**: Periodic performance observations. Stores `platform_post_id` (foreign key), `impressions`, `reach`, `likes`, `comments`, `shares`, `saves`, `clicks`, `engagement_rate` (float), and `captured_at`.
- **`insights`**: Verifiable findings derived from metrics. Stores `campaign_id` (foreign key), `summary` (text), `evidence` (JSON array of citations), and `created_at`.

---

## Testing & Quality Assurance

Chitro features a comprehensive backend test suite implemented with `pytest` and `pytest-asyncio`. Tests execute against an active asynchronous database engine and use isolated transactional rollbacks.

### Test Suite Execution

The backend test suite contains **220 automated tests across 15 test suites**, executing in under 18 seconds:

```bash
cd backend
pytest -v
```

```text
============================= test session starts ==============================
collected 220 items

tests/test_analytics.py ..........                                       [  4%]
tests/test_auth.py ........                                              [  8%]
tests/test_campaign_learning.py ...                                      [  9%]
tests/test_config.py ....                                                [ 11%]
tests/test_generation.py .....................                           [ 20%]
tests/test_media_validation.py .............                             [ 26%]
tests/test_publishing.py ......................                          [ 36%]
tests/test_reporting.py ..........................                       [ 48%]
tests/test_state_machine.py .................................            [ 63%]
tests/test_validation.py ..............................................  [ 84%]
tests/test_workflow_api.py ............                                  [ 90%]
tests/test_workspace.py ..........                                       [ 94%]
tests/test_workspace_api.py ....                                         [ 96%]
tests/test_workspace_isolation.py ....                                   [ 98%]
tests/test_x_validation.py ....                                          [100%]

============================= 220 passed in 17.52s =============================
```

### Major Test Suites

1. **`test_state_machine.py` (33 tests)**: Verifies every legal state transition, rejects illegal transitions, tests terminal statuses, and ensures domain exceptions are raised accurately.
2. **`test_validation.py` & `test_x_validation.py` (50 tests)**: Validates caption lengths, hashtag format, hook/CTA requirements, media aspect ratios, and platform-specific constraints for Instagram and X.
3. **`test_media_validation.py` (13 tests)**: Tests concrete media metadata, MIME type whitelists, MIME/media type mismatch detection, and fraction-based aspect ratio checks.
4. **`test_publishing.py` (22 tests)**: Tests scheduling preconditions, future timestamp requirements, direct publishing, channel adapter isolation, simulated failure handling, and idempotent re-publishing.
5. **`test_reporting.py` (26 tests)**: Validates deterministic citation checking, quantitative exact matching, percentage conversion tolerances on rates, rejection of uncited claims, time-window filtering, and reporting HTTP endpoints.
6. **`test_analytics.py` (10 tests)**: Verifies metric snapshot recording, publication guards, automatic engagement rate calculation, and cross-platform comparisons.
7. **`test_workspace_isolation.py` & `test_workspace.py` (14 tests)**: Enforces cross-workspace data boundaries, header-based workspace selection, 404 responses for cross-tenant resource requests, and member management rules.
8. **`test_campaign_learning.py` (3 tests)**: Verifies that prior campaign insights attach to new briefs and appear inside the prompt during generation.
9. **`test_generation.py` (21 tests)**: Tests `GenerationService`, system instruction construction, and Pydantic structured output mapping using mocks.

---

## Architectural Decisions & Rationale

| Decision | Rationale & Engineering Problem Solved |
| :--- | :--- |
| **`LLMProvider` Protocol Abstraction** | Decouples business logic from vendor SDKs. Allows instantaneous replacement of Gemini with local models or mock providers (`MockReportingLLMProvider`) during integration testing without network calls. |
| **Deterministic Validation Decoupled from LLM** | LLMs cannot reliably self-validate token lengths, hashtag regex patterns, or image dimensions. Running independent, deterministic Python checks guarantees safety before human review. |
| **Finite State Machine Enforcement** | Prevents race conditions and invalid workflows (e.g., publishing unapproved drafts or editing published posts). The state transition matrix guarantees system consistency. |
| **Mandatory Human Approval Gate** | Eliminates autonomous publishing risks. Human review is architected directly into the database schema and API, requiring explicit approval or structured rejection feedback. |
| **Quantitative Citation Verification** | Eliminates AI hallucination in performance reports. If an LLM cites a metric that does not match database snapshots within tolerance ($10^{-5}$), the report is rejected with an HTTP 502 error. |
| **`ChannelAdapter` Publishing Protocol** | Isolates publishing orchestration from social media APIs. Permits safe local simulation via `MockInstagramAdapter` while keeping the door open for real Meta or X adapters without rewriting workflow code. |
| **Workspace-Scoped Multi-Tenancy** | Enforces enterprise boundaries at the query level. Attaching `workspace_id` to campaigns and returning 404 for cross-workspace post queries prevents enumeration attacks. |
| **Native JSON Schema Generation** | Uses Gemini’s `response_schema` mode instead of prompt-based JSON requests, minimizing parsing errors and ensuring all required fields are present. |
| **Non-Storage Media Asset Representation** | Focuses compute on generative copy, structured visual direction, and metadata validation without incurring heavy cloud object storage (S3) dependencies during development. |
| **SQLAlchemy 2.0 Async + asyncpg** | Non-blocking database I/O using Python coroutines. Uses `NullPool` to prevent connection exhaustion in serverless environments. |

---

## Repository Structure

```
chitro/
├── .env.example             # Documented template for environment configuration
├── README.md                # Comprehensive system documentation
├── backend/
│   ├── app/
│   │   ├── adapters/        # Channel adapters (protocol & MockInstagramAdapter)
│   │   ├── ai/              # GeminiProvider, PlatformStrategy, prompt builder
│   │   ├── api/             # FastAPI routers (auth, campaigns, posts, workspaces)
│   │   ├── domain/          # Models, enums, exceptions, state machine
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Domain business logic services
│   │   ├── validation/      # ValidationEngine, InstagramSpec, XSpec, media rules
│   │   ├── config.py        # Environment configuration
│   │   ├── database.py      # Async database connection and session maker
│   │   └── main.py          # FastAPI application factory
│   ├── pyproject.toml       # Backend project metadata
│   ├── requirements.txt     # Locked backend Python dependencies
│   ├── scripts/             # Operational smoke test scripts
│   └── tests/               # 220 automated unit and integration tests
└── frontend/
    ├── package.json         # Frontend dependencies (Next.js 16, React 19)
    ├── tsconfig.json        # TypeScript configuration
    ├── postcss.config.mjs   # PostCSS configuration for Tailwind CSS v4
    └── src/
        ├── app/             # Next.js App Router pages
        │   ├── campaigns/   # Campaigns list, new brief wizard, campaign detail
        │   ├── login/       # User authentication login
        │   ├── register/    # New account registration
        │   ├── globals.css  # CSS custom properties and theme tokens
        │   └── layout.tsx   # Root document layout
        ├── components/      # Reusable UI components
        │   ├── app-shell.tsx# Sidebar, mobile navigation, and user status
        │   ├── auth-form.tsx# Reusable login/register form
        │   └── ui.tsx       # Button, Card, Badge, Input, Textarea, PageHeader
        └── lib/             # Frontend client utilities
            ├── api.ts       # Typed API client for FastAPI endpoints
            └── session.ts   # Client-side session and auth token storage
```

---

## Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+ and `npm`
- PostgreSQL 14+ running locally or accessible via network

### 1. Clone the Repository
```bash
git clone https://github.com/tiyasha-paul/chitro.git
cd chitro
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the repository root:
```bash
cp .env.example .env
```

Edit `.env` to match your local PostgreSQL credentials and Gemini API key:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chitro
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash
AUTH_SECRET_KEY=use-a-secure-random-secret-key-at-least-32-chars-long
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Backend Setup
Create and activate a virtual environment, then install dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run database migrations and start the backend development server:
```bash
# FastAPI automatically runs table creation in its lifespan handler
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
The API documentation is available at `http://localhost:8000/docs`.

Run the backend test suite:
```bash
pytest
```

### 4. Frontend Setup
In a separate terminal, install dependencies and start the Next.js development server:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## Environment Variables Reference

| Variable | Scope | Type | Required | Description | Example / Safe Default |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Backend | String | **Yes** | Async PostgreSQL connection string using `asyncpg`. | `postgresql+asyncpg://user:pass@localhost:5432/chitro` |
| `GEMINI_API_KEY` | Backend | String | **Yes** | Google Gemini API key from Google AI Studio. | `AIzaSy...` |
| `GEMINI_MODEL` | Backend | String | Optional | Target Gemini model name. | `gemini-2.5-flash` |
| `AUTH_SECRET_KEY` | Backend | String | **Yes** | Secret key for signing HS256 JWT bearer tokens. | `change-me-to-a-secure-random-secret` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | Integer | Optional | Lifetime of issued JWT tokens in minutes. | `60` |
| `CORS_ORIGINS` | Backend | String | Optional | Comma-separated list of allowed frontend origins. | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Frontend | String | **Yes** | Base URL of the backend API accessed by the browser. | `http://localhost:8000` |

---

## Deployment Architecture

Chitro is configured for cloud deployment across Render and Vercel:

- **Backend & Database (Render)**:
  - The FastAPI application runs as a Python web service configured with Uvicorn.
  - PostgreSQL is provisioned via Render Managed PostgreSQL. `app/config.py` automatically detects and normalizes `postgres://` URLs into `postgresql+asyncpg://`.
- **Frontend (Vercel)**:
  - The Next.js application deploys natively to Vercel.
  - The `NEXT_PUBLIC_API_URL` environment variable is configured in the Vercel dashboard to point to the production Render backend domain.
- **CORS Configuration**: The backend's `CORS_ORIGINS` environment variable is set to the production Vercel domain to permit cross-origin requests with `Authorization` and `X-Workspace-ID` headers.

---

## End-to-End Demo Walkthrough

1. **Register / Authenticate**: Navigate to `/register`. Creating an account automatically provisions your personal workspace and issues an authenticated session.
2. **Create Campaign Brief**: Click **New Campaign** and complete the brief wizard:
   - Provide a campaign name, objective, target audience, key themes, and preferred CTA.
   - Optionally select a previous campaign to import its saved insights.
3. **Generate Platform Content**: On the campaign detail page, select a platform (**Instagram** or **X**) and language (**বাংলা** or **English**), then click **Generate**.
4. **Deterministic Validation**: The system checks the generated copy against platform rules. If rules pass, the post advances to `PENDING_APPROVAL`.
5. **Human Review**:
   - Inspect the hook, caption, hashtags, CTA, and visual direction.
   - To request changes, click **Reject with feedback**, enter notes, and submit. The post transitions to `REJECTED`. Click **Regenerate** to create a revised attempt addressing your feedback.
   - If satisfied, click **Approve**. The post advances to `APPROVED`.
6. **Schedule or Publish**:
   - Choose a future timestamp and click **Schedule** (`APPROVED` -> `SCHEDULED`), or
   - Click **Mock publish** to trigger publication immediately via `MockInstagramAdapter` (`SCHEDULED` -> `PUBLISHED`).
7. **Record Performance Snapshots**: In the published post card, open the metrics section and record reach, impressions, likes, and comments.
8. **Cross-Platform Comparison**: Publish posts on both Instagram and X to view side-by-side normalized reach and engagement comparisons.
9. **Synthesize Insights**: Click **Generate insight** to extract evidence-backed findings citing specific snapshot IDs.
10. **Generate Evidence-Backed Weekly Report**: In the Weekly Report section, click **Generate weekly report**. The system builds a structured report, deterministically verifies all quantitative citations against database snapshots, and displays the report with an **Evidence checked** badge.
11. **Close the Loop**: When creating your next campaign brief, select this campaign from the dropdown to carry over its insights into future AI prompts.

---

## Current Scope & Limitations

To maintain strict engineering transparency, the following boundaries reflect the codebase's current implementation:

- **Supported Channels**: Content generation and validation rules are implemented exclusively for **Instagram** and **X**.
- **Mock Distribution**: Publishing is simulated through `MockInstagramAdapter`. No live network calls are made to Meta Graph API or X API v2.
- **Visual Direction vs. Binary Assets**: Chitro generates structured creative visual direction (`MediaDirection`) and validates concrete media metadata (`MediaAssetSpec`). It **does not currently generate raw binary JPEG/PNG images or MP4 videos** via diffusion models.
- **Metric Ingestion**: Metric snapshots are recorded via REST API endpoints (`POST /api/posts/{id}/metrics`). Automated webhook listeners or OAuth sync jobs for social platforms are not currently present.

---

## Roadmap

The Chitro architecture is designed to accommodate the following future extensions without breaking domain or workflow contracts:

1. **Generative Image & Video Synthesis**: Implement concrete media generation providers (e.g., Google Imagen on Gemini, video models) that consume `MediaDirection` to output rendered binary assets into cloud object storage.
2. **Production Social Channel Adapters**: Implement production `ChannelAdapter` classes connecting to Meta Graph API (Instagram Business/Creator accounts) and Twitter API v2.
3. **Automated Metrics Sync**: Background workers to poll platform analytics APIs or ingest webhook events to automatically append `MetricSnapshot` records.
4. **Additional Channels**: Introduce `PlatformStrategy` and `PlatformSpec` implementations for LinkedIn, YouTube Community, and Threads.
5. **Cloud Media Storage**: Integrate S3/GCS asset storage adapters with signed URL delivery for generated visual assets.
