# Planck to Parsec: daily production guide

This is the working procedure for the daily short. Channel: **Planck to Parsec** on YouTube (owner: Reza).
One video = one astonishing, true, simple physics fact, animated, 45 to 75 seconds, vertical.

## 1. Daily flow

1. **Suggest three topics** (see section 2). Send them to Reza and wait for his pick. No pick, no video: never choose for him.
2. **Fact-check** the picked topic with web search against primary sources (experiment collaborations, NASA/ESA/CERN,
   journals, university pages). Every number in the video needs a source. Drop or reword anything you cannot verify.
3. **Write** the scene script `shorts/<slug>.py` and narration `scripts/<slug>.json` (sections 3 and 4).
4. **Draft render** with `--draft`, look at one frame per caption, fix overlaps and clipped text (section 5).
5. **Full render** (4K, 60 fps) with `template/build.py`.
6. **Preview**: send Reza the MP4 and the cover with the proposed title, description, tags and sources, and wait.
   Do not push the video or upload before he approves. If he asks for changes, rebuild and send a new preview.
7. **After his explicit approval only**: commit and push to `main`, then upload through Zapier and set the cover (section 6).
8. **Log it** in `log.md` (date, topic, slug, YouTube link) and push. Send Reza the link.

There are two approvals every day: the topic, then the finished video. Nothing is published without the second.

If any step fails in a way you cannot fix, stop, tell Reza what failed, and do not upload a broken or unverified video.

## 2. Choosing the three suggestions

Start from the news, then fill with timeless facts.

- Read `log.md` first and never repeat a topic already covered.
- Subjects: particle physics, black holes, quantum mechanics and quantum field theory, relativity, Bell's theorem,
  dark matter and dark energy, gravitational waves, the LHC, cosmology, neutrinos, the early universe.
- Search the web for news from roughly the past few weeks: the latest Nobel Prize in Physics and the research
  behind it, CERN and LHC results, LIGO-Virgo-KAGRA detections, JWST, Euclid, DESI and other surveys, neutrino and
  dark matter experiments, notable new papers. Pull out the astonishing, simple fact inside the story.
- Aim for at least two of the three options to come from recent news when the news is strong enough.
- Confirm each news item in at least two reliable sources (the experiment or institution, a journal, an established
  science outlet). No rumours or unconfirmed hype; say clearly when a result is preliminary.
- Each suggestion: a working title, the one fact in a sentence, and for news items the hook with its date and source.
  Make the three different in subject.
- Prefer facts that can be *shown* (scale comparisons, motion, counts) over facts that need a derivation.
- Videos about people's work show the physics, never a real person's face or voice.

## 3. The scene script

Copy `shorts/ligo_first_detection.py` to `shorts/<slug>.py` (underscores, no hyphens) and replace the content:

- `CAPTIONS`: list of `(start, end, kicker_or_None, text)`. `*word*` highlights in gold, `|` forces a line break,
  use a non-breaking space inside units ("4 km"). 8 to 12 captions, each at most about 14 words.
- `DUR`: end of the picture timeline. Scene timings are for the pictures only; the build stretches each caption's
  scene to fit its narration line.
- Scene functions draw with `circ`, `line`, `rect` in 1080x1920 layout units (the canvas scales to 4K by itself);
  labels go through `texts.append((label_sprite(...), x, y, alpha))`. `win(T, a, b)` gives fade in/out.
- Keep the helper code (Canvas, text sprites, background, `frame`) unchanged unless a scene truly needs more.

Layout rules (layout units): captions occupy y 250 to 640; pictures live in y 650 to 1500; keep the bottom 400
and the right-hand 130 clear because the Shorts interface covers them. Palette: white text, gold highlights
(255,196,92), cyan accents (110,225,255), dark navy starfield. One idea per scene.

Honesty rules: if motion or size is exaggerated, or a curve is schematic, label it on screen
("motion hugely exaggerated", "illustration"). Never show a number that is not in your sources.

## 4. Narration

`scripts/<slug>.json`: one entry per caption, `"text"` or `["text", speed_multiplier]` (0.92 to 1.06).

- Style: calm but alive. Short sentences, vivid verbs, a sense of wonder, no hype words. The caption is the
  condensed version of the spoken line.
- Write numbers as words ("nineteen sixteen", "one thousandth"). Spell awkward names phonetically
  (LIGO is written "Lie-go"). End the last line as a plain statement; the tool adds a gentle falling close.
- Voice `am_michael`, base speed 0.95, music mood `organ` (original synthesized music; these are the defaults).
- Never imitate a real person's voice and never use existing music, film scores, characters or footage.

## 5. Build and check

```
pip install --break-system-packages kokoro-onnx soundfile aggdraw scipy pillow numpy
python3 template/build.py shorts/<slug>.py scripts/<slug>.json <slug> --draft \
    --impact <picture-time of the big moment> 
# look at frames: ffmpeg -ss <t> -i build/<slug>/draft.mp4 -frames:v 1 f.jpg  (one per caption)
python3 template/build.py shorts/<slug>.py scripts/<slug>.json <slug> --impact <t> \
    --cover-time <picture-time of the best still> --cover-text "LINE|WITH *GOLD*|WORDS" --cover-footer "TOPIC · YEAR"
```

Outputs `videos/<slug>.mp4` (2160x3840, 60 fps) and `covers/<slug>.jpg`. The full render takes roughly 7 to 10 minutes.
Check the final file with ffprobe (video and audio streams present, under 95 MB for GitHub) and view a few frames.
Nobody can listen to the audio during the run, so keep narration text simple and check `durs.json` for odd lengths.

## 6. Upload (Zapier, YouTube app `YouTubeV4CLIAPI`)

Push first; Zapier fetches files from
`https://raw.githubusercontent.com/Obligence/planck-to-parsec/main/videos/<slug>.mp4` (check it returns 200).

1. `upload_video` (tool_name `youtube_upload_video`): `title` (under 90 characters), `description` (two sentences,
   a "Sources:" line, then `#Shorts #physics` plus two or three topic hashtags), `video` = raw URL,
   `privacy_status` "public", `tags` (5 to 8), `default_language` "en", `default_audio_language` "en",
   `category_id` "28", `made_for_kids` false. Do not pass the thumbnail here; it is ignored for Shorts.
2. Wait about three minutes, then `upload_video_thumbnail` (tool_name `youtube_update_video_thumbnail`) with
   `video_id` and `thumbnail` = raw URL of `covers/<slug>.jpg`. Success shows a `shortsAspectRatio` entry.
3. Report the `play_url` to Reza.

Always inspect the action with `inspect_zapier_actions` before executing. Upload exactly one video per day, only after Reza
approved its preview, and never change or delete other videos on the channel unless Reza asks.
