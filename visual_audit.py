"""Visual Audit — Claude Vision analyses a website screenshot for design & conversion issues."""

import anthropic
import base64
import os
from pathlib import Path


AUDIT_PROMPT = """You are a conversion rate optimisation expert and UX designer reviewing a website screenshot.

Analyse this website screenshot and provide a structured visual audit. Be specific, actionable, and direct.

Return your analysis in exactly this format:

## Overall Visual Score: [X/100]
[One sentence overall impression]

## 🎯 Above the Fold
**Score: X/100**
- [Specific observation about headline clarity]
- [Specific observation about CTA visibility and placement]
- [Specific observation about value proposition clarity]
**Fix:** [Most important single change]

## 🔤 Typography & Readability
**Score: X/100**
- [Font size and hierarchy observations]
- [Line length and spacing]
- [Contrast and legibility]
**Fix:** [Most important single change]

## 🎨 Visual Hierarchy & Layout
**Score: X/100**
- [What draws the eye first — is it correct?]
- [Whitespace usage]
- [Section organisation]
**Fix:** [Most important single change]

## 🛡️ Trust Signals
**Score: X/100**
- [Social proof: testimonials, reviews, user count]
- [Authority signals: logos, certifications, press]
- [Security signals: SSL indicators, privacy]
**Fix:** [Most important single change]

## 📱 Mobile Readiness (from what's visible)
**Score: X/100**
- [Touch target sizes]
- [Text size on mobile]
- [Layout adaptability]
**Fix:** [Most important single change]

## ⚡ Conversion Elements
**Score: X/100**
- [Button visibility and copy]
- [Form friction]
- [Next step clarity]
**Fix:** [Most important single change]

## 🏆 Top 3 Priority Fixes
1. [Most impactful change — specific and actionable]
2. [Second most impactful]
3. [Third most impactful]

## ✅ What's Working Well
- [Genuine strength 1]
- [Genuine strength 2]
- [Genuine strength 3]

Be brutally honest. Don't soften feedback. Specific is more useful than general."""


def analyse_screenshot_visual(image_path: str) -> dict:
    """
    Run Claude Vision on a screenshot and return structured visual audit.

    Args:
        image_path: path to the image file (PNG, JPG, WEBP)

    Returns:
        {"score": int, "report": str, "error": str | None}
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"score": 0, "report": "", "error": "ANTHROPIC_API_KEY not set"}

    path = Path(image_path)
    if not path.exists():
        return {"score": 0, "report": "", "error": f"File not found: {image_path}"}

    ext = path.suffix.lower().lstrip(".")
    media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    try:
        image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                        {"type": "text", "text": AUDIT_PROMPT},
                    ],
                }
            ],
        )
        report = message.content[0].text

        # Extract overall score from report
        score = 0
        for line in report.split("\n"):
            if "Overall Visual Score:" in line:
                try:
                    score = int(line.split(":")[1].strip().split("/")[0].strip())
                except Exception:
                    pass
                break

        return {"score": score, "report": report, "error": None}

    except anthropic.AuthenticationError:
        return {"score": 0, "report": "", "error": "Invalid Anthropic API key"}
    except Exception as e:
        return {"score": 0, "report": "", "error": str(e)}
