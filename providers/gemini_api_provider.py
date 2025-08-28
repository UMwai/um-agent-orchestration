from __future__ import annotations

import os

import google.generativeai as genai

from orchestrator.settings import ProviderCfg


def call_gemini_api(prompt: str, cfg: ProviderCfg) -> str:
    """
    Call Google Gemini API using the official SDK
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is required for Gemini API")

    # Configure the API key
    genai.configure(api_key=api_key)

    # Get the model
    model_name = cfg.model or "gemini-2.0-flash-exp"
    model = genai.GenerativeModel(model_name)

    try:
        # Generate content
        response = model.generate_content(prompt)

        if not response.text:
            raise RuntimeError("Empty response from Gemini API")

        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e!s}")
