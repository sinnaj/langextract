import sys
import types
import langextract as lx  # ensure available to the examples code

def load_examples_from_string(examples_py: str):
    """
    Execute a Python module from a string and return the EXAMPLES constant.
    Also registers the module as 'le_examples' so you can import it elsewhere if needed.
    """
    mod = types.ModuleType("le_examples")
    # Pre-inject 'lx' so the examples code can use it even if it doesn't import.
    mod.dict["lx"] = lx
    # Optional: expose builtins (usually already available)
    mod.dict["builtins"] = builtins

    code = compile(examples_py, "le_examples.py", "exec")
    exec(code, mod.dict)

    examples = mod.dict.get("EXAMPLES")
    if not isinstance(examples, list):
        raise ValueError("EXAMPLES not found or not a list in provided examples_py string.")

    # Make importable if desired: from le_examples import EXAMPLES
    sys.modules["le_examples"] = mod
    return examples

# Example usage inside your worker:
# EXAMPLES = load_examples_from_string(payload["EXAMPLES_PY"])