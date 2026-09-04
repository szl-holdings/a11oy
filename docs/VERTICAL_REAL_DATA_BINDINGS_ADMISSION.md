# Six flagship Spaces — governed real-data admission

The binding release is admissible only when every permanent source and deployment control below passes on the same exact head.

## Product experience

- Terra, Sentra, PRISM Counsel, PURIQ Finance, Vessels, and Lyte expose their existing product feed and a distinct official-source evidence channel.
- Phone layouts collapse to one readable column with no document-level horizontal overflow.
- Interactive controls are at least 44 pixels and at least 48 pixels for coarse pointers.
- Technical URLs and JSON wrap or scroll inside bounded regions.
- Keyboard focus, reduced motion, increased contrast, forced colors, and safe-area insets remain supported.
- User, developer, and investor evidence is progressively disclosed rather than reduced to a scaled desktop dashboard.

## Data truth

- Official evidence is supplied by the A11oy Governed Real Data Gateway.
- Each source is independently labelled `LIVE`, `CACHED`, or `UNAVAILABLE`.
- A provider failure is never converted into an empty market, zero risk, success claim, or sample record.
- Product-feed availability and official-evidence availability remain independent.
- A Space may report `PARTIAL` when exactly one channel is observed.

## Authority and deployment

- `external_writes=DISABLED`
- `effectors=[]`
- `production_authorization=false`
- the existing `HF Publish Vertical Flagships` workflow remains the single canonical writer
- no second Space writer, provider mutation, secret, hardware change, or branch-protection bypass
- publisher success requires every Space to be `RUNNING`, return an exact HTTP 200 root with the Public Experience marker, and return an exact HTTP 200 `/api/live` payload bound to the expected evidence URL
- an independent post-publish workflow verifies all six deployed contracts and requires at least one current or cached official evidence observation before the release is described as operational
