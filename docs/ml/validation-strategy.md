# Time-Series Validation Strategy

## 1. Principles of Time-Series Splitting

Standard cross-validation with random shuffling (e.g. `sklearn.model_selection.train_test_split(shuffle=True)`) violates the temporal arrow of causality:
1. Future data points leak into the training partition.
2. Autocorrelated lag features suffer from extreme lookahead bias.
3. Out-of-sample error estimates become artificially optimistic and fail in real-world deployment.

In SmartDist AI, all time-series validation is strictly chronological and non-overlapping.

## 2. Chronological Cutoff Boundaries (2013 Baseline)

For models trained on the verified 1-year historical baseline:

```
[2013-01-01] ---------------- [2013-10-31] | [2013-11-01] -------- [2013-11-30] | [2013-12-01] -------- [2013-12-31]
             TRAINING PARTITION             |       VALIDATION PARTITION        |          TEST PARTITION
              (491,832 records)             |         (53,460 records)          |         (53,460 records)
```

### Partition Definitions
- **Training Set**: $T \le \text{2013-10-31}$ (Months 1–10, 491,832 records after lag warmup drop).
- **Validation Set**: $\text{2013-10-31} < T \le \text{2013-11-30}$ (Month 11, 53,460 records). Used for hyperparameter tuning and early stopping.
- **Holdout Test Set**: $T > \text{2013-11-30}$ (Month 12, 53,460 records). Used exclusively for final out-of-sample model evaluation.

## 3. Expanding-Window Cross-Validation

Implemented in `TimeSeriesSplitter.expanding_window_split`:

```
Fold 1: [===== Train Window 1 =====] [Val 1]
Fold 2: [========== Train Window 2 ==========] [Val 2]
Fold 3: [=============== Train Window 3 ===============] [Val 3]
```

- Training windows expand chronologically forward.
- Validation windows advance strictly into the future.
- Zero date overlap between training and evaluation folds.
