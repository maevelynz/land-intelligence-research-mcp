# Prompt Library

These prompts test whether an LLM can reason over a governed analytical surface without bypassing MCP and reading the underlying files directly.

## Institutional landowner / TIMO-style lens

Act as a research analyst supporting a long-duration institutional landowner evaluating development optionality across a land portfolio.

Use the `land-intelligence` MCP as your only quantitative data and analytics interface. Do not inspect the underlying CSVs, database, SQL, Python files, manifests, or other repository artifacts directly. Every material numerical claim should come from an MCP tool result. If the analytical surface cannot answer an important question, identify the gap rather than bypassing the MCP or guessing.

Determine which markets and parcels appear to have the strongest development optionality and whether that evidence is strong enough to change how an owner should think about holding, monetizing, further diligencing, or potentially repositioning an asset. A high optionality score alone is not a recommendation.

Move from market-level evidence to parcel-level candidates, investigate what contributes to the strongest signals, and actively try to break your own thesis. At the end, explain what the owner should conclude, what the owner should not conclude, and what real-world diligence would be required before a sale, hold, lease, entitlement, development-partnership, or other monetization decision.

## Investor / capital allocator lens

Act as a research analyst for an institutional investor deciding where additional land-related capital and diligence resources should be allocated.

Use the `land-intelligence` MCP as your only quantitative data and analytics interface. Do not access raw files, the database, SQL, source code, or repository artifacts directly. Every material numerical claim must originate from an MCP result.

Identify which markets and parcels appear most interesting on a risk-adjusted screening basis, not simply which have the highest optionality score. Investigate whether the strongest optionality is associated with higher current-use value, whether apparent upside could already be reflected in land value, and whether parcel-level differentiation is stronger than the surrounding market.

If you need acquisition price, cash flows, NPV, IRR, discount-rate sensitivity, exit value, liquidity, or transaction costs, identify those as underwriting gaps instead of estimating them yourself.

Conclude with where you would spend the next dollar of diligence and what evidence is still required before actual capital could be underwritten.

## Developer lens

Act as a land developer deciding where to spend scarce development and feasibility resources.

Use the `land-intelligence` MCP as your only quantitative interface. Do not inspect underlying project files or recreate calculations yourself.

Use the available evidence around parcel size, zoning, infrastructure proximity, transmission, substations, fiber, highways, flood risk, wetlands, slope, land use, and other exposed characteristics to identify candidates for deeper feasibility work.

Then red-team the leading candidates. Look for cases where a high aggregate score masks a potentially disqualifying constraint or depends too heavily on one favorable input.

Be disciplined about the distinction between a screening proxy and actual feasibility. Proximity to transmission or a substation does not establish available capacity, interconnection feasibility, cost, or timing.

Conclude with which sites you would advance, which you would deprioritize, and what missing information would determine real development viability.

## Skeptical investment committee / red-team lens

Act as the skeptical member of an investment committee reviewing a land-optionality thesis.

Use only the `land-intelligence` MCP for quantitative evidence. Try to disprove the thesis that the highest-ranked markets and parcels represent attractive opportunities.

Look for weaknesses in the scoring methodology, contradictory parcel characteristics, aggregation problems, cases where the score may be driven by a fragile input, synthetic-validation limitations, and important variables absent from the current analytical surface.

Tell me which conclusions survive the challenge, which become weaker, and which cannot currently be defended.

## Cross-stakeholder translation

Using only MCP evidence already established, take one leading parcel and explain the decision implications separately to:

1. the institutional landowner that currently owns it,
2. an investor considering acquiring it,
3. a developer considering pursuing the site.

Show where the same fact leads to different implications because each stakeholder has a different objective, and identify any conclusion one stakeholder can reasonably draw that another cannot.
