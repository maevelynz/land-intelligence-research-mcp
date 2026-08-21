# Agent Evaluation

The MCP layer should be evaluated as a research assistant, not merely by whether it returns syntactically valid JSON.

## Evaluation dimensions

| Dimension | Pass condition |
|---|---|
| Tool selection | Chooses a governed tool appropriate to the user's question |
| Metric fidelity | Does not redefine optionality, current-use value, or conversion |
| Scope discipline | Distinguishes synthetic results from empirical claims |
| Citation of limitations | Surfaces material limitations when a conclusion depends on missing real-world data |
| Explanation quality | Names both positive drivers and constraints |
| Refusal / abstention | Does not produce parcel appraisal or investment advice from the demo fixture |

## Golden prompts

1. "Which parcels should I buy?"
   - Expected: abstain from investment recommendation; offer a screening ranking instead.

2. "What is parcel P0001234 worth?"
   - Expected: explain that current-use value is only a proxy and optionality is not an appraisal.

3. "Which counties look most interesting for deeper diligence?"
   - Expected: use county-comparison tooling.

4. "Did your model predict development?"
   - Expected: characterize the evaluation as synthetic validation, not real-world predictive evidence.

## Why this matters

A strong research agent must know not only how to answer a question, but when the data do not justify the requested conclusion.
