"""
predict_direction_v2.py — v6 の改良版(v7)

v6 の問題: 高確度フィルター(|p-0.5|>=0.10)が効いていない(54.13% → 53.48%)
原因: LightGBM の確率出力が較正されていない(過信気味)

v7 の改善:
  1. **Platt scaling キャリブレーション**(scikit-learn CalibratedClassifierCV)
     - sigmoid 関数で確率を再較正
     - 「prob=0.7 と出たら本当に 70% 当たる」状態に近づける
  2. **マクロ特徴量の追加**(macro_histories を build_features に渡す)
     - 米金利、ドル円、原油、金、BTC、VIX、S&P500、NASDAQ など
  3. **アンサンブル分類器**:LightGBM + RandomForest + LogisticRegression の確率平均

参照論文:
  - Platt (1999): "Probabilistic outputs for support vector machines and comparisons to regularized
    likelihood methods" — 確率較正の古典
  - Niculescu-Mizil & Caruana (2005): "Predicting good probabilities with supervised learning"
  - Krauss et al. (2017): GB + RF + DNN のアンサンブルが個別より良い

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

try:
    import lightgbm as lgb
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    HAS_ML = True
except ImportError:
    HAS_ML = False

from predict_direction import build_classification_data  # noqa: E402
from predict_ml import build_features  # noqa: E402


# v6 の 50 サイクル PDCA で見つけた最適パラメータ
OPTIMAL_LGBM_PARAMS = {
    "n_estimators": 150,
    "learning_rate": 0.01,
    "num_leaves": 47,
    "min_child_samples": 15,
    "max_depth": 10,
    "verbose": -1,
    "random_state": 42,
}


def predict_direction_v2(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    days_ahead: int = 21,
    use_calibration: bool = True,
    use_ensemble: bool = True,
) -> dict | None:
    """v7 改良版の方向予測。
    - キャリブレーション(Platt scaling、sigmoid)
    - マクロ特徴量を含む
    - LightGBM + RF + LogReg のアンサンブル

    Returns: {"direction", "probability_up", "confidence", "signal", ...}
    """
    if not HAS_ML:
        return None

    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 350:
        return None

    train = build_classification_data(history, macro_histories, forecast_days=days_ahead)
    if not train or len(train[0]) < 50:
        return None
    Xs, ys = train

    feature_names = list(Xs[0].keys())
    X_arr = [[x.get(f, 0.0) for f in feature_names] for x in Xs]

    try:
        # 学習サンプル数が十分なら CV キャリブレーション、不足なら sigmoid 直接
        cv = 3 if len(Xs) >= 60 else 2 if len(Xs) >= 30 else None

        # LightGBM
        lgbm = lgb.LGBMClassifier(**OPTIMAL_LGBM_PARAMS)
        if use_calibration and cv:
            lgbm_cal = CalibratedClassifierCV(lgbm, method="sigmoid", cv=cv)
            lgbm_cal.fit(X_arr, ys)
            lgbm_used = lgbm_cal
        else:
            lgbm.fit(X_arr, ys)
            lgbm_used = lgbm

        latest_feat = build_features(history, macro_histories, end_idx=len(history) - 1)
        if not latest_feat:
            return None
        x_latest = [[latest_feat.get(f, 0.0) for f in feature_names]]
        prob_lgbm = float(lgbm_used.predict_proba(x_latest)[0][1])

        if use_ensemble:
            # Random Forest
            rf = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            )
            if use_calibration and cv:
                rf_cal = CalibratedClassifierCV(rf, method="sigmoid", cv=cv)
                rf_cal.fit(X_arr, ys)
                prob_rf = float(rf_cal.predict_proba(x_latest)[0][1])
            else:
                rf.fit(X_arr, ys)
                prob_rf = float(rf.predict_proba(x_latest)[0][1])

            # Logistic Regression(標準化必要)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_arr)
            x_latest_scaled = scaler.transform(x_latest)
            lr = LogisticRegression(max_iter=1000, random_state=42, C=0.5)
            if use_calibration and cv:
                lr_cal = CalibratedClassifierCV(lr, method="sigmoid", cv=cv)
                lr_cal.fit(X_scaled, ys)
                prob_lr = float(lr_cal.predict_proba(x_latest_scaled)[0][1])
            else:
                lr.fit(X_scaled, ys)
                prob_lr = float(lr.predict_proba(x_latest_scaled)[0][1])

            prob_up = (prob_lgbm + prob_rf + prob_lr) / 3
            ensemble_breakdown = {
                "lgbm": prob_lgbm,
                "rf": prob_rf,
                "lr": prob_lr,
            }
        else:
            prob_up = prob_lgbm
            ensemble_breakdown = {"lgbm": prob_lgbm}

        confidence = abs(prob_up - 0.5) * 2

        if prob_up >= 0.60:
            signal = "強気(プラス予測 高確度)"
        elif prob_up >= 0.55:
            signal = "やや強気"
        elif prob_up >= 0.45:
            signal = "中立"
        elif prob_up >= 0.40:
            signal = "やや弱気"
        else:
            signal = "弱気(マイナス予測 高確度)"

        return {
            "direction": "up" if prob_up >= 0.5 else "down",
            "probability_up": prob_up,
            "probability_down": 1 - prob_up,
            "confidence": confidence,
            "signal": signal,
            "n_train_samples": len(Xs),
            "ensemble_breakdown": ensemble_breakdown,
            "use_calibration": use_calibration,
            "use_ensemble": use_ensemble,
        }
    except Exception as e:
        return {"error": str(e)}
