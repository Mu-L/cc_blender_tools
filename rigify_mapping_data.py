# Copyright (C) 2021 Victor Soupday
# This file is part of CC3_Blender_Tools <https://github.com/soupday/cc3_blender_tools>
#
# CC3_Blender_Tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CC3_Blender_Tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CC3_Blender_Tools.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass
from sys import set_coroutine_origin_tracking_depth

@dataclass
class RigifyData:
    """Class for keeping all data relating to bones mapping for rigify."""
    head_bone: str
    bone_mapping: list
    face_bones: list
    add_def_bones: list
    vertex_group_rename: list
    roll_correction: list


@dataclass
class RetargetData:
    """Class for keeping all data relating to bones mapping for rigify."""
    retarget: list
    retarget_corrections: dict


def get_mapping_for_generation(generation):
    if generation == "GameBase":
        return RigifyData("head",
                          GAME_BASE_BONE_MAPPINGS,
                          FACE_BONES,
                          ADD_DEF_BONES,
                          GAME_BASE_VERTEX_GROUP_RENAME,
                          ROLL_CORRECTION)

    elif generation == "ActorCore" or generation == "G3" or generation == "G3Plus":
        return RigifyData("CC_Base_Head",
                          G3_BONE_MAPPINGS,
                          FACE_BONES,
                          ADD_DEF_BONES,
                          G3_VERTEX_GROUP_RENAME,
                          ROLL_CORRECTION)

    else:
        return None


def get_retarget_for_source(source):
    if source == "G3":
        return RetargetData(RETARGET_G3, RETARGET_CORRECTIONS)

    elif source == "GameBase":
        return RetargetData(RETARGET_GAME_BASE, RETARGET_CORRECTIONS)

    elif source == "Mixamo":
        return RetargetData(RETARGET_MIXAMO, RETARGET_CORRECTIONS)

    elif source == "Rokoko":
        return None

    elif source == "Maya":
        return None

    elif source == "ARP":
        return None

    else:
        return None


#   METARIG_BONE, CC_BONE_HEAD, CC_BONE_TAIL, LERP_FROM, LERP_TO
#   '-' before CC_BONE_HEAD means to copy the tail position, not the head
#   '-' before CC_BONE_TAIL means to copy the head position, not the tail
G3_BONE_MAPPINGS = [

    # Spine, Neck & Head:
    # spine chain
    ["spine", "CC_Base_Hip", ""],
    ["spine.001", "CC_Base_Waist", ""],
    ["spine.002", "CC_Base_Spine01", ""],
    ["spine.003", "CC_Base_Spine02", "-CC_Base_NeckTwist01"],
    ["spine.004", "CC_Base_NeckTwist01", ""],
    ["spine.005", "CC_Base_NeckTwist02", ""],
    ["spine.006", "CC_Base_Head", "CC_Base_Head"], # special case
    ["face", "CC_Base_FacialBone", "CC_Base_FacialBone"], # special case
    ["pelvis", "CC_Base_Pelvis", "CC_Base_Pelvis"],

    # Left Breast
    ["breast.L", "CC_Base_L_Breast", "CC_Base_L_Breast"],
    # Right Breast
    ["breast.R", "CC_Base_R_Breast", "CC_Base_R_Breast"],

    # Left Leg:
    ["thigh.L", "CC_Base_L_Thigh", ""],
    ["shin.L", "CC_Base_L_Calf", ""],
    ["foot.L", "CC_Base_L_Foot", ""],
    ["toe.L", "CC_Base_L_ToeBase", "CC_Base_L_ToeBase"],

    # Left Arm:
    ["shoulder.L", "CC_Base_L_Clavicle", "CC_Base_L_Clavicle"],
    # chain
    ["upper_arm.L", "CC_Base_L_Upperarm", ""],
    ["forearm.L", "CC_Base_L_Forearm", ""],
    ["hand.L", "CC_Base_L_Hand", "CC_Base_L_Hand", 0, 0.75],
    ["palm.01.L", "CC_Base_L_Hand", "-CC_Base_L_Index1", 0.35, 1],
    ["palm.02.L", "CC_Base_L_Hand", "-CC_Base_L_Mid1", 0.35, 1],
    ["palm.03.L", "CC_Base_L_Hand", "-CC_Base_L_Ring1", 0.35, 1],
    ["palm.04.L", "CC_Base_L_Hand", "-CC_Base_L_Pinky1", 0.35, 1],
    # Left Hand Fingers, chains
    ["thumb.01.L", "CC_Base_L_Thumb1", ""],
    ["f_index.01.L", "CC_Base_L_Index1", ""],
    ["f_middle.01.L", "CC_Base_L_Mid1", ""],
    ["f_ring.01.L", "CC_Base_L_Ring1", ""],
    ["f_pinky.01.L", "CC_Base_L_Pinky1", ""],
    ["thumb.02.L", "CC_Base_L_Thumb2", ""],
    ["f_index.02.L", "CC_Base_L_Index2", ""],
    ["f_middle.02.L", "CC_Base_L_Mid2", ""],
    ["f_ring.02.L", "CC_Base_L_Ring2", ""],
    ["f_pinky.02.L", "CC_Base_L_Pinky2", ""],
    ["thumb.03.L", "CC_Base_L_Thumb3", "CC_Base_L_Thumb3"],
    ["f_index.03.L", "CC_Base_L_Index3", "CC_Base_L_Index3"],
    ["f_middle.03.L", "CC_Base_L_Mid3", "CC_Base_L_Mid3"],
    ["f_ring.03.L", "CC_Base_L_Ring3", "CC_Base_L_Ring3"],
    ["f_pinky.03.L", "CC_Base_L_Pinky3", "CC_Base_L_Pinky3"],

    # Right Leg, chain
    ["thigh.R", "CC_Base_R_Thigh", ""],
    ["shin.R", "CC_Base_R_Calf", ""],
    ["foot.R", "CC_Base_R_Foot", ""],
    ["toe.R", "CC_Base_R_ToeBase", "CC_Base_R_ToeBase"],

    # Right Arm:
    ["shoulder.R", "CC_Base_R_Clavicle", "CC_Base_R_Clavicle"],
    ["upper_arm.R", "CC_Base_R_Upperarm", ""],
    ["forearm.R", "CC_Base_R_Forearm", ""],
    ["hand.R", "CC_Base_R_Hand", "CC_Base_R_Hand", 0, 0.75],
    ["palm.01.R", "CC_Base_R_Hand", "-CC_Base_R_Index1", 0.35, 1],
    ["palm.02.R", "CC_Base_R_Hand", "-CC_Base_R_Mid1", 0.35, 1],
    ["palm.03.R", "CC_Base_R_Hand", "-CC_Base_R_Ring1", 0.35, 1],
    ["palm.04.R", "CC_Base_R_Hand", "-CC_Base_R_Pinky1", 0.35, 1],
    # Right Hand Fingers, chains
    ["thumb.01.R", "CC_Base_R_Thumb1", ""],
    ["f_index.01.R", "CC_Base_R_Index1", ""],
    ["f_middle.01.R", "CC_Base_R_Mid1", ""],
    ["f_ring.01.R", "CC_Base_R_Ring1", ""],
    ["f_pinky.01.R", "CC_Base_R_Pinky1", ""],
    ["thumb.02.R", "CC_Base_R_Thumb2", ""],
    ["f_index.02.R", "CC_Base_R_Index2", ""],
    ["f_middle.02.R", "CC_Base_R_Mid2", ""],
    ["f_ring.02.R", "CC_Base_R_Ring2", ""],
    ["f_pinky.02.R", "CC_Base_R_Pinky2", ""],
    ["thumb.03.R", "CC_Base_R_Thumb3", "CC_Base_R_Thumb3"],
    ["f_index.03.R", "CC_Base_R_Index3", "CC_Base_R_Index3"],
    ["f_middle.03.R", "CC_Base_R_Mid3", "CC_Base_R_Mid3"],
    ["f_ring.03.R", "CC_Base_R_Ring3", "CC_Base_R_Ring3"],
    ["f_pinky.03.R", "CC_Base_R_Pinky3", "CC_Base_R_Pinky3"],

    ["tongue", "CC_Base_Tongue03", "CC_Base_Tongue02"],
    ["tongue.001", "CC_Base_Tongue02", "CC_Base_Tongue01"],
    ["tongue.002", "CC_Base_Tongue01", "CC_Base_JawRoot", 0, 0.65],

    ["teeth.T", "CC_Base_Teeth01", "CC_Base_Teeth01"],
    ["teeth.B", "CC_Base_Teeth02", "CC_Base_Teeth02"],

    ["eye.R", "CC_Base_R_Eye", ""],
    ["eye.L", "CC_Base_L_Eye", ""],

    ["eye.L", "CC_Base_L_Eye", ""],

    # only when using the basic face rig, a jaw bone is created that needs positioning...
    ["jaw", "CC_Base_JawRoot", "CC_Base_Tongue03", 0, 1.35],
]

GAME_BASE_BONE_MAPPINGS = [
    # Spine, Neck & Head:
    # spine chain
    ["pelvis", "pelvis", "pelvis"],
    ["spine", "pelvis", ""],
    ["spine.001", "spine_01", ""],
    ["spine.002", "spine_02", ""],
    ["spine.003", "spine_03", "-neck_01"],
    # moved spine.004 and spine.005 into a 50/50 split of neck_01
    # as retargeting animations to the neck uses spine.004 as the base of the neck
    ["spine.004", "neck_01", "neck_01", 0, 0.5],
    ["spine.005", "neck_01", "neck_01", 0.5, 1],
    ["spine.006", "head", "head"], # special case
    ["face", "CC_Base_FacialBone", "CC_Base_FacialBone"], # special case

    # Left Breast
    ["breast.L", "CC_Base_L_RibsTwist", "CC_Base_L_RibsTwist", 0, 0.2],
    # Right Breast
    ["breast.R", "CC_Base_R_RibsTwist", "CC_Base_R_RibsTwist", 0, 0.2],

    # Left Leg:
    ["thigh.L", "thigh_l", ""],
    ["shin.L", "calf_l", ""],
    ["foot.L", "foot_l", ""],
    ["toe.L", "ball_l", "ball_l"],

    # Left Arm:
    ["shoulder.L", "clavicle_l", "clavicle_l"],
    # chain
    ["upper_arm.L", "upperarm_l", ""],
    ["forearm.L", "lowerarm_l", ""],
    ["hand.L", "hand_l", "hand_l", 0, 0.75],
    ["palm.01.L", "hand_l", "-index_01_l", 0.35, 1],
    ["palm.02.L", "hand_l", "-middle_01_l", 0.35, 1],
    ["palm.03.L", "hand_l", "-ring_01_l", 0.35, 1],
    ["palm.04.L", "hand_l", "-pinky_01_l", 0.35, 1],
    # Left Hand Fingers, chains
    ["thumb.01.L", "thumb_01_l", ""],
    ["f_index.01.L", "index_01_l", ""],
    ["f_middle.01.L", "middle_01_l", ""],
    ["f_ring.01.L", "ring_01_l", ""],
    ["f_pinky.01.L", "pinky_01_l", ""],
    ["thumb.02.L", "thumb_02_l", ""],
    ["f_index.02.L", "index_02_l", ""],
    ["f_middle.02.L", "middle_02_l", ""],
    ["f_ring.02.L", "ring_02_l", ""],
    ["f_pinky.02.L", "pinky_02_l", ""],
    ["thumb.03.L", "thumb_03_l", "thumb_03_l"],
    ["f_index.03.L", "index_03_l", "index_03_l"],
    ["f_middle.03.L", "middle_03_l", "middle_03_l"],
    ["f_ring.03.L", "ring_03_l", "ring_03_l"],
    ["f_pinky.03.L", "pinky_03_l", "pinky_03_l"],

    # Right Leg, chain
    ["thigh.R", "thigh_r", ""],
    ["shin.R", "calf_r", ""],
    ["foot.R", "foot_r", ""],
    ["toe.R", "ball_r", "ball_r"],

    # Right Arm:
    ["shoulder.R", "clavicle_r", "clavicle_r"],
    ["upper_arm.R", "upperarm_r", ""],
    ["forearm.R", "lowerarm_r", ""],
    ["hand.R", "hand_r", "hand_r", 0, 0.75],
    ["palm.01.R", "hand_r", "-index_01_r", 0.35, 1],
    ["palm.02.R", "hand_r", "-middle_01_r", 0.35, 1],
    ["palm.03.R", "hand_r", "-ring_01_r", 0.35, 1],
    ["palm.04.R", "hand_r", "-pinky_01_r", 0.35, 1],
    # Right Hand Fingers, chains
    ["thumb.01.R", "thumb_01_r", ""],
    ["f_index.01.R", "index_01_r", ""],
    ["f_middle.01.R", "middle_01_r", ""],
    ["f_ring.01.R", "ring_01_r", ""],
    ["f_pinky.01.R", "pinky_01_r", ""],
    ["thumb.02.R", "thumb_02_r", ""],
    ["f_index.02.R", "index_02_r", ""],
    ["f_middle.02.R", "middle_02_r", ""],
    ["f_ring.02.R", "ring_02_r", ""],
    ["f_pinky.02.R", "pinky_02_r", ""],
    ["thumb.03.R", "thumb_03_r", "thumb_03_r"],
    ["f_index.03.R", "index_03_r", "index_03_r"],
    ["f_middle.03.R", "middle_03_r", "middle_03_r"],
    ["f_ring.03.R", "ring_03_r", "ring_03_r"],
    ["f_pinky.03.R", "pinky_03_r", "pinky_03_r"],

    ["tongue", "CC_Base_Tongue03", "CC_Base_Tongue02"],
    ["tongue.001", "CC_Base_Tongue02", "CC_Base_Tongue01"],
    ["tongue.002", "CC_Base_Tongue01", "CC_Base_JawRoot", 0, 0.65],

    ["teeth.T", "CC_Base_Teeth01", "CC_Base_Teeth01"],
    ["teeth.B", "CC_Base_Teeth02", "CC_Base_Teeth02"],

    ["eye.R", "CC_Base_R_Eye", ""],
    ["eye.L", "CC_Base_L_Eye", ""],

    # only when using the basic face rig, a jaw bone is created that needs positioning...
    ["jaw", "CC_Base_JawRoot", "CC_Base_Tongue03", 0, 1.35],
]

FACE_BONES = [
    ["face", "spine.006", "LR", 0],
    ["eye.L", "face", "LR", 0],
    ["eye.R", "face", "LR", 0],
    ["jaw", "face", "LR", 0, "JAW"],
    ["teeth.T", "face", "LR", 0],
    ["teeth.B", "jaw", "LR", 0],
    ["tongue", "jaw", "LR", 0, "TONGUE"],
    ["tongue.001", "tongue", "CLR", 0],
    ["tongue.002", "tongue.001", "CLR", 0],
]

# additional bones to copy from the cc3 or rigify rigs to generate rigify deformation, mech or control bones
# [source_bone, new_rigify_bone, rigify_parent, flags, layer, scale, ref, arg]
# flags C=Connected, L=Local location, R=Inherit rotation
# layers: 31 = ORG bones, 30 = MCH bones, 29 = DEF bones
# ref: reference bone(s) for position generation or constraints
# arg: constraint args (influence)
ADD_DEF_BONES = [

    ["ORG-eye.R", "DEF-eye.R", "ORG-eye.R", "LR", 29],
    ["ORG-eye.L", "DEF-eye.L", "ORG-eye.L", "LR", 29],

    ["ORG-teeth.T", "DEF-teeth.T", "ORG-teeth.T", "LR", 29],
    ["ORG-teeth.B", "DEF-teeth.B", "ORG-teeth.B", "LR", 29],

    ["CC_Base_L_RibsTwist", "DEF-breast_twist.L", "ORG-breast.L", "LR", 29],
    ["CC_Base_R_RibsTwist", "DEF-breast_twist.R", "ORG-breast.R", "LR", 29],
    # "-" instructs to re-parent the existing DEF-breast bones to the new DEF-breast_twist bones.
    ["-", "DEF-breast.L", "DEF-breast_twist.L", "LR", 29],
    ["-", "DEF-breast.R", "DEF-breast_twist.R", "LR", 29],

    ["DEF-forearm.L", "DEF-elbow_share.L", "DEF-forearm.L", "LR", 29, 0.667, "DEF-upper_arm.L.001", 0.5],
    ["DEF-shin.L", "DEF-knee_share.L", "DEF-shin.L", "LR", 29, 0.667, "DEF-thigh.L.001", 0.5],
    #["DEF-toe.L", "DEF-toe_share.L", "DEF-toe.L", "LR", 29, 4.0, "DEF-foot.L", 0.5],

    ["CC_Base_L_BigToe1", "DEF-toe_big.L", "DEF-toe.L", "LR", 29],
    ["CC_Base_L_IndexToe1", "DEF-toe_index.L", "DEF-toe.L", "LR", 29],
    ["CC_Base_L_MidToe1", "DEF-toe_mid.L", "DEF-toe.L", "LR", 29],
    ["CC_Base_L_RingToe1", "DEF-toe_ring.L", "DEF-toe.L", "LR", 29],
    ["CC_Base_L_PinkyToe1", "DEF-toe_pinky.L", "DEF-toe.L", "LR", 29],

    ["DEF-forearm.R", "DEF-elbow_share.R", "DEF-forearm.R", "LR", 29, 0.667, "DEF-upper_arm.R.001", 0.5],
    ["DEF-shin.R", "DEF-knee_share.R", "DEF-shin.R", "LR", 29, 0.667, "DEF-thigh.R.001", 0.5],
    #["DEF-toe.R", "DEF-toe_share.R", "DEF-toe.R", "LR", 29, 4.0, "DEF-foot.R", 0.5],

    ["CC_Base_R_BigToe1", "DEF-toe_big.R", "DEF-toe.R", "LR", 29],
    ["CC_Base_R_IndexToe1", "DEF-toe_index.R", "DEF-toe.R", "LR", 29],
    ["CC_Base_R_MidToe1", "DEF-toe_mid.R", "DEF-toe.R", "LR", 29],
    ["CC_Base_R_RingToe1", "DEF-toe_ring.R", "DEF-toe.R", "LR", 29],
    ["CC_Base_R_PinkyToe1", "DEF-toe_pinky.R", "DEF-toe.R", "LR", 29],

    ["+MCHEyeParent", "MCH-eyes_parent", "ORG-face", "LR", 30],
    ["+EyeControl", "eyes", "MCH-eyes_parent", "LR", 1, 0.2, ["ORG-eye.L", "ORG-eye.R"]],
    ["+EyeControl", "eye.L", "eyes", "LR", 1,           0.2, ["ORG-eye.L"]],
    ["+EyeControl", "eye.R", "eyes", "LR", 1,           0.2, ["ORG-eye.R"]],
    ["#RenameBasicFace", "jaw", "jaw_master", "", 1],
]

G3_VERTEX_GROUP_RENAME = [
    # Spine, Neck & Head:
    ["DEF-pelvis", "CC_Base_Pelvis"],
    ["DEF-spine", "CC_Base_Hip"],
    ["DEF-spine.001", "CC_Base_Waist"],
    ["DEF-spine.002", "CC_Base_Spine01"],
    ["DEF-spine.003", "CC_Base_Spine02"],
    ["DEF-spine.004", "CC_Base_NeckTwist01"],
    ["DEF-spine.005", "CC_Base_NeckTwist02"],
    ["DEF-spine.006", "CC_Base_Head"],
    # Left Breast:
    ["DEF-breast_twist.L", "CC_Base_L_RibsTwist"],
    ["DEF-breast.L", "CC_Base_L_Breast"],
    # Right Breast:
    ["DEF-breast_twist.R", "CC_Base_R_RibsTwist"],
    ["DEF-breast.R", "CC_Base_R_Breast"],
    # Left Leg:
    ["DEF-thigh.L", "CC_Base_L_ThighTwist01"],
    ["DEF-thigh.L.001", "CC_Base_L_ThighTwist02"],
    ["DEF-knee_share.L", "CC_Base_L_KneeShareBone"],
    ["DEF-shin.L", "CC_Base_L_CalfTwist01"],
    ["DEF-shin.L.001", "CC_Base_L_CalfTwist02"],
    ["DEF-foot.L", "CC_Base_L_Foot"],
    ["DEF-toe.L", "CC_Base_L_ToeBase"],
    # Left Foot:
    ["DEF-toe_big.L", "CC_Base_L_BigToe1"],
    ["DEF-toe_index.L", "CC_Base_L_IndexToe1"],
    ["DEF-toe_mid.L", "CC_Base_L_MidToe1"],
    ["DEF-toe_ring.L", "CC_Base_L_RingToe1"],
    ["DEF-toe_pinky.L", "CC_Base_L_PinkyToe1"],
    # Left Arm:
    ["DEF-shoulder.L", "CC_Base_L_Clavicle"],
    ["DEF-upper_arm.L", "CC_Base_L_UpperarmTwist01"],
    ["DEF-upper_arm.L.001", "CC_Base_L_UpperarmTwist02"],
    ["DEF-elbow_share.L", "CC_Base_L_ElbowShareBone"],
    ["DEF-forearm.L", "CC_Base_L_ForearmTwist01"],
    ["DEF-forearm.L.001", "CC_Base_L_ForearmTwist02"],
    ["DEF-hand.L", "CC_Base_L_Hand"],
    # Left Hand Fingers:
    ["DEF-thumb.01.L", "CC_Base_L_Thumb1"],
    ["DEF-f_index.01.L", "CC_Base_L_Index1"],
    ["DEF-f_middle.01.L", "CC_Base_L_Mid1"],
    ["DEF-f_ring.01.L", "CC_Base_L_Ring1"],
    ["DEF-f_pinky.01.L", "CC_Base_L_Pinky1"],
    ["DEF-thumb.02.L", "CC_Base_L_Thumb2"],
    ["DEF-f_index.02.L", "CC_Base_L_Index2"],
    ["DEF-f_middle.02.L", "CC_Base_L_Mid2"],
    ["DEF-f_ring.02.L", "CC_Base_L_Ring2"],
    ["DEF-f_pinky.02.L", "CC_Base_L_Pinky2"],
    ["DEF-thumb.03.L", "CC_Base_L_Thumb3"],
    ["DEF-f_index.03.L", "CC_Base_L_Index3"],
    ["DEF-f_middle.03.L", "CC_Base_L_Mid3"],
    ["DEF-f_ring.03.L", "CC_Base_L_Ring3"],
    ["DEF-f_pinky.03.L", "CC_Base_L_Pinky3"],
    # Right Leg:
    ["DEF-thigh.R", "CC_Base_R_ThighTwist01"],
    ["DEF-thigh.R.001", "CC_Base_R_ThighTwist02"],
    ["DEF-knee_share.R", "CC_Base_R_KneeShareBone"],
    ["DEF-shin.R", "CC_Base_R_CalfTwist01"],
    ["DEF-shin.R.001", "CC_Base_R_CalfTwist02"],
    ["DEF-foot.R", "CC_Base_R_Foot"],
    ["DEF-toe.R", "CC_Base_R_ToeBase"],
    # Right Foot:
    ["DEF-toe_big.R", "CC_Base_R_BigToe1"],
    ["DEF-toe_index.R", "CC_Base_R_IndexToe1"],
    ["DEF-toe_mid.R", "CC_Base_R_MidToe1"],
    ["DEF-toe_ring.R", "CC_Base_R_RingToe1"],
    ["DEF-toe_pinky.R", "CC_Base_R_PinkyToe1"],
    # Right Arm:
    ["DEF-shoulder.R", "CC_Base_R_Clavicle"],
    ["DEF-upper_arm.R", "CC_Base_R_UpperarmTwist01"],
    ["DEF-upper_arm.R.001", "CC_Base_R_UpperarmTwist02"],
    ["DEF-elbow_share.R", "CC_Base_R_ElbowShareBone"],
    ["DEF-forearm.R", "CC_Base_R_ForearmTwist01"],
    ["DEF-forearm.R.001", "CC_Base_R_ForearmTwist02"],
    ["DEF-hand.R", "CC_Base_R_Hand"],
    # Right Hand Fingers:
    ["DEF-thumb.01.R", "CC_Base_R_Thumb1"],
    ["DEF-f_index.01.R", "CC_Base_R_Index1"],
    ["DEF-f_middle.01.R", "CC_Base_R_Mid1"],
    ["DEF-f_ring.01.R", "CC_Base_R_Ring1"],
    ["DEF-f_pinky.01.R", "CC_Base_R_Pinky1"],
    ["DEF-thumb.02.R", "CC_Base_R_Thumb2"],
    ["DEF-f_index.02.R", "CC_Base_R_Index2"],
    ["DEF-f_middle.02.R", "CC_Base_R_Mid2"],
    ["DEF-f_ring.02.R", "CC_Base_R_Ring2"],
    ["DEF-f_pinky.02.R", "CC_Base_R_Pinky2"],
    ["DEF-thumb.03.R", "CC_Base_R_Thumb3"],
    ["DEF-f_index.03.R", "CC_Base_R_Index3"],
    ["DEF-f_middle.03.R", "CC_Base_R_Mid3"],
    ["DEF-f_ring.03.R", "CC_Base_R_Ring3"],
    ["DEF-f_pinky.03.R", "CC_Base_R_Pinky3"],
    # Tongue:
    ["DEF-tongue", "CC_Base_Tongue03"],
    ["DEF-tongue.001", "CC_Base_Tongue02"],
    ["DEF-tongue.002", "CC_Base_Tongue01"],
    # Teeth:
    ["DEF-teeth.T", "CC_Base_Teeth01"],
    ["DEF-teeth.B", "CC_Base_Teeth02"],
    # Eyes:
    ["DEF-eye.R", "CC_Base_R_Eye"],
    ["DEF-eye.L", "CC_Base_L_Eye"],
    # Jaw:
    ["DEF-jaw", "CC_Base_JawRoot"],
]

GAME_BASE_VERTEX_GROUP_RENAME = [
    # Spine, Neck & Head:
    ["DEF-spine", "pelvis"],
    ["DEF-spine.001", "spine_01"],
    ["DEF-spine.002", "spine_02"],
    ["DEF-spine.003", "spine_03"],
    ["DEF-spine.004", "neck_01"],
    ["DEF-spine.006", "head"],
    # Left Breast:
    ["DEF-breast_twist.L", "CC_Base_L_RibsTwist"],
    # Right Breast:
    ["DEF-breast_twist.R", "CC_Base_R_RibsTwist"],
    # Left Leg:
    ["DEF-thigh.L", "thigh_l"],
    ["DEF-thigh.L.001", "thigh_twist_01_l"],
    ["DEF-shin.L", "calf_l"],
    ["DEF-shin.L.001", "calf_twist_01_l"],
    ["DEF-foot.L", "foot_l"],
    ["DEF-toe.L", "ball_l"],
    # Left Arm:
    ["DEF-shoulder.L", "clavicle_l"],
    ["DEF-upper_arm.L", "upperarm_l"],
    ["DEF-upper_arm.L.001", "upperarm_twist_01_L"],
    ["DEF-forearm.L", "lowerarm_l"],
    ["DEF-forearm.L.001", "lowerarm_twist_01_l"],
    ["DEF-hand.L", "hand_l"],
    # Left Hand Fingers:
    ["DEF-thumb.01.L", "thumb_01_l"],
    ["DEF-f_index.01.L", "index_01_l"],
    ["DEF-f_middle.01.L", "middle_01_l"],
    ["DEF-f_ring.01.L", "ring_01_l"],
    ["DEF-f_pinky.01.L", "pinky_01_l"],
    ["DEF-thumb.02.L", "thumb_02_l"],
    ["DEF-f_index.02.L", "index_02_l"],
    ["DEF-f_middle.02.L", "middle_02_l"],
    ["DEF-f_ring.02.L", "ring_02_l"],
    ["DEF-f_pinky.02.L", "pinky_02_l"],
    ["DEF-thumb.03.L", "thumb_03_l"],
    ["DEF-f_index.03.L", "index_03_l"],
    ["DEF-f_middle.03.L", "middle_03_l"],
    ["DEF-f_ring.03.L", "ring_03_l"],
    ["DEF-f_pinky.03.L", "pinky_03_l"],
    # Right Leg:
    ["DEF-thigh.R", "thigh_r"],
    ["DEF-thigh.R.001", "thigh_twist_01_r"],
    ["DEF-shin.R", "calf_r"],
    ["DEF-shin.R.001", "calf_twist_01_r"],
    ["DEF-foot.R", "foot_r"],
    ["DEF-toe.R", "ball_r"],
    # Right Arm:
    ["DEF-shoulder.R", "clavicle_r"],
    ["DEF-upper_arm.R", "upperarm_r"],
    ["DEF-upper_arm.R.001", "upperarm_twist_01_r"],
    ["DEF-forearm.R", "lowerarm_r"],
    ["DEF-forearm.R.001", "lowerarm_twist_01_r"],
    ["DEF-hand.R", "hand_r"],
    # Right Hand Fingers:
    ["DEF-thumb.01.R", "thumb_01_r"],
    ["DEF-f_index.01.R", "index_01_r"],
    ["DEF-f_middle.01.R", "middle_01_r"],
    ["DEF-f_ring.01.R", "ring_01_r"],
    ["DEF-f_pinky.01.R", "pinky_01_r"],
    ["DEF-thumb.02.R", "thumb_02_r"],
    ["DEF-f_index.02.R", "index_02_r"],
    ["DEF-f_middle.02.R", "middle_02_r"],
    ["DEF-f_ring.02.R", "ring_02_r"],
    ["DEF-f_pinky.02.R", "pinky_02_r"],
    ["DEF-thumb.03.R", "thumb_03_r"],
    ["DEF-f_index.03.R", "index_03_r"],
    ["DEF-f_middle.03.R", "middle_03_r"],
    ["DEF-f_ring.03.R", "ring_03_r"],
    ["DEF-f_pinky.03.R", "pinky_03_r"],
    # Tongue:
    ["DEF-tongue", "CC_Base_Tongue03"],
    ["DEF-tongue.001", "CC_Base_Tongue02"],
    ["DEF-tongue.002", "CC_Base_Tongue01"],
    # Teeth:
    ["DEF-teeth.T", "CC_Base_Teeth01"],
    ["DEF-teeth.B", "CC_Base_Teeth02"],
    # Eyes:
    ["DEF-eye.R", "CC_Base_R_Eye"],
    ["DEF-eye.L", "CC_Base_L_Eye"],
    # Jaw:
    ["DEF-jaw", "CC_Base_JawRoot"],
]

# roll is aligned directly from meta rig bone z_axis now
# we just need to apply a few corrections for better alignment i.e. hands, fingers
# [meta rig bone name, axis],
ROLL_CORRECTION = [
    # Left Hand Fingers, chains

    ["palm.01.L", "-Z"],
    ["palm.02.L", "-Z"],
    ["palm.03.L", "-Z"],
    ["palm.04.L", "-Z"],

    ["palm.01.R", "-Z"],
    ["palm.02.R", "-Z"],
    ["palm.03.R", "-Z"],
    ["palm.04.R", "-Z"],

    ["thumb.01.L", "-Z"],
    ["f_index.01.L", "-Z"],
    ["f_middle.01.L", "-Z"],
    ["f_ring.01.L", "-Z"],
    ["f_pinky.01.L", "-Z"],
    ["thumb.02.L", "-Z"],
    ["f_index.02.L", "-Z"],
    ["f_middle.02.L", "-Z"],
    ["f_ring.02.L", "-Z"],
    ["f_pinky.02.L", "-Z"],
    ["thumb.03.L", "-Z"],
    ["f_index.03.L", "-Z"],
    ["f_middle.03.L", "-Z"],
    ["f_ring.03.L", "-Z"],
    ["f_pinky.03.L", "-Z"],

    ["thumb.01.R", "-Z"],
    ["f_index.01.R", "-Z"],
    ["f_middle.01.R", "-Z"],
    ["f_ring.01.R", "-Z"],
    ["f_pinky.01.R", "-Z"],
    ["thumb.02.R", "-Z"],
    ["f_index.02.R", "-Z"],
    ["f_middle.02.R", "-Z"],
    ["f_ring.02.R", "-Z"],
    ["f_pinky.02.R", "-Z"],
    ["thumb.03.R", "-Z"],
    ["f_index.03.R", "-Z"],
    ["f_middle.03.R", "-Z"],
    ["f_ring.03.R", "-Z"],
    ["f_pinky.03.R", "-Z"],
]

RETARGET_RIGIFY_BONES = [
    "root", "hips", "torso", "spine_fk", "spine_fk.001", "spine_fk.002", "chest", "spine_fk.003",
    "neck", "tweak_spine", "tweak_spine.001", "tweak_spine.002", "tweak_spine.003", "tweak_spine.004", "tweak_spine.005",
    "head", "neck",
    "breast.L", "breast.R",
    "thigh_fk.L", "shin_fk.L", "foot_fk.L", "toe_fk.L", "toe.L",
    "shoulder.L", "upper_arm_fk.L", "forearm_fk.L", "hand_fk.L",
    "thumb.01.L", "f_index.01.L", "f_middle.01.L", "f_ring.01.L", "f_pinky.01.L",
    "thumb.02.L", "f_index.02.L", "f_middle.02.L", "f_ring.02.L", "f_pinky.02.L",
    "thumb.03.L", "f_index.03.L", "f_middle.03.L", "f_ring.03.L", "f_pinky.03.L",
    "thigh_fk.R", "shin_fk.R", "foot_fk.R", "toe_fk.R", "toe.R",
    "shoulder.R", "upper_arm_fk.R", "forearm_fk.R", "hand_fk.R",
    "thumb.01.R", "f_index.01.R", "f_middle.01.R", "f_ring.01.R", "f_pinky.01.R",
    "thumb.02.R", "f_index.02.R", "f_middle.02.R", "f_ring.02.R", "f_pinky.02.R",
    "thumb.03.R", "f_index.03.R", "f_middle.03.R", "f_ring.03.R", "f_pinky.03.R",
    "eye.L", "eye.R", "eyes",
    "jaw_master", "teeth.T", "teeth.B",
    "tongue_master", "tongue", "tongue.001", "tongue.002", "tweak_tongue", "tweak_tongue.001", "tweak_tongue.002",
    "hand_ik.L", "hand_ik.R", "foot_ik.L", "foot_ik.R", "toe_ik.L", "toe_ik.R",
]


RETARGET_G3 = [
    #   flags (flags are processed in order of left to right)
    #
    #       "L" - constrain location (retarget rig to rigify rig)
    #       "R" - constrain rotation (retarget rig to rigify rig)
    #       "N" - no source -> retarget constraints (to avoid duplicate constraints)
    #       "C" - copy rigify bone positions
    #       "P" - parent retarget correction: for when source bone and org bone
    #             are not the in the same orientation
    #
    #   flags with parameters (are processed left to right and parameters are consecutive)
    #
    #       "+", copy_bone - this org bone needs be added copied from copy_bone
    #       "I", influence - multiply the influence of the source -> org copy location/rotation
    #       "T", next_bone - parent correction & align with target: like "P" but maintain alignment
    #                        between the org bone and next_bone.
    #                        for when the source and ORG bones should be in alignment but aren't
    #                        because of strange bone orientations (Mixamo!) in the source rig.
    #       "D", root_bone - maintain distance from root_bone
    #       "A", bone_1, bone_2 - copy average location and rotation from bone_1 and bone_2
    #
    # [origin_bone, orign_bone_parent,          source_bone(regex match), rigify_target_bone, flags, *params]
    #
    # hips
    ["ORG-hip", "",                             "(CC_Base_|)Hip", "", "+PLR", "rigify:ORG-spine"],
    ["ORG-spine", "ORG-hip",                    "(CC_Base_|)Pelvis", "torso", "LR"],
    ["ORG-spine", "ORG-hip",                    "(CC_Base_|)Pelvis", "spine_fk", "NLR"],
    ["ORG-pelvis", "ORG-hip",                   "(CC_Base_|)Pelvis", "hips", "PLR"],
    # spine
    ["ORG-spine.001", "ORG-spine",              "(CC_Base_|)Waist", "spine_fk.001", "LR"],
    ["ORG-spine.002", "ORG-spine.001",          "(CC_Base_|)Spine01", "spine_fk.002", "LR"],
    ["ORG-spine.002", "ORG-spine.001",          "(CC_Base_|)Spine01", "chest", "NLR"],
    ["ORG-spine.003", "ORG-spine.002",          "(CC_Base_|)Spine02", "spine_fk.003", "LR"],
    ["ORG-spine.004", "ORG-spine.003",          "(CC_Base_|)NeckTwist01", "neck", "LR"],
    ["ORG-spine.005", "ORG-spine.004",          "(CC_Base_|)NeckTwist02", "tweak_spine.005", "L"],
    ["ORG-spine.006", "ORG-spine.005",          "(CC_Base_|)Head", "head", "LR"],
    # torso
    ["ORG-breast.L", "ORG-spine.003",           "(CC_Base_|)L_RibsTwist", "breast.L", "LR"],
    ["ORG-breast.R", "ORG-spine.003",           "(CC_Base_|)R_RibsTwist", "breast.R", "LR"],
    # left leg
    ["ORG-thigh.L", "ORG-pelvis",               "(CC_Base_|)L_Thigh", "thigh_fk.L", "LR"],
    ["ORG-shin.L", "ORG-thigh.L",               "(CC_Base_|)L_Calf", "shin_fk.L", "LR"],
    ["ORG-foot.L", "ORG-shin.L",                "(CC_Base_|)L_Foot$", "foot_fk.L", "PLR"],
    ["ORG-toe.L", "ORG-foot.L",                 "(CC_Base_|)L_ToeBase$", "toe_fk.L", "LR"], #post 3.1
    ["ORG-toe.L", "ORG-foot.L",                 "(CC_Base_|)L_ToeBase$", "toe.L", "LR"], #pre 3.1
    # left arm
    ["ORG-shoulder.L", "ORG-spine.003",         "(CC_Base_|)L_Clavicle", "shoulder.L", "LR"],
    ["ORG-upper_arm.L", "ORG-shoulder.L",       "(CC_Base_|)L_Upperarm", "upper_arm_fk.L", "LR"],
    ["ORG-forearm.L", "ORG-upper_arm.L",        "(CC_Base_|)L_Forearm", "forearm_fk.L", "LR"],
    ["ORG-hand.L", "ORG-forearm.L",             "(CC_Base_|)L_Hand", "hand_fk.L", "LR"],
    # left fingers
    ["ORG-thumb.01.L", "ORG-hand.L",            "(CC_Base_|)L_Thumb1", "thumb.01.L", "LR"],
    ["ORG-f_index.01.L", "ORG-hand.L",          "(CC_Base_|)L_Index1", "f_index.01.L", "LR"],
    ["ORG-f_middle.01.L", "ORG-hand.L",         "(CC_Base_|)L_Mid1", "f_middle.01.L", "LR"],
    ["ORG-f_ring.01.L", "ORG-hand.L",           "(CC_Base_|)L_Ring1", "f_ring.01.L", "LR"],
    ["ORG-f_pinky.01.L", "ORG-hand.L",          "(CC_Base_|)L_Pinky1", "f_pinky.01.L", "LR"],
    ["ORG-thumb.02.L", "ORG-thumb.01.L",        "(CC_Base_|)L_Thumb2", "thumb.02.L", "LR"],
    ["ORG-f_index.02.L", "ORG-f_index.01.L",    "(CC_Base_|)L_Index2", "f_index.02.L", "LR"],
    ["ORG-f_middle.02.L", "ORG-f_middle.01.L",  "(CC_Base_|)L_Mid2", "f_middle.02.L", "LR"],
    ["ORG-f_ring.02.L", "ORG-f_ring.01.L",      "(CC_Base_|)L_Ring2", "f_ring.02.L", "LR"],
    ["ORG-f_pinky.02.L", "ORG-f_pinky.01.L",    "(CC_Base_|)L_Pinky2", "f_pinky.02.L", "LR"],
    ["ORG-thumb.03.L", "ORG-thumb.02.L",        "(CC_Base_|)L_Thumb3", "thumb.03.L", "LR"],
    ["ORG-f_index.03.L", "ORG-f_index.02.L",    "(CC_Base_|)L_Index3", "f_index.03.L", "LR"],
    ["ORG-f_middle.03.L", "ORG-f_middle.02.L",  "(CC_Base_|)L_Mid3", "f_middle.03.L", "LR"],
    ["ORG-f_ring.03.L", "ORG-f_ring.02.L",      "(CC_Base_|)L_Ring3", "f_ring.03.L", "LR"],
    ["ORG-f_pinky.03.L", "ORG-f_pinky.02.L",    "(CC_Base_|)L_Pinky3", "f_pinky.03.L", "LR"],
    # right leg
    ["ORG-thigh.R", "ORG-pelvis",               "(CC_Base_|)R_Thigh", "thigh_fk.R", "LR"],
    ["ORG-shin.R", "ORG-thigh.R",               "(CC_Base_|)R_Calf", "shin_fk.R", "LR"],
    ["ORG-foot.R", "ORG-shin.R",                "(CC_Base_|)R_Foot$", "foot_fk.R", "PLR"],
    ["ORG-toe.R", "ORG-foot.R",                 "(CC_Base_|)R_ToeBase$", "toe_fk.R", "LR"], #post 3.1
    ["ORG-toe.R", "ORG-foot.R",                 "(CC_Base_|)R_ToeBase$", "toe.R", "LR"], #pre 3.1
    # right arm
    ["ORG-shoulder.R", "ORG-spine.003",         "(CC_Base_|)R_Clavicle", "shoulder.R", "LR"],
    ["ORG-upper_arm.R", "ORG-shoulder.R",       "(CC_Base_|)R_Upperarm", "upper_arm_fk.R", "LR"],
    ["ORG-forearm.R", "ORG-upper_arm.R",        "(CC_Base_|)R_Forearm", "forearm_fk.R", "LR"],
    ["ORG-hand.R", "ORG-forearm.R",             "(CC_Base_|)R_Hand", "hand_fk.R", "LR"],
    # right fingers
    ["ORG-thumb.01.R", "ORG-hand.R",            "(CC_Base_|)R_Thumb1", "thumb.01.R", "LR"],
    ["ORG-f_index.01.R", "ORG-hand.R",          "(CC_Base_|)R_Index1", "f_index.01.R", "LR"],
    ["ORG-f_middle.01.R", "ORG-hand.R",         "(CC_Base_|)R_Mid1", "f_middle.01.R", "LR"],
    ["ORG-f_ring.01.R", "ORG-hand.R",           "(CC_Base_|)R_Ring1", "f_ring.01.R", "LR"],
    ["ORG-f_pinky.01.R", "ORG-hand.R",          "(CC_Base_|)R_Pinky1", "f_pinky.01.R", "LR"],
    ["ORG-thumb.02.R", "ORG-thumb.01.R",        "(CC_Base_|)R_Thumb2", "thumb.02.R", "LR"],
    ["ORG-f_index.02.R", "ORG-f_index.01.R",    "(CC_Base_|)R_Index2", "f_index.02.R", "LR"],
    ["ORG-f_middle.02.R", "ORG-f_middle.01.R",  "(CC_Base_|)R_Mid2", "f_middle.02.R", "LR"],
    ["ORG-f_ring.02.R", "ORG-f_ring.01.R",      "(CC_Base_|)R_Ring2", "f_ring.02.R", "LR"],
    ["ORG-f_pinky.02.R", "ORG-f_pinky.01.R",    "(CC_Base_|)R_Pinky2", "f_pinky.02.R", "LR"],
    ["ORG-thumb.03.R", "ORG-thumb.02.R",        "(CC_Base_|)R_Thumb3", "thumb.03.R", "LR"],
    ["ORG-f_index.03.R", "ORG-f_index.02.R",    "(CC_Base_|)R_Index3", "f_index.03.R", "LR"],
    ["ORG-f_middle.03.R", "ORG-f_middle.02.R",  "(CC_Base_|)R_Mid3", "f_middle.03.R", "LR"],
    ["ORG-f_ring.03.R", "ORG-f_ring.02.R",      "(CC_Base_|)R_Ring3", "f_ring.03.R", "LR"],
    ["ORG-f_pinky.03.R", "ORG-f_pinky.02.R",    "(CC_Base_|)R_Pinky3", "f_pinky.03.R", "LR"],
    #face
    ["ORG-face", "ORG-spine.006",               "(CC_Base_|)FacialBone", "", "PLR"],
    # eyes
    ["ORG-eye.L", "ORG-face",                   "(CC_Base_|)L_Eye", "eye.L", "PLRD", "ORG-eye.L"],
    ["ORG-eye.R", "ORG-face",                   "(CC_Base_|)R_Eye", "eye.R", "PLRD", "ORG-eye.R"],
    ["ORG-eyes", "ORG-face",                    "", "eyes", "+LRA", "rigify:eyes", "eye.R", "eye.L"],
    # jaw
    ["ORG-jaw", "ORG-face",                     "(CC_Base_|)JawRoot", "jaw_master", "PLR"],
    # teeth
    ["ORG-teeth.T", "ORG-face",                 "(CC_Base_|)Teeth01", "teeth.T", "PLR"],
    ["ORG-teeth.B", "ORG-face",                 "(CC_Base_|)Teeth02", "teeth.B", "PLR"],
    # tongue (full face)
    ["ORG-tongue", "ORG-jaw",                   "(CC_Base_|)Tongue03", "tongue_master", "PLR"],
    ["ORG-tongue.001", "ORG-jaw",               "(CC_Base_|)Tongue02", "tongue.001", "PL"],
    ["ORG-tongue.002", "ORG-jaw",               "(CC_Base_|)Tongue01", "tongue.002", "PL"],
    # tongue (basic face)
    ["ORG-tongue", "ORG-jaw",                   "(CC_Base_|)Tongue03", "tweak_tongue", "PL"],
    ["ORG-tongue.001", "ORG-jaw",               "(CC_Base_|)Tongue02", "tweak_tongue.001", "PL"],
    ["ORG-tongue.002", "ORG-jaw",               "(CC_Base_|)Tongue01", "tweak_tongue.002", "PL"],
    # IK bones
    ["ORG-hand.L", "ORG-forearm.L",             "(CC_Base_|)L_Hand", "hand_ik.L", "NLR"],
    ["ORG-hand.R", "ORG-forearm.R",             "(CC_Base_|)R_Hand", "hand_ik.R", "NLR"],
    ["ORG-foot.L", "ORG-shin.L",                "(CC_Base_|)L_Foot", "foot_ik.L", "NLR"],
    ["ORG-foot.R", "ORG-shin.R",                "(CC_Base_|)R_Foot", "foot_ik.R", "NLR"],
    ["ORG-toe.L", "ORG-foot.L",                 "(CC_Base_|)L_ToeBase$", "toe_ik.L", "NLR"],
    ["ORG-toe.R", "ORG-foot.R",                 "(CC_Base_|)R_ToeBase$", "toe_ik.R", "NLR"],
]

# Note: this is retarget FROM game base actions TO the rigify rig.
RETARGET_GAME_BASE = [
    #   flags (flags are processed in order of left to right)
    #
    #       "L" - constrain location (retarget rig to rigify rig)
    #       "R" - constrain rotation (retarget rig to rigify rig)
    #       "N" - no source -> retarget constraints (to avoid duplicate constraints)
    #       "C" - copy rigify bone positions
    #       "P" - parent retarget correction: for when source bone and org bone
    #             are not the in the same orientation
    #
    #   flags with parameters (are processed left to right and parameters are consecutive)
    #
    #       "+", copy_bone - this org bone needs be added copied from copy_bone
    #       "I", influence - multiply the influence of the source -> org copy location/rotation
    #       "T", next_bone - parent correction & align with target: like "P" but maintain alignment with
    #                        org bone, for when the source and ORG bones should be in alignment but aren't
    #                        because of strange bone orientations (Mixamo!) in the source rig.
    #       "D", root_bone - maintain distance from root_bone
    #       "A", bone_1, bone_2 - copy average location and rotation from bone_1 and bone_2
    #
    # [origin_bone, orign_bone_parent,          source_bone(regex match), rigify_target_bone, flags, *params]
    #
    # hips
    ["ORG-hip", "",                             "pelvis", "", "+PLR", "rigify:ORG-spine"],
    ["ORG-spine", "ORG-hip",                    "pelvis", "torso", "NPLR"],
    ["ORG-spine", "ORG-hip",                    "pelvis", "spine_fk", "NPLR"],
    ["ORG-pelvis", "ORG-hip",                   "pelvis", "hips", "NPLR"],
    # spine
    ["ORG-spine.001", "ORG-spine",              "spine_01", "spine_fk.001", "LR"],
    ["ORG-spine.002", "ORG-spine.001",          "spine_02", "spine_fk.002", "LR"],
    ["ORG-spine.002", "ORG-spine.001",          "spine_02", "chest", "NLR"],
    ["ORG-spine.003", "ORG-spine.002",          "spine_03", "spine_fk.003", "LR"],
    ["ORG-spine.004", "ORG-spine.003",          "neck_01", "neck", "LR"],
    ["ORG-spine.006", "ORG-spine.004",          "head", "head", "LR"],
    # torso
    ["ORG-breast.L", "ORG-spine.003",           "(CC_Base_|)L_RibsTwist", "breast.L", "LR"],
    ["ORG-breast.R", "ORG-spine.003",           "(CC_Base_|)R_RibsTwist", "breast.R", "LR"],
    # left leg
    ["ORG-thigh.L", "ORG-pelvis",               "thigh_l", "thigh_fk.L", "LR"],
    ["ORG-shin.L", "ORG-thigh.L",               "calf_l", "shin_fk.L", "LR"],
    ["ORG-foot.L", "ORG-shin.L",                "foot_l", "foot_fk.L", "PLR"],
    ["ORG-toe.L", "ORG-foot.L",                 "ball_l", "toe_fk.L", "LR"], #post 3.1
    ["ORG-toe.L", "ORG-foot.L",                 "ball_l", "toe.L", "LR"], #pre 3.1
    # left arm
    ["ORG-shoulder.L", "ORG-spine.003",         "clavicle_l", "shoulder.L", "LR"],
    ["ORG-upper_arm.L", "ORG-shoulder.L",       "upperarm_l", "upper_arm_fk.L", "LR"],
    ["ORG-forearm.L", "ORG-upper_arm.L",        "lowerarm_l", "forearm_fk.L", "LR"],
    ["ORG-hand.L", "ORG-forearm.L",             "hand_l", "hand_fk.L", "LR"],
    # left fingers
    ["ORG-thumb.01.L", "ORG-hand.L",            "thumb_01_l", "thumb.01.L", "LR"],
    ["ORG-f_index.01.L", "ORG-hand.L",          "index_01_l", "f_index.01.L", "LR"],
    ["ORG-f_middle.01.L", "ORG-hand.L",         "middle_01_l", "f_middle.01.L", "LR"],
    ["ORG-f_ring.01.L", "ORG-hand.L",           "ring_01_l", "f_ring.01.L", "LR"],
    ["ORG-f_pinky.01.L", "ORG-hand.L",          "pinky_01_l", "f_pinky.01.L", "LR"],
    ["ORG-thumb.02.L", "ORG-thumb.01.L",        "thumb_02_l", "thumb.02.L", "LR"],
    ["ORG-f_index.02.L", "ORG-f_index.01.L",    "index_02_l", "f_index.02.L", "LR"],
    ["ORG-f_middle.02.L", "ORG-f_middle.01.L",  "middle_02_l", "f_middle.02.L", "LR"],
    ["ORG-f_ring.02.L", "ORG-f_ring.01.L",      "ring_02_l", "f_ring.02.L", "LR"],
    ["ORG-f_pinky.02.L", "ORG-f_pinky.01.L",    "pinky_02_l", "f_pinky.02.L", "LR"],
    ["ORG-thumb.03.L", "ORG-thumb.02.L",        "thumb_03_l", "thumb.03.L", "LR"],
    ["ORG-f_index.03.L", "ORG-f_index.02.L",    "index_03_l", "f_index.03.L", "LR"],
    ["ORG-f_middle.03.L", "ORG-f_middle.02.L",  "middle_03_l", "f_middle.03.L", "LR"],
    ["ORG-f_ring.03.L", "ORG-f_ring.02.L",      "ring_03_l", "f_ring.03.L", "LR"],
    ["ORG-f_pinky.03.L", "ORG-f_pinky.02.L",    "pinky_03_l", "f_pinky.03.L", "LR"],
    # right leg
    ["ORG-thigh.R", "ORG-pelvis",               "thigh_r", "thigh_fk.R", "LR"],
    ["ORG-shin.R", "ORG-thigh.R",               "calf_r", "shin_fk.R", "LR"],
    ["ORG-foot.R", "ORG-shin.R",                "foot_r", "foot_fk.R", "PLR"],
    ["ORG-toe.R", "ORG-foot.R",                 "ball_r", "toe_fk.R", "LR"], #post 3.1
    ["ORG-toe.R", "ORG-foot.R",                 "ball_r", "toe.R", "LR"], #pre 3.1
    # right arm
    ["ORG-shoulder.R", "ORG-spine.003",         "clavicle_r", "shoulder.R", "LR"],
    ["ORG-upper_arm.R", "ORG-shoulder.R",       "upperarm_r", "upper_arm_fk.R", "LR"],
    ["ORG-forearm.R", "ORG-upper_arm.R",        "lowerarm_r", "forearm_fk.R", "LR"],
    ["ORG-hand.R", "ORG-forearm.R",             "hand_r", "hand_fk.R", "LR"],
    # right fingers
    ["ORG-thumb.01.R", "ORG-hand.R",            "thumb_01_r", "thumb.01.R", "LR"],
    ["ORG-f_index.01.R", "ORG-hand.R",          "index_01_r", "f_index.01.R", "LR"],
    ["ORG-f_middle.01.R", "ORG-hand.R",         "middle_01_r", "f_middle.01.R", "LR"],
    ["ORG-f_ring.01.R", "ORG-hand.R",           "ring_01_r", "f_ring.01.R", "LR"],
    ["ORG-f_pinky.01.R", "ORG-hand.R",          "pinky_01_r", "f_pinky.01.R", "LR"],
    ["ORG-thumb.02.R", "ORG-thumb.01.R",        "thumb_02_r", "thumb.02.R", "LR"],
    ["ORG-f_index.02.R", "ORG-f_index.01.R",    "index_02_r", "f_index.02.R", "LR"],
    ["ORG-f_middle.02.R", "ORG-f_middle.01.R",  "middle_02_r", "f_middle.02.R", "LR"],
    ["ORG-f_ring.02.R", "ORG-f_ring.01.R",      "ring_02_r", "f_ring.02.R", "LR"],
    ["ORG-f_pinky.02.R", "ORG-f_pinky.01.R",    "pinky_02_r", "f_pinky.02.R", "LR"],
    ["ORG-thumb.03.R", "ORG-thumb.02.R",        "thumb_03_r", "thumb.03.R", "LR"],
    ["ORG-f_index.03.R", "ORG-f_index.02.R",    "index_03_r", "f_index.03.R", "LR"],
    ["ORG-f_middle.03.R", "ORG-f_middle.02.R",  "middle_03_r", "f_middle.03.R", "LR"],
    ["ORG-f_ring.03.R", "ORG-f_ring.02.R",      "ring_03_r", "f_ring.03.R", "LR"],
    ["ORG-f_pinky.03.R", "ORG-f_pinky.02.R",    "pinky_03_r", "f_pinky.03.R", "LR"],
    #face
    ["ORG-face", "ORG-spine.006",               "(CC_Base_|)FacialBone", "", "PLR"],
    # eyes
    ["ORG-eye.L", "ORG-face",                   "(CC_Base_|)L_Eye", "eye.L", "PLRD", "ORG-eye.L"],
    ["ORG-eye.R", "ORG-face",                   "(CC_Base_|)R_Eye", "eye.R", "PLRD", "ORG-eye.R"],
    ["ORG-eyes", "ORG-face",                    "", "eyes", "+LRA", "rigify:eyes", "eye.R", "eye.L"],
    # jaw
    ["ORG-jaw", "ORG-face",                     "(CC_Base_|)JawRoot", "jaw_master", "PLR"],
    # teeth
    ["ORG-teeth.T", "ORG-face",                 "(CC_Base_|)Teeth01", "teeth.T", "PLR"],
    ["ORG-teeth.B", "ORG-face",                 "(CC_Base_|)Teeth02", "teeth.B", "PLR"],
    # tongue (full face)
    ["ORG-tongue", "ORG-jaw",                   "(CC_Base_|)Tongue03", "tongue_master", "PLR"],
    ["ORG-tongue.001", "ORG-jaw",               "(CC_Base_|)Tongue02", "tongue.001", "PL"],
    ["ORG-tongue.002", "ORG-jaw",               "(CC_Base_|)Tongue01", "tongue.002", "PL"],
    # tongue (basic face)
    ["ORG-tongue", "ORG-jaw",                   "(CC_Base_|)Tongue03", "tweak_tongue", "PL"],
    ["ORG-tongue.001", "ORG-jaw",               "(CC_Base_|)Tongue02", "tweak_tongue.001", "PL"],
    ["ORG-tongue.002", "ORG-jaw",               "(CC_Base_|)Tongue01", "tweak_tongue.002", "PL"],
    # IK bones
    ["ORG-hand.L", "ORG-forearm.L",             "hand_l", "hand_ik.L", "NLR"],
    ["ORG-hand.R", "ORG-forearm.R",             "hand_r", "hand_ik.R", "NLR"],
    ["ORG-foot.L", "ORG-shin.L",                "foot_l", "foot_ik.L", "NLR"],
    ["ORG-foot.R", "ORG-shin.R",                "foot_r", "foot_ik.R", "NLR"],
    ["ORG-toe.L", "ORG-foot.L",                 "ball_l", "toe_ik.L", "NLR"],
    ["ORG-toe.R", "ORG-foot.R",                 "ball_r", "toe_ik.R", "NLR"],
]


RETARGET_MIXAMO = [
    #   flags (flags are processed in order of left to right)
    #
    #       "L" - constrain location (retarget rig to rigify rig)
    #       "R" - constrain rotation (retarget rig to rigify rig)
    #       "N" - no source -> retarget constraints (to avoid duplicate constraints)
    #       "C" - copy rigify bone positions
    #       "P" - parent retarget correction: for when source bone and org bone
    #             are not the in the same orientation
    #
    #   flags with parameters (are processed left to right and parameters are consecutive)
    #
    #       "+", copy_bone - this org bone needs be added copied from copy_bone
    #       "I", influence - multiply the influence of the source -> org copy location/rotation
    #       "T", next_bone - parent correction & align with target: like "P" but maintain alignment
    #                        between the org bone and next_bone.
    #                        for when the source and ORG bones should be in alignment but aren't
    #                        because of strange bone orientations (Mixamo!) in the source rig.
    #       "D", root_bone - maintain distance from root_bone
    #       "A", bone_1, bone_2 - copy average location and rotation from bone_1 and bone_2
    #
    # [origin_bone, orign_bone_parent,          source_bone(regex match), rigify_target_bone, flags, *params]
    #
    # hips
    ["ORG-hip", "",                             "mixamorig:Hips", "", "+PLR", "rigify:ORG-spine"],
    ["ORG-spine", "ORG-hip",                    "", "torso", "LR"],
    ["ORG-spine", "ORG-hip",                    "", "spine_fk", "LR"],
    ["ORG-pelvis", "ORG-spine",                 "", "hips", "LR"],
    # spine
    # spine.001 is too short and too low to match any Mixamo spine bones
    # mixamorig:Hips = ORG-spine + ORG-spine.001
    ["ORG-spine.001", "ORG-spine",              "", "spine_fk.001", "LR"],
    #["ORG-spine.001", "ORG-spine",              "", "tweak_spine.001", "L"],
    # mixamorig:Spine = ORG-spine.002
    ["ORG-spine.002", "ORG-spine.001",          "mixamorig:Spine$", "spine_fk.002", "PLRI", 0.25], # reduce the influence of this bone
    #["ORG-spine.002", "ORG-spine.001",          "", "tweak_spine.002", "L"],
    #["ORG-spine.002", "ORG-spine.001",          "", "chest", "LR"],
    # mixamorig:Spine1 + mixamorig:Spine2 = ORG-spine.003
    ["ORG-spine.003", "ORG-spine.002",          "mixamorig:Spine1", "spine_fk.003", "PLR"],
    ["ORG-spine.003", "ORG-spine.002",          "", "chest", "LR"],
    ["ORG-spine.004", "ORG-spine.003",          "mixamorig:Neck", "neck", "PLR"],
    ["ORG-spine.006", "ORG-spine.004",          "mixamorig:Head$", "head", "PLR"],
    # left leg
    ["ORG-thigh.L", "ORG-pelvis",               "mixamorig:LeftUpLeg", "thigh_fk.L", "TLR", "mixamorig:LeftLeg"],
    ["ORG-shin.L", "ORG-thigh.L",               "mixamorig:LeftLeg", "shin_fk.L", "TLR", "mixamorig:LeftFoot"],
    ["ORG-foot.L", "ORG-shin.L",                "mixamorig:LeftFoot", "foot_fk.L", "PLR"],
    ["ORG-toe.L", "ORG-foot.L",                 "mixamorig:LeftToeBase", "toe_fk.L", "TLR", "mixamorig:LeftToe_End"], #post 3.1
    ["ORG-toe.L", "ORG-foot.L",                 "mixamorig:LeftToeBase", "toe.L", "TLR", "mixamorig:LeftToe_End"], #pre 3.1
    # left arm
    ["ORG-shoulder.L", "ORG-spine.003",         "mixamorig:LeftShoulder", "shoulder.L", "PLR"],
    ["ORG-upper_arm.L", "ORG-shoulder.L",       "mixamorig:LeftArm", "upper_arm_fk.L", "TLR", "mixamorig:LeftForeArm"],
    ["ORG-forearm.L", "ORG-upper_arm.L",        "mixamorig:LeftForeArm", "forearm_fk.L", "TLR", "mixamorig:LeftHand$"],
    ["ORG-hand.L", "ORG-forearm.L",             "mixamorig:LeftHand$", "hand_fk.L", "TLR", "mixamorig:LeftHandMiddle1"],
    # left fingers
    ["ORG-thumb.01.L", "ORG-hand.L",            "mixamorig:LeftHandThumb1", "thumb.01.L", "TLR", "mixamorig:LeftHandThumb2"],
    ["ORG-f_index.01.L", "ORG-hand.L",          "mixamorig:LeftHandIndex1", "f_index.01.L", "TLR", "mixamorig:LeftHandIndex2"],
    ["ORG-f_middle.01.L", "ORG-hand.L",         "mixamorig:LeftHandMiddle1", "f_middle.01.L", "TLR", "mixamorig:LeftHandMiddle2"],
    ["ORG-f_ring.01.L", "ORG-hand.L",           "mixamorig:LeftHandRing1", "f_ring.01.L", "TLR", "mixamorig:LeftHandRing2"],
    ["ORG-f_pinky.01.L", "ORG-hand.L",          "mixamorig:LeftHandPinky1", "f_pinky.01.L", "TLR", "mixamorig:LeftHandPinky2"],
    ["ORG-thumb.02.L", "ORG-thumb.01.L",        "mixamorig:LeftHandThumb2", "thumb.02.L", "TR", "mixamorig:LeftHandThumb3"],
    ["ORG-f_index.02.L", "ORG-f_index.01.L",    "mixamorig:LeftHandIndex2", "f_index.02.L", "TR", "mixamorig:LeftHandIndex3"],
    ["ORG-f_middle.02.L", "ORG-f_middle.01.L",  "mixamorig:LeftHandMiddle2", "f_middle.02.L", "TR", "mixamorig:LeftHandMiddle3"],
    ["ORG-f_ring.02.L", "ORG-f_ring.01.L",      "mixamorig:LeftHandRing2", "f_ring.02.L", "TR", "mixamorig:LeftHandRing3"],
    ["ORG-f_pinky.02.L", "ORG-f_pinky.01.L",    "mixamorig:LeftHandPinky2", "f_pinky.02.L", "TR", "mixamorig:LeftHandPinky3"],
    ["ORG-thumb.03.L", "ORG-thumb.02.L",        "mixamorig:LeftHandThumb3", "thumb.03.L", "TR", "mixamorig:LeftHandThumb4"],
    ["ORG-f_index.03.L", "ORG-f_index.02.L",    "mixamorig:LeftHandIndex3", "f_index.03.L", "TR", "mixamorig:LeftHandIndex4"],
    ["ORG-f_middle.03.L", "ORG-f_middle.02.L",  "mixamorig:LeftHandMiddle3", "f_middle.03.L", "TR", "mixamorig:LeftHandMiddle4"],
    ["ORG-f_ring.03.L", "ORG-f_ring.02.L",      "mixamorig:LeftHandRing3", "f_ring.03.L", "TR", "mixamorig:LeftHandRing4"],
    ["ORG-f_pinky.03.L", "ORG-f_pinky.02.L",    "mixamorig:LeftHandPinky3", "f_pinky.03.L", "TR", "mixamorig:LeftHandPinky4"],
    # right leg
    ["ORG-thigh.R", "ORG-pelvis",               "mixamorig:RightUpLeg", "thigh_fk.R", "TLR", "mixamorig:RightLeg"],
    ["ORG-shin.R", "ORG-thigh.R",               "mixamorig:RightLeg", "shin_fk.R", "TLR", "mixamorig:RightFoot"],
    ["ORG-foot.R", "ORG-shin.R",                "mixamorig:RightFoot", "foot_fk.R", "PLR"],
    ["ORG-toe.R", "ORG-foot.R",                 "mixamorig:RightToeBase", "toe_fk.R", "TLR", "mixamorig:RightToe_End"], #post 3.1
    ["ORG-toe.R", "ORG-foot.R",                 "mixamorig:RightToeBase", "toe.R", "TLR", "mixamorig:RightToe_End"], #pre 3.1
    # right arm
    ["ORG-shoulder.R", "ORG-spine.003",         "mixamorig:RightShoulder", "shoulder.R", "PLR"],
    ["ORG-upper_arm.R", "ORG-shoulder.R",       "mixamorig:RightArm", "upper_arm_fk.R", "TR", "mixamorig:RightForeArm"],
    ["ORG-forearm.R", "ORG-upper_arm.R",        "mixamorig:RightForeArm", "forearm_fk.R", "TR", "mixamorig:RightHand$"],
    ["ORG-hand.R", "ORG-forearm.R",             "mixamorig:RightHand$", "hand_fk.R", "TR", "mixamorig:RightHandMiddle1"],
    # right fingers
    ["ORG-thumb.01.R", "ORG-hand.R",            "mixamorig:RightHandThumb1", "thumb.01.R", "TLR", "mixamorig:RightHandThumb2"],
    ["ORG-f_index.01.R", "ORG-hand.R",          "mixamorig:RightHandIndex1", "f_index.01.R", "TLR", "mixamorig:RightHandIndex2"],
    ["ORG-f_middle.01.R", "ORG-hand.R",         "mixamorig:RightHandMiddle1", "f_middle.01.R", "TLR", "mixamorig:RightHandMiddle2"],
    ["ORG-f_ring.01.R", "ORG-hand.R",           "mixamorig:RightHandRing1", "f_ring.01.R", "TLR", "mixamorig:RightHandRing2"],
    ["ORG-f_pinky.01.R", "ORG-hand.R",          "mixamorig:RightHandPinky1", "f_pinky.01.R", "TLR", "mixamorig:RightHandPinky2"],
    ["ORG-thumb.02.R", "ORG-thumb.01.R",        "mixamorig:RightHandThumb2", "thumb.02.R", "TR", "mixamorig:RightHandThumb3"],
    ["ORG-f_index.02.R", "ORG-f_index.01.R",    "mixamorig:RightHandIndex2", "f_index.02.R", "TR", "mixamorig:RightHandIndex3"],
    ["ORG-f_middle.02.R", "ORG-f_middle.01.R",  "mixamorig:RightHandMiddle2", "f_middle.02.R", "TR", "mixamorig:RightHandMiddle3"],
    ["ORG-f_ring.02.R", "ORG-f_ring.01.R",      "mixamorig:RightHandRing2", "f_ring.02.R", "TR", "mixamorig:RightHandRing3"],
    ["ORG-f_pinky.02.R", "ORG-f_pinky.01.R",    "mixamorig:RightHandPinky2", "f_pinky.02.R", "TR", "mixamorig:RightHandPinky3"],
    ["ORG-thumb.03.R", "ORG-thumb.02.R",        "mixamorig:RightHandThumb3", "thumb.03.R", "TR", "mixamorig:RightHandThumb4"],
    ["ORG-f_index.03.R", "ORG-f_index.02.R",    "mixamorig:RightHandIndex3", "f_index.03.R", "TR", "mixamorig:RightHandIndex4"],
    ["ORG-f_middle.03.R", "ORG-f_middle.02.R",  "mixamorig:RightHandMiddle3", "f_middle.03.R", "TR", "mixamorig:RightHandMiddle4"],
    ["ORG-f_ring.03.R", "ORG-f_ring.02.R",      "mixamorig:RightHandRing3", "f_ring.03.R", "TR", "mixamorig:RightHandRing4"],
    ["ORG-f_pinky.03.R", "ORG-f_pinky.02.R",    "mixamorig:RightHandPinky3", "f_pinky.03.R", "TR", "mixamorig:RightHandPinky4"],
    #face
    ["ORG-face", "ORG-spine.006",               "", "", ""],
    # eyes
    ["ORG-eye.L", "ORG-face",                   "mixamorig:LeftEye", "eye.L", "PRD", "ORG-eye.L"],
    ["ORG-eye.R", "ORG-face",                   "mixamorig:RightEye", "eye.R", "PRD", "ORG-eye.R"],
    ["ORG-eyes", "ORG-face",                    "", "eyes", "+LRA", "rigify:eyes", "eye.R", "eye.L"],
    # IK bones
    ["ORG-hand.L", "ORG-forearm.L",             "mixamorig:LeftHand$", "hand_ik.L", "NTLR", "mixamorig:LeftHandMiddle1"],
    ["ORG-hand.R", "ORG-forearm.R",             "mixamorig:RightHand$", "hand_ik.R", "NTLR", "mixamorig:RightHandMiddle1"],
    ["ORG-foot.L", "ORG-shin.L",                "mixamorig:LeftFoot", "foot_ik.L", "NPLR", "mixamorig:LeftToeBase"],
    ["ORG-foot.R", "ORG-shin.R",                "mixamorig:RightFoot", "foot_ik.R", "NPLR", "mixamorig:RightToeBase"],
    ["ORG-toe.L", "ORG-foot.L",                 "mixamorig:LeftToeBase", "toe_ik.L", "NTLR", "mixamorig:LeftToe_End"],
    ["ORG-toe.R", "ORG-foot.R",                 "mixamorig:RightToeBase", "toe_ik.R", "NTLR", "mixamorig:RightToe_End"],
]


RETARGET_CORRECTIONS = {
    "Heel_Angle": {
        "bone": [(0, 0, 0), (0, 0, 0.1), "retarget_heel_correction_angle", "rotation_euler", 0],
        "constraints": [
            ["ORG-foot.L", "ROT_ADD_LOCAL", "-X"],
            ["ORG-foot.R", "ROT_ADD_LOCAL", "-X"],
        ],
    },

    "Arm_Angle": {
        "bone": [(0, 0, 0), (0, 0, 0.1), "retarget_arm_correction_angle", "rotation_euler", 2],
        "constraints": [
            ["ORG-upper_arm.L", "ROT_ADD_LOCAL", "Z"],
            ["ORG-upper_arm.R", "ROT_ADD_LOCAL", "-Z"],
        ],
    },

    "Leg_Angle": {
        "bone": [(0, 0, 0), (0, 0, 0.1), "retarget_leg_correction_angle", "rotation_euler", 2],
        "constraints": [
            ["ORG-thigh.L", "ROT_ADD_LOCAL", "Z"],
            ["ORG-thigh.R", "ROT_ADD_LOCAL", "-Z"],
        ],
    },

    "Z_Correction": {
        "bone": [(0, 0, 0), (0, 0, 0.1), "retarget_z_correction_height", "location", 1],
        "constraints": [
            ["ORG-hip", "LOC_OFF_LOCAL", "Y"],
        ],
    },
}