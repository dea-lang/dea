# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from l0_analysis import AnalysisResult
from l0_c_emitter import CEmitter
from l0_backend_state import BackendState
from l0_backend_convert import OwnershipConversion
from l0_backend_lifetime import ValueLifetime
from l0_backend_initializers import StaticInitializers
from l0_backend_ordering import TypeOrdering
from l0_backend_module import ModuleGeneration
from l0_backend_lowering import Lowering


@dataclass
class Backend:
    """Generate C from one analyzed compilation unit through explicit collaborators."""

    analysis: AnalysisResult
    emitter: CEmitter = field(default_factory=CEmitter)

    def __post_init__(self) -> None:
        """Connect backend algorithms to one canonical emission and scope state."""
        self.state = BackendState(self.analysis, self.emitter)
        self.convert = OwnershipConversion(state=self.state)
        self.lifetime = ValueLifetime(convert=self.convert, state=self.state)
        self.initializers = StaticInitializers(state=self.state)
        self.ordering = TypeOrdering(state=self.state)
        self.lowering = Lowering(convert=self.convert, lifetime=self.lifetime, state=self.state)
        self.module = ModuleGeneration(initializers=self.initializers, lifetime=self.lifetime, lowering=self.lowering, ordering=self.ordering, state=self.state)

    def generate(self) -> str:
        """Generate the complete C translation unit.

        Returns:
            Generated C source, including its final newline.

        Raises:
            ValueError: If the analysis is missing a unit or contains errors.
        """
        return self.module.generate()
