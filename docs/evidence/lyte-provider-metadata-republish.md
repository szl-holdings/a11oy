# Source-owned Lyte provider-metadata repair

The canonical A11oy Hugging Face publisher is pinned to:

```text
szl-holdings/lyte-services@b26e66f18f563f5e9a98f8bdcfa5f28527e3e195
```

That protected-main revision repairs the three provider-card validation blockers observed during the prior publication attempt:

- the Space emoji is an Extended Pictographic emoji;
- `colorFrom` uses a supported Hugging Face gradient value;
- `short_description` is at most 60 characters.

This record is not deployment evidence. Protected merge must still run the canonical `hf-sync` single writer, publish the exact Dockerfile-derived closure, restart `SZLHOLDINGS/lyte`, and verify the running source revision and public API contract.
