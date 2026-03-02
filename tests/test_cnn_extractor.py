from __future__ import annotations

import pytest
import torch


def test_window_cnn_extractor_output_shape() -> None:
    gym = pytest.importorskip("gymnasium")
    pytest.importorskip("stable_baselines3")
    from forex.ml.rl.models import WindowCnnExtractor

    observation_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(25,), dtype=float)
    extractor = WindowCnnExtractor(
        observation_space,
        window_size=4,
        feature_dim=6,
        cnn_output_dim=32,
    )
    batch = torch.zeros((3, 25), dtype=torch.float32)
    out = extractor(batch)
    assert out.shape == (3, 32)
