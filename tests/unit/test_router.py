import pytest

from gar.models.base import ModelNotFound, ModelProfile
from gar.models.router import Requirements, choose


def test_router_privacy_unknown_capability_cost_and_stable_order():
    profiles = [
        ModelProfile(id="remote", provider="x", coding=True, cost=0.1),
        ModelProfile(id="local", provider="o", local=True, cost=0.0),
    ]
    assert choose(profiles, Requirements(local_only=True)).id == "local"
    with pytest.raises(ModelNotFound):
        choose(profiles, Requirements(local_only=True, coding=True))
    with pytest.raises(ModelNotFound):
        choose(profiles, Requirements(context_size=1000))
    assert choose(profiles, Requirements(coding=True, max_cost=0.2)).id == "remote"
    assert choose(list(reversed(profiles)), Requirements()).id == "local"
