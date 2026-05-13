import os
import sys
from typing import Optional


class GroqFeedback:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.enabled = bool(self.api_key)
        self.client = None
        
        if self.enabled:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
            except ImportError:
                print("Warning: openai library not available, disabling AI feedback.", file=sys.stderr)
                self.enabled = False
            except Exception as e:
                print(f"Warning: Failed to init Groq client, disabling AI feedback: {e}", file=sys.stderr)
                self.enabled = False

    def generate_feedback(
        self,
        expected_text: str | None,
        transcribed_text: str,
        accuracy_score: float,
        mispronounced_words: list[dict],
        has_expected: bool,
    ) -> Optional[str]:
        if not self.enabled or not self.client:
            return None

        try:
            mispronounced_str = ""
            if mispronounced_words:
                mispronounced_str = "\n".join(
                    [f"- Expected: '{w.get('expected', '')}', Spoken: '{w.get('spoken', '')}'" for w in mispronounced_words[:5]]
                )

            prompt = f"""You are a friendly pronunciation coach helping someone improve their English speaking skills.

Context:
- Overall accuracy: {accuracy_score:.1f}%
- Spoken text: {transcribed_text}"""

            if has_expected and expected_text:
                prompt += f"""
- Expected text: {expected_text}
- Words needing attention:
{mispronounced_str}"""

            prompt += """

Please provide concise, encouraging feedback in 3-4 sentences. Focus on:
1. One positive aspect of their pronunciation
2. One specific area to improve (if accuracy < 95%)
3. A simple tip to practice
4. Keep it conversational, not too technical

Avoid jargon. Make it supportive and actionable.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"Groq API error: {e}", file=sys.stderr)
            return None

    def generate_grammar_analysis(self, transcribed_text: str) -> Optional[str]:
        if not self.enabled or not self.client:
            return None

        try:
            prompt = f"""You are an English grammar expert. Please analyze the following transcribed text for any grammatical errors.
Text: "{transcribed_text}"

Provide a concise, helpful summary (2-3 sentences) of any grammar, structural, or usage issues. If the grammar is perfect, say "Your grammar is perfect!" and briefly explain why it's well-structured. Keep the tone encouraging."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=250,
            )

            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq API error (grammar): {e}", file=sys.stderr)
            return None
