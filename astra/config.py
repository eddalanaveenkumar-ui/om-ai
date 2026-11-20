import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    shared_key: str = os.getenv("NVIDIA_API_KEY", "")
    orchestrator_key: str = os.getenv("ORCHESTRATOR_API_KEY", "")
    planner_key: str = os.getenv("PLANNER_API_KEY", "")
    executor_key: str = os.getenv("EXECUTOR_API_KEY", "")
    verifier_key: str = os.getenv("VERIFIER_API_KEY", "")
    computer_key: str = os.getenv("COMPUTER_API_KEY", "")

    # Distinct models by role. Verify exact IDs and endpoint access in your NVIDIA account.
    orchestrator_model: str = os.getenv("ORCHESTRATOR_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    planner_model: str = os.getenv("PLANNER_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    executor_model: str = os.getenv("EXECUTOR_MODEL", "nvidia/nemotron-3.5-bolt-e4b")
    verifier_model: str = os.getenv("VERIFIER_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    computer_model: str = os.getenv("COMPUTER_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")

    max_tokens: int = int(os.getenv("MAX_TOKENS", "1800"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.2"))
    agent_timeout_seconds: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))

    def key_for(self, agent: str) -> str:
        specific = getattr(self, f"{agent}_key", "")
        return specific or self.shared_key

settings = Settings()
