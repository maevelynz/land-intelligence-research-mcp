# Repository Guide

```text
.
├── .github/workflows/test.yml
├── data/
│   ├── counties.csv
│   ├── parcels.csv
│   ├── infrastructure.csv
│   ├── parcel_infrastructure.csv
│   ├── transactions.csv
│   ├── development_outcomes.csv
│   ├── research_catalog.csv
│   ├── MANIFEST.json
│   └── CHECKSUMS.sha256
├── docs/
│   ├── assets/
│   │   ├── optionality_distribution.png
│   │   ├── county_comparison.png
│   │   ├── score_anatomy.png
│   │   └── decile_validation.png
│   ├── AGENT_EVALUATION.md
│   ├── ARCHITECTURE.md
│   ├── CODE_WALKTHROUGH.md
│   ├── DATA_MODEL.md
│   ├── RUNTIME_DESIGN_LESSONS.md
│   ├── PROJECT_WALKTHROUGH.md
│   ├── LIMITATIONS.md
│   ├── LOCAL_RUNBOOK.md
│   ├── REPOSITORY_GUIDE.md
│   ├── RESEARCH_METHODS.md
│   └── REVIEW_CHECKLIST.md
├── scripts/
│   ├── generate_dummy_data.py
│   ├── generate_visualizations.py
│   ├── preflight.py
│   ├── register_claude.sh
│   ├── run_mcp_dev.sh
│   ├── run_mcp_stdio.sh
│   └── smoke_test.py
├── src/land_intelligence_mcp/
│   ├── __init__.py
│   └── server.py
├── tests/
├── DATASET_VERSION
├── DATA_DICTIONARY.csv
├── DEMO_QUESTIONS.md
├── LICENSE
├── README.md
└── pyproject.toml
```

## Reviewer reading order

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/PROJECT_WALKTHROUGH.md`
4. `docs/DATA_MODEL.md`
5. `docs/RESEARCH_METHODS.md`
6. `docs/LIMITATIONS.md`
7. `docs/CODE_WALKTHROUGH.md`
8. `docs/AGENT_EVALUATION.md`
