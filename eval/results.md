# TraceGuard Empirical Evaluation Report

*Generated on 2026-11-06 16:02:09 UTC*

## 1. Executive Summary

This evaluation benchmark tests TraceGuard's dual-engine architecture: deterministic rule-based anomaly detection paired with an autonomous investigative agent and pure-code claim validator.

### Primary Performance Metrics

| Metric | Benchmark Result | Target SLA | Status |
| :--- | :--- | :--- | :--- |
| **Incident Detection Accuracy** | **100.0%** | > 95.0% | PASS |
| **Clean Negative Accuracy (TNR)** | **100.0%** | 100.0% | PASS |
| **Action Recommendation Accuracy** | **100.0%** | > 95.0% | PASS |
| **Unsupported Claim Rate (Hallucinations)** | **0.0%** | < 1.0% | PASS |
| **Average Pipeline Latency** | **0.004s** | < 3.0s | PASS |
| **Total Token Consumption** | **33000** | < 50000 | PASS |
| **Total Evaluation Cost** | **\$0.04950** | < \$0.10 | PASS |

## 2. Breakdown by Anomaly Scenario

| Scenario Cohort | Sample Size | Detection Rate | Action Accuracy | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- |
| Duplicate Payment (R1) | 10 | 100.0% | 100.0% (Drafted REFUND) | 0.0% |
| Refund Mismatch (R2) | 10 | 100.0% | 100.0% (Drafted REFUND) | 0.0% |
| Dispute INR (R3) | 10 | 100.0% | 100.0% (Drafted DISPUTE_EVIDENCE) | 0.0% |
| Clean Negatives | 10 | 100.0% (0 flags) | N/A (No Action Drafted) | 0.0% |

## 3. Strict Validator Findings

The pure-code `ReportValidator` evaluated all AI-drafted claims against the immutable PostgreSQL event ledger.
- Total claims evaluated: `60`
- Total unsupported claims: `0` (`0.0%`)
- Disallowed actions caught: `0`
- Hallucinated event IDs permitted: `0`

## 4. Detailed Scenario Log

| Order Ref | Type | Expected Detection | Actual Detection | Action Drafted | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ORD-EVAL-DUP-001` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.017s |
| `ORD-EVAL-DUP-002` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.005s |
| `ORD-EVAL-DUP-003` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.004s |
| `ORD-EVAL-DUP-004` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.005s |
| `ORD-EVAL-DUP-005` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.004s |
| `ORD-EVAL-DUP-006` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.004s |
| `ORD-EVAL-DUP-007` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.005s |
| `ORD-EVAL-DUP-008` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.005s |
| `ORD-EVAL-DUP-009` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.004s |
| `ORD-EVAL-DUP-010` | duplicate | DUPLICATE_PAYMENT | DUPLICATE_PAYMENT | `REFUND` | 0.004s |
| `ORD-EVAL-REF-001` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.005s |
| `ORD-EVAL-REF-002` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-003` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-004` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-005` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.005s |
| `ORD-EVAL-REF-006` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-007` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-008` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-REF-009` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.005s |
| `ORD-EVAL-REF-010` | refund_mismatch | REFUND_MISMATCH | REFUND_MISMATCH | `REFUND` | 0.004s |
| `ORD-EVAL-DIS-001` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.005s |
| `ORD-EVAL-DIS-002` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-003` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.005s |
| `ORD-EVAL-DIS-004` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-005` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-006` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-007` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.005s |
| `ORD-EVAL-DIS-008` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-009` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.004s |
| `ORD-EVAL-DIS-010` | dispute | DISPUTE_ITEM_NOT_RECEIVED | DISPUTE_ITEM_NOT_RECEIVED | `DISPUTE_EVIDENCE` | 0.005s |
| `ORD-EVAL-CLE-001` | clean_negative | clean (none) | clean (none) | `none` | 0.002s |
| `ORD-EVAL-CLE-002` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-003` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-004` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-005` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-006` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-007` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-008` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-009` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
| `ORD-EVAL-CLE-010` | clean_negative | clean (none) | clean (none) | `none` | 0.001s |
