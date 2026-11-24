reference proxy on seeds vs official: ['+0.01', '-0.57', '+0.47'] std=0.52
| variant | paired proxy vs ref per seed (B, C, D) | mean | std |
|---|---|---|---|
| variant_ref_rerun | +0.00, +0.00, +0.00 | +0.00 | 0.00 |
| variant_weaker_nopin_fcfs | -1.21, -0.90, -1.22 | -1.11 | 0.19 |
| variant_weaker_vllm_as_method | -1.95, -1.54, -1.74 | -1.75 | 0.21 |
| variant_weaker_static_ttl | -0.74, -0.56, -0.93 | -0.74 | 0.19 |
| variant_coldstart_only | -0.40, +0.20, -0.09 | -0.10 | 0.30 |
| variant_warm_history | -0.28, +0.05, +0.18 | -0.02 | 0.24 |
| variant_true_deadlock_unpin | -0.72, -0.43, -0.80 | -0.65 | 0.20 |
| variant_bruteforce_pin_max | +3.90, +4.61, +4.34 | +4.28 | 0.36 |
| shortcut_oracle_ttl | +2.44, +2.96, +2.72 | +2.70 | 0.26 |
| shortcut_static_grid_overfit | +3.90, +4.61, +4.34 | +4.28 | 0.36 |
