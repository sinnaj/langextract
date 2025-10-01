# Information Gain Assessment Tool

This tool computes **Information Gain (IG)** for candidate features extracted from `applies_if` predicates in building code norm extractions. It helps identify which questions (features) are most valuable for determining norm applicability.

## What is Information Gain?

Information Gain measures how much a feature reduces uncertainty about norm applicability. Given a set of norms, each with an `applies_if` predicate:

1. **Base Entropy (H_base)**: Total uncertainty about which norms apply before asking any questions
   - Computed as the sum of binary entropies over all norms: `Σ h(p_norm)`
   - Where `h(p) = -p*log₂(p) - (1-p)*log₂(1-p)` is the binary entropy function
   - `p_norm` is the probability that a norm applies (estimated via Monte-Carlo sampling)

2. **Conditional Entropy (H|F)**: Remaining uncertainty after learning feature F's value
   - Computed as the expected entropy after conditioning on each possible value of F
   - `E[H|F] = Σ_v P(F=v) * H(F=v)`

3. **Information Gain**: Reduction in uncertainty
   - `IG(F) = H_base - E[H|F]`
   - Higher IG means the feature is more informative

4. **IG per Cost**: For practical decision-making, we normalize by cost
   - `IG/Cost = IG(F) / cost(F)`
   - Identifies cost-effective questions

5. **Dismissal Statistics**: Understanding norm filtering power
   - **Max Dismissal Rate**: Fraction of norms dismissed by the best value of this feature
   - **Avg Dismissal Rate**: Average dismissal rate across all values
   - **Best Dismissal Value**: The value that dismisses the most norms
   - A norm is dismissed when it becomes inapplicable (FALSE) given a feature value

## What are Dismissal Statistics?

Dismissal statistics complement Information Gain by showing which feature values actively **filter out** or **dismiss** norms from consideration. This is particularly useful when you want to identify:

- **High-impact filtering features**: Features where selecting certain values eliminates many norms
- **Efficient early filters**: Features that can quickly narrow down the set of applicable norms
- **Value-specific impact**: Which specific values of a feature have the strongest filtering effect

For example, if `PROJECT.TYPE == 'REFORM'` causes 5 out of 10 norms to become inapplicable (FALSE), then:
- `PROJECT.TYPE` would have a dismissal rate of 0.5 (50%) for value `'REFORM'`
- This helps identify that asking about project type early can efficiently filter the norm set

**Key difference from IG**: While IG measures uncertainty reduction, dismissal rate directly measures how many norms become definitively inapplicable.

## Features

- **DSL Parser**: Safe parsing of `applies_if` predicates using Lark
  - Boolean operators: `AND`, `OR`, `NOT`, parentheses
  - Comparisons: `==`, `!=`, `>`, `>=`, `<`, `<=`
  - Membership: `IN [...]`
  - Special functions: `HAS(...)`, geographic scoping

- **Tri-state Evaluator**: Kleene logic for partial assignments
  - Returns `TRUE`, `FALSE`, or `UNKNOWN`
  - Proper propagation: `TRUE AND UNKNOWN → UNKNOWN`, `FALSE AND X → FALSE`

- **Feature Extraction**: Automatic discovery of features and their value spaces
  - Numeric features: Derives bins from thresholds (e.g., `>100`, `>500` → bins `(-∞,100], (100,500], (500,∞)`)
  - Categorical features: Collects observed values from comparisons and `IN` lists

- **Monte-Carlo Sampling**: Estimates probabilities via random sampling
  - Samples feature assignments from priors
  - Evaluates all norms under each sample
  - Computes entropies from empirical frequencies

- **Cost-Aware Ranking**: Balances information value with acquisition cost

- **Dismissal Statistics**: Computes how many norms each feature value dismisses
  - Identifies high-impact filtering features
  - Shows which values eliminate the most norms
  - Complements IG by focusing on definitive filtering rather than uncertainty reduction

## Installation

```bash
cd ig_assessment
pip install -r requirements.txt
```

Dependencies:
- `lark>=1.1.0` - Parser generation
- `pyyaml>=6.0` - YAML support
- `pandas>=1.3.0` - DataFrame manipulation
- `numpy>=1.20.0` - Numerical computing
- `pytest>=7.4.0` - Testing
- `tabulate>=0.9.0` - Pretty tables

## Usage

### Basic Usage

```bash
python compute_ig.py \
  --input enhanced_extraction_results.json \
  --output ig_results.csv \
  --samples 20000 \
  --seed 7
```

### With Custom Costs

Create a `costs.yaml` file:
```yaml
AREA.USAGE: 0.1        # Cheap question
AREA.SIZE: 0.25        # Moderate cost (default)
AREA.OCCUPANCY: 0.5    # More expensive
BUILDING.HEIGHT: 1.0   # Requires measurement
```

Then run:
```bash
python compute_ig.py \
  --input enhanced_extraction_results.json \
  --output ig_results.csv \
  --costs costs.yaml \
  --samples 20000 \
  --seed 7
```

### With Custom Priors

Create a `priors.yaml` file with known probabilities:
```yaml
AREA.USAGE:
  RESIDENTIAL.HOUSING: 0.4
  COMMERCIAL: 0.3
  PARKING: 0.15
  STORAGE: 0.1
  PUBLIC.ASSEMBLY: 0.05

AREA.SIZE:
  0: 0.5    # Bin index 0: (-∞, 100]
  1: 0.3    # Bin index 1: (100, 500]
  2: 0.2    # Bin index 2: (500, ∞)
```

Then run:
```bash
python compute_ig.py \
  --input enhanced_extraction_results.json \
  --output ig_results.csv \
  --priors priors.yaml \
  --samples 20000
```

### With Detailed Report

```bash
python compute_ig.py \
  --input enhanced_extraction_results.json \
  --output ig_results.csv \
  --report ig_report.json \
  --samples 20000
```

The report includes:
- Feature schema (bins and categories)
- Priors used
- Per-norm marginal applicability
- Top 20 features by IG and IG/Cost

### Filtering Features

Include only specific features:
```bash
python compute_ig.py \
  --input data.json \
  --output results.csv \
  --include AREA.USAGE AREA.SIZE BUILDING.TYPE
```

Exclude certain features:
```bash
python compute_ig.py \
  --input data.json \
  --output results.csv \
  --exclude INTERNAL.DEBUG.FLAG
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--input` | Path | Required | Path to enhanced_extraction_results.json |
| `--output` | Path | Required | Path to output CSV file |
| `--samples` | int | 20000 | Number of Monte-Carlo samples |
| `--seed` | int | 7 | Random seed for reproducibility |
| `--costs` | Path | Optional | Path to costs.yaml (default: 0.25 for all) |
| `--priors` | Path | Optional | Path to priors.yaml (default: uniform) |
| `--report` | Path | Optional | Path to JSON report file |
| `--include` | List | Optional | Features to include (whitelist) |
| `--exclude` | List | Optional | Features to exclude (blacklist) |

## Output Format

### CSV Columns

| Column | Description |
|--------|-------------|
| `feature` | Feature name (e.g., `AREA.USAGE`) |
| `base_entropy` | Total entropy before conditioning |
| `expected_entropy` | Expected entropy after conditioning on this feature |
| `IG` | Information Gain: `base_entropy - expected_entropy` |
| `cost` | Cost of acquiring this feature |
| `IG_per_cost` | Cost-normalized IG: `IG / cost` |
| `num_values` | Number of possible values (bins or categories) |
| `numeric` | Boolean: Is this a numeric feature? |
| `categories_or_bins` | String representation of value space |
| `max_dismissal_rate` | Fraction of norms dismissed by the best value (0.0 to 1.0) |
| `avg_dismissal_rate` | Average dismissal rate across all values (0.0 to 1.0) |
| `best_dismissal_value` | The value that dismisses the most norms |

### Example Output

```
Feature                           IG      Cost  IG/Cost  #Values  Numeric?
AREA.USAGE                      2.8503   0.10   28.503      7     False
AREA.SIZE                       1.4251   0.25    5.700      3     True
BUILDING.USAGE                  0.9234   0.10    9.234      5     False
AREA.OCCUPANCY                  0.5123   0.50    1.025      2     True
AREA.FIRE.LOAD_TOTAL_CORRECTED  0.3421   0.25    1.368      2     True
```

**Dismissal Statistics Output:**
```
Feature                         Max Dismissal  Avg Dismissal  Best Value
AREA.USAGE                             0.6667         0.6667  ADMINISTRATIVE
AREA.SIZE                              0.3333         0.1667  ≤100.0
AREA.OCCUPANCY                         0.1667         0.0833  ≤500.0
AREA.FIRE.LOAD_TOTAL_CORRECTED         0.1667         0.0833  ≤3000000.0
```

Interpretation:
- **AREA.USAGE**: Selecting "ADMINISTRATIVE" usage dismisses 66.67% of norms (4 out of 6)
- **AREA.SIZE**: Values ≤100.0 dismiss 33.33% of norms (2 out of 6)
- This helps identify which questions provide the strongest filtering effect

## Example: Toy Dataset

The included test dataset (`tests/data/enhanced_extraction_results.min.json`) contains 6 norms:

1. Parking areas >100m² require fire extinguishers
2. Residential housing requires smoke detectors
3. Storage with high fire load (≥3M) requires sprinklers
4. Public assembly with >500 occupants needs emergency exits
5. Large commercial/education areas (>500m²) require fire alarms
6. All buildings require fire safety plan

Running the tool:
```bash
cd ig_assessment
python compute_ig.py \
  --input tests/data/enhanced_extraction_results.min.json \
  --output /tmp/ig.csv \
  --samples 5000
```

Expected ranking:
1. **AREA.USAGE** (highest IG) - gates 5/6 norms
2. **AREA.SIZE** - gates 2 norms
3. **AREA.OCCUPANCY** - gates 1 norm
4. **AREA.FIRE.LOAD_TOTAL_CORRECTED** - gates 1 norm

## Interpreting Results

### When to Use Information Gain vs. Dismissal Rate

**Use Information Gain when:**
- You want to maximize overall uncertainty reduction
- You need to balance between confirming and dismissing norms
- You want a feature that helps narrow down the applicable norm set efficiently

**Use Dismissal Rate when:**
- You specifically want to identify features that filter out many norms
- You're designing an early filtering stage in a decision tree
- You want to understand which feature values have the strongest negative impact on norm applicability

**Best Practice:** Use both metrics together:
1. Sort by IG to find features that provide the most information
2. Check dismissal rates to understand the filtering power of each feature
3. For early decision stages, prefer high-dismissal features to quickly eliminate inapplicable norms
4. For later stages, prefer high-IG features to refine the remaining norm set

### Example Interpretation

Given this output:
```
Feature         IG     IG/Cost  Max Dismissal  Best Value
PROJECT.TYPE   2.45    9.80     0.50          NEW_CONSTRUCTION
AREA.USAGE     2.30    9.20     0.67          ADMINISTRATIVE
AREA.SIZE      1.20    4.80     0.33          ≤100.0
```

**Interpretation:**
- **PROJECT.TYPE** has the highest IG, making it most informative overall
- **AREA.USAGE** has the highest dismissal rate (67%), meaning certain usage types eliminate 2/3 of norms
- For a questionnaire design:
  1. Ask PROJECT.TYPE first (highest IG, good balance)
  2. Then ask AREA.USAGE (strong filtering for certain values)
  3. Finally ask AREA.SIZE (lower impact, use for refinement)

## Testing

Run the test suite:
```bash
cd ig_assessment
pytest tests/
```

Tests cover:
- **Parser**: All operators, nested parentheses, complex expressions
- **Evaluator**: Tri-state logic truth tables, partial evaluation
- **Feature Schema**: Threshold extraction, bin derivation, categorical values
- **IG Computation**: Entropy calculation, sampling, ranking validation
- **Dismissal Statistics**: Norm filtering, dismissal rate computation

## Testing

Run the test suite:
```bash
cd ig_assessment
pytest tests/
```

Tests cover:
- **Parser**: All operators, nested parentheses, complex expressions
- **Evaluator**: Tri-state logic truth tables, partial evaluation
- **Feature Schema**: Threshold extraction, bin derivation, categorical values
- **IG Computation**: Entropy calculation, sampling, ranking validation
- **Dismissal Statistics**: Norm filtering, dismissal rate computation

## Architecture

```
ig_assessment/
├── compute_ig.py         # Main script (CLI entry point)
├── dsl_parser.py         # Parser for applies_if DSL → AST
├── evaluator.py          # Tri-state evaluator (Kleene logic)
├── feature_schema.py     # Feature extraction and schema building
├── requirements.txt      # Dependencies
├── README.md            # This file
└── tests/
    ├── data/
    │   └── enhanced_extraction_results.min.json  # Toy dataset
    ├── test_parser.py           # Parser tests
    ├── test_evaluator.py        # Evaluator tests
    ├── test_feature_schema.py   # Feature extraction tests
    ├── test_compute_ig.py       # IG computation tests
    └── test_dismissal.py        # Dismissal statistics tests
```

## Algorithm Details

### 1. Parse Phase
- Parse each norm's `applies_if` predicate into an AST
- Handle syntax errors gracefully (skip unparseable norms with warning)

### 2. Feature Discovery
- Traverse all ASTs to collect:
  - Feature names (dotted identifiers)
  - Numeric thresholds from `>`, `>=`, `<`, `<=` comparisons
  - Categorical values from `==` comparisons and `IN` lists
- Derive bins for numeric features from sorted unique thresholds

### 3. Prior Assignment
- If `priors.yaml` provided: load and normalize
- Otherwise: uniform priors with Laplace smoothing (α=1)

### 4. Monte-Carlo Sampling
- For each sample:
  - Draw each feature's value from its prior
  - For numeric features: sample a bin, then pick a representative value within that bin
  - Create a full assignment (all features have concrete values)

### 5. Norm Evaluation
- For each (norm, sample) pair:
  - Evaluate the AST under the assignment
  - Record TRUE/FALSE (UNKNOWN shouldn't occur with full assignments)
- Result: boolean matrix `applicability[n_norms, n_samples]`

### 6. Entropy Computation
- **Base**: `H_base = Σ_i h(p_i)` where `p_i = mean(applicability[i, :])`
- **Conditional**: For each feature F and value v:
  - Filter samples where `F=v` (mask)
  - Recompute entropy over the masked samples
  - Weight by `P(F=v) = fraction_of_samples_matching`
- **IG**: `IG(F) = H_base - E[H|F]`

### 7. Dismissal Statistics Computation
- **For each feature F and value v**:
  - Filter samples where `F=v` (mask)
  - Count how many norms have `applicability[i, mask].sum() == 0`
  - These norms are "dismissed" (never applicable when F=v)
  - Dismissal rate = dismissed_count / total_norms
- **Max Dismissal**: The highest dismissal rate across all values of F
- **Avg Dismissal**: Mean dismissal rate across all values of F
- **Best Value**: The value with the highest dismissal rate

**Key insight**: A norm is dismissed by a feature-value pair when it evaluates to FALSE for all samples with that feature value. This captures how effectively that value filters out norms in practice.

### 8. Ranking
- Sort by `IG / cost` descending
- Also provide ranking by `max_dismissal_rate` descending
- Output tables and CSV

## Performance

- **Target**: <5 seconds for 20k samples and ~1k norms on a laptop
- **Optimizations**:
  - Vectorized operations (NumPy boolean arrays)
  - Parse ASTs once, reuse for all samples
  - Precompute masks for feature values
  - Use efficient binary entropy function

## Limitations & Non-Goals

- **No web access or external API calls**: All computation is local
- **No unsafe `eval()`**: Uses proper parser (Lark)
- **No unit conversion**: Uses thresholds as-is from the DSL
- **Discrete bins for numerics**: Doesn't model continuous distributions
- **Independence assumption**: Features sampled independently (no correlations)

## Troubleshooting

**Problem**: Parser fails on some `applies_if` expressions
- **Solution**: Check for unsupported syntax. The parser supports the DSL spec but may not handle all edge cases. Review the failing expression and adjust or file an issue.

**Problem**: IG values are all very close
- **Solution**: Increase `--samples` for more stable estimates. Try 50k or 100k samples.

**Problem**: Feature X has zero IG but should be important
- **Solution**: Check if priors are realistic. If a feature's prior heavily favors one value, it won't show high IG. Provide custom priors via `--priors`.

**Problem**: Out of memory with large sample counts
- **Solution**: Reduce `--samples` or use filtering (`--include`/`--exclude`) to limit features.

## Contributing

When adding new features:
1. Update the grammar in `dsl_parser.py` if adding DSL syntax
2. Update `evaluator.py` for new evaluation logic
3. Add tests to validate the behavior
4. Update this README with usage examples

## License

Apache 2.0 (same as langextract parent project)

## References

- **Information Gain**: Classic decision tree splitting criterion (Quinlan, 1986)
- **Kleene Logic**: Three-valued logic for partial information (Kleene, 1952)
- **Lark Parser**: https://github.com/lark-parser/lark
