# Usage Examples

## Basic Usage

### Toy Dataset (Testing)

```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig.csv \
  --samples 5000
```

**Expected Output:**
```
Top 20 features by IG per cost:
Feature                             IG    Cost    IG/Cost    #Values  Numeric?
------------------------------  ------  ------  ---------  ---------  ----------
AREA.USAGE                      1.4700  0.2500     5.8801          8  False
AREA.SIZE                       0.3747  0.2500     1.4988          3  True
AREA.OCCUPANCY                  0.0663  0.2500     0.2652          2  True
AREA.FIRE.LOAD_TOTAL_CORRECTED  0.0639  0.2500     0.2556          2  True
```

### With Custom Costs

Create `costs.yaml`:
```yaml
AREA.USAGE: 0.1        # Quick question
AREA.SIZE: 0.5         # Needs measurement
AREA.OCCUPANCY: 1.0    # Complex calculation
```

Run:
```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig_with_costs.csv \
  --costs costs.yaml \
  --samples 5000
```

### With JSON Report

```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig.csv \
  --report /tmp/ig_report.json \
  --samples 10000
```

The report includes:
- Feature schema (bins and categories)
- Priors used
- Top 20 features by IG and IG/Cost
- Per-norm marginal applicability

### With Custom Priors

Create `priors.yaml`:
```yaml
AREA.USAGE:
  PARKING: 0.2
  RESIDENTIAL.HOUSING: 0.4
  COMMERCIAL: 0.2
  STORAGE: 0.1
  PUBLIC.ASSEMBLY: 0.1

AREA.SIZE:
  0: 0.6    # Bin 0: (-∞, 100]
  1: 0.3    # Bin 1: (100, 500]
  2: 0.1    # Bin 2: (500, ∞)
```

Run:
```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig.csv \
  --priors priors.yaml \
  --samples 10000
```

## Real-World Example

Process actual extraction results:

```bash
python compute_ig.py \
  --input output_runs/1757807061/enhanced_output/enhanced_extraction_results.json \
  --output analysis/ig_results.csv \
  --report analysis/ig_report.json \
  --samples 20000 \
  --seed 42
```

## Feature Filtering

### Include Only Specific Features

```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig_filtered.csv \
  --include AREA.USAGE AREA.SIZE BUILDING.TYPE \
  --samples 5000
```

### Exclude Certain Features

```bash
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig_filtered.csv \
  --exclude DEBUG.FLAG INTERNAL.STATE \
  --samples 5000
```

## Interpreting Results

### CSV Output Columns

- **feature**: Feature name (e.g., `AREA.USAGE`)
- **base_entropy**: Total entropy before any questions
- **expected_entropy**: Expected entropy after learning this feature
- **IG**: Information Gain = base_entropy - expected_entropy
- **cost**: Cost of acquiring this feature
- **IG_per_cost**: Cost-normalized IG (higher is better)
- **num_values**: Number of possible values
- **numeric**: Boolean indicating if numeric feature
- **categories_or_bins**: String representation of value space

### What High IG Means

A feature with high IG significantly reduces uncertainty about which norms apply:

- **AREA.USAGE** with IG=1.47: Learning the area usage (parking, residential, etc.) 
  tells us which 5 out of 6 norms apply
  
- **AREA.SIZE** with IG=0.37: The size threshold (>100, >500) helps determine 
  applicability of 2 norms

### What High IG/Cost Means

Features with high IG per cost are the most cost-effective questions:

- If **AREA.USAGE** has IG=1.47 and cost=0.1, IG/cost=14.7 
  → Very high value question

- If **AREA.OCCUPANCY** has IG=0.06 and cost=1.0, IG/cost=0.06
  → Low value, expensive question

## Performance Tuning

### For Quick Iteration

```bash
python compute_ig.py \
  --input data.json \
  --output results.csv \
  --samples 1000 \
  --seed 42
```

Runtime: ~1-2 seconds for 100 norms

### For Production Analysis

```bash
python compute_ig.py \
  --input data.json \
  --output results.csv \
  --samples 50000 \
  --seed 42
```

Runtime: ~10-20 seconds for 1000 norms

### For Stable Results

Use higher sample counts for:
- More norms (>500)
- More features (>50)
- Features with many values (>10)

Recommended: 20,000-50,000 samples

## Common Workflows

### 1. Initial Exploration

```bash
# Quick scan with default settings
python compute_ig.py \
  --input data.json \
  --output initial_ig.csv \
  --samples 5000
```

### 2. Detailed Analysis

```bash
# Full analysis with costs and report
python compute_ig.py \
  --input data.json \
  --output detailed_ig.csv \
  --costs costs.yaml \
  --report detailed_report.json \
  --samples 20000
```

### 3. Focus on Top Features

```bash
# After initial scan, focus on promising features
python compute_ig.py \
  --input data.json \
  --output focused_ig.csv \
  --include AREA.USAGE BUILDING.TYPE DOOR.TYPE \
  --priors custom_priors.yaml \
  --samples 50000
```

## Troubleshooting

### Issue: Parser Fails on Some Expressions

**Solution**: Check DSL syntax. The parser supports:
- Identifiers: `AREA.USAGE`, `BUILDING.TYPE`
- Operators: `==`, `!=`, `>`, `>=`, `<`, `<=`, `AND`, `OR`, `NOT`
- Membership: `IN ['A','B','C']`
- Special: `HAS(...)`, geographic functions

### Issue: IG Values Too Close

**Solution**: Increase `--samples` to 50,000 or more for stable estimates.

### Issue: Feature Has Zero IG

**Solution**: Check if:
1. Feature doesn't actually gate any norms
2. Prior distribution is too concentrated (99% one value)
3. Feature always has same value in samples

### Issue: Out of Memory

**Solution**: 
1. Reduce `--samples`
2. Use `--include` to limit features
3. Process in batches (filter norms)

## Integration with Pipeline

The IG tool can be integrated into the extraction pipeline:

```bash
# After extraction
python enhanced_lx_runner.py ... 

# Analyze features
python ig_assessment/compute_ig.py \
  --input output_runs/latest/enhanced_output/enhanced_extraction_results.json \
  --output output_runs/latest/analysis/ig_results.csv \
  --report output_runs/latest/analysis/ig_report.json \
  --samples 20000

# Use results to guide manual review or form generation
```
