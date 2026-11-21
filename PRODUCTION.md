# Planck to Parsec: daily production guide

This is the working procedure for the daily short. Channel: **Planck to Parsec** on YouTube (owner: Reza).
One video = one astonishing, true, simple physics fact, animated, 35 to 50 seconds, vertical (see "Length and the final third").

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
- Each suggestion: an exciting title (rules below), the one fact in a sentence, the opening line of the video,
  and for news items the news hook with its date and source.
  Make the three different in subject.
- Prefer facts that can be *shown* (scale comparisons, motion, counts) over facts that need a derivation.
- Videos about people's work show the physics, never a real person's face or voice.

## Titles and the opening hook

**Title.** The title is half of whether anyone watches. Write five candidates and keep the best.
- Under 70 characters, with the surprising part in the first few words.
- Build it on a concrete contrast, number or question: "A teaspoon of this star outweighs a mountain",
  "100 trillion ghosts pass through you every second", "Why your head is older than your feet".
- Create curiosity, then keep the promise: the video must deliver exactly what the title claims.
  No fake mysteries, no "scientists are shocked", no "you won't believe", no all-caps words.
- For news topics, name what is new: "The 2026 Nobel Prize in one minute: ..." only if the video does that.

**The first three seconds.** Viewers decide almost instantly whether to swipe away.
- The first caption appears by 0.3 s and the first spoken line starts at once. No logo, no greeting, no
  "did you know", no channel name, no scene-setting.
- Open with the most astonishing claim in the video or a sharp question, in eight words or fewer on screen.
  Start with the consequence, then explain: "Right now, 100 trillion particles are passing through you."
- Something must already be moving in the first frame, and the picture should show the claim, not decorate it.
- Leave a loop open that only the ending closes ("...and we only found out because of a tank of cleaning fluid"),
  and make the last line pay it off. Keep the first spoken line under about four seconds.
- Every following scene should raise a small new question or escalate the scale, so there is always a reason
  to stay for the next ten seconds. Put the single biggest number or image near the end, not the middle.

**Length and the final third.** (From YouTube's early analytics on the Sun tunnelling short, 2026-11-20: 67% stayed
to watch, but average view was 41 s of a 66 s video, with the drop-off put at the move from the main reveal to a
secondary fact.)
- Aim for 35 to 50 seconds in the finished video: 6 to 8 captions, about 80 to 100 spoken words. Check the length
  printed by the draft build and cut lines if it is over 50 s.
- One idea only. After the main reveal, go straight to the closing payoff. No second fact, comparison or aside
  after the reveal, however good; save it for its own video or for the pinned comment.
- Corrections that accuracy needs stay in, but as a clause inside an existing line, not as an extra scene.
- With every preview, propose one short open question for Reza to pin as the first comment (a spare fact from the
  research works well, for example "Did you know your body makes more heat per litre than the Sun's core?").

## 3. The scene script

Copy `shorts/ligo_first_detection.py` to `shorts/<slug>.py` (underscores, no hyphens) and replace the content:

- `CAPTIONS`: list of `(start, end, kicker_or_None, text)`. `*word*` highlights in gold, `|` forces a line break,
  use a non-breaking space inside units ("4 km"). 6 to 8 captions, each at most about 14 words.
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

`scripts/<slug>.json`: one entry per caption: `{"say": spoken text, "speed": 0.92 to 1.06}` (`speed` is optional;
a plain string also works).

**No subtitles.** Reza does not want subtitles burned into the videos. Do not pass `--subtitles` to the build and do
not draw a running transcript on screen. The large captions at the top are the only text that follows the narration.

- Style: calm but alive. Short sentences, vivid verbs, a sense of wonder, no hype words. The caption is the
  condensed version of the spoken line.
- Write numbers as words ("nineteen sixteen", "one thousandth"). Spell awkward names phonetically
  (LIGO is written "Lie-go"). Years that can be misheard get help: say "in the year nineteen-sixteen", since
  "sixteen" and "sixty" sound alike, and show the year on screen. End the last line as a plain statement; the tool
  adds a gentle falling close.
- Stops and questions: `[0.7]` inside a line makes a deliberate stop of that many seconds, and the phrase after it is
  voiced on its own with a fresh intonation ("...be duplicated? [0.8] ~Nobody knows. [0.6] It is one of..."). A phrase
  starting with `~` is weighted (slightly slower and lower): use it for payoff phrases. A phrase ending in `?` gets a
  rising, questioning ending automatically; put a stop before or after a question so it is voiced as its own phrase.
- Voice `am_michael`, base speed 0.95, music mood `organ` (original synthesized music; these are the defaults).
- Never imitate a real person's voice and never use existing music, film scores, characters or footage.

## 5. Build and check

```
pip install --break-system-packages kokoro-onnx soundfile aggdraw scipy pillow numpy pyworld
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
3. Report the `play_url` to Reza, and say in the same message that the cover is set.

**The cover is mandatory.** Every upload is followed by the thumbnail action in the same run; an upload without its
cover is not finished. If the thumbnail action fails, retry it once after another minute, and if it still fails tell
Reza plainly that the video is live without its cover.

Upload limit: Zapier allows about 5 YouTube uploads per day on free and trial plans. The error
"This action has been throttled" means that limit was hit. Do not keep retrying: tell Reza, leave the
files pushed, and upload on a later day. Every re-upload of a corrected video also counts, so get the
preview approved before the first upload.

Always inspect the action with `inspect_zapier_actions` before executing. Upload exactly one video per day, only after Reza
approved its preview, and never change or delete other videos on the channel unless Reza asks.

## 7. Growth rules (apply to every Short)

- **G1 First-second hook:** the first frame already moves and shows the most surprising claim or a sharp question, spoken from 0.0 s. No intro, logo or slow fade-in.
- **G2 On-screen hook text:** one short line of large text (at most about 8 words) in the first frame, held 2 to 3 s. A title card, never the full narration as subtitles.
- **G3 Looping ending:** the last spoken line flows back into the opening line when the Short replays; the final frame matches or leads into the first. Narrator tone settles down. (Parts 1 and 2 of a series end with a teaser instead, see S3.)
- **G4 Caption file:** an English SRT `captions/<slug>.srt` timed to the narration audio, numbers and years as digits. Commit it with the scene script.
- **G5 Series number:** the channel number N is the number of published rows in `log.md` plus 1. "Planck to Parsec #N" is the first line of the description and small text on the cover, not in the title.
- **G6 Comment question:** one short, curious question for viewers, posted as the pinned comment and ending the description.
- **G7 Description and tags:** the first two lines hold the main search terms; include sources; add 3 hashtags including #Shorts and #physics.

## 8. Series rules (multi-part stories, one part per day)

- **S1** A series is one story told in 3 Shorts on consecutive days. Each part is a complete Short built with all growth rules.
- **S2** Each part has its own title followed by " (Part k/3)"; the cover shows "Part k/3". The series name appears in every description, and each description links the earlier parts.
- **S3** Parts 1 and 2 end with a teaser for the next part instead of the loop. Part 3 pays off the story and may loop into part 1's opening.
- **S4** In `log.md` mark parts in the topic column as "<series name> - Part k/3". A series is in progress if Part 1 or 2 is logged and Part 3 is not.
- **S5** While a series is in progress, do not offer three new topics: send the plan for the next part (title, what it covers, opening line and hook text, ending line) and ask Reza for "go" or changes.
