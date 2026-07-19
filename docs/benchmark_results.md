# Benchmark Results (real run)

Generated: 2026-07-18T19:09:17.763732+00:00

Real postings: 2330

| Query | Bitmap (ms) | B-tree (ms) | Faster |
|---|---|---|---|
| single skill | 7.09 | 2.29 | btree |
| two-skill AND | 10.72 | 1.87 | btree |
| three-skill AND | 14.75 | 1.61 | btree |
| skill + seniority + country | 12.93 | 3.39 | btree |

## EXPLAIN ANALYZE (native B-tree path)
```
Limit  (cost=46.35..46.37 rows=1 width=16) (actual time=0.046..0.048 rows=0 loops=1)
  ->  GroupAggregate  (cost=46.35..46.37 rows=1 width=16) (actual time=0.045..0.046 rows=0 loops=1)
        Group Key: e.event_id
        Filter: (count(DISTINCT js.skill) = 1)
        ->  Sort  (cost=46.35..46.35 rows=1 width=23) (actual time=0.044..0.045 rows=0 loops=1)
              Sort Key: e.event_id, js.skill
              Sort Method: quicksort  Memory: 25kB
              ->  Nested Loop  (cost=0.43..46.34 rows=1 width=23) (actual time=0.033..0.033 rows=0 loops=1)
                    ->  Index Scan using idx_skills_skill on job_skills js  (cost=0.29..2.50 rows=1 width=23) (actual time=0.032..0.032 rows=0 loops=1)
                          Index Cond: (skill = ANY ('{python}'::text[]))
                    ->  Append  (cost=0.14..43.64 rows=19 width=16) (never executed)
                          ->  Index Only Scan using "37_job_events_pkey" on _hyper_9_37_chunk e_1  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "38_job_events_pkey" on _hyper_9_38_chunk e_2  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "39_job_events_pkey" on _hyper_9_39_chunk e_3  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "40_job_events_pkey" on _hyper_9_40_chunk e_4  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "41_job_events_pkey" on _hyper_9_41_chunk e_5  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "42_job_events_pkey" on _hyper_9_42_chunk e_6  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "43_job_events_pkey" on _hyper_9_43_chunk e_7  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "44_job_events_pkey" on _hyper_9_44_chunk e_8  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "45_job_events_pkey" on _hyper_9_45_chunk e_9  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "46_job_events_pkey" on _hyper_9_46_chunk e_10  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "47_job_events_pkey" on _hyper_9_47_chunk e_11  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "48_job_events_pkey" on _hyper_9_48_chunk e_12  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "49_job_events_pkey" on _hyper_9_49_chunk e_13  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "50_job_events_pkey" on _hyper_9_50_chunk e_14  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "51_job_events_pkey" on _hyper_9_51_chunk e_15  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "52_job_events_pkey" on _hyper_9_52_chunk e_16  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Index Only Scan using "53_job_events_pkey" on _hyper_9_53_chunk e_17  (cost=0.14..2.36 rows=1 width=16) (never executed)
                                Index Cond: (event_id = js.event_id)
                                Heap Fetches: 0
                          ->  Bitmap Heap Scan on _hyper_9_54_chunk e_18  (cost=1.26..3.40 rows=2 width=16) (never executed)
                                Recheck Cond: (event_id = js.event_id)
                                ->  Bitmap Index Scan on "54_job_events_pkey"  (cost=0.00..1.26 rows=2 width=0) (never executed)
                                      Index Cond: (event_id = js.event_id)
Planning Time: 1.321 ms
Execution Time: 0.278 ms
```
