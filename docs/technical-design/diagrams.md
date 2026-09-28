# Creator Helper Studio — Architecture and Use-Case Diagrams

All diagrams use Mermaid and can be rendered in GitHub, GitLab, Mermaid Live, or compatible documentation tools.

## 1. System architecture

~~~mermaid
flowchart LR
    Browser[Next.js Browser App]
    Auth[Firebase Authentication]
    API[FastAPI API on Cloud Run]
    FS[(Firestore)]
    GCS[(Cloud Storage)]
    PubSub{{Pub/Sub}}
    Workers[Cloud Run Workers and Jobs]
    Gemini[Gemini on Agent Platform]
    STT[Speech-to-Text V2]
    BQ[(BigQuery)]
    Social[YouTube / Meta APIs]
    Translate[Translation / Text-to-Speech]

    Browser --> Auth
    Browser --> API
    Browser -->|direct upload| GCS
    API --> FS
    API --> GCS
    API --> PubSub
    GCS -->|object finalized| PubSub
    PubSub --> Workers
    Workers --> STT
    Workers --> Gemini
    Workers --> GCS
    Workers --> FS
    Workers --> BQ
    Workers --> Social
    Workers --> Translate
    API --> BQ
~~~

## 2. Authentication and onboarding

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Next.js App
    participant Auth as Firebase Auth
    participant API as FastAPI API
    participant FS as Firestore
    participant GCS as Cloud Storage

    User->>UI: Open website
    UI->>Auth: Sign in with Google/email
    Auth-->>UI: Firebase ID token
    UI->>API: GET /me with token
    API->>FS: Read users/uid
    alt First login
        API-->>UI: onboardingCompleted=false
        User->>UI: Answer creator questions
        UI->>API: PUT /onboarding
        UI->>API: POST /onboarding/complete
        API->>GCS: Write persona.md
        API->>FS: Save user and persona metadata
        API-->>UI: Onboarding complete
    else Returning user
        API-->>UI: Existing profile and persona version
    end
~~~

## 3. Connect a social platform and sync data

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Settings UI
    participant API as FastAPI API
    participant OAuth as YouTube or Meta OAuth
    participant Secret as Secret Manager and KMS
    participant PubSub as Pub/Sub
    participant Worker as Social Sync Worker
    participant Platform as Platform API
    participant GCS as Cloud Storage
    participant BQ as BigQuery
    participant Gemini as Gemini Sentiment Flow

    User->>UI: Click Connect YouTube
    UI->>API: POST /connections/youtube/oauth/start
    API-->>UI: Authorization URL
    UI->>OAuth: User grants access
    OAuth-->>API: OAuth callback with code
    API->>OAuth: Exchange code for tokens
    API->>Secret: Store encrypted token reference
    API->>PubSub: Publish social.sync.requested
    PubSub->>Worker: Deliver sync job
    Worker->>Platform: Fetch posts and analytics
    Worker->>Platform: Fetch comments
    Worker->>GCS: Store raw JSON
    Worker->>BQ: Load normalized posts, metrics, comments
    Worker->>Gemini: Classify comment sentiment
    Gemini-->>Worker: Sentiment labels
    Worker->>BQ: Write comment_sentiment
    Worker->>API: Mark sync complete
    UI->>API: Read sync status
~~~

## 4. Create project and upload video

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Project UI
    participant API as FastAPI API
    participant FS as Firestore
    participant GCS as Cloud Storage
    participant PubSub as Pub/Sub
    participant Worker as Transcribe Worker

    User->>UI: Create project
    UI->>API: POST /projects
    API->>FS: Create project document
    API-->>UI: projectId
    User->>UI: Select video
    UI->>API: POST /projects/projectId/upload-session
    API->>FS: Create pending asset
    API-->>UI: Short-lived upload URL
    UI->>GCS: Upload video directly
    UI->>API: POST /assets/assetId/complete (authoritative for UX)
    API->>FS: Mark asset uploaded, project processing
    GCS->>PubSub: object finalized notification
    PubSub->>Worker: video.uploaded
    Worker->>FS: Create transcribe job (idempotent)
    UI->>API: Subscribe to project events (WebSocket /api/ws)
~~~

## 5. Transcription and captions

~~~mermaid
flowchart TD
    A[video.uploaded] --> B[Create transcribe job]
    B --> C[Read video from Cloud Storage]
    C --> D[Speech-to-Text V2]
    D --> E[Word timestamps]
    E --> F[Segment into sentences and paragraphs]
    F --> G[Generate VTT and SRT captions]
    G --> H[Write transcript JSON and captions]
    H --> I[Write metadata and segments to Firestore]
    I --> J[Publish transcript.ready]
    J --> K[Update project status]
~~~

## 6. Multi-reviewer analysis and heatmap

~~~mermaid
flowchart TD
    A[transcript.ready] --> B[Create analysis run]
    B --> C[Load persona, transcript and target platform]
    C --> D{Run reviewers in parallel}
    D --> T[Truth and Evidence]
    D --> CL[Clarity]
    D --> ST[Structure and Pacing]
    D --> CU[Cultural and Localization]
    D --> PL[Platform Fit]
    D --> SEO[SEO and Discoverability]
    D --> LS[Legal and Safety]
    D --> AR[Audience Retention]
    D --> AC[Accessibility]
    D --> BV[Brand Voice]
    T --> V[Validate JSON schemas]
    CL --> V
    ST --> V
    CU --> V
    PL --> V
    SEO --> V
    LS --> V
    AR --> V
    AC --> V
    BV --> V
    V --> N[Normalize timestamps and severity]
    N --> H[Aggregate findings into heatmap bins]
    H --> S[Store findings and bins]
    S --> R[analysis.ready]
    R --> UI[Timeline heatmap UI]
    R --> Q{High or critical finding, or user clicks Deep Review}
    Q --> M[FFmpeg extract clip and frames]
    M --> V2[Gemini multimodal deep review]
    V2 --> S
~~~

## 7. Deep review of a selected segment

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Timeline UI
    participant API as FastAPI API
    participant Media as FFmpeg Cloud Run Job
    participant GCS as Cloud Storage
    participant Agent as Visual and Transcript Reviewer

    User->>UI: Click Deep Review on a finding
    UI->>API: POST segment-review with startMs and endMs
    API->>Media: Extract clip and representative frames
    Media->>GCS: Write temporary segment assets
    Media-->>API: Segment asset references
    API->>Agent: Send transcript, frames and clip context
    Agent-->>API: Detailed structured finding
    API->>GCS: Store detailed result
    API-->>UI: Return review job
    UI->>API: Poll or receive completion event
~~~

## 8. Generate short-form clips

~~~mermaid
flowchart LR
    A[Project transcript] --> B[Short candidate agent]
    B --> C[Candidate timestamps and hook]
    C --> D[User selects candidate]
    D --> E[Create clip job]
    E --> F[FFmpeg trim]
    F --> G[Convert to 9:16]
    G --> H[Generate and burn captions]
    H --> I[Optional intro or outro]
    I --> J[Write MP4 to Cloud Storage]
    J --> K[Create artifact document]
    K --> L[Display preview and download]
~~~

## 9. Caption localization and dubbing

~~~mermaid
flowchart TD
    A[Source transcript] --> B[Segment into translatable units]
    B --> R[Retrieve global corpus + trap list + project glossary]
    R --> C[Translate with Cloud Translation Advanced glossary]
    C --> D[Gemini cultural adaptation grounded on retrieved entries]
    D --> E[Generate localized VTT and SRT]
    D --> F[Generate localized speech with Text-to-Speech]
    F --> G[Normalize audio duration]
    G --> H[Mux audio and video with FFmpeg]
    E --> I[Caption artifact]
    H --> J[Dubbed video artifact]
    I --> K[User review and flag wrong phrases]
    J --> K
    K --> L[Candidate corpus entry for review]
~~~

## 10. Thumbnail generation and critique

~~~mermaid
flowchart TD
    A[Transcript and project topic] --> B[Extract key frames]
    B --> C[Thumbnail concept agent]
    C --> D[Three concepts and text overlays]
    D --> E[Image generation model]
    E --> F[Store thumbnail variants]
    F --> G[User chooses or regenerates]
    H[Existing user thumbnail] --> I[Thumbnail critique agent]
    I --> G
~~~

## 11. Text-based promotion content

~~~mermaid
flowchart LR
    A[Transcript, persona and audience data] --> B[Content generation request]
    B --> C{Requested output}
    C --> X[X post]
    C --> IG[Instagram caption or story poll]
    C --> Y[YouTube community post]
    C --> L[LinkedIn post]
    C --> M[Medium or newsletter outline]
    X --> S[Validate platform constraints]
    IG --> S
    Y --> S
    L --> S
    M --> S
    S --> A1[Store artifact]
    A1 --> UI[Artifact gallery]
~~~

## 12. Veo intro and outro generation

~~~mermaid
sequenceDiagram
    actor User
    participant UI
    participant API
    participant Veo as Vertex AI video generation
    participant GCS as Cloud Storage
    participant Media as FFmpeg Job

    User->>UI: Request intro or outro
    UI->>API: POST artifact type=veo_intro
    API->>Veo: Submit prompt and duration
    Veo-->>API: Generated video reference
    API->>GCS: Store generated segment
    API->>Media: Optional mux request
    Media->>GCS: Write final short
    API-->>UI: Artifact ready
~~~

## 13. Project chat

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Project Chat
    participant API as FastAPI
    participant FS as Firestore
    participant Context as Context Builder
    participant Agent as ADK Project Agent
    participant Tools as Project Tools

    User->>UI: Ask project question
    UI->>API: POST chat message
    API->>FS: Save user message
    API->>Context: Load persona, transcript, findings, artifacts
    Context-->>Agent: Project context pack
    Agent->>Tools: Optional tool call
    Tools-->>Agent: Project data or generated artifact
    Agent-->>API: Stream response and citations
    API->>FS: Save assistant message
    API-->>UI: Stream response
~~~

## 14. Persona update through usage

~~~mermaid
flowchart TD
    A[User edits or rejects suggestions] --> B[Collect explicit preference signal]
    C[Approved chat preference] --> B
    D[Repeated artifact choices] --> B
    B --> E[Persona update agent]
    E --> F[Generate proposed Markdown diff]
    F --> G{User approves?}
    G -- Yes --> H[Write new persona version]
    G -- No --> I[Discard proposal]
    H --> J[Create persona revision record]
~~~

## 15. Account deletion

~~~mermaid
flowchart TD
    A[User requests deletion] --> B[Require re-authentication]
    B --> C[Disable new jobs]
    C --> D[Revoke platform connections]
    D --> E[Delete Firestore user subtree]
    E --> F[Delete Cloud Storage objects]
    F --> G[Delete BigQuery rows by ownerUid]
    G --> H[Delete Firebase Auth user]
    H --> I[Write deletion audit result]
~~~

## 16. Provider layer

~~~mermaid
flowchart TD
    A[Worker or agent] --> B[Provider interface]
    B --> C[Real GCP service]
    C --> D[Response]
    D --> E[Return to caller]
~~~

Feature code never imports a Google SDK directly; every external call goes through a provider in
`app/providers/`. The earlier cassette/`MOCK_MODE` layer was removed (see backend-plan section 16).

## 17. Seed and demo scenarios

~~~mermaid
flowchart LR
    A[seed.py --demo] --> B[Firebase Auth demo users]
    A --> C[GCS demo videos]
    A --> D[Firestore projects, transcripts, analyses, artifacts]
    A --> E[BigQuery posts, metrics, comments, sentiment]
    A --> F[Fixtures and seed data]
    B --> G[Frontend renders full workspace]
    C --> G
    D --> G
    E --> G
    F --> G
~~~

