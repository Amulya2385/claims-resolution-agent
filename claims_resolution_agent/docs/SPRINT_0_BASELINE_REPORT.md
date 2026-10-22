# Sprint 0 — Baseline Audit & Reproduction Report



## 1. Objective



Sprint 0 establishes the empirical baseline of the faculty-provided Claims Resolution Agent reference implementation before any architectural modification.



The purpose is to:



- reproduce the supplied implementation;

- understand its existing security, governance, policy, ledger, and evaluation mechanisms;

- execute the supplied validation suite;

- identify reproducibility or portability limitations;

- establish baseline observations without modifying the faculty implementation;

- preserve the reference implementation as the comparison baseline for subsequent research development.



No faculty source implementation was modified during this baseline audit.



---



## 2. Development Environment



| Component | Observed Environment |

|---|---|

| Operating System | Windows |

| Python | 3.12.0 |

| Faculty documented Python | 3.12+; reference build tested on 3.12.3 |

| Docker | 29.7.2 |

| Docker Compose | v5.4.0 |

| PostgreSQL CLI (`psql`) | Not installed locally |

| Test framework | Faculty build uses standalone Python test scripts |

| pytest | Not part of the supplied baseline and was not added |



The faculty requirements were reproduced from the supplied `requirements.txt`:



- `jsonschema==4.26.0`

- `PyJWT==2.7.0`

- `scikit-learn==1.8.0`



The project was executed inside an isolated Python virtual environment.



---



## 3. Reference Architecture Observed



The faculty reference implementation contains the following major components:



### Server



- Tool server / MCP dispatch

- Identity verification

- Claim classification

- Governance boundaries

- Approval protocol

- Test fixtures

- Registry



### Policy



- Refund authorization policy

- Customer-account-standing policy

- Policy chunking

- Hybrid policy retrieval/indexing



### Ledger



- Hash-chained audit ledger

- Idempotency-key lookup

- Tamper-detection validation



### Evaluation



- Golden claims

- Evaluation harness

- Deployment gating

- Staged deployment behavior



The reference implementation uses fixtures for simulated claim/customer data and SQLite for the audit ledger.



---



## 4. Baseline Validation Results



### 4.1 Approval and Governance



The supplied approval tests demonstrated the expected governance protections, including:



- approval replay protection;

- approval payload re-verification;

- four-eyes approval behavior;

- stale approval rejection.



Result:



**PASS**



---



### 4.2 Adversarial Security



The supplied adversarial evaluation demonstrated protection against the tested attacks, including:



- prompt/instruction injection;

- forged approval tokens;

- stale approvals;

- claim-ID/schema injection.



The observed live system reported zero successful breaches under the supplied adversarial scenarios.



Result:



**PASS**



---



### 4.3 Engagement / Deliberation



The engagement validation demonstrated the supplied deliberation/engagement constraint behavior.



Result:



**PASS**



---



### 4.4 Ledger Tamper Detection



The ledger tamper test successfully detected modification of a historical ledger entry.



Result:



**PASS**



---



### 4.5 Deployment Evaluation



The supplied deployment evaluation demonstrated:



- evaluation evidence is required for promotion;

- deployment without appropriate evaluation evidence is rejected;

- a failing evaluation can trigger demotion behavior.



The supplied golden-set evaluation reported an accuracy value of 1.0.



This value is recorded strictly as:



> Reference-build golden-set accuracy = 1.0 on the supplied evaluation harness.



It is not treated as a general claim of model accuracy or real-world performance. Dataset size, independence, difficulty, statistical significance, and external validity have not yet been established.



Result:



**PASS**



---



## 5. Idempotency Investigation



### 5.1 Supplied Faculty Test



The supplied `test_idempotency_kill.py` uses an actual subprocess and process kill to test the following scenario:



1\. Start a worker process.

2\. Execute a refund.

3\. Commit the ledger write.

4\. Kill the process before the response is returned.

5\. Retry the same operation using the same idempotency key.

6\. Inspect the ledger directly.

7\. Verify that only one ledger entry exists.



This is a strong test design because it models a real timeout/crash-after-commit failure mode rather than merely calling the same function twice.



However, the supplied test hardcodes the database path:



`/tmp/cra_kill_test_ledger.db`



The Windows execution environment cannot open this Unix-style path.



The resulting error was:



`sqlite3.OperationalError: unable to open database file`



The failure occurred before `execute_refund()` was reached.



Therefore, the supplied kill-test harness is **not directly portable to the Windows environment**.



---



### 5.2 Underlying Idempotency Mechanism



To distinguish the portability issue from an actual idempotency defect, the worker was executed using a valid Windows-native SQLite path without modifying the faculty implementation.



First execution using idempotency key:



`windows-kill-test-001`



returned:



`status = executed`



with entry hash:



`e0899bea011fcd81c3adb71e2dadc808af8ed160e3caf8bed48d53cc655e2e5a`



A second execution using the identical idempotency key returned:



`status = already_executed`



and returned the same entry hash.



Direct ledger inspection reported:



`Total entries: 1`



The single ledger payload contained the expected refund event and the same idempotency key.



### Conclusion



The underlying idempotency mechanism successfully prevents duplicate execution for repeated idempotency keys.



The limitation is in the portability of the supplied process-kill test harness, not evidence of an underlying idempotency failure.



---



## 6. Baseline Integrity



During Sprint 0:



- Faculty implementation files were not modified.

- Faculty tests were not modified.

- Evaluation expectations were not modified.

- No results were fabricated or selectively altered.

- No evaluation data was changed.

- No additional accuracy claims were inferred from the supplied golden-set result.



The reference implementation therefore remains a clean comparison baseline.



---



## 7. Research-Relevant Baseline Findings



The faculty implementation provides a strong security/governance foundation, particularly around:



- deterministic authorization boundaries;

- approval validation;

- replay protection;

- policy retrieval;

- auditability;

- idempotency;

- adversarial resistance;

- deployment evidence gating.



However, the baseline also exposes important extension points for the research-grade system:



1\. Persistent application state currently relies heavily on fixtures and SQLite.

2\. Claims/customer state requires a production-grade persistence layer.

3\. The agentic reasoning layer has not yet been developed.

4\. Stateful agent memory is not yet present.

5\. Research-grade reasoning/evidence evaluation needs to be expanded.

6\. Comparative model and ablation evaluation has not yet been implemented.

7\. The supplied evaluation set is insufficient by itself for broad claims about real-world accuracy.

8\. The supplied idempotency kill harness has a platform-specific filesystem assumption.



These findings will guide subsequent development without changing the original project objective.



---



## 8. Sprint 0 Gate



### Status: READY TO CLOSE



The faculty reference implementation has been audited and reproduced to the extent supported by the supplied environment.



The observed Windows-specific limitation has been isolated and independently distinguished from the underlying idempotency behavior.



The reference implementation is now suitable to serve as the controlled baseline for subsequent engineering and research contributions.



### Next Sprint



**Sprint 1 — Production Engineering Foundation + PostgreSQL**



The next sprint will introduce the production persistence foundation while preserving the faculty governance behavior and maintaining the reference implementation as the baseline.
