id: {{ MODULE_ID }}
name: {{ MODULE_NAME }}
maturity: experimental
levels: [beginner]
disciplines:
  - life-sciences
inputs:
  - name: outcome
    kind: numeric-column
    required: true
    description: The numeric column you want to analyse (replace this with the real input).
    constraints: must be a numeric column
parameters:
  - name: alpha
    type: number
    default: 0.05
    min: 0.001
    max: 0.5
    description: Significance level.
outputs:
  - a results table
  - an optional figure
  - methods.txt paragraph
  - report.html
assumptions:
  - State the assumptions your analysis relies on here.
  - Quote any scalar value that contains a colon followed by a space, or YAML will parse it as a mapping.
limitations:
  - State the limitations / what this does not imply here.
test_data:
  - "Deterministic synthetic data in tests/test_{{ MODULE_ID }}.py, with
     hand-computed answers compared against a reference implementation."