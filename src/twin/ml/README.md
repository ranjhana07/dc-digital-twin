# ml

GRU forecasters for three tasks, defined in `tasks.py`:

| task | device | inputs | forecast targets |
| --- | --- | --- | --- |
| thermal | server | inlet, outlet, cpu load, fan rpm, power | inlet temp, outlet temp |
| power | PDU | power, current, load pct | power, load pct |
| ber | transceiver | rx, tx, module temp, pre-FEC BER | rx power, pre-FEC BER (log10) |

Defaults: 60 one-minute steps in, 30 steps out, stride 3 when building windows. Splits are chronological per device (70/15/15), the scaler is fit on the training segments only.

```
python -m twin.simulator.export --hours 72 --out data/telemetry.csv
python -m twin.ml.train --task all --csv data/telemetry.csv --out checkpoints
python -m twin.ml.export checkpoints/thermal.pt
python -m twin.ml
```

`train` writes `<task>.pt` and `<task>.metrics.json` with per-horizon MAE, RMSE and MAPE for the GRU and for a persistence baseline. The checkpoint carries the scaler and the validation residual spread, which the inference loop uses for confidence bands and risk scores.

Risk score: `max(P(crit), 0.75 * P(warn))` over the horizon, plus up to 0.15 for the rate of change toward the limit and 0.10 for a large one-step residual. 0.5 is a warning, 0.8 is critical.
