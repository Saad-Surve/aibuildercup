"""Platform Dynamics reviewer (`platform_fit`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review whether the script conforms to the distribution mechanics and user
expectations of the target platform named in the task.

PLATFORM-SPECIFIC BENCHMARKS:
- YouTube long-form: sustained narrative arc, chapter signposting, title-to-hook
  continuity, and end-screen video transitions.
- TikTok / Instagram Reels / YouTube Shorts: sub-2-second verbal disruption, zero intro
  fluff, high information density, and natural loops back to the start.
- LinkedIn / professional video: actionable professional insights, clean framing, early
  value delivery, and professional context without corporate buzzwords.

WHAT TO FLAG:
- Repurposed Artifacts: spoken references to an action unavailable on this platform
  (for example "swipe up" where that action is unavailable). Establish that the action
  is unavailable or poorly suited to this format first; short videos can have descriptions.
- Platform Mismatch: pacing that is either too slow for short-form or too frenetic for
  long-form educational content.

Do not reward generic "good content" - reward fit.
Respect the actual video format, duration, and creator brief. Do not apply short-form
rules to long-form content or prescribe arbitrary cut frequencies. For a mismatch give
the exact opening/transition/CTA replacement or edit, not a vague platform best practice.

findingType vocabulary (severity in brackets):
  native_execution         [none]   an opening/format that is native to the platform (score 5)
  slow_scroll_stop         [high]   on short-form
  repurposed_artifact      [medium]
  platform_pacing_mismatch [high]
  off_platform_framing     [medium]"""


class PlatformFitReviewer(LlmReviewer):
    dimension = AnalysisDimension.platform_fit
    focus = FOCUS
    finding_types = (
        "native_execution",
        "slow_scroll_stop",
        "repurposed_artifact",
        "platform_pacing_mismatch",
        "off_platform_framing",
    )
