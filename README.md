# Banging Cuts
Blender VSE Addon to cut up audio and video clips based on peaks in the audio track.

## Why?
I got bored of doing this kind of editing manually.

## How to install
[Download the zip](https://github.com/OllyFunkster/bangingcuts/archive/refs/heads/main.zip) of this repo, save it wherever you like. Open Blender preferences and navigate to Addons, then choose Install and pick the zip file. Tick the box at the left of the list to enable the addon, and you should see a Banging Cuts menu appear on the right hand side of the Sequencer area's menu bar.

## How to use it:
Select your strips - generally, one video strip and one audio strip that are the same length and are in sync with each other. Optionally, multiple strips - the audio strip with the highest channel number in the sequencer will be used as the reference strip.

Click on Banging Cuts on the top right of the sequencer panel, and choose Make Cuts. A dialog appears and you can choose how many frames you want before and after the peak, the audio level to use as the threshold, and the operation mode. Make some appropriate choices.

### Operation modes:
- **Bang:** Makes fixed-length clips at each point where the audio rises above threshold, and does not retrigger until after audio drops back below threshold. Use pre- and post-roll frame counts to determine the length of the clip and the position of the audio peak within the clip.
- **Remove Silence:** Makes variable-length clips containing the sections where the audio was above the threshold. Use the pre- and post-roll frame counts to control the smallest length of silence to be removed (low pre- and post-roll will result in more smaller clips).
- **Naive:** Probably not useful. Tell me if you think otherwise.

Click OK, and after a short* pause your clip will be reduced to however many smaller clips each containing one peak.

If your other strips were shorter than your reference strip, you will just get the bits of those strips that overlapped peaks in the reference.

*depends on variable, obviously. It's not exactly efficient, and if you have a long clip it'll take a while - it shows progress via the mouse cursor.

## Demo
[![Banging Cuts demo video on YouTube](https://img.youtube.com/vi/9Aih2OgvYlo/0.jpg)](http://www.youtube.com/watch?v=9Aih2OgvYlo)

## Limitations:
- Goodness knows what happens if the video strip has modifier strips on it - use the addon before you start getting into crossfades etc.
- Since audio strips can only be shuffled around at 1-frame resolution, the peaks won't be perfectly aligned with a frame, so if you're going for a super tight clip to get a buzz of events, the period will be a bit wonky. If this is a problem you can maybe resample to a higher framerate.
