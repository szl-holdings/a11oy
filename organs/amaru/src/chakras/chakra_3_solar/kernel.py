# SPDX-License-Identifier: Apache-2.0
# Chakra 3 RIMAY — propose kernel
# Leader: vllm-project/vllm @ 6548560  (Apache-2.0)
# Distilled from: vllm/v1/sample/sampler.py  Sampler.sample()
import torch


def propose(state, world, features, priors, seed: int) -> int:
    logits = torch.tensor(priors, dtype=torch.float32)
    logits = logits + torch.tensor(features, dtype=torch.float32)
    g = torch.Generator(); g.manual_seed(seed)
    probs = torch.softmax(logits, dim=-1)
    return int(torch.multinomial(probs, 1, generator=g).item())
