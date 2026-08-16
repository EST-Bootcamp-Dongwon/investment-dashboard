"""머신러닝 실습 차트 5종 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤. 아키텍처 5절의
3번 명령 — *"라우터가 차트를 직접 그리지 않음"* — 이 여기로 옮겨 온 근거다.
`routers/ml.py` 에 있던 다섯 라우트의 **본문 전체**가 이 파일이다.

## 왜 인코딩만 떼지 않았는가

`savefig`·`b64encode` 두 줄만 공용 헬퍼로 뽑아도 판정 명령
(`grep "savefig|b64encode" routers/`)은 0 이 된다. **그렇게 하지 않았다.**
그러면 `plt.subplots` 부터 `ax.set_title` 까지가 라우터에 그대로 남아
*"라우터가 차트를 그리지 않는다"* 는 문장은 거짓인데 검사는 통과한다 —
[CN-128](../../../docs/spec/00-index/변경이력.md#cn-128)·CN-130 이 경계한
**공허한 통과**다. 그림을 만드는 일 전체가 이 계층에 있어야 문장과 검사가 맞는다.

## HTTP 를 모른다

옮기기 전 다섯 라우트에 `HTTPException` 이 **한 건도 없었다.** 그래서 F03~F28 이
했던 "도메인 예외를 만들고 라우터가 번역한다" 를 여기서는 할 일이 없었다 —
실패하면 sklearn 이 던지는 그대로 올라가고, 그 처리는 예전과 같다.

## 무작위성

`random_state=42` 와 `default_rng(42)` 로 고정돼 있어 **같은 요청은 같은 그림을
낸다.** 옮기면서 바꾸지 않았다. 교육용 화면이라 새로고침할 때마다 결과가 달라지면
설명과 그림이 어긋나기 때문이다.

정본: docs/spec/60-운영/아키텍처.md 2.1절(`services/` 계층) · 5절(판정 명령 6개).
"""

from __future__ import annotations

import base64
import io
from typing import Any


def _png_base64(fig: Any, plt: Any, *, dpi: int) -> str:
    """그림을 PNG 로 굽고 base64 문자열로 만든 뒤 **닫는다.**

    다섯 함수가 똑같이 하던 네 줄이다. `plt.close(fig)` 를 빠뜨리면 요청마다
    Figure 가 쌓여 matplotlib 이 경고를 내고 메모리가 늘어난다 — 원본도 전부
    닫고 있었고, 한자리에 모아 **빠뜨릴 수 없게** 했다.

    `plt` 를 인자로 받는 것은 `charting.configure_matplotlib_korean_font` 와 같은
    이유다. matplotlib 은 무거워서 함수 안에서 import 하는 것이 이 저장소의 관례이고
    (`indicators.py:20~22`), 그러면 모듈 최상단에는 이름이 없다.
    """
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def decision_boundary() -> dict[str, str]:
    """로지스틱 회귀의 결정 경계. `routers/ml.py:159~201` 그대로다."""
    import matplotlib
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    X, y = make_classification(
        n_samples=240,
        n_features=2,
        n_redundant=0,
        n_informative=2,
        n_clusters_per_class=1,
        random_state=42,
    )
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    model = LogisticRegression()
    model.fit(X_train, y_train)

    x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
    y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 400), np.linspace(y_min, y_max, 400))
    Z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.contourf(xx, yy, Z, alpha=0.3, cmap=plt.cm.coolwarm)
    ax.scatter(X_train[:, 0], X_train[:, 1], c=y_train, marker="o", edgecolors="k", label="Train")
    ax.scatter(X_test[:, 0], X_test[:, 1], c=y_test, marker="x", label="Test")
    ax.set_title("Decision Boundary")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()

    return {"image_base64": _png_base64(fig, plt, dpi=140)}


def kmeans(*, n_samples: int, n_clusters: int, cluster_std: float) -> dict[str, object]:
    """KMeans 군집 + 엘보 곡선. `routers/ml.py:257~312` 그대로다."""
    import matplotlib
    from sklearn.cluster import KMeans
    from sklearn.datasets import make_blobs
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    X, _ = make_blobs(
        n_samples=n_samples,
        centers=n_clusters,
        cluster_std=cluster_std,
        random_state=42,
    )
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(X_scaled)
    centers = model.cluster_centers_
    sil = float(silhouette_score(X_scaled, labels))

    # 엘보 곡선 — k 를 늘려 가며 관성(inertia)이 꺾이는 지점을 눈으로 찾게 한다.
    inertias = []
    ks = list(range(2, min(n_clusters + 4, 10)))
    for ki in ks:
        km = KMeans(n_clusters=ki, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append(float(km.inertia_))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(X_scaled[:, 0], X_scaled[:, 1], c=labels, cmap="tab10", alpha=0.7, s=12)
    axes[0].scatter(centers[:, 0], centers[:, 1], c="red", marker="X", s=200, zorder=5)
    axes[0].set_title(f"KMeans (k={n_clusters})  Silhouette={sil:.3f}")
    axes[0].grid(True)
    axes[1].plot(ks, inertias, "bo-")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("Inertia")
    axes[1].set_title("Elbow Method")
    axes[1].grid(True)
    plt.tight_layout()

    return {
        "image_base64": _png_base64(fig, plt, dpi=120),
        "silhouette_score": sil,
        "inertia": float(model.inertia_),
        "elbow": {"ks": ks, "inertias": inertias},
    }


def svm(*, kernel: str, c: float) -> dict[str, object]:
    """SVM 결정 경계 + 서포트 벡터. `routers/ml.py:315~368` 그대로다.

    인자 이름만 `C` → `c` 로 낮췄다. 요청 필드는 `C` 로 남는다(화면이 그 이름을
    보낸다). 파이썬 쪽에서 대문자 한 글자 인자는 상수로 읽히기 쉬워서다.
    """
    import matplotlib
    import numpy as np
    from sklearn.datasets import make_classification
    from sklearn.inspection import DecisionBoundaryDisplay
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    X, y = make_classification(
        n_samples=300, n_features=2, n_redundant=0, n_informative=2,
        n_clusters_per_class=1, random_state=42,
    )
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=42)

    model = SVC(kernel=kernel, C=c, gamma="scale", random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True)
    accuracy = float(accuracy_score(y_test, y_pred))
    n_support = int(np.sum(model.n_support_))

    fig, ax = plt.subplots(figsize=(7, 5))
    DecisionBoundaryDisplay.from_estimator(
        model, X_scaled, ax=ax, alpha=0.3, cmap=plt.cm.coolwarm, response_method="predict"
    )
    ax.scatter(X_train[:, 0], X_train[:, 1], c=y_train, cmap=plt.cm.coolwarm, edgecolors="k", s=25, label="Train")
    ax.scatter(X_test[:, 0], X_test[:, 1], c=y_test, cmap=plt.cm.coolwarm, marker="^", edgecolors="k", s=25, label="Test")
    ax.scatter(
        model.support_vectors_[:, 0], model.support_vectors_[:, 1],
        s=100, linewidth=1.5, facecolors="none", edgecolors="k", label="Support Vectors",
    )
    ax.set_title(f"SVM ({kernel} kernel, C={c})  Acc={accuracy:.3f}")
    ax.legend(fontsize=8)
    ax.grid(True)
    plt.tight_layout()

    return {
        "image_base64": _png_base64(fig, plt, dpi=140),
        "accuracy": accuracy,
        "n_support_vectors": n_support,
        "report": report,
    }


def mlp(*, hidden_layers: str, max_iter: int, n_samples: int) -> dict[str, object]:
    """다층 퍼셉트론의 손실 곡선. `routers/ml.py:371~419` 그대로다.

    `hidden_layers` 는 `"128,64,32"` 같은 문자열로 온다. **모양 검사는 라우터의
    `pattern` 이 이미 끝냈고**(`^\\d+(,\\d+)*$`), 여기서는 정수 튜플로 바꾸기만 한다.
    """
    import matplotlib
    from sklearn.datasets import make_classification
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    layers = tuple(int(x) for x in hidden_layers.split(","))

    X, y = make_classification(
        n_samples=n_samples, n_features=10, n_informative=6,
        n_redundant=2, n_classes=2, random_state=42,
    )
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    model = MLPClassifier(
        hidden_layer_sizes=layers, activation="relu", solver="adam",
        max_iter=max_iter, random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(model.loss_curve_, linewidth=2, color="#2563eb")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Loss")
    ax.set_title(f"MLP Loss Curve  (layers={layers})  Acc={accuracy:.3f}")
    ax.grid(True)
    plt.tight_layout()

    return {
        "image_base64": _png_base64(fig, plt, dpi=140),
        "accuracy": accuracy,
        "n_iterations": model.n_iter_,
        "report": report,
    }


def linear_regression(*, degree: int, n_samples: int, noise: float) -> dict[str, object]:
    """다항 회귀 적합. `routers/ml.py:422~473` 그대로다."""
    import matplotlib
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_squared_error, r2_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(42)
    X = rng.uniform(0, 10, size=(n_samples, 1))
    # 차수를 올리면 다항 항이 실제로 이득을 보도록 참 함수 자체를 2차까지 섞어 둔다.
    y = sum(
        c * X.ravel() ** i
        for i, c in enumerate([10, -4, 0.5][: degree + 1])
    ) + rng.normal(0, noise, n_samples)

    model = make_pipeline(
        PolynomialFeatures(degree=degree, include_bias=False),
        LinearRegression(),
    )
    model.fit(X, y)
    y_pred = model.predict(X)
    r2 = float(r2_score(y, y_pred))
    mse = float(mean_squared_error(y, y_pred))

    X_plot = np.linspace(0, 10, 200).reshape(-1, 1)
    y_plot = model.predict(X_plot)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(X, y, alpha=0.4, s=15, label="Data")
    ax.plot(X_plot, y_plot, "r-", linewidth=2, label=f"Poly degree={degree}")
    ax.set_title(f"Regression (degree={degree})  R²={r2:.3f}  MSE={mse:.2f}")
    ax.set_xlabel("X")
    ax.set_ylabel("y")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()

    return {
        "image_base64": _png_base64(fig, plt, dpi=140),
        "r2_score": r2,
        "mse": mse,
        "degree": degree,
    }
