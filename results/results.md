# Results (auto-generated)

NOTE: the agent brain is SimulatedBrain (follows injections with probability p=0.8). Re-run with a real LLM before reporting in the paper.

## E1 Indirect prompt injection (30 poisoned tickets)

| System | Attack success rate | Task success under attack | Caller attribution | Authorizer attribution |
|---|---|---|---|---|
| baseline | 96.7% | 100.0% | 0.0% | n/a |
| delegateguard | 0.0% | 100.0% | 100.0% | 100.0% |

## E2 Normal tasks (20 benign tickets)

| System | Task success | False-block rate |
|---|---|---|
| baseline | 100.0% | 0.0% |
| delegateguard | 100.0% | 0.0% |

## E3 Direct escalation attacks (5 kinds x 5 repeats)

| Attack (attacker success) | Baseline | DelegateGuard |
|---|---|---|
| forged_token | 100.0% | 0.0% |
| self_extended_token | 100.0% | 0.0% |
| stolen_token | 100.0% | 0.0% |
| replay_after_close | 100.0% | 0.0% |
| depth_exceeded | 100.0% | 0.0% |
| OVERALL block rate | 0.0% | 100.0% |

## E4 Overhead per tool call

| System | Depth | Mean ms | P95 ms | Token bytes |
|---|---|---|---|---|
| baseline | - | 0.001 | 0.002 | - |
| delegateguard | 1 | 0.748 | 1.216 | 719 |
| delegateguard | 2 | 1.068 | 1.805 | 1035 |
| delegateguard | 3 | 1.178 | 1.611 | 1346 |
| delegateguard | 4 | 1.507 | 2.328 | 1653 |
| delegateguard | 5 | 1.612 | 2.415 | 1960 |

## E5 Sensitivity: attack success vs. how easily the agent is fooled (p)

| p(follows injection) | Baseline ASR | DelegateGuard ASR |
|---|---|---|
| 0.3 | 46.7% | 0.0% |
| 0.6 | 83.3% | 0.0% |
| 1.0 | 100.0% | 0.0% |

## E6 Limitation: injection abusing an IN-SCOPE tool (close an unrelated ticket)

| System | Attack success rate |
|---|---|
| baseline | 96.7% |
| delegateguard | 76.7% |
