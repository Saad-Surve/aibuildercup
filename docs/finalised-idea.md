...timeline

user memory (persona) -> on onboarding we will get some data + update as we go -> (most likely 100% -> user-profile.md)

script generation -> thumbnail -> caption etc -> community polls tweets linkedin

browser -> gcs -> signed url -> apna backend -> auto generate transcript

MAIN ENTITY -> project

User -> many projects

project -> 

- video_url
- chats
- thumbnails
- transcript
- export_video_url (semi-mvp) short form contents
- debugger-suggestions(keep/undo)

label green - most understood red vague
---------------------------------------------------------------------------
             |.   |          |.    |               |.      |
waghskar       red             red                     red    
panchal        green          pink                    green 
kkd sir
modiji         orange         orange                 orange

| Content reviewer | What it evaluates |
|---|---|
| Truth & evidence reviewer | Factual accuracy, unsupported claims, source quality, misinformation |
| Clarity reviewer | Whether the message is understandable, specific, and free of ambiguity |
| Structure reviewer | Hook, narrative flow, pacing, transitions, intro/outro, conclusion |
| Audience-fit reviewer | Whether it matches the intended audience’s knowledge, interests, language, and context |
| Brand/voice reviewer | Tone, personality, consistency, positioning, and brand safety |
| Engagement reviewer | Likelihood of holding attention, generating comments, shares, or retention |
| Emotional reviewer | Emotional impact, empathy, relatability, and whether the tone feels appropriate |
| Cultural/localization reviewer | Regional sensitivities, translations, idioms, cultural references, and inclusivity |
| Platform reviewer | Suitability for YouTube Shorts, Instagram, LinkedIn, X, newsletters, etc. |
| SEO/discoverability reviewer | Title, keywords, captions, hashtags, metadata, and search intent |
| Visual reviewer | Thumbnail, visual hierarchy, subtitle readability, framing, and accessibility |
| Legal/safety reviewer | Copyright, defamation, privacy, regulated claims, and harmful content |
| Conversion reviewer | Whether the content achieves its objective: educate, subscribe, click, buy, or share |

```json
{
  "dimension": "clarity",
  "score": 7,
  "confidence": 0.86,
  "severity": "medium",
  "evidence": "The speaker introduces three concepts but never defines the second one.",
  "suggestion": "Add a one-sentence definition before continuing.",
  "timestamp": "00:42-00:58"
}
```


misinformation analysis -> 1. straightforward facts/trivia verification 2. cites anything without a proper source that can be classified as misinformation

audience insights


persona platformnusar



audience insights -> coming from various connectors into bigquery -> sentimental analysis

comment analysis -> coming from various connectors into bigquery -> sentimental analysis

both the above into dashboard

presets for scripts and thumbnails



video -> transcription -> captions -> slices

long YT -> short form video -> polls etc

localization -> 

up to s3

medium/substack/e-newspaper blogs


semi mvp:

short form content intro outro - video generation

beyond mvp:

video generation

trending topics -> tbd

