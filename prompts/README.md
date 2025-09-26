# Prompt Management System

## Overview
All prompts are externalized for maintainability and rapid iteration without touching code.

## Structure
- `agents/` - Agent-specific prompts for different task types
- `tools/` - Tool-related prompts and definitions
- `system/` - System-level prompts for JSON instructions and error handling
- `templates/` - Reusable prompt components
- `debug/` - Debug and development prompts

## Variables
Each prompt can use variables defined in:
1. Global config (`config.yaml`)
2. Category-specific variables
3. Runtime variables passed to format_prompt()

Variables are substituted using Python's `.format()` syntax: `{variable_name}`

## Adding New Prompts
1. Create file in appropriate directory with `.txt`, `.json`, or `.md` extension
2. Document variables in the category section of `config.yaml`
3. Add test case if complex logic
4. Update this README if needed

## Model-Specific Adaptations
System prompts can be adapted for different models by using model-specific variables or separate files.

## Development
- Use `PromptManager.clear_cache()` to reload prompts during development
- Use `PromptValidator` to check for missing variables
- Variables missing at runtime will return unformatted prompt with error logging