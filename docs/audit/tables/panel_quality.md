# AEI panel quality checks

Coverage only: AEI data are conversations matched to O*NET tasks. Nothing here says anything about jobs or the labour market.

Overall: PASS

| check | result | detail |
| --- | --- | --- |
| columns_and_labels | pass | columns match: True; unknown releases: []; unknown taxonomies: [] |
| canonical_metrics | pass | 56 metrics; non-canonical: [] |
| unique_keys | pass | 0 rows share a panel key; 15467 null values |
| shares_sum | pass | 16394 groups; max sum 100.00; 0 above 100.5; 11750 below 99.5 (unpublished mass: mean 34.25, max 98.49 points) |
| pattern_partition | pass | 39028 nodes with all five patterns: 0 with pattern sum off 100 by > 0.1; 38717 also carry both buckets: 0 with automation + augmentation off 100 |
| r6_bucket_consistency | pass | 31374 r6 nodes: published automation vs renormalised directive + feedback_loop; max abs gap 0.132 points, mean 0.0035; 0 nodes gap > 1.0 (published value kept) |
| unmatched_tasks | pass | global onet_task nodes with no O*NET match (sentinels none/not_classified excluded; unmatched nodes / all nodes, mean pct mass per period): r1 claude_ai 0/3514 nodes, 0.00%; r2 claude_ai 0/3365 nodes, 0.00%; r3 1p_api 0/2056 nodes, 0.00%; r3 claude_ai 0/2618 nodes, 0.00%; r4 1p_api 0/2253 nodes, 0.00%; r4 claude_ai 0/3170 nodes, 0.00%; r5 1p_api 0/2299 nodes, 0.00%; r5 claude_ai 0/3260 nodes, 0.00%; r6 1p_api 1/2427 nodes, 0.00%; r6 claude_ai 2/2823 nodes, 0.07% |
| row_counts | pass | r1 claude_ai 3522; r2 claude_ai 30277; r3 1p_api 20495; r3 claude_ai 97754; r4 1p_api 42066; r4 claude_ai 199956; r5 1p_api 43891; r5 claude_ai 205847; r6 1p_api 491705; r6 claude_ai 1636573 |
