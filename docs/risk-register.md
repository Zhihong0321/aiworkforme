# Risk Register: Eternalgy Migration & Build

This document tracks known risks, their impact on the Masterplan MVP, and mitigation strategies.

## 1. Technical Risks

| Risk ID | Description | Impact | Mitigation |
| --- | --- | --- | --- |
| R-001 | **Tenant Leakage** | High: Data breach across clients. | Implement strict Global Search/Filter overrides at the Repository layer in M1. |
| R-002 | **Policy Bypass** | High: Illegal/Spam outreach. | Centralize all `send` actions through a single `PolicyEngine` decorator in M2. |
| R-003 | **Test Drift** | Med: Regressions in chat logic. | Convert prototype "scenarios" into deterministic unit/integration tests with M0 hardening. |
| R-004 | **UniAPI Reliability** | Med: API downtime. | Implement exponential backoff and alternate regional endpoint strategy in the Provider Layer. |
| R-005 | **Token Cost Overrun** | Med: Margin erosion. | Implement the **RED** cost tier path mapping in M5. |

## 2. Product Risks

| Risk ID | Description | Impact | Mitigation |
| --- | --- | --- | --- |
| P-001 | **Low Conversion Lift** | High: Failure to meet +15% KPI. | Rapid strategy iteration via the `Simulation Bench` in M4. |
| P-002 | **WhatsApp Blocking** | High: Complete service cutoff. | Strict adherence to the Safety Floor (Quiet hours/Outbound caps) in M2. |
| P-003 | **Operator Fatigue** | Med: Low adoption. | Median time-to-action < 60s KPI target for the Inbox page in M6. |

## 3. Implementation Risks

| Risk ID | Description | Impact | Mitigation |
| --- | --- | --- | --- |
| I-001 | **Prototype Dependency** | Med: Legacy code slowing build. | Follow the Extraction Matrix strictly; REWRITE when in doubt rather than REFACTOR. |
| I-002 | **Scope Creep** | Low: Delaying Pilot. | Freeze features at `MASTERPLAN.MD` version 2; all new ideas go to "Post-MVP" log. |
