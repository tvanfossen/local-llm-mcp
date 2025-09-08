# Local LLM MCP Server - Self-Maintenance Workflow

## Overview

This repository is designed to maintain itself using the local LLM through MCP tools. The workflow leverages:
- **Schema validation hooks** for structural consistency
- **Jinja2 templates** for code generation standardization
- **Co-located tests** for immediate validation
- **Bite-sized contexts** optimized for local model consumption
- **MCP tool exposure** to the local model, server, and HTML interface
- **Unified validation tool** for comprehensive testing

## Self-Maintenance Architecture

### Core Principle: Local Model as Primary Worker
- **Claude Code**: High-level orchestration, planning, and validation
- **Local Model**: Implementation, code generation, and detailed work
- **Schema Enforcement**: Automated validation via pre-commit hooks
- **Template System**: Consistent code generation patterns
- **MCP Tools**: All operations exposed as MCP tools for both external clients and local model

### Workflow Components

#### 1. Schema Validation Pipeline
```bash
# Pre-commit validation
python3 scripts/schema_validator.py

# Template compliance check
python3 scripts/template_validator.py  # To be created

# Test discovery and execution
pytest src/ --tb=short

# Or use the unified MCP tool
# Tool: run_all_validations
