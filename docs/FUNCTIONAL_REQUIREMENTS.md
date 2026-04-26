# Functional Requirements

Specification document for AGENT_USER_STATUS module.

## Overview

This document enumerates the functional requirements that guide implementation, testing, and
quality validation for this project. Each FR has an assigned identifier for cross-reference
in tests, PRs, and architectural documentation.

## Functional Requirements

### FR-AGENT_USER_STATUS-002

**Description:** HTTP/REST API endpoints

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-004

**Description:** Caching layer with TTL support

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-001

**Description:** CLI interface and command dispatch

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-009

**Description:** Configuration management

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-006

**Description:** Persistent data storage

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-005

**Description:** Event streaming and pub/sub

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-010

**Description:** Monitoring and observability

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

### FR-AGENT_USER_STATUS-011

**Description:** Structured agent-to-user message envelopes with sender/session/task/project metadata

**Status:** IMPLEMENTED

**Test Traces:** `tests/unit/test_agent_imessage_envelope.py`, `tests/unit/test_agent_imessage_recipients.py`, `tests/unit/test_agent_imessage_mcp.py`

---

### FR-AGENT_USER_STATUS-012

**Description:** User-side echo cleanup and deletion lifecycle for agent-sent Messages/iMessage artifacts

**Status:** PARTIAL

**Test Traces:** `tests/unit/test_agent_imessage_outbox.py`, `tests/unit/test_agent_imessage_recipients.py`

---

### FR-AGENT_USER_STATUS-013

**Description:** Elicitation schemas for multi-question and multi-answer prompts using stable A1/A2/A3 option IDs

**Status:** IMPLEMENTED

**Test Traces:** `tests/unit/test_agent_imessage_elicitation.py`, `tests/unit/test_agent_imessage_recipients.py`, `tests/unit/test_agent_imessage_mcp.py`

---

### FR-AGENT_USER_STATUS-014

**Description:** Async communication queue with delivery receipts, response correlation, retries, and expiration

**Status:** PARTIAL

**Test Traces:** `tests/unit/test_agent_imessage_outbox.py`

---

### FR-AGENT_USER_STATUS-015

**Description:** Codex experimental hook integration for lifecycle events, permission/tool telemetry, and stop decisions

**Status:** IMPLEMENTED

**Test Traces:** `tests/unit/test_codex_hooks.py`

---

### FR-AGENT_USER_STATUS-016

**Description:** Stop-hook performance hardening with bounded state reads, rotation, caching, and degradation backoff

**Status:** PARTIAL

**Test Traces:** `tests/unit/test_jsonl_tail.py`

---

### FR-AGENT_USER_STATUS-007

**Description:** User interface components

**Status:** SCAFFOLD

**Test Traces:** (pending implementation)

---

## Traceability

All tests MUST reference at least one FR using this marker:

```rust
// Traces to: FR-<REPOID>-NNN
#[test]
fn test_feature_name() { }
```

Every FR must have at least one corresponding test. Use the pattern above to link test to requirement.
