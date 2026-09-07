# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from l0_analysis import AnalysisResult
from l0_c_state import CEmitterState
from l0_c_names import CNames
from l0_c_types import CTypes
from l0_c_declarations import CDeclarations
from l0_c_cleanup import CCleanup
from l0_c_values import CValues
from l0_c_statements import CStatements


@dataclass
class CEmitter:
    """One C emission session composed from explicit syntax collaborators.

    Each session owns its output, source context, name sequence, and optional
    wrapper registry. Collaborators receive only their declared dependencies.
    """

    state: CEmitterState = field(default_factory=CEmitterState)
    names: CNames = field(default_factory=CNames)
    types: CTypes = field(init=False)
    values: CValues = field(init=False)
    cleanup: CCleanup = field(init=False)
    declarations: CDeclarations = field(init=False)
    statements: CStatements = field(init=False)

    def __post_init__(self) -> None:
        """Connect syntax collaborators to this session's canonical owners."""
        self.types = CTypes(names=self.names, state=self.state)
        self.values = CValues(names=self.names, state=self.state, types=self.types)
        self.cleanup = CCleanup(names=self.names, state=self.state, values=self.values)
        self.declarations = CDeclarations(cleanup=self.cleanup, names=self.names, state=self.state, types=self.types)
        self.statements = CStatements(names=self.names, state=self.state, types=self.types, values=self.values)

    def set_analysis(self, analysis: AnalysisResult) -> None:
        """Initialize emitter with analysis data.

        Args:
            analysis: The AnalysisResult containing the compilation products.
        """
        self.state.analysis = analysis

    def get_output(self) -> str:
        """Get the generated C code.

        Returns:
            The complete generated C code string.
        """
        return self.state.out.to_string()
