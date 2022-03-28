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
    'version': (0, 2),
    'blender': (2, 80, 0),
    'description': 'Banging Cuts addon for Blender VSE. Chop bits out of your strips in sync with audio peaks!',
    'category': 'Sequencer',
}

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
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        edits = []
        thresh = pow(10,self.audio_thresh_db / 20.0)
        scene = context.scene
        actual_fps = scene.render.fps / scene.render.fps_base
        samplerate = scene.render.ffmpeg.audio_mixrate
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
        self.report({'INFO'}, 'Ref strip has {} channels, {} samples per channel!'.format(audiochannels, numsamples))
        # only start looking where the ref_strip actually starts
        startsample = int((start_offset / actual_fps) * samplerate)
        # and only look until where the ref strip ends, even if the audio itself is longer
        endsample = startsample + int((ref_strip.frame_final_duration / actual_fps) * samplerate)
        # add some room at the end so that we always have room for the last post-roll
        endsample -= int((self.frames_postroll / actual_fps) * samplerate)
        
        # ready to look for peaks!
        frame = 0
        wm.progress_begin(0, 100)
        progress = 0
        progress_prev = 0
        sampleindex = startsample
        while sampleindex < endsample:
            frame = actual_fps * (sampleindex / samplerate)
            if dataarray[sampleindex][0] > thresh or dataarray[sampleindex][0] < (0 - thresh):
                inpoint = int(frame - self.frames_preroll)
                if inpoint < 0:
                    inpoint = 0
                outpoint = int(frame + self.frames_postroll)
                edits.append([inpoint, outpoint])
                # advance until after postroll since we have already got this one
                sampleindex += int((self.frames_postroll / actual_fps) * samplerate)
                # also advance until after next preroll so we don't get repeats
                sampleindex += int((self.frames_preroll / actual_fps) * samplerate)
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
            
        # make the edits
        for strip in bpy.context.sequences:
            if strip.select:
                keeps = []
                strip_hard_start = strip.frame_start
                ref_offset = reference_start - strip_hard_start
                newstrip_keep = strip
                newstrip_bin = strip
                for edit_index in range(len(edits)):
                    newstrip_keep = newstrip_keep.split(frame=edits[edit_index][0] + strip_hard_start + ref_offset, split_method='SOFT')
                    if newstrip_bin.frame_final_duration > 0:
                        bpy.context.scene.sequence_editor.sequences.remove(newstrip_bin)
                    keeps.append(newstrip_keep)
                    newstrip_bin = newstrip_keep.split(frame=edits[edit_index][1] + strip_hard_start + ref_offset, split_method='SOFT')
                    newstrip_keep = newstrip_bin
                # delete the final unused bit, if it exists
                if newstrip_bin is not None and newstrip_bin.frame_final_duration > 0:
                    bpy.context.scene.sequence_editor.sequences.remove(newstrip_bin)
                # shuffle kept bits together
                for bit_index in range(len(keeps) - 1):
                    distance = 0 - (keeps[bit_index + 1].frame_offset_start - keeps[bit_index].frame_offset_start) + keeps[bit_index].frame_final_duration
                    # base the new start on the start of the previous clip
                    new_start = keeps[bit_index].frame_start + distance
                    keeps[bit_index + 1].frame_start = new_start
                    
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
