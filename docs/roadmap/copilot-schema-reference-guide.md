# Copilot Schema Reference Guide

This guide provides the primary documentation links for the schemas used by major Copilot and Agent platforms. These are the formats your `brimley manifest` (v0.9) will likely need to export or align with.

## 1. Microsoft 365 Copilot (Extensibility)

Microsoft uses a combination of "Declarative Agent" manifests and API manifests to define how a Copilot interacts with external tools.

- **Declarative Agent Manifest:** [Documentation Link](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/overview-declarative-agent "null")
    
    _Overview: Defines the high-level personality and instructions of the agent._
    
- **API Manifest for Copilot:** [Documentation Link](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api-manifest "null")
    
    _Overview: The specific YAML/JSON schema that describes your endpoints to Microsoft 365._
    

## 2. The Foundation: OpenAPI Specification (OAS)

Almost all agentic platforms (OpenAI GPTs, Microsoft Copilot, LangChain) ingest OpenAPI files to understand "Tools."

- **OpenAPI 3.1.0 Specification:** [Documentation Link](https://www.openapis.org/ "null")
    
- **Tool-Calling (OpenAI/JSON Schema):** [Documentation Link](https://platform.openai.com/docs/guides/function-calling "null")
    
    _Note: OpenAI specifically uses a subset of JSON Schema for "Function Calling."_
    

## 3. GitHub Copilot Extensions

GitHub's ecosystem uses a specific manifest to define "Agentic" extensions within the IDE.

- **GitHub Copilot Extension Manifest:** [Documentation Link](https://docs.github.com/en/copilot/building-copilot-extensions/about-building-copilot-extensions "null")
    

## 4. How Brimley Maps to These

Your current Brimley definitions map almost 1:1 to these standards:

|   |   |
|---|---|
|**Brimley Concept**|**Copilot Schema Equivalent**|
|`name`|`operationId` (OpenAPI)|
|`description`|`description` (OpenAPI/Tool definition)|
|`return_shape`|`components/schemas` (JSON Schema)|
|`mcp: type: tool`|`function` / `tool` (OpenAI/MCP Tool)|
|`entities/`|`definitions` (JSON Schema)|

## Summary for v0.9 "Manifest" Feature

When building the `brimley manifest` command, the goal should be to transform your internal `Registry` into a **valid OpenAPI 3.1 spec** accompanied by a **Microsoft API Manifest**, as these two combined cover roughly 90% of the agentic market.