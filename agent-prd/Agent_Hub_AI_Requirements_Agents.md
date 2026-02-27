# Agent Hub — AI Requirements Agents

## Context & Scenario

The target user is a **Technical Program Manager (TPM)** working on AI use cases within a large enterprise engagement. She frequently receives business requirements from customers and must translate them into clear, structured AI requirements that applied scientists, engineers, and user researchers can act on.

This translation process typically involves:

- Clarifying vague or broad business objectives
- Collaborating with cross-functional partners (applied scientists, user researchers, engineers)
- Breaking down business needs into AI-specific requirements
- Defining required models, inputs, outputs, constraints, and success criteria

The agents below are designed to support the TPM through each stage of this workflow — from raw business input to a reviewed AI requirements document.

---

## Agent Summary

| # | Agent | Key | Emoji | Role |
|---|-------|-----|-------|------|
| 1 | Business Objectives Clarifier | `biz_clarifier` | 🎯 | Extracts structured business objectives from vague customer input |
| 2 | Applied Scientist Advisor | `science_advisor` | 🧪 | Advises on AI/ML feasibility, model approaches, and evaluation |
| 3 | User Research Advisor | `ux_advisor` | 🔬 | Surfaces user-centered requirements and acceptance criteria |
| 4 | Engineering Advisor | `eng_advisor` | ⚙️ | Assesses technical feasibility and system constraints |
| 5 | AI Requirements Writer | `ai_req_writer` | 📝 | Drafts the structured AI requirements document |
| 6 | Requirements Reviewer | `req_reviewer` | 🔍 | Red-teams the draft for gaps, ambiguities, and blind spots |

All agents belong to `category: "professional"` and map to the existing `CustomAgent` model (`key`, `label`, `emoji`, `description`, `system_prompt`, `category`, `is_default`).

---

## Agent Definitions

### 1. 🎯 Business Objectives Clarifier (`biz_clarifier`)

**Description:** Business objectives · Stakeholder alignment · Requirements structuring

Helps the TPM extract clear, structured business objectives from raw or vague customer input. Acts as the first filter: turns an ambiguous ask into a crisp problem statement before any AI-specific work begins.

**Responsibilities:**

- Probe for missing context: who is the end user, what problem are they solving, what does success look like
- Identify the key stakeholders and their competing priorities
- Decompose broad requests into discrete, scoped objectives
- Define measurable business outcomes (KPIs, OKRs) tied to each objective
- Flag ambiguities, conflicting goals, or unstated assumptions
- Produce a structured **Business Objectives Brief** as output

---

### 2. 🧪 Applied Scientist Advisor (`science_advisor`)

**Description:** AI/ML feasibility · Model selection · Evaluation methodology

Represents the applied scientist's perspective. Advises the TPM on whether a business problem is solvable with AI, what approaches are viable, and what data and evaluation infrastructure are needed.

**Responsibilities:**

- Assess whether the business objective is a good fit for an AI/ML solution
- Suggest candidate model approaches (e.g., classification, NER, generative, retrieval-augmented) with trade-offs
- Identify data requirements: volume, quality, labeling needs, availability
- Recommend evaluation methodology and metrics (precision, recall, NDCG, human evaluation, etc.)
- Flag known limitations, failure modes, and bias risks for proposed approaches
- Clarify the boundary between what the model can and cannot do

---

### 3. 🔬 User Research Advisor (`ux_advisor`)

**Description:** User needs · Personas · Acceptance criteria · Usability risks

Represents the user researcher's lens. Ensures that AI requirements are grounded in real user problems and that the resulting feature will be usable and trustworthy from the end-user's perspective.

**Responsibilities:**

- Define user personas and segments affected by the AI feature
- Map the user journey: where does the AI feature fit, what precedes and follows it
- Articulate user-facing acceptance criteria (not just model metrics)
- Surface usability risks: explainability, trust, error recovery, user control
- Identify where user research is needed before committing to requirements
- Highlight edge cases in user behavior that the AI solution must handle

---

### 4. ⚙️ Engineering Advisor (`eng_advisor`)

**Description:** Technical feasibility · System integration · Infrastructure constraints

Provides the engineering perspective. Reviews proposed AI requirements for buildability, integration complexity, and operational readiness.

**Responsibilities:**

- Assess system integration points: where does the model plug into the existing architecture
- Identify infrastructure needs: compute, storage, serving layer, CI/CD for ML
- Define non-functional constraints: latency, throughput, availability, cost budget
- Flag deployment considerations: model versioning, A/B testing, rollback, monitoring
- Surface dependencies on other teams, services, or data pipelines
- Call out requirements that are underspecified from an implementation standpoint

---

### 5. 📝 AI Requirements Writer (`ai_req_writer`)

**Description:** Requirements synthesis · Document drafting · Structured output

Synthesizes all gathered input — from the clarifier, the three advisors, and the TPM's own context — into a structured AI requirements document ready for stakeholder review.

**Responsibilities:**

- Produce a document with standard sections:
  - Problem Statement
  - Business Objectives (from Clarifier)
  - Proposed AI Approach (from Science Advisor)
  - User Context & Acceptance Criteria (from UX Advisor)
  - Inputs and Outputs
  - Model Requirements & Constraints
  - Infrastructure & Integration Notes (from Engineering Advisor)
  - Success Criteria (business + model + user metrics)
  - Open Questions & Risks
- Ensure consistency and traceability across sections
- Write in clear, stakeholder-readable language (not just technical jargon)
- Flag sections that lack sufficient input and need further discussion

---

### 6. 🔍 Requirements Reviewer (`req_reviewer`)

**Description:** Gap analysis · Assumption challenging · Cross-functional review

Red-teams the draft AI requirements document. Acts as the final quality gate before the TPM shares the document with stakeholders.

**Responsibilities:**

- Identify gaps: missing inputs, undefined edge cases, unaddressed failure modes
- Challenge assumptions: is the data actually available? Is the latency target realistic?
- Verify that success criteria are testable and measurable
- Check cross-functional alignment: do science, engineering, and UX sections tell a coherent story
- Flag scope risks: requirements that are too broad, too vague, or too ambitious for the timeline
- Suggest specific questions or follow-ups the TPM should raise with stakeholders

---

## Recommended Workflow

The agents support a sequential workflow that mirrors how a TPM naturally collaborates with cross-functional partners:

```
Raw Business Input
       │
       ▼
┌──────────────────────┐
│  🎯 Biz Clarifier    │  ← Structure the business ask
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  🧪 Science  ·  🔬 UX  ·  ⚙️ Eng       │  ← Cross-functional input
│        (Round Table mode)                │     (parallel or sequential)
└──────────────────┬───────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  📝 AI Req Writer│  ← Draft the document
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  🔍 Reviewer     │  ← Red-team the draft
         └────────┬────────┘
                  │
                  ▼
        Final AI Requirements
```

**Usage notes:**

- **Step 1 — Clarify:** The TPM pastes raw customer input (email, meeting notes, brief). The Clarifier structures it into a Business Objectives Brief.
- **Step 2 — Advise:** The three advisor agents can be engaged in **Round Table mode** so each contributes their domain perspective on the same objectives simultaneously. Alternatively, the TPM can consult them one at a time in **Focused mode** via `@science_advisor`, `@ux_advisor`, `@eng_advisor`.
- **Step 3 — Draft:** The Writer synthesizes the full conversation into a structured AI requirements document using the **Generate Output** capability.
- **Step 4 — Review:** The Reviewer challenges the draft and surfaces gaps. The TPM iterates as needed.

---

## Mapping to Data Model

Each agent maps directly to the existing `CustomAgent` model:

| Field | Value Pattern |
|-------|---------------|
| `key` | Unique slug (e.g., `biz_clarifier`, `science_advisor`) |
| `label` | Display name (e.g., "Business Objectives Clarifier") |
| `emoji` | Single emoji identifier |
| `description` | Short tagline (3–5 words separated by ` · `) |
| `system_prompt` | Detailed persona and behavioral instructions (to be defined during implementation) |
| `category` | `"professional"` for all agents in this set |
| `is_default` | `True` — shipped with the app, non-deletable |

No new data models or orchestrator changes are required. These agents use the existing `CustomAgentRunner` execution path and are compatible with all current workroom modes (Open, Round Table, Focused).
