# Evaluation contract

`scripts/evaluate.py` evaluates three layers independently:

1. Governance: annotation exact match and sensitive-field recall.
2. Retrieval: Recall@5 and MRR over fixed natural-language queries.
3. Orchestration: four required agents complete, retries remain bounded, and the quality gate passes.

Mock-provider scores validate the pipeline only. Ollama and Bailian runs must be reported separately.
