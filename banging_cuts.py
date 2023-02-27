# Banging Cuts addon for Blender VSE
# Copyright (C) 2022 Funkster (funkster.org)
# 
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>

bl_info = {
    'name': 'Banging Cuts',
    'author': 'Funkster',
    'version': (0, 6),
    'blender': (2, 80, 0),
    'description': 'Banging Cuts addon for Blender VSE. Chop bits out of your strips in sync with audio peaks!',
    'category': 'Sequencer',
}

DEBUG = False

# how many audio samples to use for debounce
TRIGGER_DEBOUNCE_COUNT_FALLING = 50

import bpy
import aud
import numpy

class BANGING_CUTS_OT_make_cuts(bpy.types.Operator):
    bl_description = 'Use peaks above given threshold to isolate sections of selected strips'
    bl_idname = 'banging_cuts.make_cuts'
    bl_label = 'Make Cuts'
    
    audio_thresh_db: bpy.props.FloatProperty(
        name='Trigger threshold dB',
        description='audio level threshold for trigger',
        default=-15.0,
        max=-0.1,
        )
        
    frames_preroll: bpy.props.IntProperty(
        name='Preroll frames',
        description='how many frames to keep before the trigger',
        default=1,
        min=0,
        )
        
    frames_postroll: bpy.props.IntProperty(
        name='Postroll',
        description='how many frames to keep after the trigger',
        default=5,
        min=1,
        )
    
    auto_holdoff: bpy.props.BoolProperty(
        name='Auto holdoff',
        description="don't allow retrigger until level drops below threshold",
        default=True,
        )
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        edits = []
        thresh_rising = pow(10,self.audio_thresh_db / 20.0)
        # falling threshold is a little lower than rising, for a little bit of hysteresis
        thresh_falling = pow(10,(self.audio_thresh_db - 2) / 20.0)
        scene = context.scene
        actual_fps = scene.render.fps / scene.render.fps_base
        scene_samplerate = scene.render.ffmpeg.audio_mixrate
        reference_start = 0
        wm = context.window_manager
        soundstrips = []
        for strip in context.sequences:
            if strip.select and strip.type == 'SOUND':
                soundstrips.append(strip)
        
        if len(soundstrips) == 0:
            self.report({'WARNING'}, 'No sound strips selected')
            return {'CANCELLED'}
        
        ref_strip = soundstrips[0]
        if len(soundstrips) > 1:
            # need to figure out which strip has the highest channel number
            for strip in soundstrips:
                if strip.channel > ref_strip.channel:
                    ref_strip = strip
        
        strip_hard_start = ref_strip.frame_start
        reference_start = strip_hard_start
        start_offset = ref_strip.frame_offset_start
        # can't access audio samples directly from a sequencer audio strip, so instead we make a copy as an Aud sound object...
        audsound = aud.Sound(bpy.path.abspath(ref_strip.sound.filepath))
        cachedsound = audsound.cache()
        dataarray = audsound.data()
        audiochannels = dataarray.shape[1]
        numsamples = dataarray.shape[0]
        # can't get the strip's samplerate directly, so work it out the hard way...
        strip_samplerate = numsamples / (ref_strip.frame_duration / actual_fps)
        if DEBUG:
            self.report({'INFO'}, 'Ref strip has {} channels, {} samples per channel!'.format(audiochannels, numsamples))
            self.report({'INFO'}, 'start_offset is {}, actual_fps is {}, scene_samplerate is {}, strip_samplerate is {}, frame_final_duration is {}'.format(start_offset, actual_fps, scene_samplerate, strip_samplerate, ref_strip.frame_final_duration))
        # only start looking where the ref_strip actually starts
        startsample = int((start_offset / actual_fps) * strip_samplerate)
        # and only look until where the ref strip ends, even if the audio itself is longer
        endsample = startsample + int((ref_strip.frame_final_duration / actual_fps) * strip_samplerate)
        # leave room for the first preroll
        startsample += int(((self.frames_preroll + 1) / actual_fps) * strip_samplerate)
        # add some room at the end so that we always have room for the last post-roll
        endsample -= int(((self.frames_postroll + 1) / actual_fps) * strip_samplerate)
        if DEBUG:
            self.report({'INFO'}, 'startsample is {}, endsample is {}'.format(startsample, endsample))
        
        # ready to look for peaks!
        frame = 0
        wm.progress_begin(0, 100)
        progress = 0
        progress_prev = 0
        triggered = False
        sampleindex = startsample
        while sampleindex < endsample:
            frame = actual_fps * (sampleindex / strip_samplerate)
            if triggered:
                if dataarray[sampleindex][0] < thresh_falling and dataarray[sampleindex][0] > (0 - thresh_falling):
                    trigger_debounce += 1
                    if trigger_debounce > TRIGGER_DEBOUNCE_COUNT_FALLING:
                        if DEBUG:
                            self.report({'INFO'}, 'Back below threshold at frame {}'.format(frame))
                        triggered = False
                        trigger_debounce = 0
                else:
                    trigger_debounce = 0
            elif dataarray[sampleindex][0] > thresh_rising or dataarray[sampleindex][0] < (0 - thresh_rising):
                if self.auto_holdoff:
                    if DEBUG:
                        self.report({'INFO'}, 'Marking trigger active for holdoff at frame {}'.format(frame))
                    triggered = True
                    trigger_debounce = 0
                inpoint = int(frame - self.frames_preroll)
                if inpoint < 0:
                    inpoint = 0
                outpoint = int(frame + self.frames_postroll)
                edits.append([inpoint, outpoint])
                # advance until after postroll since we have already got this one
                sampleindex += int((self.frames_postroll / actual_fps) * strip_samplerate)
                # also advance until after next preroll so we don't get repeats
                sampleindex += int((self.frames_preroll / actual_fps) * strip_samplerate)
            sampleindex += 1
            progress = int((100 * (sampleindex - startsample)) / (endsample - startsample))
            if progress_prev != progress:
                progress_prev = progress
                wm.progress_update(progress)
        wm.progress_end()
        # TODO: do we need to delete the audsound object and/or clear the cache? or is that taken care of by the script exiting?

        if len(edits) == 0:
            self.report({'WARNING'}, 'No peaks found above threshold')
            return {'CANCELLED'}
        
        # work out the final timeline positions for each of the clips once shuffled
        clip_starts = []
        clip_starts.append(edits[0][0] + reference_start)
        for edit_index in range(1, len(edits)):
            clip_starts.append(clip_starts[edit_index - 1] + self.frames_preroll + self.frames_postroll)
            if DEBUG:
                self.report({'INFO'}, 'Final position {} start {}'.format(edit_index, clip_starts[edit_index]))
        
        # make the edits
        for strip in bpy.context.sequences:
            if strip.select:
                if DEBUG:
                    self.report({'INFO'}, 'Strip {} start {}'.format(strip.name, strip.frame_start + strip.frame_offset_start))
                keeps = []
                strip_hard_start = strip.frame_start
                ref_offset = reference_start - strip_hard_start
                newstrip_keep = strip
                newstrip_bin = strip
                begin_index_offset = 0
                for edit_index in range(len(edits)):
                    if edits[edit_index][0] + strip_hard_start + ref_offset >= (newstrip_keep.frame_start + newstrip_keep.frame_offset_start + newstrip_keep.frame_final_duration):
                        # inpoint is beyond the end of this strip, we are done here
                        break
                    if DEBUG:
                        self.report({'INFO'}, 'Edit {}, in {} out {}'.format(edit_index, reference_start + edits[edit_index][0], reference_start + edits[edit_index][1]))
                    if edits[edit_index][1] + strip_hard_start + ref_offset <= (newstrip_bin.frame_start + newstrip_bin.frame_offset_start):
                        # entire edit is before the start of this clip, ignore it (keeping a note of the offset for later correct positioning)
                        begin_index_offset += 1
                        continue
                    if edits[edit_index][0] + strip_hard_start + ref_offset <= (newstrip_bin.frame_start + newstrip_bin.frame_offset_start):
                        # nothing to trim off and bin from before the good bit
                        newstrip_bin = None
                    else:
                        newstrip_keep = newstrip_keep.split(frame=(int)(edits[edit_index][0] + strip_hard_start + ref_offset), split_method='SOFT')
                        bpy.context.scene.sequence_editor.sequences.remove(newstrip_bin)
                    keeps.append(newstrip_keep)
                    if edits[edit_index][1] + strip_hard_start + ref_offset >= (newstrip_keep.frame_start + newstrip_keep.frame_offset_start + newstrip_keep.frame_final_duration):
                        # the outpoint is beyond the end of the remaining strip, we are done here.
                        newstrip_bin = None
                        break
                    # make the cut at the outpoint of the good bit, and set the clip to be binned next time round
                    newstrip_bin = newstrip_keep.split(frame=(int)(edits[edit_index][1] + strip_hard_start + ref_offset), split_method='SOFT')
                    newstrip_keep = newstrip_bin
                # delete the final unused bit, if it exists
                if newstrip_bin is not None and newstrip_bin.frame_final_duration > 0:
                    bpy.context.scene.sequence_editor.sequences.remove(newstrip_bin)
                # shuffle kept bits together
                for bit_index in range(len(keeps)):
                    keeps[bit_index].frame_start = clip_starts[bit_index + begin_index_offset] - keeps[bit_index].frame_offset_start
                    
        self.report({'INFO'}, 'Banged {} Cuts!'.format(len(edits)))
        return {'FINISHED'}

class BANGING_CUTS_MT_main(bpy.types.Menu):
    bl_description = 'BANGING CUTS from Funkster. Chop bits out of your strips in sync with audio peaks!'
    bl_label = 'Banging Cuts'

    def draw(self, context):
        layout = self.layout
        layout.operator(BANGING_CUTS_OT_make_cuts.bl_idname, text="Make Cuts", icon='ALIGN_FLUSH')


def menu_draw(self, context):
    layout = self.layout
    layout.menu('BANGING_CUTS_MT_main')
    

def register():
    bpy.utils.register_class(BANGING_CUTS_OT_make_cuts)
    bpy.utils.register_class(BANGING_CUTS_MT_main)
    bpy.types.SEQUENCER_HT_header.append(menu_draw)

def unregister():
    bpy.utils.unregister_class(BANGING_CUTS_OT_make_cuts)
    bpy.utils.unregister_class(BANGING_CUTS_MT_main)
    bpy.types.SEQUENCER_HT_header.remove(menu_draw)
