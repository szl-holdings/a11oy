# Sign a voice transcript

**id:** `recipe-transcript-sign`  
**tags:** speech, stt, voice, transcript, sign, provenance, aide  

## Summary
Transcribe speech (STT) and sign the transcript so the spoken record is provenanced.

## Steps
1. Send audio to the speech specialist (STT).
2. Sign the transcript via szl_dsse.
3. Store signed transcript for recall.

## Code
```python
from szl_speech import transcribe
from szl_dsse import sign_payload
env = sign_payload({'transcript': transcribe(audio)})
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._