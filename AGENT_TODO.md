# AGENT TODO

This file tracks issues and improvements needed across the local-llm-mcp system.

## CRITICAL Priority Issues
*Issues that could cause system failure or security breaches*

- [ ] None currently identified

## HIGH Priority Issues
*Issues that significantly impact functionality or user experience*

- [ ] **Consider a change that allows us to use MCP protocols json rpc methodology to inform claude (or the orchestrator html) when a task has finished**

## MEDIUM Priority Issues
*Issues that should be addressed for production readiness*

- [ ] **Authentication Security Gap**: The MCP server authentication accepts ANY non-empty string as a private key (src/core/security/manager/manager.py:create_session()). This is development-mode only behavior that needs proper key validation before production use.

## LOW Priority Issues
*Nice-to-have improvements and optimizations*

- [ ] **Consider adding some sort of sms notification system to allow remote prompting of the local model**

---
*File maintained by agents and developers - add issues as they are discovered*