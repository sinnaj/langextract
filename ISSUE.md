# Implement schema constraints for OpenAI (#59)

### Description

Currently, LangExtract supports schema-constrained extraction with the use_schema_constraints option, but this feature is not available when using OpenAI models (via the openai backend) unless fence_output=True. However, OpenAI now provides official support for JSON schema, allowing structured output without relying on output fencing. Support for YAML formatting is not available via OpenAI's JSON schema mechanism.

### Feature Request

Enable the use of use_schema_constraints=True with fence_output=False when leveraging OpenAI models, but restrict this functionality to cases where FormatType.JSON is used. If users select FormatType.YAML, the schema constraint option should remain unavailable or raise a clear exception.

### Acceptance Criteria

- When using `language_model_type` for `OpenAILanguageModel` (e.g., "gpt-4o" or "o4-mini"), and `FormatType.JSON`, allow use_schema_constraints=True` with `fence_output=False`.
- When `FormatType.YAML` is specified with OpenAI models, do not enable schema constraints, and provide an explicit error message or fallback.
- Update documentation, tests and error messaging to clarify this limitation and the newly supported use case for OpenAI.

### References/Related Work
- Existing Gemini output schema enforcement implementation.
- Possibility to leverage libraries like `pydantic` for runtime validation.
