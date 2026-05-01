import math


def compute_edge_metrics(weights, log_scale=True):
    """
    Compute normalized and scaled weights for consistent visualization.
    """

    if not weights:
        return []

    # --- scaling ---
    if log_scale:
        scaled = [math.log1p(w) for w in weights]
    else:
        scaled = list(weights)

    max_scaled = max(scaled) if scaled else 1.0
    max_scaled = max(max_scaled, 1e-9)

    norm = [s / max_scaled for s in scaled]

    return scaled, norm


def style_edges(edges):
    if not edges:
        return edges

    # --- extract weights ONLY for similarity edges ---
    sim_weights = [e["weight"] for e in edges if e["type"] == "similarity"]

    _, norm = compute_edge_metrics(sim_weights, log_scale=True)

    # map normalized weights back
    norm_iter = iter(norm)

    styled = []

    for e in edges:
        if e["type"] == "kde":
            styled.append({
                **e,
                "color": "#cccccc",
                "size": 0.5,
                "type_sigma": "dashed",
                "alpha": 0.4
            })
        else:
            w_norm = next(norm_iter, 0.5)

            styled.append({
                **e,
                "color": "#888888",
                "size": 0.5 + 2.5 * w_norm,   # 👈 key improvement
                "type_sigma": "line",
                "alpha": 0.9
            })

    return styled
