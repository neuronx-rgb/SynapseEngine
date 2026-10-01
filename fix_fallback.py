import re

with open("backend/llm.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the fallback block
old_fallback = """    logger.error(f"All LLM providers failed. Last error: {last_error}. Returning empty result.")
    try:
        return schema.model_validate({"issues": []})
    except Exception:
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")"""

new_fallback = """    logger.error(f"All LLM providers failed. Last error: {last_error}. Returning empty result.")
    schema_name = schema.__name__
    try:
        if schema_name == "ParseResult":
            return schema.model_validate({"requirements": []})
        elif schema_name == "LLMIssueList":
            return schema.model_validate({"issues": []})
        elif schema_name == "OpenAPIGenerateResult":
            return schema.model_validate({"yaml_content": "", "source_req_ids": []})
        elif schema_name == "SQLGenerateResult":
            return schema.model_validate({"ddl_content": "", "source_req_ids": []})
        elif schema_name == "TestPlanResult":
            return schema.model_validate({"test_cases": []})
        else:
            return schema.model_validate({"issues": []})
    except Exception:
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")"""

content = content.replace(old_fallback, new_fallback)

with open("backend/llm.py", "w", encoding="utf-8") as f:
    f.write(content)
