#!/usr/bin/env python3
"""main.py — minimal Mistral chat completion using the official Python SDK.

Setup
-----
1. Install the official SDK:

       pip install mistralai

2. Generate an API key in Mistral Studio:
   - Sign in to the Studio console at https://console.mistral.ai
   - Open "API Keys" in the left sidebar, then select "New key"
   - Enter a name (for example "a11oy-example"), set an expiration date, and
     choose a connector access scope
   - Copy the key immediately: the full key is shown only once. Store it in a
     password manager or secrets vault. Never commit it to this repo.

3. Set MISTRAL_API_KEY in your terminal (it lasts for the current session only):

       PowerShell:  $env:MISTRAL_API_KEY = "your-api-key"
       CMD:         set MISTRAL_API_KEY=your-api-key
       bash / WSL:  export MISTRAL_API_KEY="your-api-key"

4. Run from the project folder:

       python main.py

The key is read from the MISTRAL_API_KEY environment variable; this file
never contains a key.

Reference: https://docs.mistral.ai/studio/conversations/chat-completion
"""

import os
import sys

from mistralai.client import Mistral

MODEL = "mistral-small-latest"


def main() -> int:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print(
            "MISTRAL_API_KEY is not set. Create a key in Mistral Studio "
            "(https://console.mistral.ai -> API Keys -> New key), then set it in "
            'this terminal, e.g. $env:MISTRAL_API_KEY = "your-api-key" '
            '(PowerShell) or export MISTRAL_API_KEY="your-api-key" (bash).',
            file=sys.stderr,
        )
        return 1

    client = Mistral(api_key=api_key)
    response = client.chat.complete(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "Say hello from mistral-small-latest in one short sentence.",
            }
        ],
    )
    print(response.choices[0].message.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
