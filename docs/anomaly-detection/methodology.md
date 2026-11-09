# SmartDist AI — Sales Anomaly Detection Methodology

## 1. Detection Principles & Mathematical Foundations

### 1.1 Robust Statistical Dispersion (MAD & Robust Z-Score)
Traditional mean-variance standard scores ($Z = (x - \mu)/\sigma$) are fragile in retail time-series because extreme demand spikes contaminate both the mean and sample standard deviation.

To achieve robust outlier resilience, SmartDist AI applies Median Absolute Deviation:
$$\operatorname{MAD}(X) = \operatorname{median}(|x_i - \operatorname{median}(X)|)$$

Under standard normal distributions, $\mathbb{E}[\operatorname{MAD}] \approx 0.6745 \sigma$, yielding the consistency multiplier $0.6745$:
$$Z_{\text{robust}} = \frac{0.6745(x_t - \operatorname{median}(X))}{\operatorname{MAD}(X)}$$

#### Zero-MAD Handling:
In low-demand or constant items, $\operatorname{MAD}(X) = 0$. The system evaluates:
1. If $\sigma_X > 0$, standardizes using sample standard deviation: $Z = (x_t - \operatorname{median}(X))/\sigma_X$.
2. If $\sigma_X = 0$ (all values in history are identical):
   - $x_t = \operatorname{median}(X) \implies Z_{\text{robust}} = 0.0$
   - $x_t > \operatorname{median}(X) \implies Z_{\text{robust}} = +10.0$
   - $x_t < \operatorname{median}(X) \implies Z_{\text{robust}} = -10.0$

### 1.2 Forecast Residual Normalization
Using the champion LightGBM model, the system evaluates the point forecast error:
$$e_t = A_t - F_t$$
where $A_t$ is actual observed demand and $F_t$ is model expectation.

Standardized residual score:
$$Z_{\text{forecast}} = \frac{e_t - \mu_e}{\sigma_e}$$
where $\mu_e$ and $\sigma_e$ are empirical mean bias and residual standard deviation derived strictly from out-of-sample validation residuals (November 2013).

### 1.3 Machine Learning Isolation Trees
Isolation Forest recursively partitions feature space. Anomalies are isolated closer to the root of trees, resulting in shorter average path lengths:
$$s(x, n) = 2^{-\frac{\mathbb{E}[h(x)]}{c(n)}}$$
Raw decision scores are converted to a calibrated probability in $[0.0, 1.0]$ using a logistic sigmoid:
$$S_{\text{ml}} = \frac{1}{1 + \exp(10 \cdot \text{decision\_function}(x))}$$

---

## 2. Dynamic Renormalization & Hybrid Aggregation

Score normalization maps real-valued Z-scores into $[0.0, 1.0]$:
$$S_{\text{norm}}(Z) = 2 \left(\frac{1}{1 + \exp(-0.6 |Z|)} - 0.5\right)$$

Dynamic weight normalization ensures that when any detector is missing or has insufficient history, the remaining detectors seamlessly take over:
$$w'_i = \frac{w_i}{\sum_{j \in \text{available}} w_j}$$
$$S_{\text{hybrid}} = \sum_{i \in \text{available}} w'_i S_i$$

---

## 3. Directional Classification Taxonomy

| Direction | Trigger Conditions |
|---|---|
| `SPIKE` | $Z_{\text{robust}} \ge 3.0$ or ($x_t > \text{IQR}_{\text{upper}}$ and $Z_{\text{robust}} \ge 2.0$) |
| `DROP` | $Z_{\text{robust}} \le -3.0$ or ($x_t < \text{IQR}_{\text{lower}}$ and $Z_{\text{robust}} \le -2.0$) |
| `ZERO_SALES` | $x_t = 0.0$ and baseline historical median $\ge 2.0$ units |
| `FORECAST_DEVIATION` | $|Z_{\text{forecast}}| \ge 2.5$ or ($|e_t| > 10.0$ and $|Z_{\text{forecast}}| \ge 2.0$) |
| `TREND_SHIFT` | Multi-day sustained divergence from rolling baseline |
