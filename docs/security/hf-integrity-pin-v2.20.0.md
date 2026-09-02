# Hugging Face integrity validator pin advance

The protected Hugging Face repository-parity workflow, its independent source-integrity validator, and all adversarial fixtures now agree on the fixed Harden-Runner commit:

`bf7454d06d71f1098171f2acdf0cd4708d7b5920` (`v2.20.0`)

The branch controller proved the complete 50-case source-integrity suite, the repository-parity unit tests, and the canonical validator before committing the replacement and removing itself.

This change does not weaken any workflow envelope, permitted action, source pin, immutable revision, or fail-closed policy. It advances the accepted security dependency while preserving the same independent validation boundary.
