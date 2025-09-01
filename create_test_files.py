import json
import random

# Create a large JSON file to test preview performance
large_data = []
for i in range(5000):
    large_data.append({
        "id": i,
        "name": f"item_{i}",
        "description": f"This is a test item with id {i}. " * 10,
        "timestamp": f"2024-01-{(i % 30) + 1:02d}T10:00:00Z",
        "categories": [f"cat_{j}" for j in range(i % 5)],
        "metadata": {
            "score": random.uniform(0, 100),
            "active": random.choice([True, False]),
            "nested": {
                "level1": f"value_{i}",
                "level2": {
                    "data": list(range(i % 10))
                }
            }
        }
    })

# Write large JSON file
with open("output_runs/test_performance/large_output.json", "w") as f:
    json.dump(large_data, f, indent=2)

# Create a large text file 
with open("output_runs/test_performance/large_log.txt", "w") as f:
    for i in range(10000):
        f.write(f"[{i:06d}] This is log line {i} with some sample data and timestamps 2024-01-01T{(i%24):02d}:00:00Z\n")

# Create a moderate size markdown file
with open("output_runs/test_performance/documentation.md", "w") as f:
    f.write("# Large Documentation File\n\n")
    for i in range(500):
        f.write(f"""
## Section {i}

This is section {i} of the documentation. It contains various information about the system.

### Subsection {i}.1

Here's some code:

```python
def function_{i}():
    return "This is function {i}"
    
class Class{i}:
    def __init__(self):
        self.value = {i}
```

### Subsection {i}.2

And here's some more text with lists:

- Item 1 for section {i}
- Item 2 for section {i}
- Item 3 for section {i}

""")

# Create run_input.json for the test run
run_input = {
    "RUN_ID": "test_performance",
    "MODEL_ID": "test-model",
    "MODEL_TEMPERATURE": "0.15",
    "MAX_NORMS_PER_5K": "10",
    "MAX_CHAR_BUFFER": "5000",
    "EXTRACTION_PASSES": "2",
    "INPUT_PROMPTFILE": "",
    "INPUT_GLOSSARYFILE": "",
    "INPUT_EXAMPLESFILE": "",
    "INPUT_SEMANTCSFILE": "",
    "INPUT_TEACHFILE": ""
}

with open("output_runs/test_performance/run_input.json", "w") as f:
    json.dump(run_input, f, indent=2)

print("Test files created successfully!")
