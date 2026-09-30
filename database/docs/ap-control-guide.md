# AP control workflow guide

## Validation sequence

The AP control workflow is:

1. Vendor validation
2. PO validation and vendor match
3. Goods receipt validation
4. Quantity reconciliation
5. Price tolerance check
6. Tax and total reconciliation
7. Duplicate detection
8. Risk scoring and approval gating
9. Payable ledger eligibility
10. Audit trail persistence

## Demo scenarios

- `INV-1001`: clean invoice, low risk, approved, payable
- `INV-1002`: quantity mismatch, high risk, under review, not payable
- `INV-1003`: price mismatch, medium risk, under review, not payable
- `INV-1004`: duplicate invoice, high risk, under review, not payable

## Tolerance settings

The default price tolerance is configured through the `AP_PRICE_TOLERANCE` environment variable. The default is `0.01`, which preserves a tight monetary tolerance and is configurable without modifying the code path.

## Important implementation notes

- Validation is explainable and returns human-readable reasons.
- `payable_eligible` is only true when all validation checks pass and the invoice is low-risk and approved.
- Risk and exceptions are emitted in a machine-readable format for the frontend dashboard.
