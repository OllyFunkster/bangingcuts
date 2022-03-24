# Banging Cuts
Blender VSE Addon to cut up audio and video clips based on peaks in the audio track.

## Why?
I got bored of doing this kind of editing manually.

## How to install
Download the zip of this repo, save it wherever you like. Open Blender preferences and navigate to Addons, then choose Install and pick the zip file. Tick the box at the left of the list to enable the addon.

## How to use it:
Select your strips - generally, one video strip and one audio strip that are the same length and are in sync with each other.

Click on Banging Cuts on the top right of the sequencer panel, and choose Make Cuts. A dialog appears and you can choose how many frames you want before and after the peak, and the audio level to use as the threshold. Make some appropriate choices.

Click OK, and after a short pause your clip will be reduced to however many smaller clips each containing one peak.

## Limitations:
- There's no implicit support for working on multiple audio clips, as it just uses whichever selected audio clip comes first in the internal list (which may not correspond to selection order or scene channel). Might work, might not. Let me know.
- Goodness knows what happens if the video strip has modifier strips on it - use the addon before you start getting into crossfades etc.
- It can cope with audio and video clips that have different lengths etc. (e.g. audio from a separate recorder that you have synced) but if the audio has peaks after the end of the video, it'll break.
- Since audio strips can only be shuffled around at 1-frame resolution, the peaks won't be perfectly aligned with a frame, so if you're going for a super tight clip to get a buzz of events, the period will be a bit wonky. If this is a problem you can maybe resample to a higher framerate.
