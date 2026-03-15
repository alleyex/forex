from __future__ import annotations

import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


class WindowCnnExtractor(BaseFeaturesExtractor):
    """1D CNN extractor for flattened rolling-window observations."""

    def __init__(
        self,
        observation_space: gym.Space,
        *,
        window_size: int,
        feature_dim: int,
        cnn_output_dim: int = 128,
    ) -> None:
        self._window_size = max(1, int(window_size))
        self._feature_dim = max(1, int(feature_dim))
        expected_dim = self._window_size * self._feature_dim + 1
        obs_dim = int(observation_space.shape[0])
        if obs_dim != expected_dim:
            raise ValueError(
                f"WindowCnnExtractor expected obs_dim={expected_dim}, got {obs_dim}. "
                "Check window_size and feature_dim."
            )
        super().__init__(observation_space, features_dim=cnn_output_dim)

        channels = 64
        self._conv = nn.Sequential(
            nn.Conv1d(self._feature_dim, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self._head = nn.Sequential(
            nn.Linear(channels + 1, cnn_output_dim),
            nn.ReLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        sequence = observations[:, :-1]
        position = observations[:, -1:].float()
        sequence = sequence.view(-1, self._window_size, self._feature_dim).transpose(1, 2)
        cnn_features = self._conv(sequence)
        return self._head(torch.cat([cnn_features, position], dim=1))
