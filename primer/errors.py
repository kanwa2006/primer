"""Custom exceptions for PRIMER (leaf module — imports nothing from PRIMER)."""


class PrimerError(Exception):
    """Base class for all PRIMER errors."""


class ConfigError(PrimerError):
    """Raised when configuration is invalid or required keys are missing."""


class OllamaOutputError(PrimerError):
    """Raised when a local Ollama model returns empty, non-UTF-8, or too-short output."""


class GenerationError(PrimerError):
    """Raised when AGENTS.md / CLAUDE.md generation fails after one retry."""


class AgentNotFoundError(PrimerError):
    """Raised when the eval agent CLI is not installed in the eval image."""


class InsufficientTasksError(PrimerError):
    """Raised when fewer than min_tasks validated tasks can be derived from the repo."""


class TaskValidationError(PrimerError):
    """Raised when a task candidate fails pre-flight validation."""


class IsolationError(PrimerError):
    """Raised when network/proxy/container isolation cannot be guaranteed."""


class HarnessValidityError(PrimerError):
    """Raised when the WITH arm does not acknowledge the context file (M4 gate).

    The fingerprint instruction planted in the context file was not found in
    the agent's log output. The harness cannot certify that the agent read the
    file. No delta is reported — abort, do not report (M4 ruling).
    """
