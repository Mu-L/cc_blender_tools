import bpy #, bpy_extras
#import bpy_extras.view3d_utils as v3d
import atexit
from enum import IntEnum
import os, socket, time, select, struct, json, copy, shutil, tempfile
#import subprocess
from mathutils import Vector, Quaternion, Matrix, Color, Euler
from . import (rlx, importer, exporter, bones, geom, colorspace,
               world, rigging, rigutils, drivers, modifiers,
               cc, jsonutils, utils, vars)
import textwrap

BLENDER_PORT = 9333
UNITY_PORT = 9334
HANDSHAKE_TIMEOUT_S = 60
KEEPALIVE_TIMEOUT_S = 300
PING_INTERVAL_S = 120
TIMER_INTERVAL = 1/30
MAX_CHUNK_SIZE = 32768
SERVER_ONLY = False
CLIENT_ONLY = True
CHARACTER_TEMPLATE: list = None
MAX_RECEIVE = 30
USE_PING = False
USE_KEEPALIVE = False
SOCKET_TIMEOUT = 5.0
INCLUDE_POSE_MESHES = False

class OpCodes(IntEnum):
    NONE = 0
    HELLO = 1
    PING = 2
    STOP = 10
    DISCONNECT = 11
    DEBUG = 15
    NOTIFY = 50
    INVALID = 55
    SAVE = 60
    FILE = 75
    MORPH = 90
    MORPH_UPDATE = 91
    REPLACE_MESH = 95
    MATERIALS = 96
    CHARACTER = 100
    CHARACTER_UPDATE = 101
    PROP = 102
    STAGING = 104
    LIGHTS_UPDATE = 105
    CAMERA = 106
    CAMERA_UPDATE = 107
    UPDATE_REPLACE = 108
    RIGIFY = 110
    TEMPLATE = 200
    POSE = 210
    POSE_FRAME = 211
    SEQUENCE = 220
    SEQUENCE_FRAME = 221
    SEQUENCE_END = 222
    SEQUENCE_ACK = 223
    LIGHTING = 230
    CAMERA_SYNC = 231
    FRAME_SYNC = 232
    MOTION = 240
    REQUEST = 250
    CONFIRM = 251


VISEME_NAME_MAP = {
    "None": "None",
    "Open": "V_Open",
    "Explosive": "V_Explosive",
    "Upper Dental": "V_Dental_Lip",
    "Tight O": "V_Tight_O",
    "Pucker": "V_Tight",
    "Wide": "V_Wide",
    "Affricate": "V_Affricate",
    "Lips Parted": "V_Lip_Open",
    "Tongue Up": "V_Tongue_up",
    "Tongue Raised": "V_Tongue_Raise",
    "Tongue Out": "V_Tongue_Out",
    "Tongue Narrow": "V_Tongue_Narrow",
    "Tongue Lower": "V_Tongue_Lower",
    "Tongue Curl-U": "V_Tongue_Curl_U",
    "Tongue Curl-D": "V_Tongue_Curl_D",
    "EE": "EE",
    "Er": "Er",
    "Ih": "IH",
    "Ah": "Ah",
    "Oh": "Oh",
    "W.OO": "W_OO",
    "S.Z": "S_Z",
    "Ch.J": "Ch_J",
    "F.V": "F_V",
    "Th": "TH",
    "T.L.D": "T_L_D_N",
    "B.M.P": "B_M_P",
    "K.G": "K_G_H_NG",
    "N.NG": "AE",
    "R": "R",
}


class LinkActor():
    name: str = "Name"
    chr_cache = None
    object: bpy.types.Object = None
    bones: list = None
    meshes: list = None
    id_tree: dict = None
    id_map: dict = None
    skin_meshes: dict = None
    rig_bones: list = None
    expressions: list = None
    visemes: list = None
    morphs: list = None
    cache: dict = None
    alias: list = None
    shape_keys: dict = None
    ik_store: dict = None
    rigify_ik_fk: float = 0.0

    def __init__(self, obj_or_chr_cache):
        if type(obj_or_chr_cache) is bpy.types.Object:
            self.object = obj_or_chr_cache
            self.name = obj_or_chr_cache.name
        else:
            self.object = None
            self.chr_cache = obj_or_chr_cache
            self.name = obj_or_chr_cache.character_name
        self.bones = []
        self.meshes = []
        self.id_tree = None
        self.id_map = None
        self.skin_meshes = None
        self.rig_bones = []
        self.expressions = []
        self.visemes = []
        self.morphs = []
        self.cache = None
        self.alias = []
        self.shape_keys = {}
        return

    def get_chr_cache(self):
        return self.chr_cache

    def get_link_id(self):
        if self.object:
            return utils.get_rl_link_id(self.object)
        elif self.chr_cache:
            return self.chr_cache.get_link_id()
        return None

    def get_armature(self):
        if self.chr_cache:
            return self.chr_cache.get_armature()
        return None

    def select(self):
        if self.chr_cache:
            self.chr_cache.select_all()
        elif self.object:
            utils.try_select_object(self.object)

    def get_type(self):
        """AVATAR|PROP|LIGHT|CAMERA|NONE"""
        if self.chr_cache:
            return self.chr_cache_type(self.chr_cache)
        elif self.object:
            return self.object.type
        return "NONE"

    def add_alias(self, link_id):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            actor_link_id = chr_cache.link_id
            if not actor_link_id:
                utils.log_info(f"Assigning actor link_id: {chr_cache.character_name}: {link_id}")
                chr_cache.set_link_id(link_id)
                return
            if link_id not in self.alias and actor_link_id != link_id:
                utils.log_info(f"Assigning actor alias: {chr_cache.character_name}: {link_id}")
                self.alias.append(link_id)
                return

    @staticmethod
    def find_actor(link_id, search_name=None, search_type=None, context_chr_cache=None):
        props = vars.props()
        prefs = vars.prefs()
        link_data = get_link_data()

        utils.log_detail(f"Looking for LinkActor: {search_name} {link_id} {search_type}")
        actor: LinkActor = None

        for obj in bpy.data.objects:
            if obj.type == "LIGHT" or obj.type == "CAMERA":
                if not search_type or (obj.type == search_type):
                    obj_link_id = utils.get_rl_link_id(obj)
                    if obj_link_id is not None and link_id == obj_link_id:
                        actor = LinkActor(obj)
                        utils.log_detail(f"Staging (Light/Camera) found by link_id: {actor.name} / {link_id}")
                        return actor

        chr_cache = props.find_character_by_link_id(link_id)
        if chr_cache:
            if not search_type or LinkActor.chr_cache_type(chr_cache) == search_type:
                actor = LinkActor(chr_cache)
                utils.log_detail(f"Chr found by link_id: {actor.name} / {link_id}")
                return actor
        utils.log_detail(f"Chr not found by link_id")

        # try to find the character by name if the link id finds nothing
        # character id's change after every reload in iClone/CC4 so these can change.
        if search_name:
            chr_cache = props.find_character_by_name(search_name)
            if chr_cache:
                if not search_type or LinkActor.chr_cache_type(chr_cache) == search_type:
                    utils.log_detail(f"Chr found by name: {chr_cache.character_name} / {chr_cache.link_id} -> {link_id}")
                    actor = LinkActor(chr_cache)
                    actor.add_alias(link_id)
                    return actor
            utils.log_detail(f"Chr not found by name")

        # finally if matching to any avatar, trying to find an avatar and there is only
        # one avatar in the scene, use that one avatar, otherwise use the selected avatar
        if False and link_data and link_data.is_cc() and prefs.datalink_match_any_avatar and search_type == "AVATAR":
            chr_cache = None

            if len(props.get_avatars()) == 1:
                chr_cache = props.get_first_avatar()
            else:
                if not context_chr_cache:
                    context_chr_cache = props.get_context_character_cache()
                if context_chr_cache and context_chr_cache.is_avatar():
                    chr_cache = context_chr_cache
            if chr_cache:
                utils.log_detail(f"Falling back to first Chr Avatar: {chr_cache.character_name} / {chr_cache.link_id} -> {link_id}")
                actor = LinkActor(chr_cache)
                actor.add_alias(link_id)
                return actor

        utils.log_info(f"LinkActor not found: {search_name} {link_id} {search_type}")
        return actor

    @staticmethod
    def chr_cache_type(chr_cache):
        if chr_cache:
            return chr_cache.cache_type()
        return "NONE"

    def get_mesh_objects(self):
        objects = None
        chr_cache = self.get_chr_cache()
        if chr_cache:
            objects = chr_cache.get_all_objects(include_armature=False,
                                                include_children=True,
                                                of_type="MESH")
        return objects

    def object_has_sequence_shape_keys(self, obj):
        if obj.data.shape_keys and obj.data.shape_keys.key_blocks:
            for expression_name in self.expressions:
                if expression_name in obj.data.shape_keys.key_blocks:
                    return True
            for viseme_name in self.visemes:
                if viseme_name in obj.data.shape_keys.key_blocks:
                    return True
        return False

    def collect_shape_keys(self):
        self.shape_keys = {}
        objects: list = self.get_mesh_objects()
        # sort objects by reverse shape_key count (this should put the body mesh first)
        objects.sort(key=utils.key_count, reverse=True)
        # collect dictionary of shape keys and their primary key block
        for obj in objects:
            if obj.data.shape_keys and obj.data.shape_keys.key_blocks:
                for key in obj.data.shape_keys.key_blocks:
                    if key.name not in self.shape_keys:
                        self.shape_keys[key.name] = key

    def get_sequence_objects(self):
        objects = []
        non_sequence_objects = []
        chr_cache = self.get_chr_cache()
        if chr_cache:
            all_objects = chr_cache.get_all_objects(include_armature=False,
                                                    include_children=True,
                                                    of_type="MESH")
            for obj in all_objects:
                if self.object_has_sequence_shape_keys(obj):
                    objects.append(obj)
                else:
                    non_sequence_objects.append(obj)
        return objects, non_sequence_objects

    def set_template(self, actor_data: dict):
        self.set_id_tree(actor_data.get("bones"),
                         actor_data.get("ids"),
                         actor_data.get("id_tree"))
        self.expressions = actor_data.get("expressions")
        self.visemes = self.remap_visemes(actor_data.get("visemes"))
        self.morphs = actor_data.get("morphs")
        skin_meshes = {}
        if vars.DEV:
            if self.get_type() == "AVATAR" or self.get_type() == "PROP":
                utils.log_detail(f"Actor: {self.name}")
                utils.log_detail(f"Bones: {self.bones}")
                utils.log_detail(f"{json.dumps(self.id_tree, indent=4)}")
                utils.log_detail(f"{json.dumps(self.id_map, indent=4)}")
        for id, id_def in self.id_map.items():
            if id_def["mesh"]:
                obj: bpy.types.Object = bpy.data.objects[id_def["name"]]
                skin_meshes[id] = [obj, Vector((0,0,0)), Quaternion((1,0,0,0)), Vector((1,1,1))]
        self.skin_meshes = skin_meshes

    def set_id_tree(self, bones, ids, id_tree):
        arm = self.get_armature()
        if self.is_rigified():
            arm = None
        if bones and ids and id_tree:
            self.bones = bones
            self.ids = ids
            self.id_tree, self.id_map = cc.convert_id_tree(arm, id_tree)
            self.meshes = [ id_def["name"] for id_def in self.id_map.values() if id_def["mesh"] ]
            cc.confirm_bone_order(bones, ids, self.id_map)
        else:
            self.bones = None
            self.ids = None
            self.id_tree = None
            self.id_map = None

    def get_bone_id(self, bone_name):
        if self.id_map:
            for id, id_def in self.id_map.items():
                if id_def["name"] == bone_name:
                    return id
                if "_BoneRoot" in bone_name and "_BoneRoot" in id_def["name"]:
                    return id
        return -1

    def remap_visemes(self, visemes):
        exported_visemes = []
        for viseme_name in visemes:
            if viseme_name in VISEME_NAME_MAP:
                exported_visemes.append(VISEME_NAME_MAP[viseme_name])
        return exported_visemes

    def clear_template(self):
        self.bones = None

    def set_cache(self, cache):
        self.cache = cache

    def clear_cache(self):
        self.cache = None

    def update_name(self, new_name):
        self.name = new_name
        chr_cache = self.get_chr_cache()
        if chr_cache:
            chr_cache.character_name = new_name

    def update_link_id(self, new_link_id):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            utils.log_info(f"Assigning new link_id: {chr_cache.character_name}: {new_link_id}")
            chr_cache.set_link_id(new_link_id)

    def ready(self, require_cache=True):
        if require_cache and not self.cache:
            return False
        return (self.chr_cache and self.get_armature()) or self.object

    def is_rigified(self):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            return chr_cache.rigified
        return False

    def has_key(self):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            return chr_cache.get_import_has_key()
        return False

    def can_go_cc(self):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            return chr_cache.can_go_cc()
        return False

    def can_go_ic(self):
        chr_cache = self.get_chr_cache()
        if chr_cache:
            return chr_cache.can_go_ic()
        return False


class LinkData():
    actors: list = []
    # Sequence/Pose Props
    sequence_current_frame: int = 0
    sequence_start_frame: int = 0
    sequence_end_frame: int = 0
    sequence_actors: list = None
    sequence_type: str = None
    #
    preview_shape_keys: bool = True
    preview_skip_frames: bool = False
    # remote props
    remote_app: str = None
    remote_version: str = None
    remote_path: str = None
    remote_exe: str = None
    #
    ack_rate: float = 0.0
    ack_time: float = 0.0
    #
    motion_prefix: str = ""
    use_fake_user: bool = False
    set_keyframes: bool = True

    def __init__(self):
        return

    def reset(self):
        self.actors = []
        self.sequence_actors = None
        self.sequence_type = None

    def is_cc(self):
        if self.remote_app == "Character Creator":
            return True
        else:
            return False

    def find_sequence_actor(self, link_id) -> LinkActor:
        for actor in self.sequence_actors:
            if actor.get_link_id() == link_id:
                return actor
        for actor in self.sequence_actors:
            if link_id in actor.alias:
                return actor
        return None

    def set_action_settings(self, prefix: str, fake_user, set_keyframes):
        self.motion_prefix = prefix.strip()
        self.use_fake_user = fake_user
        self.set_keyframes = set_keyframes






LINK_DATA = LinkData()

def get_link_data():
    global LINK_DATA
    return LINK_DATA


def encode_from_json(json_data) -> bytearray:
    json_string = json.dumps(json_data)
    json_bytes = bytearray(json_string, "utf-8")
    return json_bytes


def decode_to_json(data) -> dict:
    text = data.decode("utf-8")
    json_data = json.loads(text)
    return json_data


def pack_string(s) -> bytearray:
    buffer = bytearray()
    buffer += struct.pack("!I", len(s))
    buffer += bytes(s, encoding="utf-8")
    return buffer


def unpack_string(buffer, offset=0):
    length = struct.unpack_from("!I", buffer, offset)[0]
    offset += 4
    string: bytearray = buffer[offset:offset+length]
    offset += length
    return offset, string.decode(encoding="utf-8")


def get_datalink_temp_local_folder():
    prefs = vars.prefs()
    link_props = vars.link_props()
    # prefs.temp_folder is the user definable temp folder
    # link_props.temp_folder is the temp folder that was used to generate the current link_props.temp_files folder
    # if prefs.temp_folder is changed, generate a new link_props.temp_files and store the new temp_folder
    if prefs.temp_folder != link_props.temp_folder:
        link_props.temp_files = ""
    if not link_props.temp_files:
        parent_dir = prefs.temp_folder if prefs.temp_folder else None
        link_props.temp_files = tempfile.mkdtemp(dir=parent_dir)
        link_props.temp_folder = prefs.temp_folder
    return link_props.temp_files


def get_local_data_path():
    prefs = vars.prefs()
    link_props = vars.link_props()
    local_path = utils.local_path()
    blend_file_name = utils.blend_file_name()
    data_path = ""
    # if blend file is saved and has a local path, always use this as the parent folder to save local files
    if local_path and blend_file_name:
        data_path = local_path
    # otherwise, if not saved yet, determine a temp folder location
    else:
        # if connected locally and we have CC/iClone's datalink path, use that for our local files
        if (LINK_SERVICE and
            LINK_SERVICE.is_local() and
            LINK_SERVICE.remote_path and
            not link_props.temp_files):
            link_props.temp_files = tempfile.mkdtemp(dir=LINK_SERVICE.remote_path)
            data_path = link_props.temp_files
        # otherwise generate a temp folder in either the system temp files or in the user temp folder
        #                                  or regenerate a new one if the user temp folder has changed
        elif not link_props.temp_files or prefs.temp_folder != link_props.temp_folder:
            data_path = get_datalink_temp_local_folder()
        else:
            data_path = link_props.temp_files
    return data_path


def get_remote_tar_file_path(remote_id):
    data_path = get_local_data_path()
    remote_import_path = utils.make_sub_folder(data_path, "imports")
    remote_file_path = os.path.join(remote_import_path, f"{remote_id}.tar")
    return remote_file_path


def get_unpacked_tar_file_folder(remote_id):
    data_path = get_local_data_path()
    remote_import_path = utils.make_sub_folder(data_path, "imports")
    remote_files_folder = os.path.join(data_path, "imports", remote_id)
    return remote_files_folder


def find_rig_pivot_bone(rig, parent):
    bone: bpy.types.PoseBone
    for bone in rig.pose.bones:
        if bone.name.startswith("CC_Base_Pivot"):
            if bones.is_target_bone_name(bone.parent.name, parent):
                return bone.name
    return None


def BFA(f):
    """Blender Frame Adjust:
            Convert Blender frame index (starting at frame 1)
            to CC/iC frame index (starting at frame 0)
    """
    return max(0, f - 1)


def RLFA(f):
    """Reallusion Frame Adjust:
            Convert Reallusion frame index (starting at frame 0)
            to Blender frame index (starting at frame 1)
    """
    return f + 1


def make_datalink_import_rig(actor: LinkActor, objects: list):
    """Creates or re-uses and existing datalink pose rig for the character.
       This uses a pre-generated character template (list of bones in the character)
       sent from CC/iC to avoid encoding the bone names into the pose data stream."""

    if not actor:
        utils.log_error("make_datalink_import_rig - Invalid Actor:")
        return None
    if not actor.get_chr_cache():
        utils.log_error(f"make_datalink_import_rig - Invalid Actor cache: {actor.name}")
        return None
    # get character armature
    chr_rig = actor.get_armature()
    if not chr_rig:
        utils.log_error(f"make_datalink_import_rig - Invalid Actor armature: {actor.name}")
        return None

    RV = utils.store_render_visibility_state(chr_rig)

    utils.unhide(chr_rig)
    chr_cache = actor.get_chr_cache()
    is_prop = actor.get_type() == "PROP"

    if utils.object_exists_is_armature(chr_cache.rig_datalink_rig):
        actor.rig_bones = actor.bones.copy()
        utils.hide(chr_cache.rig_datalink_rig)
        #utils.log_info(f"Using existing datalink transfer rig: {chr_cache.rig_datalink_rig.name}")
        # add child proxy objects
        for obj in chr_cache.rig_datalink_rig.children:
            if utils.object_exists_is_mesh(obj):
                objects.append(obj)
        utils.restore_render_visibility_state(RV)
        return chr_cache.rig_datalink_rig

    rig_name = f"{chr_cache.character_name}_Link_Rig"
    utils.log_info(f"Creating datalink transfer rig: {rig_name}")

    # create pose armature
    datalink_rig = utils.get_armature(rig_name)
    if not datalink_rig:
        datalink_rig = utils.create_reuse_armature(rig_name)
        chr_rig = chr_cache.get_armature()
        chr_collections = utils.get_object_scene_collections(chr_rig)
        utils.move_object_to_scene_collections(datalink_rig, chr_collections)
        edit_bone: bpy.types.EditBone
        arm: bpy.types.Armature = datalink_rig.data
        rig_bones = []
        if utils.edit_mode_to(datalink_rig):
            while len(datalink_rig.data.edit_bones) > 0:
                datalink_rig.data.edit_bones.remove(datalink_rig.data.edit_bones[0])
            for i, id in enumerate(actor.ids):
                if id in actor.id_map:
                    id_def = actor.id_map[id]
                    if not id_def["mesh"]:
                        edit_bone = arm.edit_bones.new(id_def["name"])
                        rig_bones.append(id_def["name"])
                        edit_bone.head = Vector((0,0,0))
                        edit_bone.tail = Vector((0,1,0))
                        edit_bone.align_roll(Vector((0,0,1)))
                        edit_bone.length = 0.1

        utils.object_mode_to(datalink_rig)
        datalink_rig.show_in_front = False
        datalink_rig.data.display_type = "STICK"

        # constrain character armature if not rigified
        if not chr_cache.rigified:
            for i, rig_bone_name in enumerate(rig_bones):
                sk_bone_name = actor.bones[i]
                chr_bone_name = bones.find_target_bone_name(chr_rig, rig_bone_name)
                if chr_bone_name:
                    bones.add_copy_location_constraint(datalink_rig, chr_rig, rig_bone_name, chr_bone_name)
                    bones.add_copy_rotation_constraint(datalink_rig, chr_rig, rig_bone_name, chr_bone_name)
                    bones.add_copy_scale_constraint(datalink_rig, chr_rig, rig_bone_name, chr_bone_name)
                else:
                    utils.log_warn(f"Could not find target bone for: {rig_bone_name} in character rig!")
        utils.safe_set_action(datalink_rig, None)

    utils.object_mode_to(datalink_rig)
    utils.hide(datalink_rig)

    chr_cache.rig_datalink_rig = datalink_rig

    if chr_cache.rigified:
        # a rigified character must retarget the link rig, but...
        # the link rig doesn't have a valid bind pose, so the retargeting rig
        # can't use it as a source rig for the roll axes on the ORG bones,
        # so we use the original ones for the character type (option to_original_rig)
        # (data on the original bones is added the ORG bones during rigify process)
        rigging.adv_retarget_remove_pair(None, chr_cache)
        if not chr_cache.rig_retarget_rig:
            rigging.adv_retarget_pair_rigs(None, chr_cache, datalink_rig,
                                                 to_original_rig=True,
                                                 objects=objects,
                                                 shape_keys=actor.expressions)

    utils.restore_render_visibility_state(RV)
    return datalink_rig


def remove_datalink_import_rig(actor: LinkActor, apply_contraints=False):
    if actor:
        chr_cache = actor.get_chr_cache()
        chr_rig = actor.get_armature()

        RV = utils.store_render_visibility_state(chr_rig)
        utils.unhide(chr_rig)

        if apply_contraints and chr_rig:
            if utils.set_active_object(chr_rig):
                if utils.pose_mode_to(chr_rig):
                    action = utils.safe_get_action(chr_rig)
                    utils.safe_set_action(chr_rig, None)
                    bpy.ops.pose.visual_transform_apply()
                    pose = bones.copy_pose(chr_rig)
                    utils.safe_set_action(chr_rig, action)

        if utils.object_exists_is_armature(chr_cache.rig_datalink_rig):

            if chr_cache.rigified:
                rigging.adv_retarget_remove_pair(None, chr_cache)
                if actor.ik_store:
                    rigutils.set_rigify_ik_fk_influence(chr_rig, actor.ik_store["ik_fk"])
                    rigutils.restore_ik_stretch(actor.ik_store)

            else:
                # remove all contraints on the character rig
                if utils.object_exists(chr_rig):
                    if utils.object_mode_to(chr_rig):
                        for pose_bone in chr_rig.pose.bones:
                            bones.clear_constraints(chr_rig, pose_bone.name)

            utils.delete_armature_object(chr_cache.rig_datalink_rig)
            chr_cache.rig_datalink_rig = None

        if apply_contraints and chr_rig:
            if utils.set_active_object(chr_rig):
                if utils.pose_mode_to(chr_rig):
                    bones.paste_pose(chr_rig, pose)

        #rigging.reset_shape_keys(chr_cache)
        utils.restore_render_visibility_state(RV)
        utils.object_mode_to(chr_rig)


def set_actor_expression_weight(objects, expression_name, weight):
    global LINK_DATA
    if objects:
        obj: bpy.types.Object
        for obj in objects:
            if expression_name in obj.data.shape_keys.key_blocks:
                if obj.data.shape_keys.key_blocks[expression_name].value != weight:
                    obj.data.shape_keys.key_blocks[expression_name].value = weight


def set_actor_viseme_weight(objects, viseme_name, weight):
    global LINK_DATA
    if objects and LINK_DATA.preview_shape_keys:
        for obj in objects:
            if obj.data.shape_keys and obj.data.shape_keys.key_blocks:
                if viseme_name in obj.data.shape_keys.key_blocks:
                    if obj.data.shape_keys.key_blocks[viseme_name].value != weight:
                        obj.data.shape_keys.key_blocks[viseme_name].value = weight


def ensure_current_frame(current_frame):
    if bpy.context.scene.frame_current != current_frame:
        bpy.context.scene.frame_current = current_frame
    return current_frame


def next_frame(current_frame=None):
    if current_frame is None:
        current_frame = bpy.context.scene.frame_current
    fps = bpy.context.scene.render.fps
    end_frame = bpy.context.scene.frame_end
    current_frame = min(end_frame, current_frame + 1)
    bpy.context.scene.frame_current = current_frame
    return current_frame


def prev_frame(current_frame=None):
    if current_frame is None:
        current_frame = bpy.context.scene.frame_current
    fps = bpy.context.scene.render.fps
    start_frame = bpy.context.scene.frame_start
    current_frame = max(start_frame, current_frame - 1)
    bpy.context.scene.frame_current = current_frame
    return current_frame


def create_rotation_fcurves_cache(obj, count):
    if obj.rotation_mode == "QUATERNION":
        indices = 4
        defaults = [1,0,0,0]
    elif obj.rotation_mode == "AXIS_ANGLE":
        indices = 4
        defaults = [0,0,1,0]
    else: # transform_object.rotation_mode in [ "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX" ]:
        indices = 3
        defaults = [0,0,0]
    return create_fcurves_cache(count, indices, defaults, cache_type=obj.rotation_mode)


def create_fcurves_cache(count, indices, defaults, cache_type="VALUE"):
    curves = []
    cache = {
        "count": count,
        "indices": indices,
        "curves": curves,
        "type": cache_type,
    }
    for i in range(0, indices):
        d = defaults[i]
        cache_data = [d]*(count*2)
        curves.append(cache_data)
    return cache


def get_datalink_rig_action(rig, motion_id=None):
    if not motion_id:
        motion_id = "DataLink"
    rig_id = rigutils.get_rig_id(rig)
    action_name = rigutils.make_armature_action_name(rig_id, motion_id, LINK_DATA.motion_prefix)
    if action_name in bpy.data.actions:
        action = bpy.data.actions[action_name]
    else:
        action = bpy.data.actions.new(action_name)
    utils.safe_set_action(rig, action)
    action.use_fake_user = LINK_DATA.use_fake_user
    return action


def get_datalink_obj_actions(obj, motion_id=None):

    if not motion_id:
        motion_id = "DataLink"

    name = obj.name
    f_prefix = rigutils.get_formatted_prefix(LINK_DATA.motion_prefix)

    ob_name = f"{f_prefix}{name}|O|{motion_id}"
    data_name = f"{f_prefix}{name}|{obj.type[0]}|{motion_id}"

    if ob_name in bpy.data.actions:
        ob_action = bpy.data.actions[ob_name]
    else:
        ob_action = bpy.data.actions.new(ob_name)
    utils.safe_set_action(obj, ob_action)
    ob_action.use_fake_user = LINK_DATA.use_fake_user

    data_action = ob_action
    if not utils.B440():
        if data_name in bpy.data.actions:
            data_action = bpy.data.actions[data_name]
        else:
            data_action = bpy.data.actions.new(data_name)
        utils.safe_set_action(obj.data, data_action)
        data_action.use_fake_user = LINK_DATA.use_fake_user

    return ob_action, data_action


def prep_pose_actor(actor: LinkActor, start_frame, end_frame):
    """Prepares the character rig for keyframing poses from the pose data stream."""

    motion_id = "Pose" if LINK_DATA.sequence_type == "POSE" else "Sequence"

    if actor and actor.get_type() == "LIGHT":

        # create keyframe cache for light animation sequences
        if LINK_DATA.set_keyframes:

            rlx.prep_rlx_actions(actor.object, actor.name, motion_id,
                                 reuse_existing=True,
                                 timestamp=False,
                                 motion_prefix=LINK_DATA.motion_prefix)

            count = end_frame - start_frame + 1
            transform_cache = {}
            light_cache = {}
            actor_cache = {
                "object": actor.object,
                "transform": transform_cache,
                "light": light_cache,
                "start": start_frame,
                "end": end_frame,
            }

            transform_cache["loc"] = create_fcurves_cache(count, 3, [0,0,0])
            transform_cache["rot"] = create_rotation_fcurves_cache(actor.object, count)
            transform_cache["sca"] = create_fcurves_cache(count, 3, [1,1,1])
            light_cache["color"] = create_fcurves_cache(count, 3, [1,1,1])
            light_cache["energy"] = create_fcurves_cache(count, 1, [1])
            light_cache["cutoff_distance"] = create_fcurves_cache(count, 1, [9])
            light_cache["spot_blend"] = create_fcurves_cache(count, 1, [1])
            light_cache["spot_size"] = create_fcurves_cache(count, 1, [1])
            actor.set_cache(actor_cache)

        else:
            # when not setting keyframes remove all actions from the light
            # and let the DataLink set the pose and light settings directly
            utils.safe_set_action(actor.object, None)
            utils.safe_set_action(actor.object.data, None)

    elif actor and actor.get_type() == "CAMERA":

        # create keyframe cache for camera animation sequences
        if LINK_DATA.set_keyframes:

            rlx.prep_rlx_actions(actor.object, actor.name, motion_id,
                                 reuse_existing=True,
                                 timestamp=False,
                                 motion_prefix=LINK_DATA.motion_prefix)

            count = end_frame - start_frame + 1
            transform_cache = {}
            camera_cache = {}
            actor_cache = {
                "object": actor.object,
                "transform": transform_cache,
                "camera": camera_cache,
                "start": start_frame,
                "end": end_frame,
            }

            transform_cache["loc"] = create_fcurves_cache(count, 3, [0,0,0])
            transform_cache["rot"] = create_rotation_fcurves_cache(actor.object, count)
            transform_cache["sca"] = create_fcurves_cache(count, 3, [1,1,1])
            camera_cache["lens"] = create_fcurves_cache(count, 1, [50])
            camera_cache["dof"] = create_fcurves_cache(count, 1, [1])
            camera_cache["focus_distance"] = create_fcurves_cache(count, 1, [1])
            camera_cache["f_stop"] = create_fcurves_cache(count, 1, [2.8])
            actor.set_cache(actor_cache)

        else:
            # when not setting keyframes remove all actions from the camera
            # and let the DataLink set the pose and light settings directly
            utils.safe_set_action(actor.object, None)
            utils.safe_set_action(actor.object.data, None)

    elif actor and actor.get_chr_cache():

        # create keyframe cache for avatar or prop animation sequences
        chr_cache = actor.get_chr_cache()
        rig = actor.get_armature()
        if not rig:
            utils.log_error(f"Actor: {actor.name} invalid rig!")
            return
        objects, none_objects = actor.get_sequence_objects()
        if rig:
            rig_id = rigutils.get_rig_id(rig)
            rl_arm_id = utils.get_rl_object_id(rig)
            utils.log_info(f"Preparing Character Rig: {actor.name} {rig_id} / {len(actor.bones)} bones")

            if LINK_DATA.set_keyframes:
                set_id, set_generation = rigutils.generate_motion_set(rig, motion_id, LINK_DATA.motion_prefix)

                # rig action
                action = get_datalink_rig_action(rig, motion_id)
                rigutils.add_motion_set_data(action, set_id, set_generation, rl_arm_id=rl_arm_id)
                utils.log_info(f"Preparing rig action: {action.name}")
                utils.clear_action(action)

                # shape key actions
                num_expressions = len(actor.expressions)
                num_visemes = len(actor.visemes)
                if objects:
                    for obj in objects:
                        obj_id = rigutils.get_action_obj_id(obj)
                        action_name = rigutils.make_key_action_name(rig_id, motion_id, obj_id, LINK_DATA.motion_prefix)
                        utils.log_info(f"Preparing shape key action: {action_name} / {num_expressions}+{num_visemes} shape keys")
                        if action_name in bpy.data.actions:
                            action = bpy.data.actions[action_name]
                        else:
                            action = bpy.data.actions.new(action_name)
                        rigutils.add_motion_set_data(action, set_id, set_generation, obj_id=obj_id)
                        utils.clear_action(action)
                        utils.safe_set_action(obj.data.shape_keys, action)
                        action.use_fake_user = LINK_DATA.use_fake_user
                    # remove actions from non sequence objects
                    for obj in none_objects:
                        utils.safe_set_action(obj.data.shape_keys, None)

            else:
                # when not setting keyframes remove all actions from the rig
                # and let the DataLink set the pose and shape keys directly
                utils.safe_set_action(rig, None)
                for obj in objects:
                    utils.safe_set_action(obj.data.shape_keys, None)

            if chr_cache.rigified:
                # disable IK stretch, set rig to FK during transfer
                actor.ik_store = rigutils.disable_ik_stretch(rig)
                actor.ik_store["ik_fk"] = rigutils.get_rigify_ik_fk_influence(rig)
                rigutils.set_rigify_ik_fk_influence(rig, 1.0)

                BAKE_BONE_GROUPS = ["FK", "IK", "Special", "Root", "Face"] #not Tweak and Extra
                BAKE_BONE_COLLECTIONS = ["Face", #"Face (Primary)", "Face (Secondary)",
                                         "Face (Expressions)",
                                         "Torso", "Torso (Tweak)",
                                         "Fingers", "Fingers (Detail)",
                                         "Arm.L (IK)", "Arm.L (FK)", "Arm.L (Tweak)",
                                         "Leg.L (IK)", "Leg.L (FK)", "Leg.L (Tweak)",
                                         "Arm.R (IK)", "Arm.R (FK)", "Arm.R (Tweak)",
                                         "Leg.R (IK)", "Leg.R (FK)", "Leg.R (Tweak)",
                                         "Root"]
                SHOW_BONE_COLLECTIONS = [ "Face (UI)" ]
                SHOW_BONE_COLLECTIONS.extend(BAKE_BONE_COLLECTIONS)
                # These bones may need to have their pose reset as they are damped tracked in the rig:
                #    - adv pair rigs now resets all pose bones.
                BAKE_BONE_EXCLUSIONS = [
                    "thigh_ik.L", "thigh_ik.R", "thigh_parent.L", "thigh_parent.R",
                    "upper_arm_ik.L", "upper_arm_ik.R", "upper_arm_parent.L", "upper_arm_parent.R"
                ]
                BAKE_BONE_LAYERS = [0,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,22,28]
                SHOW_BONE_LAYERS = [ 23 ]
                SHOW_BONE_LAYERS.extend(BAKE_BONE_LAYERS)
                if rigutils.is_face_rig(rig):
                    SHOW_BONE_COLLECTIONS.remove("Face")
                    SHOW_BONE_LAYERS.remove(0)
                if utils.object_mode_to(rig):
                    bone: bpy.types.Bone
                    pose_bone: bpy.types.PoseBone
                    bones.make_bones_visible(rig, collections=SHOW_BONE_COLLECTIONS, layers=SHOW_BONE_LAYERS)
                    for pose_bone in rig.pose.bones:
                        bone = pose_bone.bone
                        bone.select = False
                        if bones.is_bone_in_collections(rig, bone, BAKE_BONE_COLLECTIONS,
                                                                   BAKE_BONE_GROUPS):
                            if bone.name not in BAKE_BONE_EXCLUSIONS:
                                bone.hide = False
                                if bones.can_unlock(pose_bone):
                                    bone.hide_select = False
                                bone.select = True
            else:
                if utils.object_mode_to(rig):
                    bone: bpy.types.Bone
                    pose_bone: bpy.types.PoseBone
                    for pose_bone in rig.pose.bones:
                        bone = pose_bone.bone
                        bone.hide = False
                        if bones.can_unlock(pose_bone):
                            bone.hide_select = False
                        bone.select = True

            # create keyframe cache for animation sequences
            if LINK_DATA.set_keyframes:

                count = end_frame - start_frame + 1
                bone_cache = {}
                expression_cache = {}
                viseme_cache = {}
                morph_cache = {}
                actor_cache = {
                    "rig": rig,
                    "bones": bone_cache,
                    "expressions": expression_cache,
                    "visemes": viseme_cache,
                    "morphs": morph_cache,
                    "start": start_frame,
                    "end": end_frame,
                }
                for pose_bone in rig.pose.bones:
                    bone_name = pose_bone.name
                    bone = rig.data.bones[bone_name]
                    if bone.select:
                        loc_cache = create_fcurves_cache(count, 3, [0,0,0])
                        sca_cache = create_fcurves_cache(count, 3, [1,1,1])
                        rot_cache = create_rotation_fcurves_cache(pose_bone, count)
                        bone_cache[bone_name] = {
                            "loc": loc_cache,
                            "sca": sca_cache,
                            "rot": rot_cache,
                        }

                for expression_name in actor.expressions:
                    expression_cache[expression_name] = create_fcurves_cache(count, 1, [0])

                for viseme_name in actor.visemes:
                    viseme_cache[viseme_name] = create_fcurves_cache(count, 1, [0])

                for morph_name in actor.morphs:
                    pass

                actor.set_cache(actor_cache)


def set_frame_range(start, end):
    bpy.data.scenes["Scene"].frame_start = start
    bpy.data.scenes["Scene"].frame_end = end


def set_frame(frame):
    bpy.data.scenes["Scene"].frame_current = frame
    bpy.context.view_layer.update()


def key_frame_pose_visual():
    area = [a for a in bpy.context.screen.areas if a.type=="VIEW_3D"][0]
    with bpy.context.temp_override(area=area):
        bpy.ops.anim.keyframe_insert_menu(type='BUILTIN_KSI_VisualLocRot')


def store_cache_curves_frame(cache, prop, frame, start, value):
    T = type(value)
    index = (frame - start) * 2
    if T is Quaternion:
        cache_type = cache[prop]["type"]
        if cache_type == "QUATERNION":
            l = len(value)
            for i in range(0, l):
                curve = cache[prop]["curves"][i]
                curve[index] = frame
                curve[index + 1] = value[i]
        elif cache_type == "AXIS_ANGLE":
            # convert quaternion to angle axis
            v,a = value.to_axis_angle()
            l = len(v)
            for i in range(0, l):
                curve = cache[prop]["curves"][i]
                curve[index] = frame
                curve[index + 1] = v[i]
            curve = cache[prop]["curves"][3]
            curve[index] = frame
            curve[index + 1] = a
        else:
            euler = value.to_euler(cache_type)
            l = len(euler)
            for i in range(0, l):
                curve = cache[prop]["curves"][i]
                curve[index] = frame
                curve[index + 1] = euler[i]
    elif T is Vector or T is Color or T is tuple or T is list:
        l = len(value)
        for i in range(0, l):
            curve = cache[prop]["curves"][i]
            curve[index] = frame
            curve[index + 1] = value[i]
    else:
        curve = cache[prop]["curves"][0]
        curve[index] = frame
        curve[index + 1] = value


def store_bone_cache_keyframes(actor: LinkActor, frame):
    """Needs to be called after all constraints have been set and all bones in the pose positioned"""

    if not actor.cache:
        utils.log_error(f"No actor cache: {actor.name}")
        return

    rig = actor.get_armature()
    start = actor.cache["start"]
    bone_cache = actor.cache["bones"]
    for bone_name in bone_cache:
        pose_bone: bpy.types.PoseBone = rig.pose.bones[bone_name]
        L: Matrix   # local space matrix we want
        NL: Matrix  # non-local space matrix we want (if not using local location or inherit rotation)
        M: Matrix = pose_bone.matrix # object space matrix of the pose bone after contraints and drivers
        R: Matrix = pose_bone.bone.matrix_local # bone rest pose matrix
        RI: Matrix = R.inverted() # bone rest pose matrix inverted
        if pose_bone.parent:
            PI: Matrix = pose_bone.parent.matrix.inverted() # parent object space matrix inverted (after contraints and drivers)
            PR: Matrix = pose_bone.parent.bone.matrix_local # parent rest pose matrix
            L = RI @ (PR @ (PI @ M))
            NL = PI @ M
        else:
            L = RI @ M
            NL = M
        if not pose_bone.bone.use_local_location:
            loc = NL.to_translation()
        else:
            loc = L.to_translation()
        sca = L.to_scale()
        if not pose_bone.bone.use_inherit_rotation:
            rot = NL.to_quaternion()
        else:
            rot = L.to_quaternion()
        store_cache_curves_frame(bone_cache[bone_name], "loc", frame, start, loc)
        store_cache_curves_frame(bone_cache[bone_name], "rot", frame, start, rot)
        store_cache_curves_frame(bone_cache[bone_name], "sca", frame, start, sca)


def store_shape_key_cache_keyframes(actor: LinkActor, frame, expression_weights, viseme_weights, morph_weights):

    if not actor.cache:
        utils.log_error(f"No actor cache: {actor.name}")
        return

    start = actor.cache["start"]
    expression_cache = actor.cache["expressions"]
    for i, expression_name in enumerate(expression_cache):
        store_cache_curves_frame(actor.cache["expressions"], expression_name, frame, start, expression_weights[i])
    viseme_cache = actor.cache["visemes"]
    for i, viseme_name in enumerate(viseme_cache):
        store_cache_curves_frame(actor.cache["visemes"], viseme_name, frame, start, viseme_weights[i])


def store_light_cache_keyframes(actor: LinkActor, frame):

    if not actor.cache:
        utils.log_error(f"No actor cache: {actor.name}")
        return

    light: bpy.types.Object = actor.object
    data: bpy.types.SpotLight = light.data
    transform_cache = actor.cache["transform"]
    light_cache = actor.cache["light"]
    start = actor.cache["start"]
    M: Matrix = light.matrix_local
    loc = M.to_translation()
    rot = M.to_quaternion()
    sca = M.to_scale()
    store_cache_curves_frame(transform_cache, "loc", frame, start, loc)
    store_cache_curves_frame(transform_cache, "rot", frame, start, rot)
    store_cache_curves_frame(transform_cache, "sca", frame, start, sca)
    store_cache_curves_frame(light_cache, "color", frame, start, data.color)
    store_cache_curves_frame(light_cache, "energy", frame, start, data.energy)
    store_cache_curves_frame(light_cache, "cutoff_distance", frame, start, data.cutoff_distance)
    if light.type == "SPOT":
        store_cache_curves_frame(light_cache, "spot_blend", frame, start, data.spot_blend)
        store_cache_curves_frame(light_cache, "spot_size", frame, start, data.spot_size)


def store_camera_cache_keyframes(actor: LinkActor, frame):

    if not actor.cache:
        utils.log_error(f"No actor cache: {actor.name}")
        return

    camera: bpy.types.Object = actor.object
    data: bpy.types.Camera = camera.data
    transform_cache = actor.cache["transform"]
    camera_cache = actor.cache["camera"]
    start = actor.cache["start"]
    M: Matrix = camera.matrix_local
    loc = M.to_translation()
    rot = M.to_quaternion()
    sca = M.to_scale()
    store_cache_curves_frame(transform_cache, "loc", frame, start, loc)
    store_cache_curves_frame(transform_cache, "rot", frame, start, rot)
    store_cache_curves_frame(transform_cache, "sca", frame, start, sca)
    store_cache_curves_frame(camera_cache, "lens", frame, start, data.lens)
    store_cache_curves_frame(camera_cache, "dof", frame, start, 1.0 if data.dof.use_dof else 0.0)
    store_cache_curves_frame(camera_cache, "focus_distance", frame, start, data.dof.focus_distance)
    store_cache_curves_frame(camera_cache, "f_stop", frame, start, data.dof.aperture_fstop)


def write_action_rotation_cache_curve(action: bpy.types.Action, cache, prop, obj, num_frames, group_name=None, slot=None):
    cache_type = cache[prop]["type"]
    data_path = None
    if cache_type == "QUATERNION":
        data_path = obj.path_from_id("rotation_quaternion")
        if not group_name:
            group_name = "Rotation Quaternion"
    elif cache_type == "AXIS_ANGLE":
        data_path = obj.path_from_id("rotation_axis_angle")
        if not group_name:
            group_name = "Rotation Axis-Angle"
    else:
        data_path = obj.path_from_id("rotation_euler")
        if not group_name:
            group_name = "Rotation Euler"
    write_action_cache_curve(action, cache, prop, data_path, num_frames, group_name, slot=slot)


def write_action_cache_curve(action: bpy.types.Action, cache, prop, data_path, num_frames, group_name, slot=None):
    if not LINK_DATA.set_keyframes: return
    prop_cache = cache[prop]
    num_curves = len(prop_cache["curves"])
    channels = utils.get_action_channels(action, slot)
    fcurve: bpy.types.FCurve = None
    if group_name not in channels.groups:
        channels.groups.new(group_name)
    for i in range(0, num_curves):
        cache_curve = prop_cache["curves"][i]
        fcurve = channels.fcurves.new(data_path, index=i)
        fcurve.keyframe_points.add(num_frames)
        set_count = num_frames * 2
        if set_count < len(cache_curve):
            # if setting fewer frames than are in the cache (sequence was stopped early)
            fcurve.keyframe_points.foreach_set('co', cache_curve[:set_count])
        else:
            fcurve.keyframe_points.foreach_set('co', cache_curve)


def write_sequence_actions(actor: LinkActor, num_frames):
    if actor.cache:

        if actor.get_type() == "PROP" or actor.get_type() == "AVATAR":

            rig = actor.cache["rig"]
            rig_action = utils.safe_get_action(rig)
            objects, none_objects = actor.get_sequence_objects()

            if rig_action:
                utils.clear_action(rig_action, "OBJECT", rig_action.name)
                bone_cache = actor.cache["bones"]
                for bone_name in bone_cache:
                    pose_bone: bpy.types.PoseBone = rig.pose.bones[bone_name]
                    write_action_cache_curve(rig_action, bone_cache[bone_name], "loc",
                                                pose_bone.path_from_id("location"), num_frames, bone_name)
                    write_action_rotation_cache_curve(rig_action, bone_cache[bone_name], "rot",
                                                pose_bone, num_frames, group_name=bone_name)
                    write_action_cache_curve(rig_action, bone_cache[bone_name], "sca",
                                                pose_bone.path_from_id("scale"), num_frames, bone_name)
                # re-apply action to fix slot
                utils.safe_set_action(rig, rig_action)

            expression_cache = actor.cache["expressions"]
            viseme_cache = actor.cache["visemes"]
            for obj in objects:
                obj_action = utils.safe_get_action(obj.data.shape_keys)
                if obj_action:
                    utils.clear_action(obj_action, "KEY", obj_action.name)
                    for expression_name in expression_cache:
                        if expression_name in obj.data.shape_keys.key_blocks:
                            key = obj.data.shape_keys.key_blocks[expression_name]
                            write_action_cache_curve(obj_action, expression_cache, expression_name,
                                                        key.path_from_id("value"), num_frames, "Expression")
                    for viseme_name in viseme_cache:
                        if viseme_name in obj.data.shape_keys.key_blocks:
                            key = obj.data.shape_keys.key_blocks[viseme_name]
                            write_action_cache_curve(obj_action, viseme_cache, viseme_name,
                                                        key.path_from_id("value"), num_frames, "Viseme")
                    utils.safe_set_action(obj.data.shape_keys, obj_action) # re-apply action to fix slot

            # remove actions from non sequence objects
            for obj in none_objects:
                utils.safe_set_action(obj.data.shape_keys, None)

        elif actor.get_type() == "LIGHT":

            light = actor.object
            ob_action = utils.safe_get_action(light)
            light_action = utils.safe_get_action(light.data)
            ob_slot = utils.get_action_slot(ob_action, "OBJECT")
            light_slot = utils.get_action_slot(light_action, "LIGHT")
            write_action_cache_curve(ob_action, actor.cache["transform"], "loc", "location", num_frames, "Location", slot=ob_slot)
            write_action_rotation_cache_curve(ob_action, actor.cache["transform"], "rot", light, num_frames, slot=ob_slot)
            write_action_cache_curve(ob_action, actor.cache["transform"], "sca", "scale", num_frames, "Scale", slot=ob_slot)
            write_action_cache_curve(light_action, actor.cache["light"], "color", "color", num_frames, "Light", slot=light_slot)
            write_action_cache_curve(light_action, actor.cache["light"], "energy", "energy", num_frames, "Light", slot=light_slot)
            write_action_cache_curve(light_action, actor.cache["light"], "cutoff_distance", "cutoff_distance", num_frames, "Light", slot=light_slot)
            if light.type == "SPOT":
                write_action_cache_curve(light_action, actor.cache["light"], "spot_blend", "spot_blend", num_frames, "Spotlight", slot=light_slot)
                write_action_cache_curve(light_action, actor.cache["light"], "spot_size", "spot_size", num_frames, "Spotlight", slot=light_slot)
            # re-apply actions to fix slot
            utils.safe_set_action(light, ob_action)
            utils.safe_set_action(light.data, light_action)

        elif actor.get_type() == "CAMERA":

            camera = actor.object
            ob_action = utils.safe_get_action(camera)
            cam_action = utils.safe_get_action(camera.data)
            ob_slot = utils.get_action_slot(ob_action, "OBJECT")
            cam_slot = utils.get_action_slot(cam_action, "CAMERA")
            write_action_cache_curve(ob_action, actor.cache["transform"], "loc", "location", num_frames, "Location", slot=ob_slot)
            write_action_rotation_cache_curve(ob_action, actor.cache["transform"], "rot", camera, num_frames, slot=ob_slot)
            write_action_cache_curve(ob_action, actor.cache["transform"], "sca", "scale", num_frames, "Scale", slot=ob_slot)
            write_action_cache_curve(cam_action, actor.cache["camera"], "lens", "lens", num_frames, "Light", slot=cam_slot)
            write_action_cache_curve(cam_action, actor.cache["camera"], "dof", "dof.use_dof", num_frames, "Light", slot=cam_slot)
            write_action_cache_curve(cam_action, actor.cache["camera"], "focus_distance", "dof.focus_distance", num_frames, "Light", slot=cam_slot)
            write_action_cache_curve(cam_action, actor.cache["camera"], "f_stop", "dof.aperture_f_stop", num_frames, "Light", slot=cam_slot)
            # re-apply actions to fix slot
            utils.safe_set_action(camera, ob_action)
            utils.safe_set_action(camera.data, cam_action)

        actor.clear_cache()


class Signal():
    callbacks: list = None

    def __init__(self):
        self.callbacks = []

    def connect(self, func):
        self.callbacks.append(func)

    def disconnect(self, func=None):
        if func:
            self.callbacks.remove(func)
        else:
            self.callbacks.clear()

    def emit(self, *args):
        for func in self.callbacks:
            func(*args)


class LinkService():
    timer = None
    server_sock: socket.socket = None
    client_sock: socket.socket = None
    server_sockets = []
    client_sockets = []
    empty_sockets = []
    client_ip: str = "127.0.0.1"
    client_port: int = BLENDER_PORT
    is_listening: bool = False
    is_connected: bool = False
    is_connecting: bool = False
    ping_timer: float = 0
    keepalive_timer: float = 0
    time: float = 0
    is_data: bool = False
    is_sequence: bool = False
    is_import: bool = False
    loop_rate: float = 0.0
    loop_count: int = 0
    sequence_send_count: int = 5
    sequence_send_rate: float = 5.0
    # Signals
    listening = Signal()
    connecting = Signal()
    connected = Signal()
    lost_connection = Signal()
    server_stopped = Signal()
    client_stopped = Signal()
    received = Signal()
    accepted = Signal()
    sent = Signal()
    changed = Signal()
    sequence = Signal()
    # local props
    local_app: str = None
    local_version: str = None
    local_path: str = None
    # remote props
    remote_app: str = None
    remote_version: str = None
    remote_path: str = None
    remote_exe: str = None
    plugin_version: str = None
    link_data: LinkData = None
    remote_is_local: bool = True

    def __init__(self):
        global LINK_DATA
        self.link_data = LINK_DATA
        atexit.register(self.service_disconnect)

    def __enter__(self):
        return self

    def __exit__(self):
        self.service_stop()

    def compatible_plugin(self, plugin_version):
        if f"v{plugin_version}" == vars.VERSION_STRING:
            return True
        if plugin_version in vars.PLUGIN_COMPATIBLE:
            return True
        return False

    def is_cc(self):
        return self.remote_app == "Character Creator"

    def is_iclone(self):
        return self.remote_app == "iClone"

    def start_server(self):
        if not self.server_sock:
            try:
                self.keepalive_timer = HANDSHAKE_TIMEOUT_S
                self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_sock.settimeout(SOCKET_TIMEOUT)
                self.server_sock.bind(('', BLENDER_PORT))
                self.server_sock.listen(5)
                #self.server_sock.setblocking(False)
                self.server_sockets = [self.server_sock]
                self.is_listening = True
                utils.log_info(f"Listening on TCP *:{BLENDER_PORT}")
                self.listening.emit()
                self.changed.emit()
            except Exception as e:
                self.server_sock = None
                self.server_sockets = []
                self.is_listening = True
                utils.log_error(f"Unable to start server on TCP *:{BLENDER_PORT}", e)

    def stop_server(self):
        if self.server_sock:
            utils.log_info(f"Closing Server Socket")
            try:
                self.server_sock.shutdown()
                self.server_sock.close()
            except:
                pass
        self.is_listening = False
        self.server_sock = None
        self.server_sockets = []
        self.server_stopped.emit()
        self.changed.emit()

    def start_timer(self):
        self.time = time.time()
        if not self.timer:
            bpy.app.timers.register(self.loop, first_interval=TIMER_INTERVAL)
            self.timer = True
            utils.log_info(f"Service timer started")

    def stop_timer(self):
        if self.timer:
            try:
                bpy.app.timers.unregister(self.loop)
            except:
                pass
            self.timer = False
            utils.log_info(f"Service timer stopped")

    def try_start_client(self, host, port):
        link_props = vars.link_props()

        if not self.client_sock:
            utils.log_info(f"Attempting to connect")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(SOCKET_TIMEOUT)
                sock.connect((host, port))
                #sock.setblocking(False)
                self.is_connected = False
                link_props.connected = False
                self.is_connecting = True
                self.client_sock = sock
                self.client_sockets = [sock]
                self.client_ip = host
                self.client_port = port
                self.keepalive_timer = KEEPALIVE_TIMEOUT_S
                self.ping_timer = PING_INTERVAL_S
                self.remote_is_local = True if self.client_ip == "127.0.0.1" else False
                utils.log_info(f"connecting with data link server on {host}:{port}")
                self.send_hello()
                self.connecting.emit()
                self.changed.emit()
                return True
            except:
                self.client_sock = None
                self.client_sockets = []
                self.is_connected = False
                link_props.connected = False
                self.is_connecting = False
                utils.log_info(f"Client socket connect failed!")
                return False
        else:
            utils.log_info(f"Client already connected!")
            return True

    def send_hello(self):
        prefs = vars.prefs()
        self.local_app = "Blender"
        self.local_version = bpy.app.version_string
        self.local_path = get_local_data_path()
        json_data = {
            "Application": self.local_app,
            "Version": self.local_version,
            "Path": self.local_path,
            "Addon": vars.VERSION_STRING[1:],
            "Local": self.remote_is_local,
        }
        utils.log_info(f"Send Hello: {self.local_path}")
        self.send(OpCodes.HELLO, encode_from_json(json_data))

    def stop_client(self):
        if self.client_sock:
            utils.log_info(f"Closing Client Socket")
            try:
                self.client_sock.shutdown()
                self.client_sock.close()
            except:
                pass
        self.is_connected = False
        self.is_connecting = False
        try:
            link_props = vars.link_props()
            link_props.connected = False
        except:
            pass
        self.client_sock = None
        self.client_sockets = []
        if self.listening:
            self.keepalive_timer = HANDSHAKE_TIMEOUT_S
        self.client_stopped.emit()
        self.changed.emit()

    def has_client_sock(self):
        if self.client_sock and (self.is_connected or self.is_connecting):
            return True
        else:
            return False

    def recv(self):
        prefs = vars.prefs()

        self.is_data = False
        self.is_import = False
        if self.has_client_sock():
            try:
                r,w,x = select.select(self.client_sockets, self.empty_sockets, self.empty_sockets, 0)
            except Exception as e:
                utils.log_error("Client socket recv:select failed!", e)
                self.client_lost()
                return
            count = 0
            while r:
                op_code = None
                try:
                    header = self.client_sock.recv(8)
                    if header == 0:
                        utils.log_always("Socket closed by client")
                        self.client_lost()
                        return
                except Exception as e:
                    utils.log_error("Client socket recv:recv header failed!", e)
                    self.client_lost()
                    return
                if header and len(header) == 8:
                    op_code, size = struct.unpack("!II", header)
                    data = None
                    if size > 0:
                        data = bytearray()
                        while size > 0:
                            chunk_size = min(size, MAX_CHUNK_SIZE)
                            try:
                                chunk = self.client_sock.recv(chunk_size)
                            except Exception as e:
                                utils.log_error("Client socket recv:recv chunk failed!", e)
                                self.client_lost()
                                return
                            data.extend(chunk)
                            size -= len(chunk)
                    if op_code == OpCodes.FILE:
                        remote_id = data.decode(encoding="utf-8")
                        chunk = self.client_sock.recv(4)
                        size = struct.unpack("!I", chunk)[0]
                        tar_file_path = get_remote_tar_file_path(remote_id)
                        with open(tar_file_path, 'wb') as file:
                            while size > 0:
                                chunk_size = min(size, MAX_CHUNK_SIZE)
                                try:
                                    chunk = self.client_sock.recv(chunk_size)
                                    file.write(chunk)
                                except Exception as e:
                                    utils.log_error("Client socket recv:recv file chunk failed!", e)
                                    self.client_lost()
                                    return
                                size -= len(chunk)
                    self.parse(op_code, data)
                    self.received.emit(op_code, data)
                    count += 1
                self.is_data = False
                # parse may have received a disconnect notice
                if not self.has_client_sock():
                    return
                # if preview frame sync update every frame in sequence
                if op_code == OpCodes.SEQUENCE_FRAME and prefs.datalink_frame_sync:
                    self.is_data = True
                    return
                # if not key framing, update every frame
                if not LINK_DATA.set_keyframes:
                    self.is_data = True
                    return
                if (op_code == OpCodes.CHARACTER or
                    op_code == OpCodes.PROP or
                    op_code == OpCodes.STAGING or
                    op_code == OpCodes.CAMERA):
                    # give imports time to process, otherwise bad things happen
                    self.is_data = False
                    self.is_import = True
                    return
                try:
                    r,w,x = select.select(self.client_sockets, self.empty_sockets, self.empty_sockets, 0)
                except Exception as e:
                    utils.log_error("Client socket recv:select (reselect) failed!", e)
                    self.client_lost()
                    return
                if r:
                    self.is_data = True
                    if count >= MAX_RECEIVE or op_code == OpCodes.NOTIFY or op_code == OpCodes.INVALID:
                        return

    def accept(self):
        link_props = vars.link_props()

        if self.server_sock and self.is_listening:
            r,w,x = select.select(self.server_sockets, self.empty_sockets, self.empty_sockets, 0)
            while r:
                try:
                    sock, address = self.server_sock.accept()
                except Exception as e:
                    utils.log_error("Server socket accept failed!", e)
                    self.service_lost()
                    return
                self.client_sock = sock
                self.client_sockets = [sock]
                self.client_ip = address[0]
                self.client_port = address[1]
                self.is_connected = False
                self.is_connecting = True
                link_props.connected = False
                self.keepalive_timer = KEEPALIVE_TIMEOUT_S
                self.ping_timer = PING_INTERVAL_S
                utils.log_info(f"Incoming connection received from: {address[0]}:{address[1]}")
                self.send_hello()
                self.accepted.emit(self.client_ip, self.client_port)
                self.changed.emit()
                r,w,x = select.select(self.server_sockets, self.empty_sockets, self.empty_sockets, 0)

    def parse(self, op_code, data):
        props = vars.props()
        link_props = vars.link_props()
        self.keepalive_timer = KEEPALIVE_TIMEOUT_S

        if op_code == OpCodes.HELLO:
            utils.log_info(f"Hello Received")
            if data:
                json_data = decode_to_json(data)
                self.remote_app = json_data["Application"]
                self.remote_version = json_data["Version"]
                self.remote_path = json_data["Path"]
                self.remote_exe = json_data["Exe"]
                self.plugin_version = json_data.get("Plugin", "")
                self.link_data.remote_app = self.remote_app
                self.link_data.remote_version = self.remote_version
                self.link_data.remote_path = self.remote_path
                self.link_data.remote_exe = self.remote_exe
                if self.compatible_plugin(self.plugin_version):
                    self.service_initialize()
                    link_props.remote_app = self.remote_app
                    link_props.remote_version = f"{self.remote_version[0]}.{self.remote_version[1]}.{self.remote_version[2]}"
                    link_props.remote_path = self.remote_path
                    link_props.remote_exe = self.remote_exe
                    utils.log_always(f"Connected to: {self.remote_app} {self.remote_version} / {self.plugin_version}")
                    utils.log_always(f"Using file path: {self.remote_path}")
                    utils.log_always(f"Using exe path: {self.remote_exe}")
                else:
                    self.service_disconnect()
                    messages = ["CC/iC Plug-in and Blender Add-on versions do not match!",
                                f"Blender add-on version: {vars.VERSION_STRING}",
                                f"CC/iC plug-in version: {self.plugin_version}",
                                f"*Compatible plug-in versions: {vars.PLUGIN_COMPATIBLE}"]
                    utils.message_box_multi("Version Error", icon="ERROR", messages=messages)


        elif op_code == OpCodes.PING:
            utils.log_info(f"Ping Received")

        elif op_code == OpCodes.STOP:
            utils.log_info(f"Termination Received")
            self.service_stop()

        elif op_code == OpCodes.DISCONNECT:
            utils.log_info(f"Disconnection Received")
            self.service_recv_disconnected()

        elif op_code == OpCodes.NOTIFY:
            self.receive_notify(data)

        elif op_code == OpCodes.INVALID:
            self.receive_invalid(data)

        elif op_code == OpCodes.DEBUG:
            self.receive_debug(data)

        ##
        #

        elif op_code == OpCodes.SAVE:
            self.receive_save(data)

        elif op_code == OpCodes.FILE:
            self.receive_remote_file(data)

        elif op_code == OpCodes.TEMPLATE:
            self.receive_actor_templates(data)

        elif op_code == OpCodes.POSE:
            self.receive_pose(data)

        elif op_code == OpCodes.POSE_FRAME:
            self.receive_pose_frame(data)

        elif op_code == OpCodes.MORPH:
            self.receive_morph(data)

        elif op_code == OpCodes.MORPH_UPDATE:
            self.receive_morph(data, update=True)

        elif op_code == OpCodes.CHARACTER:
            self.receive_actor_import(data)

        elif op_code == OpCodes.PROP:
            self.receive_actor_import(data)

        elif op_code == OpCodes.STAGING:
            self.receive_rlx_import(data)

        elif op_code == OpCodes.CAMERA:
            self.receive_camera_fbx_import(data)

        elif op_code == OpCodes.MOTION:
            self.receive_motion_import(data)

        elif op_code == OpCodes.CHARACTER_UPDATE:
            self.receive_actor_update(data)

        elif op_code == OpCodes.UPDATE_REPLACE:
            self.receive_update_replace(data)

        elif op_code == OpCodes.RIGIFY:
            self.receive_rigify_request(data)

        elif op_code == OpCodes.SEQUENCE:
            self.receive_sequence(data)

        elif op_code == OpCodes.SEQUENCE_FRAME:
            self.receive_sequence_frame(data)

        elif op_code == OpCodes.SEQUENCE_END:
            self.receive_sequence_end(data)

        elif op_code == OpCodes.SEQUENCE_ACK:
            self.receive_sequence_ack(data)

        elif op_code == OpCodes.LIGHTING:
            self.receive_lighting_sync(data)

        elif op_code == OpCodes.CAMERA_SYNC:
            self.receive_camera_sync(data)

        elif op_code == OpCodes.FRAME_SYNC:
            self.receive_frame_sync(data)

        elif op_code == OpCodes.REQUEST:
            self.receive_request(data)

        elif op_code == OpCodes.CONFIRM:
            self.receive_confirm(data)

    def service_start(self, host, port):
        if not self.is_listening:
            self.start_timer()
            if SERVER_ONLY:
                self.start_server()
            else:
                if not self.try_start_client(host, port):
                    if not CLIENT_ONLY:
                        self.start_server()

    def service_initialize(self):
        link_props = vars.link_props()
        if self.is_connecting:
            self.is_connecting = False
            self.is_connected = True
            link_props.connected = True
            self.on_connected()
            self.connected.emit()
            self.changed.emit()

    def service_disconnect(self):
        try:
            self.send(OpCodes.DISCONNECT)
            self.service_recv_disconnected()
        except: ...

    def service_recv_disconnected(self):
        if CLIENT_ONLY:
            self.stop_timer()
        self.stop_client()

    def service_stop(self):
        self.send(OpCodes.STOP)
        self.stop_timer()
        self.stop_client()
        self.stop_server()

    def service_lost(self):
        self.lost_connection.emit()
        self.stop_timer()
        self.stop_client()
        self.stop_server()

    def client_lost(self):
        self.lost_connection.emit()
        if CLIENT_ONLY:
            self.stop_timer()
        self.stop_client()

    def is_remote(self):
        return not self.remote_is_local

    def is_local(self):
        return self.remote_is_local

    def check_service(self):
        global LINK_SERVICE
        global LINK_DATA
        if not LINK_SERVICE or not LINK_DATA:
            utils.log_error("DataLink service data lost. Due to script reload?")
            utils.log_error("Connection is maintained but actor data has been reset.")
            LINK_SERVICE = self
            LINK_DATA = self.link_data
            LINK_DATA.reset()
        return True

    def check_paths(self):
        local_path = get_local_data_path()
        if local_path != self.local_path:
            self.local_path = local_path
            self.send_hello()

    def loop(self):
        try:
            current_time = time.time()
            delta_time = current_time - self.time
            self.time = current_time
            if delta_time > 0:
                rate = 1.0 / delta_time
                self.loop_rate = self.loop_rate * 0.75 + rate * 0.25
                #if self.loop_count % 100 == 0:
                #    utils.log_detail(f"LinkServer loop timer rate: {self.loop_rate}")
                self.loop_count += 1

            self.check_paths()

            if not self.check_service():
                return None

            if not self.timer:
                return None

            if self.is_connected:
                self.ping_timer -= delta_time
                self.keepalive_timer -= delta_time

                if USE_PING and self.ping_timer <= 0:
                    self.send(OpCodes.PING)

                if USE_KEEPALIVE and self.keepalive_timer <= 0:
                    utils.log_info("lost connection!")
                    self.service_stop()
                    return None

            elif self.is_listening:
                self.keepalive_timer -= delta_time

                if USE_KEEPALIVE and self.keepalive_timer <= 0:
                    utils.log_info("no connection within time limit!")
                    self.service_stop()
                    return None

            # accept incoming connections
            self.accept()

            # receive client data
            self.recv()

            # run anything in sequence
            for i in range(0, self.sequence_send_count):
                self.sequence.emit()

            if self.is_import:
                return 0.5
            else:
                interval = 0.0 if (self.is_data or self.is_sequence) else TIMER_INTERVAL
                return interval

        except Exception as e:
            utils.log_error("LinkService timer loop crash!", e)
            return TIMER_INTERVAL


    def send(self, op_code, binary_data = None):
        try:
            if self.client_sock and (self.is_connected or self.is_connecting):
                data_length = len(binary_data) if binary_data else 0
                header = struct.pack("!II", op_code, data_length)
                data = bytearray()
                data.extend(header)
                if binary_data:
                    data.extend(binary_data)
                try:
                    self.client_sock.sendall(data)
                except Exception as e:
                    utils.log_error("Client socket sendall failed!")
                    self.client_lost()
                    return
                self.ping_timer = PING_INTERVAL_S
                self.sent.emit()
        except Exception as e:
            utils.log_error("LinkService send failed!", e)

    def send_file(self, tar_id, tar_file):
        try:
            utils.log_info(f"Sending Remote files: {tar_file}")
            if self.client_sock and (self.is_connected or self.is_connecting):
                file_size = os.path.getsize(tar_file)
                id_data = pack_string(tar_id)
                data = bytearray()
                data.extend(struct.pack("!I", OpCodes.FILE))
                data.extend(id_data)
                data.extend(struct.pack("!I", file_size))
                self.client_sock.send(data)
                remaining_size = file_size
                with open(tar_file, 'rb') as file:
                    while remaining_size > 0:
                        chunk_size = min(MAX_CHUNK_SIZE, remaining_size)
                        byte_array = bytearray(file.read(chunk_size))
                        remaining_size -= MAX_CHUNK_SIZE
                        self.client_sock.send(byte_array)
                self.ping_timer = PING_INTERVAL_S
                self.sent.emit()
        except Exception as e:
            utils.log_error("LinkService send failed!", e)

    def start_sequence(self, func=None):
        self.is_sequence = True
        self.sequence_send_count = 5
        self.sequence_send_rate = 5.0
        if func:
            self.sequence.connect(func)
        else:
            self.sequence.disconnect()

    def stop_sequence(self):
        self.is_sequence = False
        self.sequence.disconnect()

    def update_sequence(self, count, delta_frames):
        if count is None:
            self.sequence_send_rate = 5.0
            self.sequence_send_count = 5
        else:
            self.sequence_send_rate = count
            self.sequence_send_count = count
            if self.loop_count % 30 == 0:
                utils.log_info(f"send_count: {self.sequence_send_count} delta_frames: {delta_frames}")


    def on_connected(self):
        self.send_notify("Connected")

    def send_notify(self, message):
        notify_json = { "message": message }
        self.send(OpCodes.NOTIFY, encode_from_json(notify_json))

    def send_invalid(self, message):
        notify_json = { "message": message }
        self.send(OpCodes.INVALID, encode_from_json(notify_json))

    def receive_notify(self, data):
        notify_json = decode_to_json(data)
        update_link_status(notify_json["message"])

    def receive_invalid(self, data):
        invalid_json = decode_to_json(data)
        update_link_status(invalid_json["message"])
        self.abort_sequence()

    def receive_save(self, data):
        if bpy.data.filepath:
            utils.log_info("Saving Mainfile")
            bpy.ops.wm.save_mainfile()

    def receive_remote_file(self, data: bytearray):
        remote_id = data.decode(encoding="utf-8")
        tar_file_path = get_remote_tar_file_path(remote_id)
        parent_path = os.path.dirname(tar_file_path)
        unpack_folder = utils.make_sub_folder(parent_path, remote_id)
        utils.log_info(f"Receive Remote Files: {remote_id} / {unpack_folder}")
        shutil.unpack_archive(tar_file_path, unpack_folder, "tar")
        os.remove(tar_file_path)
        #utils.show_system_file_browser(unpack_folder)

    def receive_debug(self, data):
        debug_json = None
        if data:
            debug_json = decode_to_json(data)
        debug(debug_json)

    def get_key_path(self, model_path, key_ext):
        dir, file = os.path.split(model_path)
        name, ext = os.path.splitext(file)
        key_path = os.path.normpath(os.path.join(dir, name + key_ext))
        return key_path

    def get_export_folder(self, folder_name, reuse=False):
        remote_path = self.remote_path
        local_path = self.local_path
        if not local_path:
            local_path = get_local_data_path()
        if local_path:
            export_folder = utils.make_sub_folder(local_path, "exports")
        else:
            export_folder = utils.make_sub_folder(remote_path, "exports")
        character_export_folder = utils.get_unique_folder_path(export_folder, folder_name, create=True, reuse=reuse)
        return character_export_folder

    def get_export_path(self, folder_name, file_name, reuse_folder=False, reuse_file=False):
        character_export_folder = self.get_export_folder(folder_name, reuse=reuse_folder)
        export_path = utils.get_unique_file_path(character_export_folder, file_name, reuse=reuse_file)
        return export_path

    def send_remote_files(self, export_folder):
        link_service: LinkService = LINK_SERVICE
        remote_id = ""
        if link_service.is_remote():
            parent_folder = os.path.dirname(export_folder)
            remote_id = str(time.time_ns())
            cwd = os.getcwd()
            tar_file_name = remote_id
            os.chdir(parent_folder)
            utils.log_info(f"Packing Remote files: {tar_file_name}")
            update_link_status("Packing Remote files")
            shutil.make_archive(tar_file_name, "tar", export_folder)
            os.chdir(cwd)
            tar_file_path = os.path.join(parent_folder, f"{tar_file_name}.tar")
            if os.path.exists(tar_file_path):
                update_link_status("Sending Remote files")
                link_service.send_file(remote_id, tar_file_path)
                update_link_status("Files Sent")
            if os.path.exists(tar_file_path):
                utils.log_info(f"Cleaning up remote export package: {tar_file_path}")
                os.remove(tar_file_path)
            if os.path.exists(export_folder):
                utils.log_info(f"Cleaning up remote export folder: {export_folder}")
                shutil.rmtree(export_folder)
        return remote_id

    def get_actor_from_object(self, obj):
        global LINK_DATA
        props = vars.props()
        chr_cache = props.get_character_cache(obj, None)
        if chr_cache:
            actor = LinkActor(chr_cache)
            return actor
        return None

    def get_selected_actors(self):
        global LINK_DATA
        props = vars.props()

        selected_objects = bpy.context.selected_objects
        avatars = props.get_avatars()
        actors = []
        cache_actors = []

        # if nothing selected then use the first available Avatar
        if not selected_objects and len(avatars) == 1:
            cache_actors.append(avatars[0])

        else:
            for obj in selected_objects:
                chr_cache = props.get_character_cache(obj, None)
                if chr_cache and chr_cache not in cache_actors:
                    cache_actors.append(chr_cache)

        for chr_cache in cache_actors:
            actor = LinkActor(chr_cache)
            actors.append(actor)

        for obj in selected_objects:
            if obj.type == "LIGHT" or obj.type == "CAMERA" and utils.get_rl_link_id(obj):
                actor = LinkActor(obj)
                actors.append(actor)

        return actors

    def get_actor_mesh_selection(self):
        selection = {}
        for obj in bpy.context.selected_objects:
            if obj.type == "MESH" or obj.type == "ARMATURE":
                actor = self.get_actor_from_object(obj)
                chr_cache = actor.get_chr_cache()
                selection.setdefault(chr_cache, {"meshes": [], "armatures": []})
                if obj.type == "MESH":
                    selection[chr_cache]["meshes"].append(obj)
                elif obj.type == "ARMATURE":
                    selection[chr_cache]["armatures"].append(obj)
        return selection


    def get_active_actor(self):
        global LINK_DATA
        props = vars.props()
        active_object = utils.get_active_object()
        if active_object:
            chr_cache = props.get_character_cache(active_object, None)
            if chr_cache:
                actor = LinkActor(chr_cache)
                return actor
        return None

    def send_actor(self):
        actors = self.get_selected_actors()
        state = utils.store_mode_selection_state()
        utils.clear_selected_objects()
        actor: LinkActor
        utils.log_info(f"Sending LinkActors: {([a.name for a in actors])}")
        count = 0
        for actor in actors:
            if actor.get_type() != "PROP" and actor.get_type() != "AVATAR": continue
            if self.is_cc() and not actor.can_go_cc(): continue
            if self.is_iclone() and not actor.can_go_ic(): continue
            self.send_notify(f"Blender Exporting: {actor.name}...")
            # Determine export path
            export_folder = self.get_export_folder(actor.name)
            export_file = actor.name + ".fbx"
            export_path = os.path.join(export_folder, export_file)
            if not export_path: continue
            # Export Actor Fbx
            self.send_notify(f"Exporting: {actor.name}")
            is_remote = LINK_SERVICE.is_remote()
            if actor.get_type() == "PROP":
                bpy.ops.cc3.exporter(param="EXPORT_CC3", link_id_override=actor.get_link_id(), filepath=export_path, include_textures=is_remote)
            elif actor.get_type() == "AVATAR":
                bpy.ops.cc3.exporter(param="EXPORT_CC3", link_id_override=actor.get_link_id(), filepath=export_path, include_textures=is_remote)
            # Send Remote Files First
            remote_id = self.send_remote_files(export_folder)
            # Send Actor
            update_link_status(f"Sending: {actor.name}")
            export_data = encode_from_json({
                "path": export_path,
                "remote_id": remote_id,
                "name": actor.name,
                "type": actor.get_type(),
                "link_id": actor.get_link_id(),
            })
            if is_remote or os.path.exists(export_path):
                self.send(OpCodes.CHARACTER, export_data)
                update_link_status(f"Sent: {actor.name}")
                count += 1
        utils.restore_mode_selection_state(state)
        return count

    def send_morph(self):
        actor: LinkActor = self.get_active_actor()
        if actor:
            self.send_notify(f"Blender Exporting: {actor.name}...")
            # Determine export path
            export_folder = self.get_export_folder("Morphs", reuse=True)
            export_file = actor.name + "_morph.obj"
            export_path = os.path.join(export_folder, export_file)
            key_path = self.get_key_path(export_path, ".ObjKey")
            if not export_path:
                return
            # Export Morph Obj
            self.send_notify(f"Exporting: {actor.name}")
            is_remote = LINK_SERVICE.is_remote()
            state = utils.store_mode_selection_state()
            bpy.ops.cc3.exporter(param="EXPORT_CC3", filepath=export_path)
            # Send Remote Files First
            remote_id = self.send_remote_files(export_folder)
            # Send Morph
            update_link_status(f"Sending: {actor.name}")
            export_data = encode_from_json({
                "path": export_path,
                "remote_id": remote_id,
                "key_path": key_path,
                "name": actor.name,
                "type": actor.get_type(),
                "link_id": actor.get_link_id(),
                "morph_name": "Test Morph",
                "morph_path": "Some/Path",
            })
            utils.restore_mode_selection_state(state)
            if is_remote or os.path.exists(export_path):
                self.send(OpCodes.MORPH, export_data)
                update_link_status(f"Sent: {actor.name}")
                return True
        return False

    def obj_export(self, file_path, use_selection=False, use_animation=False, global_scale=100,
                         use_vertex_colors=False, use_vertex_groups=False, apply_modifiers=True,
                         keep_vertex_order=False, use_materials=False):
        if utils.B330():
            bpy.ops.wm.obj_export(filepath=file_path,
                                global_scale=global_scale,
                                export_selected_objects=use_selection,
                                export_animation=use_animation,
                                export_materials=use_materials,
                                export_colors=use_vertex_colors,
                                export_vertex_groups=use_vertex_groups,
                                apply_modifiers=apply_modifiers)
        else:
            bpy.ops.export_scene.obj(filepath=file_path,
                                    global_scale=global_scale,
                                    use_selection=use_selection,
                                    use_materials=use_materials,
                                    use_animation=use_animation,
                                    use_vertex_groups=use_vertex_groups,
                                    use_mesh_modifiers=apply_modifiers,
                                    keep_vertex_order=keep_vertex_order)

    def send_replace_mesh(self):
        state = utils.store_mode_selection_state()
        objects = utils.get_selected_meshes()
        # important that character is in the exact same pose on both sides,
        # so make sure the character is on the same frame in the animation.
        self.send_frame_sync()
        count = 0
        for obj in objects:
            if obj.type == "MESH":
                actor = self.get_actor_from_object(obj)
                if actor:
                    obj_cache = actor.get_chr_cache().get_object_cache(obj)
                    object_name = obj.name
                    mesh_name = obj.data.name
                    if obj_cache:
                        object_name = obj_cache.source_name
                        mesh_name = obj_cache.source_name
                    export_path = self.get_export_path("Meshes", f"{obj.name}_mesh.obj",
                                                       reuse_folder=True, reuse_file=True)
                    utils.set_active_object(obj, deselect_all=True)
                    self.obj_export(export_path, use_selection=True, use_vertex_colors=True)
                    export_data = encode_from_json({
                        "path": export_path,
                        "actor_name": actor.name,
                        "object_name": object_name,
                        "mesh_name": mesh_name,
                        "type": actor.get_type(),
                        "link_id": actor.get_link_id(),
                    })
                    self.send(OpCodes.REPLACE_MESH, export_data)
                    update_link_status(f"Sent Mesh: {actor.name}")
                    count += 1

        utils.restore_mode_selection_state(state)

        return count

    def export_object_material_data(self, context, actor: LinkActor, objects):
        prefs = vars.prefs()
        obj: bpy.types.Object

        chr_cache = actor.get_chr_cache()
        if chr_cache:
            if prefs.datalink_send_mode == "ACTIVE":
                materials = []
                for obj in objects:
                    idx = obj.active_material_index
                    if len(obj.material_slots) > idx:
                        mat = obj.material_slots[idx].material
                        if mat:
                            materials.append(mat)
            else:
                materials = None
            export_path = self.get_export_path("Materials", f"{actor.name}.json",
                                               reuse_folder=True, reuse_file=True)
            export_dir, json_file = os.path.split(export_path)
            json_data = chr_cache.get_json_data()
            if not json_data:
                json_data = jsonutils.generate_character_base_json_data(actor.name)
                exporter.set_character_generation(json_data, chr_cache, actor.name)
            exporter.prep_export(context, chr_cache, actor.name, objects, json_data,
                                 chr_cache.get_import_dir(), export_dir,
                                 False, False, False, False, True,
                                 materials=materials, sync=True, force_bake=True)
            jsonutils.write_json(json_data, export_path)
            export_data = encode_from_json({
                        "path": export_path,
                        "actor_name": actor.name,
                        "type": actor.get_type(),
                        "link_id": actor.get_link_id(),
                    })
            self.send(OpCodes.MATERIALS, export_data)

    def send_material_update(self, context):
        state = utils.store_mode_selection_state()

        selection = self.get_actor_mesh_selection()
        count = 0
        for chr_cache in selection:
            actor = LinkActor(chr_cache)
            meshes = selection[chr_cache]["meshes"]
            armatures = selection[chr_cache]["armatures"]
            if armatures:
                # export material info for whole character
                all_meshes = actor.get_mesh_objects()
                self.export_object_material_data(context, actor, all_meshes)
                count += 1
            elif meshes:
                # export material info just for selected meshes
                self.export_object_material_data(context, actor, meshes)
                count += 1

        utils.restore_mode_selection_state(state)

        return count

    def encode_actor_templates(self, actors: list):
        pose_bone: bpy.types.PoseBone
        actor_data = []
        character_template = {
            "count": len(actors),
            "actors": actor_data,
        }

        actor: LinkActor
        for actor in actors:

            if actor.get_type() in ["PROP", "AVATAR"]:

                chr_cache = actor.get_chr_cache()
                bones = []
                meshes = []
                bone_ids = []
                mesh_ids = []

                if chr_cache.rigified:
                    rig = actor.get_armature()
                    # disable IK stretch
                    actor.ik_store = rigutils.disable_ik_stretch(rig)
                    # add the export retarget rig
                    if utils.object_exists_is_armature(chr_cache.rig_export_rig):
                        export_rig = chr_cache.rig_export_rig
                    else:
                        export_rig = rigging.adv_export_pair_rigs(chr_cache, link_target=True)[0]
                    # get all the exportable deformation bones
                    if rigutils.select_rig(export_rig):
                        for pose_bone in export_rig.pose.bones:
                            print(pose_bone)
                            if (pose_bone.name != "root" and
                                not pose_bone.name.startswith("DEF-") and
                                not pose_bone.name.startswith("NDP-") and
                                not pose_bone.name.startswith("NDC-")):
                                bones.append(pose_bone.name)
                                bone_id = actor.get_bone_id(pose_bone.name)
                                bone_ids.append(bone_id)
                    driver_mode = "BONE"
                    for i, id in enumerate(bone_ids):
                        if id == -1:
                            utils.log_info(f"Unidentified bone: {bones[i]}")
                else:
                    # get all the bones
                    rig: bpy.types.Object = chr_cache.get_armature()
                    if rigutils.select_rig(rig):
                        for pose_bone in rig.pose.bones:
                            bones.append(pose_bone.name)
                            bone_id = actor.get_bone_id(pose_bone.name)
                            bone_ids.append(bone_id)
                    if drivers.has_facial_shape_key_bone_drivers(chr_cache) or rigutils.is_face_rig(rig):
                        driver_mode = "EXPRESSION"
                    else:
                        driver_mode = "BONE"

                meshes = []
                for mesh_name in actor.meshes:
                    if mesh_name in bpy.data.objects:
                        mesh_obj = bpy.data.objects[mesh_name]
                        if utils.object_exists_is_mesh(mesh_obj):
                            meshes.append(mesh_name)
                            mesh_id = actor.get_bone_id(mesh_name)
                            mesh_ids.append(mesh_id)

                actor.collect_shape_keys()
                shapes = [key for key in actor.shape_keys]

                actor.bones = bones
                actor.meshes = meshes
                actor_data.append({
                    "name": actor.name,
                    "type": actor.get_type(),
                    "link_id": actor.get_link_id(),
                    "bones": bones,
                    "bone_ids": bone_ids,
                    "meshes": meshes, # meshes derived from the template send in confirm
                    "mesh_ids": mesh_ids,
                    "shapes": shapes,
                    "drivers": driver_mode,
                })

            else:

                # lights and cameras just have root transforms to animate
                # and fixed properties
                actor_data.append({
                    "name": actor.name,
                    "type": actor.get_type(),
                    "link_id": actor.get_link_id(),
                })

        return encode_from_json(character_template)

    def encode_request_data(self, actors, request_type):
        actors_data = []
        data = {
            "type": request_type,
            "actors": actors_data,
        }
        actor: LinkActor
        for actor in actors:
            actors_data.append({
                "name": actor.name,
                "type": actor.get_type(),
                "link_id": actor.get_link_id(),
            })
        return encode_from_json(data)

    def encode_pose_data(self, actors):
        fps = bpy.context.scene.render.fps
        start_frame = BFA(bpy.context.scene.frame_start)
        end_frame = BFA(bpy.context.scene.frame_end)
        start_time = start_frame / fps
        end_time = end_frame / fps
        frame = BFA(bpy.context.scene.frame_current)
        time = frame / fps
        actors_data = []
        data = {
            "fps": fps,
            "start_time": start_time,
            "end_time": end_time,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "time": time,
            "frame": frame,
            "actors": actors_data,
        }
        actor: LinkActor
        for actor in actors:
            actors_data.append({
                "name": actor.name,
                "type": actor.get_type(),
                "link_id": actor.get_link_id(),
            })
        return encode_from_json(data)

    def encode_pose_frame_data(self, actors: list):
        pose_bone: bpy.types.PoseBone
        data = bytearray()
        data += struct.pack("!II", len(actors), BFA(bpy.context.scene.frame_current))
        actor: LinkActor
        for actor in actors:
            actor_type = actor.get_type()

            data += pack_string(actor.name)
            data += pack_string(actor.get_type())
            data += pack_string(actor.get_link_id())

            if actor_type == "PROP" or actor_type == "AVATAR":

                chr_cache = actor.get_chr_cache()

                if chr_cache.rigified:
                    # add the import retarget rig
                    if utils.object_exists_is_armature(chr_cache.rig_export_rig):
                        export_rig = chr_cache.rig_export_rig
                    else:
                        export_rig = rigging.adv_export_pair_rigs(chr_cache, link_target=True)[0]
                    M: Matrix = export_rig.matrix_world

                    # pack object transform
                    T: Matrix = M
                    t = T.to_translation() * 100
                    r = T.to_quaternion()
                    s = T.to_scale()
                    data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)

                    # pack all the bone data for the exportable deformation bones
                    data += struct.pack("!I", len(actor.bones))
                    if utils.object_mode_to(export_rig):
                        for bone_name in actor.bones:
                            pose_bone = export_rig.pose.bones[bone_name]
                            T: Matrix = M @ pose_bone.matrix
                            t = T.to_translation() * 100
                            r = T.to_quaternion()
                            s = T.to_scale()
                            data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)
                else:
                    rig: bpy.types.Object = chr_cache.get_armature()
                    M: Matrix = rig.matrix_world

                    # pack object transform
                    T: Matrix = M
                    t = T.to_translation() * 100
                    r = T.to_quaternion()
                    s = T.to_scale()
                    data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)

                    # pack all the bone data
                    data += struct.pack("!I", len(rig.pose.bones))
                    if utils.object_mode_to(rig):
                        pose_bone: bpy.types.PoseBone
                        for pose_bone in rig.pose.bones:
                            T: Matrix = M @ pose_bone.matrix
                            t = T.to_translation()
                            r = T.to_quaternion()
                            s = T.to_scale()
                            data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)

                # pack mesh transforms (actor.meshes is sanitized by encode_actor_templates)
                if INCLUDE_POSE_MESHES:
                    data += struct.pack("!I", len(actor.meshes))
                    if utils.object_mode_to(rig):
                        mesh_obj: bpy.types.Object
                        for mesh_name in actor.meshes:
                            mesh_obj = bpy.data.objects[mesh_name]
                            T: Matrix = mesh_obj.matrix_world
                            t = T.to_translation()
                            r = T.to_quaternion()
                            s = T.to_scale()
                            data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)

                # pack shape_keys
                data += struct.pack("!I", len(actor.shape_keys))
                for shape_key, key in actor.shape_keys.items():
                    data += struct.pack("!f", key.value)

            elif actor_type == "LIGHT":
                M: Matrix = actor.object.matrix_world
                T: Matrix = M
                t = T.to_translation() * 100
                r = T.to_quaternion()
                s = T.to_scale()
                data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)
                light: bpy.types.SpotLight = actor.object.data
                # pack animateable light data
                data += struct.pack("!?fffffff",
                                    light.energy > 0.0001,
                                    light.color[0],
                                    light.color[1],
                                    light.color[2],
                                    light.energy,
                                    light.cutoff_distance * 100,
                                    light.spot_size if light.type == "SPOT" else 0.0,
                                    light.spot_blend if light.type == "SPOT" else 0.0)

            elif actor_type == "CAMERA":
                M: Matrix = actor.object.matrix_world
                T: Matrix = M
                t = T.to_translation() * 100
                r = T.to_quaternion()
                s = T.to_scale()
                data += struct.pack("!ffffffffff", t.x, t.y, t.z, r.x, r.y, r.z, r.w, s.x, s.y, s.z)
                camera: bpy.types.Camera = actor.object.data
                # pack animateable camera data
                data += struct.pack("!f?ff",
                                     camera.lens,
                                     camera.dof.use_dof,
                                     camera.dof.focus_distance * 100,
                                     camera.dof.aperture_fstop)

        return data

    def encode_sequence_data(self, actors, aborted=False):
        fps = bpy.context.scene.render.fps
        start_frame = BFA(bpy.context.scene.frame_start)
        end_frame = BFA(bpy.context.scene.frame_end)
        start_time = start_frame / fps
        end_time = end_frame / fps
        frame = BFA(bpy.context.scene.frame_current)
        time = frame / fps
        actors_data = []
        data = {
            "fps": fps,
            "start_time": start_time,
            "end_time": end_time,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "time": time,
            "frame": frame,
            "actors": actors_data,
            "aborted": aborted,
        }
        actor: LinkActor
        for actor in actors:
            actors_data.append({
                "name": actor.name,
                "type": actor.get_type(),
                "link_id": actor.get_link_id(),
            })
        return encode_from_json(data)

    def restore_actor_rigs(self, actors: LinkActor):
        """Restores any disabled IK stretch settings after export"""
        for actor in actors:
            chr_cache = actor.get_chr_cache()
            if chr_cache:
                arm = chr_cache.get_armature()
                if arm and chr_cache.rigified:
                    if actor.ik_store:
                        rigutils.restore_ik_stretch(actor.ik_store)
                # remove the export rigs
                utils.delete_armature_object(chr_cache.rig_export_rig)

    def send_request(self, request_type):
        global LINK_DATA
        # get actors
        actors = self.get_selected_actors()
        if actors:
            mode_selection = utils.store_mode_selection_state()
            update_link_status(f"Sending Request")
            self.send_notify(f"Request")
            # send request
            pose_data = self.encode_request_data(actors, request_type)
            self.send(OpCodes.REQUEST, pose_data)
            # store the actors
            LINK_DATA.sequence_actors = actors
            LINK_DATA.sequence_type = request_type
            # restore
            utils.restore_mode_selection_state(mode_selection)

    def send_pose_request(self):
        self.send_request("POSE")

    def send_sequence_request(self):
        self.send_request("SEQUENCE")

    def receive_request(self, data):
        update_link_status(f"Receiving Request ...")
        json_data = decode_to_json(data)
        request_type = json_data["type"]
        actors_data = json_data["actors"]
        for actor_data in actors_data:
            name = actor_data["name"]
            link_id = actor_data["link_id"]
            character_type = actor_data["type"]
            actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
            actor_data["confirm"] = actor is not None
            utils.log_info(f"Actor: {name} " + ("Confirmed!" if actor_data["confirm"] else "Missing!"))
            if actor:
                if actor.get_link_id() != link_id:
                    actor_data["update_link_id"] = actor.get_link_id()
                if actor.name != name:
                    actor_data["update_name"] = actor.name
        self.send(OpCodes.CONFIRM, encode_from_json(json_data))

    def receive_confirm(self, data):
        global LINK_DATA
        json_data = decode_to_json(data)
        request_type = json_data["type"]
        actors_data = json_data["actors"]
        for actor_data in actors_data:
            link_id = actor_data.get("link_id")
            name = actor_data.get("name")
            character_type = actor_data.get("type")
            new_link_id = actor_data.get("new_link_id")
            new_name = actor_data.get("new_name")
            actor = LINK_DATA.find_sequence_actor(link_id)
            if actor:
                if new_link_id:
                    actor.update_link_id(new_link_id)
                if new_name:
                    actor.update_name(new_name)
                actor.set_id_tree(actor_data.get("bones"),
                                  actor_data.get("ids"),
                                  actor_data.get("id_tree"))

        if request_type == "POSE":
            self.send_pose()
        elif request_type == "SEQUENCE":
            self.send_sequence()
        return

    def send_pose(self):
        global LINK_DATA

        # get actors
        if not LINK_DATA.sequence_actors:
            LINK_DATA.sequence_actors = self.get_selected_actors()
        actors = LINK_DATA.sequence_actors

        if actors:
            mode_selection = utils.store_mode_selection_state()
            update_link_status(f"Sending Current Pose Set")
            self.send_notify(f"Pose Set")
            # send pose info
            pose_data = self.encode_pose_data(actors)
            self.send(OpCodes.POSE, pose_data)
            # send template data first
            template_data = self.encode_actor_templates(actors)
            self.send(OpCodes.TEMPLATE, template_data)
            # store the actors
            LINK_DATA.sequence_actors = actors
            LINK_DATA.sequence_type = "POSE"
            # force recalculate all transforms
            bpy.context.view_layer.update()
            # send pose data
            pose_frame_data = self.encode_pose_frame_data(actors)
            self.send(OpCodes.POSE_FRAME, pose_frame_data)
            # clear the actors
            self.restore_actor_rigs(LINK_DATA.sequence_actors)
            LINK_DATA.sequence_actors = None
            LINK_DATA.sequence_type = None
            # restore
            utils.restore_mode_selection_state(mode_selection)

    def send_animation(self):
        return

    def abort_sequence(self):
        global LINK_DATA
        if self.is_sequence:
            # as the next frame was never sent, go back 1 frame
            LINK_DATA.sequence_current_frame = prev_frame(LINK_DATA.sequence_current_frame)
            update_link_status(f"Sequence Aborted: {LINK_DATA.sequence_current_frame}")
            self.stop_sequence()
            self.send_sequence_end(aborted=True)
            return True
        return False

    def send_sequence(self):
        global LINK_DATA

        # get actors
        if not LINK_DATA.sequence_actors:
            LINK_DATA.sequence_actors = self.get_selected_actors()
        actors = LINK_DATA.sequence_actors

        if actors:
            update_link_status(f"Sending Animation Sequence")
            self.send_notify(f"Animation Sequence")
            # reset animation to start
            bpy.context.scene.frame_current = bpy.context.scene.frame_start
            LINK_DATA.sequence_current_frame = bpy.context.scene.frame_current
            # send animation meta data
            sequence_data = self.encode_sequence_data(actors)
            self.send(OpCodes.SEQUENCE, sequence_data)
            # send template data first
            template_data = self.encode_actor_templates(actors)
            self.send(OpCodes.TEMPLATE, template_data)
            # store the actors
            LINK_DATA.sequence_actors = actors
            LINK_DATA.sequence_type = "SEQUENCE"
            # start the sending sequence
            self.start_sequence(self.send_sequence_frame)

    def send_sequence_frame(self):
        global LINK_DATA

        # set/fetch the current frame in the sequence
        current_frame = ensure_current_frame(LINK_DATA.sequence_current_frame)
        update_link_status(f"Sequence Frame: {current_frame}")
        # force recalculate all transforms
        bpy.context.view_layer.update()
        # send current sequence frame pose
        pose_data = self.encode_pose_frame_data(LINK_DATA.sequence_actors)
        self.send(OpCodes.SEQUENCE_FRAME, pose_data)
        # check for end
        if current_frame >= bpy.context.scene.frame_end:
            self.stop_sequence()
            self.send_sequence_end()
            return
        # advance to next frame now
        LINK_DATA.sequence_current_frame = next_frame(current_frame)


    def send_sequence_end(self, aborted=False):
        sequence_data = self.encode_sequence_data(LINK_DATA.sequence_actors, aborted=aborted)
        self.send(OpCodes.SEQUENCE_END, sequence_data)
        # clear the actors
        self.restore_actor_rigs(LINK_DATA.sequence_actors)
        LINK_DATA.sequence_actors = None
        LINK_DATA.sequence_type = None

    def send_sequence_ack(self, frame):
        global LINK_DATA
        # encode sequence ack
        data = encode_from_json({
            "frame": BFA(frame),
            "rate": self.loop_rate,
        })
        # send sequence ack
        self.send(OpCodes.SEQUENCE_ACK, data)

    def decode_pose_frame_header(self, pose_data):
        count, frame = struct.unpack_from("!II", pose_data)
        frame = RLFA(frame)
        LINK_DATA.sequence_current_frame = frame
        return frame

    def decode_pose_frame_data(self, pose_data):
        global LINK_DATA
        prefs = vars.prefs()

        offset = 0
        count, frame = struct.unpack_from("!II", pose_data, offset)
        frame = RLFA(frame)
        if LINK_DATA.set_keyframes:
            ensure_current_frame(frame)
        LINK_DATA.sequence_current_frame = frame
        offset = 8
        actors = []
        for i in range(0, count):
            offset, name = unpack_string(pose_data, offset)
            offset, character_type = unpack_string(pose_data, offset)
            offset, link_id = unpack_string(pose_data, offset)
            actor = LINK_DATA.find_sequence_actor(link_id)
            actor_ready = False
            if actor:
                objects, none_objects = actor.get_sequence_objects()
                rig: bpy.types.Object = actor.get_armature()
                actor_ready = actor.ready(require_cache=LINK_DATA.set_keyframes)
                if actor_ready:
                    actors.append(actor)
                else:
                    utils.log_error(f"Actor not ready: {name}/ {link_id}")
                is_prop = actor.get_type() == "PROP"
            else:
                utils.log_error(f"Could not find actor: {name}/ {link_id}")
                objects = []
                rig = None
                is_prop = False

            # unpack rig transform
            tx,ty,tz,rx,ry,rz,rw,sx,sy,sz = struct.unpack_from("!ffffffffff", pose_data, offset)
            loc = Vector((tx, ty, tz)) * 0.01
            rot = Quaternion((rw, rx, ry, rz))
            sca = Vector((sx, sy, sz))
            offset += 40
            if rig:
                rig.location = Vector((0, 0, 0))
                rot_mode = rig.rotation_mode
                utils.set_transform_rotation(rig, Quaternion((1, 0, 0, 0)))
                if actor.get_chr_cache().rigified:
                    rig.scale = Vector((1, 1, 1))
                else:
                    rig.scale = Vector((0.01, 0.01, 0.01))
                rig.rotation_mode = rot_mode

            if character_type == "PROP" or character_type == "AVATAR":

                datalink_rig = make_datalink_import_rig(actor, objects) if actor_ready else None

                # unpack bone transforms
                num_bones = struct.unpack_from("!I", pose_data, offset)[0]
                offset += 4

                # unpack the binary transform data directly into the datalink rig pose bones
                for i in range(0, num_bones):
                    tx,ty,tz,rx,ry,rz,rw,sx,sy,sz = struct.unpack_from("!ffffffffff", pose_data, offset)
                    offset += 40
                    if actor and datalink_rig:
                        id = actor.ids[i]
                        if id in actor.id_map:
                            id_def = actor.id_map[id]
                            if id_def["mesh"]:
                                obj = actor.skin_meshes[id][0]
                                actor.skin_meshes[id][1] = Vector((tx, ty, tz)) * 0.01
                                actor.skin_meshes[id][2] = Quaternion((rw, rx, ry, rz))
                                actor.skin_meshes[id][3] = Vector((utils.sign(sx), utils.sign(sy), utils.sign(sz))) * rig.scale
                            else:
                                bone_name = id_def["name"]
                                pose_bone: bpy.types.PoseBone = datalink_rig.pose.bones[bone_name]
                                loc = Vector((tx, ty, tz)) * 0.01
                                rot = Quaternion((rw, rx, ry, rz))
                                sca = Vector((utils.sign(sx), utils.sign(sy), utils.sign(sz))) * rig.scale
                                pose_bone.location = loc
                                utils.set_transform_rotation(pose_bone, rot)
                                pose_bone.scale = sca

                # unpack the expression shape keys into the mesh objects
                num_weights = struct.unpack_from("!I", pose_data, offset)[0]
                offset += 4
                expression_weights = [0] * num_weights
                for i in range(0, num_weights):
                    weight = struct.unpack_from("!f", pose_data, offset)[0]
                    offset += 4
                    if actor and objects and (prefs.datalink_preview_shape_keys or not LINK_DATA.set_keyframes):
                        expression_name = actor.expressions[i]
                        set_actor_expression_weight(objects, expression_name, weight)
                    expression_weights[i] = weight

                # unpack the viseme shape keys into the mesh objects
                num_weights = struct.unpack_from("!I", pose_data, offset)[0]
                offset += 4
                viseme_weights = [0] * num_weights
                for i in range(0, num_weights):
                    weight = struct.unpack_from("!f", pose_data, offset)[0]
                    offset += 4
                    if actor and objects and (prefs.datalink_preview_shape_keys or not LINK_DATA.set_keyframes):
                        viseme_name = actor.visemes[i]
                        set_actor_viseme_weight(objects, viseme_name, weight)
                    viseme_weights[i] = weight

                # TODO: morph weights
                morph_weights = []

                # store shape keys in the cache
                if LINK_DATA.set_keyframes and actor_ready:
                    store_shape_key_cache_keyframes(actor, frame, expression_weights, viseme_weights, morph_weights)

            elif character_type == "LIGHT":
                active,r,g,b,m,rng,angle,falloff,attenuation,darkness = struct.unpack_from("!?fffffffff", pose_data, offset)
                color = Color((r,g,b))
                if actor:
                    rlx.apply_light_pose(actor.object, loc, rot, sca, color, active, m, rng, angle, falloff, attenuation, darkness)
                offset += 37

            elif character_type == "CAMERA":
                lens,enable,focus,rng,fb,nb,ft,nt,mbd = struct.unpack_from("!f?fffffff", pose_data, offset)
                if actor:
                    rlx.apply_camera_pose(actor.object, loc, rot, sca, lens, enable, focus, rng, fb, nb, ft, nt, mbd)
                offset += 33

        return actors

    def reposition_prop_meshes(self, actors):
        actor: LinkActor
        for actor in actors:
            if actor.get_type() == "PROP":
                for mesh_name in actor.skin_meshes:
                    obj: bpy.types.Object
                    obj, loc, rot, sca = actor.skin_meshes[mesh_name]
                    rig = obj.parent
                    # do not adjust mesh transforms on skinned props
                    mod = modifiers.get_armature_modifier(obj)
                    if mod: continue
                    obj.matrix_world = utils.make_transform_matrix(loc, rot, sca)

    def decode_lighting_data(self, data):
        props = vars.props()
        prefs = vars.prefs()

        lights_data = decode_to_json(data)

        utils.log_info(f"Light Decoded, Use Lights: {lights_data['use_lights']}")

        ambient_color = utils.array_to_color(lights_data["ambient_color"])
        ambient_strength = 0.125 + ambient_color.v

        utils.object_mode()

        use_lights = lights_data.get("use_lights", True)

        if use_lights:
            container = rlx.add_light_container()
            # create or modify existing lights
            for light_data in lights_data["lights"]:
                light = rlx.find_link_id(light_data["link_id"])
                light = rlx.decode_rlx_light(light_data, light, container)
            # clean up lights not found in scene
            for obj in bpy.data.objects:
                if obj.type == "LIGHT":
                    obj_link_id = utils.get_rl_link_id(obj)
                    if obj_link_id and obj_link_id not in lights_data["scene_lights"]:
                        utils.delete_light_object(obj)
        #
        bpy.context.scene.eevee.use_taa_reprojection = True
        if utils.B420():
            bpy.context.scene.eevee.use_shadows = True
            bpy.context.scene.eevee.use_volumetric_shadows = True
            bpy.context.scene.eevee.use_raytracing = True
            bpy.context.scene.eevee.ray_tracing_options.use_denoise = True
            bpy.context.scene.eevee.use_shadow_jitter_viewport = True
            bpy.context.scene.eevee.use_bokeh_jittered = True
            bpy.context.scene.world.use_sun_shadow = True
            bpy.context.scene.world.use_sun_shadow_jitter = True
        else:
            bpy.context.scene.eevee.use_gtao = True
            bpy.context.scene.eevee.gtao_distance = 0.25
            bpy.context.scene.eevee.gtao_factor = 0.5
            bpy.context.scene.eevee.use_bloom = True
            bpy.context.scene.eevee.bloom_threshold = 0.8
            bpy.context.scene.eevee.bloom_knee = 0.5
            bpy.context.scene.eevee.bloom_radius = 2.0
            bpy.context.scene.eevee.bloom_intensity = 0.5
            bpy.context.scene.eevee.use_ssr = True
            bpy.context.scene.eevee.use_ssr_refraction = True
        bpy.context.scene.eevee.bokeh_max_size = 32
        view_transform = prefs.lighting_use_look if utils.B400() else "Filmic"
        colorspace.set_view_settings(view_transform, "Medium High Contrast", 0, 0.75)
        if bpy.context.scene.cycles.transparent_max_bounces < 100:
            bpy.context.scene.cycles.transparent_max_bounces = 100
        view_space = utils.get_view_3d_space()
        shading = utils.get_view_3d_shading()
        if shading:
            if shading.type != 'MATERIAL' and shading.type != "RENDERED":
                shading.type = 'MATERIAL'
            shading.use_scene_lights = True
            shading.use_scene_lights_render = True
            shading.use_scene_world = False
            shading.use_scene_world_render = True
            shading.studio_light = 'studio.exr'
            shading.studiolight_rotate_z = -25 * 0.01745329
            shading.studiolight_intensity = ambient_strength
            shading.studiolight_background_alpha = 0.0
            shading.studiolight_background_blur = 0.5
        if view_space and self.is_cc():
            # only hide the lights if it's from Character Creator
            view_space.overlay.show_extras = False
        if bpy.context.scene.view_settings.view_transform == "AgX":
            c = props.light_filter
            props.light_filter = (0.875, 1, 1, 1)
            bpy.ops.cc3.scene(param="FILTER_LIGHTS")
            props.light_filter = c

        use_ibl = lights_data.get("use_ibl", False)
        if use_ibl:
            ibl_path = lights_data.get("ibl_path", "")
            ibl_remote_id = lights_data.get("ibl_remote_id")
            ibl_path = self.get_remote_file(ibl_remote_id, ibl_path)
            ibl_strength = lights_data.get("ibl_strength", 0.5)
            ibl_location = utils.array_to_vector(lights_data.get("ibl_location", [0,0,0])) / 100
            ibl_rotation = utils.array_to_vector(lights_data.get("ibl_rotation", [0,0,0]))
            ibl_scale = lights_data.get("ibl_scale", 1.0)
            if ibl_path:
                world.world_setup(None, ibl_path, ambient_color, ibl_location, ibl_rotation, ibl_scale, ibl_strength)
        else:
            world.world_setup(None, "", ambient_color, Vector((0,0,0)), Vector((0,0,0)), 1.0, ambient_strength)


    def receive_lighting_sync(self, data):
        props = vars.props()
        update_link_status(f"Light Data Receveived")
        state = utils.store_mode_selection_state()
        props.lighting_brightness = 1.0
        self.decode_lighting_data(data)
        utils.restore_mode_selection_state(state)


    # Camera
    #

    def get_view_camera_data(self):
        view_space: bpy.types.Space
        r3d: bpy.types.RegionView3D
        view_space, r3d = utils.get_region_3d()
        t = r3d.view_location
        r = r3d.view_rotation
        d = r3d.view_distance
        dir = Vector((0,0,-1))
        dir.rotate(r)
        loc: Vector = t - (dir * d)
        lens = view_space.lens
        data = {
            "link_id": "0",
            "name": "Viewport Camera",
            "loc": [loc.x, loc.y, loc.z],
            "rot": [r.x, r.y, r.z, r.w],
            "sca": [1, 1, 1],
            "focal_length": lens,
        }
        return data

    def get_view_camera_pivot(self):
        view_space, r3d = utils.get_region_3d()
        t = r3d.view_location
        return t

    def send_camera_sync(self):
        update_link_status(f"Synchronizing View Camera")
        self.send_notify(f"Sync View Camera")
        camera_data = self.get_view_camera_data()
        pivot = self.get_view_camera_pivot()
        data = {
            "view_camera": camera_data,
            "pivot": [pivot.x, pivot.y, pivot.z],
        }
        self.send(OpCodes.CAMERA_SYNC, encode_from_json(data))

    def decode_camera_sync_data(self, data):
        data = decode_to_json(data)
        camera_data = data["view_camera"]
        pivot = utils.array_to_vector(data["pivot"]) / 100
        view_space, r3d = utils.get_region_3d()
        loc = utils.array_to_vector(camera_data["loc"]) / 100
        rot = utils.array_to_quaternion(camera_data["rot"])
        to_pivot = pivot - loc
        dir = Vector((0,0,-1))
        dir.rotate(rot)
        dist = to_pivot.dot(dir)
        if dist <= 0:
            dist = 1.0
        r3d.view_location = loc + dir * dist
        r3d.view_rotation = rot
        r3d.view_distance = dist
        view_space.lens = camera_data["focal_length"] * 1.625

    def receive_camera_sync(self, data):
        update_link_status(f"Camera Data Receveived")
        self.decode_camera_sync_data(data)

    def send_frame_sync(self):
        update_link_status(f"Sending Frame Sync")
        fps = bpy.context.scene.render.fps
        start_frame = BFA(bpy.context.scene.frame_start)
        end_frame = BFA(bpy.context.scene.frame_end)
        current_frame = BFA(bpy.context.scene.frame_current)
        start_time = start_frame / fps
        end_time = end_frame / fps
        current_time = current_frame / fps
        frame_data = {
            "fps": fps,
            "start_time": start_time,
            "end_time": end_time,
            "current_time": current_time,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "current_frame": current_frame,
        }
        self.send(OpCodes.FRAME_SYNC, encode_from_json(frame_data))

    def receive_frame_sync(self, data):
        update_link_status(f"Frame Sync Receveived")
        frame_data = decode_to_json(data)
        start_frame = frame_data["start_frame"]
        end_frame = frame_data["end_frame"]
        current_frame = frame_data["current_frame"]
        bpy.context.scene.frame_start = RLFA(start_frame)
        bpy.context.scene.frame_end = RLFA(end_frame)
        bpy.context.scene.frame_current = RLFA(current_frame)


    # Character Pose
    #

    def receive_actor_templates(self, data):
        props = vars.props()
        global LINK_DATA

        state = utils.store_mode_selection_state()

        props.validate_and_clean_up()

        # decode character templates
        template_json = decode_to_json(data)
        count = template_json["count"]
        utils.log_info(f"Receive Character Template: {count} actors")

        # fetch actors and set templates
        for actor_data in template_json["actors"]:
            name = actor_data["name"]
            character_type = actor_data["type"]
            link_id = actor_data["link_id"]
            actor = LINK_DATA.find_sequence_actor(link_id)
            if actor:
                if actor.get_type() == "AVATAR" or actor.get_type() == "PROP":
                    actor.set_template(actor_data)
                utils.log_info(f"Preparing Actor: {actor.name} ({actor.get_link_id()})")
                prep_pose_actor(actor, LINK_DATA.sequence_start_frame, LINK_DATA.sequence_end_frame)
            else:
                utils.log_error(f"Unable to find actor: {name} ({link_id})")

        update_link_status(f"Character Templates Received")
        utils.restore_mode_selection_state(state)

    def select_actor_rigs(self, actors, start_frame=0, end_frame=0):
        rigs = []
        objects = []
        actor: LinkActor
        all_selected = True
        # determine what needs to be selected
        for actor in actors:
            rig = actor.get_armature()
            if rig:
                rigs.append(rig)
                if rig not in bpy.context.selected_objects:
                    all_selected = False
            elif actor.object:
                objects.append(actor.object)
                if actor.object not in bpy.context.selected_objects:
                    all_selected = False
        all_objects = rigs.copy()
        all_objects.extend(objects)
        # make sure only actors are selected
        for obj in bpy.context.selected_objects:
            if obj not in all_objects:
                all_selected = False
        # if there are armatures make sure we are in pose mode
        if rigs and utils.get_mode() != "POSE":
            all_selected = False
        if not all_selected:
            utils.object_mode()
            utils.clear_selected_objects()
            utils.try_select_objects(all_objects, True)
            if rigs:
                utils.set_active_object(rigs[0])
                utils.set_mode("POSE")
        return rigs, objects

    def receive_pose(self, data):
        props = vars.props()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode pose data
        json_data = decode_to_json(data)
        start_frame = RLFA(json_data["start_frame"])
        end_frame = RLFA(json_data["end_frame"])
        frame = RLFA(json_data["frame"])
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        set_keyframes = json_data.get("set_keyframes", True)
        LINK_DATA.sequence_start_frame = frame
        LINK_DATA.sequence_end_frame = frame
        LINK_DATA.sequence_current_frame = frame
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, set_keyframes)
        utils.log_info(f"Receive Pose: {frame}")

        # fetch actors
        actors_data = json_data["actors"]
        actors = []
        for actor_data in actors_data:
            name = actor_data["name"]
            character_type = actor_data["type"]
            link_id = actor_data["link_id"]
            actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
            if actor:
                actors.append(actor)

        # set pose frame
        update_link_status(f"Receiving Pose Frame: {frame}")
        LINK_DATA.sequence_actors = actors
        LINK_DATA.sequence_type = "POSE"
        bpy.ops.screen.animation_cancel()
        if LINK_DATA.set_keyframes:
            set_frame_range(start_frame, end_frame)
            set_frame(frame)
        else:
            bpy.context.view_layer.update()

    def receive_pose_frame(self, data):
        global LINK_DATA

        state = utils.store_mode_selection_state()

        # decode and cache pose
        frame = self.decode_pose_frame_header(data)
        utils.log_info(f"Receive Pose Frame: {frame}")
        actors = self.decode_pose_frame_data(data)

        # force recalculate all transforms
        bpy.context.view_layer.update()

        self.reposition_prop_meshes(actors)

        # store frame data
        update_link_status(f"Pose Frame: {frame}")
        self.select_actor_rigs(actors)

        actor: LinkActor
        if LINK_DATA.set_keyframes:
            for actor in actors:
                if actor.ready(require_cache=LINK_DATA.set_keyframes):
                    if actor.get_type() == "PROP" or actor.get_type() == "AVATAR":
                        store_bone_cache_keyframes(actor, frame)
                    elif actor.get_type() == "LIGHT":
                        store_light_cache_keyframes(actor, frame)
                    elif actor.get_type() == "CAMERA":
                        store_camera_cache_keyframes(actor, frame)

        # write pose action
        for actor in actors:
            if actor.ready(require_cache=LINK_DATA.set_keyframes):
                if LINK_DATA.set_keyframes:
                    write_sequence_actions(actor, 1)
                if actor.get_type() == "PROP" or actor.get_type() == "AVATAR":
                    remove_datalink_import_rig(actor, apply_contraints=not LINK_DATA.set_keyframes)

            if actor.get_type() == "PROP":
                rigutils.update_prop_rig(actor.get_armature())
            elif actor.get_type() == "AVATAR":
                rigutils.update_avatar_rig(actor.get_armature())

        # finish
        LINK_DATA.sequence_actors = None
        LINK_DATA.sequence_type = None
        if LINK_DATA.set_keyframes:
            bpy.context.scene.frame_current = frame
        utils.restore_mode_selection_state(state, include_frames=False)

        # doesn't work with existing actions, the pose is reset back to action after execution.
        #for actor in actors:
        #    rig: bpy.types.Object = actor.get_armature()
        #    bone: bpy.types.PoseBone = rig.pose.bones["CC_Base_R_Upperarm"]
        #    bone.rotation_quaternion = (1,0,0,0)


    def receive_sequence(self, data):
        props = vars.props()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode sequence data
        json_data = decode_to_json(data)
        start_frame = RLFA(json_data["start_frame"])
        end_frame = RLFA(json_data["end_frame"])
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        set_keyframes = json_data.get("set_keyframes", True)
        LINK_DATA.sequence_start_frame = start_frame
        LINK_DATA.sequence_end_frame = end_frame
        LINK_DATA.sequence_current_frame = start_frame
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, set_keyframes)
        num_frames = end_frame - start_frame + 1
        utils.log_info(f"Receive Sequence: {start_frame} to {end_frame}, {num_frames} frames")

        # fetch sequence actors
        actors_data = json_data["actors"]
        actors = []
        for actor_data in actors_data:
            name = actor_data["name"]
            character_type = actor_data["type"]
            link_id = actor_data["link_id"]
            actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
            if actor:
                actors.append(actor)
        LINK_DATA.sequence_actors = actors
        LINK_DATA.sequence_type = "SEQUENCE"

        if not actors:
            self.send_invalid("No valid sequence Actors!")

        # update scene range
        update_link_status(f"Receiving Live Sequence: {num_frames} frames")
        bpy.ops.screen.animation_cancel()
        set_frame_range(LINK_DATA.sequence_start_frame, LINK_DATA.sequence_end_frame)
        set_frame(LINK_DATA.sequence_start_frame)

        # start the sequence
        self.start_sequence()

    def receive_sequence_frame(self, data):
        global LINK_DATA

        # decode and cache pose
        frame = self.decode_pose_frame_header(data)
        utils.log_detail(f"Receive Sequence Frame: {frame}")
        actors = self.decode_pose_frame_data(data)

        # force recalculate all transforms
        bpy.context.view_layer.update()

        self.reposition_prop_meshes(actors)

        # store frame data
        update_link_status(f"Sequence Frame: {LINK_DATA.sequence_current_frame}")
        self.select_actor_rigs(actors)

        actor: LinkActor
        for actor in actors:
            if actor.ready(require_cache=LINK_DATA.set_keyframes):
                if LINK_DATA.set_keyframes:
                    if actor.get_type() == "PROP" or actor.get_type() == "AVATAR":
                        store_bone_cache_keyframes(actor, frame)
                    elif actor.get_type() == "LIGHT":
                        store_light_cache_keyframes(actor, frame)
                    elif actor.get_type() == "CAMERA":
                        store_camera_cache_keyframes(actor, frame)

        # send sequence frame ack
        self.send_sequence_ack(frame)

    def receive_sequence_end(self, data):
        global LINK_DATA

        # decode sequence end
        json_data = decode_to_json(data)
        actors_data = json_data["actors"]
        end_frame = RLFA(json_data["frame"])
        aborted = json_data.get("aborted", False)
        LINK_DATA.sequence_end_frame = end_frame
        utils.log_info("Receive Sequence End")

        # fetch actors
        actors = []
        actor: LinkActor
        for actor_data in actors_data:
            name = actor_data["name"]
            character_type = actor_data["type"]
            link_id = actor_data["link_id"]
            actor = LINK_DATA.find_sequence_actor(link_id)
            if actor:
                actors.append(actor)
        num_frames = LINK_DATA.sequence_end_frame - LINK_DATA.sequence_start_frame + 1
        if not aborted:
            utils.log_info(f"sequence complete: {LINK_DATA.sequence_start_frame} to {LINK_DATA.sequence_end_frame} = {num_frames}")
            update_link_status(f"Live Sequence Complete: {num_frames} frames")
        else:
            update_link_status(f"Live Sequence Aborted!")

        # write actions
        for actor in actors:
            if LINK_DATA.set_keyframes:
                write_sequence_actions(actor, num_frames)
            if actor.get_type() == "PROP" or actor.get_type() == "AVATAR":
                remove_datalink_import_rig(actor, apply_contraints=not LINK_DATA.set_keyframes)
            if actor.get_type() == "PROP":
                rigutils.update_prop_rig(actor.get_armature())
            elif actor.get_type() == "AVATAR":
                rigutils.update_avatar_rig(actor.get_armature())

        # stop sequence
        self.stop_sequence()
        LINK_DATA.sequence_actors = None
        LINK_DATA.sequence_type = None
        bpy.context.scene.frame_current = LINK_DATA.sequence_start_frame

        # play the recorded sequence
        if not aborted and LINK_DATA.set_keyframes:
            bpy.ops.screen.animation_play()

    def receive_sequence_ack(self, data):
        prefs = vars.prefs()
        global LINK_DATA

        json_data = decode_to_json(data)
        ack_frame = RLFA(json_data["frame"])
        server_rate = json_data["rate"]
        delta_frames = LINK_DATA.sequence_current_frame - ack_frame
        if prefs.datalink_match_client_rate:
            if LINK_DATA.ack_time == 0.0:
                LINK_DATA.ack_time = time.time()
                LINK_DATA.ack_rate = 120
                count = 5
            else:
                t = time.time()
                delta_time = max(t - LINK_DATA.ack_time, 1/120)
                LINK_DATA.ack_time = t
                ack_rate = (1.0 / delta_time)
                LINK_DATA.ack_rate = utils.lerp(LINK_DATA.ack_rate, ack_rate, 0.5)

                if delta_frames >= 20:
                    count = 0
                elif delta_frames >= 10:
                    count = 1
                elif delta_frames >= 5:
                    count = 2
                else:
                    count = 4

            self.update_sequence(count, delta_frames)
        else:
            self.update_sequence(5, delta_frames)

    def get_remote_file(self, remote_id, source_path, file_override=None):
        if remote_id:
            remote_files_folder = get_unpacked_tar_file_folder(remote_id)
            if file_override:
                source_file = file_override
            else:
                source_folder, source_file = os.path.split(source_path)
            source_path = os.path.join(remote_files_folder, source_file)
        else:
            if file_override:
                source_folder = os.path.split(source_path)[0]
                source_path = os.path.join(source_folder, file_override)
        return source_path

    def receive_actor_import(self, data):
        props = vars.props()
        prefs = vars.prefs()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode character import data
        json_data = decode_to_json(data)
        fbx_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        fbx_path = self.get_remote_file(remote_id, fbx_path)
        name = json_data.get("name")
        character_type = json_data.get("type")
        link_id = json_data.get("link_id")
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        save_after_import = json_data.get("save_after_import", False)
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, True)

        utils.log_info(f"Receive Character Import: {name} / {link_id} / {fbx_path}")

        if not os.path.exists(fbx_path):
            update_link_status(f"Invalid Import Path!")
            return

        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
        if actor:
            update_link_status(f"Character: {name} exists!")
            utils.log_info(f"Actor {name} ({link_id}) already exists!")
            if prefs.datalink_confirm_replace:
                bpy.ops.ccic.link_confirm_dialog("INVOKE_DEFAULT",
                                                 message=f"Character {name} already exists in the scene. Do you want to replace the character?",
                                                 mode="REPLACE",
                                                 name=name,
                                                 filepath=fbx_path,
                                                 link_id=link_id,
                                                 character_type=character_type,
                                                 prefs="datalink_confirm_replace")
            else:
                self.do_update_replace(name, link_id, fbx_path, character_type, True,
                                       objects_to_replace_names=None,
                                       replace_actions=True)
        else:
            update_link_status(f"Receving Character Import: {name}")
            self.do_file_import(fbx_path, link_id, save_after_import)


    def do_file_import(self, file_path, link_id, save_after_import):
        try:
            bpy.ops.cc3.importer(param="IMPORT", filepath=file_path, link_id=link_id,
                                 zoom=False, no_rigify=True,
                                 motion_prefix=LINK_DATA.motion_prefix,
                                 use_fake_user=LINK_DATA.use_fake_user)
        except Exception as e:
            utils.log_error(f"Error importing {file_path}", e)
            return
        actor = LinkActor.find_actor(link_id)
        # props have big ugly bones, so show them as wires
        if actor and actor.get_type() == "PROP":
            arm = actor.get_armature()
            #rigutils.custom_prop_rig(arm)
            #rigutils.de_pivot(actor.get_chr_cache())
        elif actor and actor.get_type() == "AVATAR":
            if actor.get_chr_cache().is_non_standard():
                arm = actor.get_armature()
                #rigutils.custom_avatar_rig(arm)
        if actor:
            update_link_status(f"Character Imported: {actor.name}")
        if save_after_import:
            self.receive_save()
        # force frame update (for actions to apply)
        bpy.context.scene.frame_current = bpy.context.scene.frame_current

    def receive_camera_fbx_import(self, data):
        props = vars.props()
        prefs = vars.prefs()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode character import data
        json_data = decode_to_json(data)
        fbx_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        fbx_path = self.get_remote_file(remote_id, fbx_path)
        name = json_data.get("name")
        character_type = json_data.get("type")
        link_id = json_data.get("link_id")
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        save_after_import = json_data.get("save_after_import", False)
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, True)

        utils.log_info(f"Receive Camera Import: {name} / {link_id} / {fbx_path}")

        if not os.path.exists(fbx_path):
            update_link_status(f"Invalid Import Path!")
            utils.log_error(f"Invalid Import Path: {fbx_path}")
            return

        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
        if actor:
            update_link_status(f"Camera: {name} exists!")
            utils.log_info(f"Camera {name} ({link_id}) already exists!")
            if prefs.datalink_confirm_replace:
                bpy.ops.ccic.link_confirm_dialog("INVOKE_DEFAULT",
                                                 message=f"Camera {name} already exists in the scene. Do you want to replace the character?",
                                                 mode="CAMERA",
                                                 name=name,
                                                 filepath=fbx_path,
                                                 link_id=link_id,
                                                 character_type=character_type,
                                                 prefs="datalink_confirm_replace")
            else:
                self.do_motion_import(link_id, fbx_path, character_type)

        else:
            update_link_status(f"Receving Camera Import: {name}")
            self.do_file_import(fbx_path, link_id, save_after_import)

    def receive_rlx_import(self, data):
        props = vars.props()
        prefs = vars.prefs()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode character import data
        json_data = decode_to_json(data)
        base_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        names = json_data.get("names")
        character_types = json_data.get("types")
        link_ids = json_data.get("link_ids")
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        save_after_import = json_data.get("save_after_import", False)
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, True)

        for i, name in enumerate(names):
            link_id = link_ids[i]
            character_type = character_types[i]
            file = name + ".rlx"
            rlx_path = self.get_remote_file(remote_id, base_path, file_override=file)

            utils.log_info(f"Receive Light / Camera Import: {name} / {link_id} / {rlx_path}")

            if not os.path.exists(rlx_path):
                update_link_status(f"Invalid Import Path!")
                utils.log_error(f"Invalid Import Path: {rlx_path}")
                continue

            self.do_file_import(rlx_path, link_id, save_after_import)

    def receive_motion_import(self, data):
        props = vars.props()
        prefs = vars.prefs()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode character import data
        json_data = decode_to_json(data)
        fbx_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        fbx_path = self.get_remote_file(remote_id, fbx_path)
        name = json_data["name"]
        character_type = json_data["type"]
        link_id = json_data["link_id"]
        start_frame = RLFA(json_data["start_frame"])
        end_frame = RLFA(json_data["end_frame"])
        frame = RLFA(json_data["frame"])
        motion_prefix = json_data.get("motion_prefix", "")
        use_fake_user = json_data.get("use_fake_user", False)
        LINK_DATA.sequence_start_frame = start_frame
        LINK_DATA.sequence_end_frame = end_frame
        LINK_DATA.sequence_current_frame = frame
        LINK_DATA.set_action_settings(motion_prefix, use_fake_user, True)
        num_frames = end_frame - start_frame + 1
        utils.log_info(f"Receive Motion Import: {name} / {link_id} / {fbx_path}")
        utils.log_info(f"Motion Range: {start_frame} to {end_frame}, {num_frames} frames")

        # update scene range
        bpy.ops.screen.animation_cancel()
        set_frame_range(LINK_DATA.sequence_start_frame, LINK_DATA.sequence_end_frame)
        set_frame(LINK_DATA.sequence_start_frame)
        bpy.context.scene.frame_current = frame

        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
        if not actor:
            chr_cache, obj, mat, obj_cache, mat_cache = utils.get_context_character(bpy.context)
            update_link_status(f"Character: {name} not found!")
            utils.log_info(f"Actor {name} ({link_id}) not found!")
            if chr_cache and LinkActor.chr_cache_type(chr_cache) == character_type:
                link_id = chr_cache.link_id
                if link_id:
                    utils.log_info(f"Redirecting to active character: {chr_cache.character_name}")
                    if prefs.datalink_confirm_mismatch:
                        bpy.ops.ccic.link_confirm_dialog("INVOKE_DEFAULT",
                                                        message=f"Character {name} not found, do you want to apply the motion to the current character: {chr_cache.character_name}?",
                                                        mode="MOTION",
                                                        name=name,
                                                        filepath=fbx_path,
                                                        link_id=chr_cache.link_id,
                                                        character_type=character_type,
                                                        prefs="datalink_confirm_mismatch")
                    else:
                        self.do_motion_import(link_id, fbx_path, character_type)
            return

        link_id = actor.get_link_id()
        self.do_motion_import(link_id, fbx_path, character_type)

    def do_motion_import(self, link_id, fbx_path, character_type):
        actor = LinkActor.find_actor(link_id, search_type=character_type)
        update_link_status(f"Receving Motion Import: {actor.name}")

        if actor.get_type() != character_type:
            update_link_status(f"Invalid character type for motion!")
            return

        if os.path.exists(fbx_path):
            try:
                bpy.ops.cc3.anim_importer(filepath=fbx_path, remove_meshes=False,
                                          remove_materials_images=True, remove_shape_keys=False,
                                          motion_prefix=LINK_DATA.motion_prefix,
                                          use_fake_user=LINK_DATA.use_fake_user)
            except Exception as e:
                utils.log_error(f"Error importing {fbx_path}", e)
            motion_rig = utils.get_active_object()
            if motion_rig:
                self.replace_actor_motion(actor, motion_rig)
                #except:
                #    utils.log_error(f"Error importing motion {fbx_path}")
                #    return
                update_link_status(f"Motion Imported: {actor.name}")
            else:
                update_link_status(f"Motion Import Failed!: {actor.name}")

    def replace_actor_motion(self, actor: LinkActor, motion_rig):
        prefs = vars.prefs()

        if actor and motion_rig:
            motion_rig_action = utils.safe_get_action(motion_rig)
            motion_objects = utils.get_child_objects(motion_rig)
            motion_id = rigutils.get_action_motion_id(motion_rig_action)
            utils.log_info(f"Replacing Actor Motion:")
            utils.log_indent()
            utils.log_info(f"Motion rig action: {motion_rig_action.name}")
            # fetch all associated actions...
            source_actions = rigutils.find_source_actions(motion_rig_action, motion_rig)
            # fetch actor rig
            actor_rig = actor.get_armature()
            chr_cache = actor.get_chr_cache()
            actor_rig_id = rigutils.get_rig_id(actor_rig)
            rl_arm_id = utils.get_rl_object_id(actor_rig)
            motion_id = rigutils.get_unique_set_motion_id(actor_rig_id, motion_id, LINK_DATA.motion_prefix)
            # generate new action set data
            set_id, set_generation = rigutils.generate_motion_set(actor_rig, motion_id, LINK_DATA.motion_prefix)
            remove_actions = []
            if actor_rig:
                if actor.get_type() == "PROP":
                    # if it's a prop retarget the animation (or copy the rest pose):
                    #    props have no bind pose so the rest pose is the first frame of
                    #    the animation, which changes with every new animation import...
                    if prefs.datalink_retarget_prop_actions:
                        action = get_datalink_rig_action(actor_rig, motion_id)
                        rigutils.add_motion_set_data(action, set_id, set_generation, rl_arm_id=rl_arm_id)
                        update_link_status(f"Retargeting Motion...")
                        armature_action = rigutils.bake_rig_action_from_source(motion_rig, actor_rig)
                        armature_action.use_fake_user = LINK_DATA.use_fake_user
                        remove_actions.append(motion_rig_action)
                    else:
                        rigutils.add_motion_set_data(motion_rig_action, set_id, set_generation, rl_arm_id=rl_arm_id)
                        rigutils.set_armature_action_name(motion_rig_action, actor_rig_id, motion_id, LINK_DATA.motion_prefix)
                        motion_rig_action.use_fake_user = LINK_DATA.use_fake_user
                        rigutils.copy_rest_pose(motion_rig, actor_rig)
                        utils.safe_set_action(actor_rig, motion_rig_action)
                    rigutils.update_prop_rig(actor_rig)
                else: # Avatar
                    if chr_cache.rigified:
                        update_link_status(f"Retargeting Motion...")
                        armature_action = rigging.adv_bake_retarget_to_rigify(None, chr_cache, motion_rig, motion_rig_action)[0]
                        armature_action.use_fake_user = LINK_DATA.use_fake_user
                        rigutils.add_motion_set_data(armature_action, set_id, set_generation, rl_arm_id=rl_arm_id)
                        rigutils.set_armature_action_name(armature_action, actor_rig_id, motion_id, LINK_DATA.motion_prefix)
                        remove_actions.append(motion_rig_action)
                    else:
                        rigutils.add_motion_set_data(motion_rig_action, set_id, set_generation, rl_arm_id=rl_arm_id)
                        rigutils.set_armature_action_name(motion_rig_action, actor_rig_id, motion_id, LINK_DATA.motion_prefix)
                        motion_rig_action.use_fake_user = LINK_DATA.use_fake_user
                        utils.safe_set_action(actor_rig, motion_rig_action)
                    rigutils.update_avatar_rig(actor_rig)
            # assign motion object shape key actions:
            key_actions = rigutils.apply_source_key_actions(actor_rig,
                                                source_actions, copy=True,
                                                motion_id=motion_id,
                                                motion_prefix=LINK_DATA.motion_prefix,
                                                all_matching=True,
                                                set_id=set_id, set_generation=set_generation)
            for action in key_actions.values():
                action.use_fake_user = LINK_DATA.use_fake_user
            # remove unused motion key actions
            for obj_action in source_actions["keys"].values():
                if obj_action not in key_actions.values():
                    remove_actions.append(obj_action)
            # delete imported motion rig and objects
            for obj in motion_objects:
                utils.delete_mesh_object(obj)
            if motion_rig:
                utils.delete_armature_object(motion_rig)
            # remove old actions
            for old_action in remove_actions:
                if old_action:
                    utils.log_info(f"Removing unused Action: {old_action.name}")
                    bpy.data.actions.remove(old_action)
            utils.log_recess()

    def receive_actor_update(self, data):
        props = vars.props()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode character update
        json_data = decode_to_json(data)
        old_name = json_data["old_name"]
        old_link_id = json_data["old_link_id"]
        character_type = json_data["type"]
        new_name = json_data["new_name"]
        new_link_id = json_data["new_link_id"]
        utils.log_info(f"Receive Character Update: {old_name} -> {new_name} / {old_link_id} -> {new_link_id}")

        # update character data
        actor = LinkActor.find_actor(old_link_id, search_name=old_name, search_type=character_type)
        utils.log_info(f"Updating Actor: {actor.name} {actor.get_link_id()}")
        actor.update_name(new_name)
        actor.update_link_id(new_link_id)

    def receive_morph(self, data, update=False):
        props = vars.props()
        global LINK_DATA

        props.validate_and_clean_up()

        # decode receive morph
        json_data = decode_to_json(data)
        obj_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        obj_path = self.get_remote_file(remote_id, obj_path)
        name = json_data["name"]
        character_type = json_data["type"]
        link_id = json_data["link_id"]
        utils.log_info(f"Receive Character Morph: {name} / {link_id} / {obj_path}")

        # fetch actor to update morph or import new morph character
        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
        if actor:
            update = True
        else:
            update = False
        if actor:
            chr_cache = actor.get_chr_cache()
            if not chr_cache.is_import_type("OBJ"):
                update_link_status(f"Character is not for Morph editing!")
                return
        update_link_status(f"Receving Character Morph: {name}")
        if os.path.exists(obj_path):
            if update:
                self.import_morph_update(actor, obj_path)
                update_link_status(f"Morph Updated: {actor.name}")
            else:
                try:
                    bpy.ops.cc3.importer(param="IMPORT", filepath=obj_path, link_id=link_id)
                except Exception as e:
                    utils.log_error(f"Error importing {obj_path}", e)
                actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
                update_link_status(f"Morph Imported: {actor.name}")

    def import_morph_update(self, actor: LinkActor, file_path):
        utils.log_info(f"Import Morph Update: {actor.name} / {file_path}")

        old_objects = utils.get_set(bpy.data.objects)
        importer.obj_import(file_path, split_objects=False, split_groups=False, vgroups=True)
        objects = utils.get_set_new(bpy.data.objects, old_objects)
        if objects and actor and actor.get_chr_cache():
            for source in objects:
                source.scale = (0.01, 0.01, 0.01)
                dest = actor.get_chr_cache().object_cache[0].object
                geom.copy_vert_positions_by_index(source, dest)
                utils.delete_mesh_object(source)

    def receive_update_replace(self, data):
        props = vars.props()
        props.validate_and_clean_up()

        json_data = decode_to_json(data)
        fbx_path = json_data.get("path")
        remote_id = json_data.get("remote_id")
        fbx_path = self.get_remote_file(remote_id, fbx_path)
        name = json_data["name"]
        character_type = json_data["type"]
        link_id = json_data["link_id"]
        replace_all = json_data["replace"]
        objects_to_replace_names = json_data["objects"]
        utils.log_info(f"Receive Update / Replace: {name} - {objects_to_replace_names}")

        self.do_update_replace(name, link_id, fbx_path, character_type, replace_all, objects_to_replace_names)

    def do_update_replace(self, name, link_id, fbx_path, character_type, replace_all, objects_to_replace_names=None, replace_actions=False):
        props = vars.props()
        global LINK_DATA
        context_chr_cache = props.get_context_character_cache()

        process_only = ""
        if not replace_all and objects_to_replace_names:
            for n in objects_to_replace_names:
                if process_only:
                    process_only += "|"
                process_only += n

        # import character assign new link_id
        temp_link_id = utils.generate_random_id(20)
        utils.log_info(f"Importing replacement with temp link_id: {temp_link_id}")
        try:
            bpy.ops.cc3.importer(param="IMPORT", filepath=fbx_path, link_id=temp_link_id, process_only=process_only)
        except Exception as e:
            utils.log_error(f"Error importing {fbx_path}", e)

        # the actor to replace
        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type, context_chr_cache=context_chr_cache)
        rig: bpy.types.Object = actor.get_armature()
        rig_action = utils.safe_get_action(rig)
        utils.log_info(f"Character Rig: {rig.name} / {rig_action.name if rig_action else 'No Action'}")
        chr_cache = actor.get_chr_cache()
        # the replacements
        temp_actor = LinkActor.find_actor(temp_link_id, search_name=name, search_type=character_type)
        temp_rig: bpy.types.Object = temp_actor.get_armature()
        temp_rig_action = utils.safe_get_action(temp_rig)
        temp_chr_cache = temp_actor.get_chr_cache()
        utils.log_info(f"Replacement Rig: {temp_rig.name} / {temp_rig_action.name if temp_rig_action else 'No Action'}")

        # can happen if the link_id's don't match
        if chr_cache == temp_chr_cache:
            utils.log_error("Character replacement and original are the same!")
            update_link_status(f"Error! Character Mismatch")
            temp_chr_cache.invalidate()
            temp_chr_cache.delete()
            return

        if not replace_all:

            # firstly convert the rest pose of the old rig to the new rig
            # (so the new objects aren't modified by this process)
            new_rest_pose = False
            if not rigutils.is_rest_pose_same(temp_rig, rig):
                utils.log_info(f"Incoming Rest Pose {temp_rig.name} is different: applying new rest pose...")
                rigutils.copy_rest_pose(temp_rig, rig)
                new_rest_pose = True

            if rig and temp_rig:

                # find and invalidate the cache data for the objects/materials being replaced
                original_data = {}
                done = []

                # source cache objects and split meshes are treated separately here
                for obj_cache in chr_cache.object_cache:
                    obj = obj_cache.get_object()
                    if obj not in done:
                        done.append(obj)
                        if obj_cache.source_name in objects_to_replace_names:
                            if obj:
                                original_data[obj_cache.source_name] = {
                                        "name": obj.name,
                                        "object_id": obj_cache.object_id
                                    }
                                if obj.type == "MESH":
                                    for mat in obj.data.materials:
                                        if chr_cache.count_material(mat) <= 1:
                                            mat_cache = chr_cache.get_material_cache(mat)
                                            if mat_cache:
                                                mat_cache.invalidate()
                                                mat_cache.delete()
                            obj_cache.invalidate()
                            obj_cache.delete()

                to_delete = []
                for child in rig.children:
                    if child not in done and utils.object_exists_is_mesh(child):
                        done.append(child)
                        child_source_name = utils.strip_name(child.name)
                        if child_source_name in objects_to_replace_names:
                            obj_cache = chr_cache.get_object_cache(child)
                            if obj_cache:
                                original_data[child_source_name] = {
                                        "name": child.name,
                                        "object_id": obj_cache.object_id
                                    }
                                if child.type == "MESH":
                                    for mat in child.data.materials:
                                        if chr_cache.count_material(mat) <= 1:
                                            mat_cache = chr_cache.get_material_cache(mat)
                                            if mat_cache:
                                                mat_cache.invalidate()
                                                mat_cache.delete()
                                to_delete.append(child)

                utils.delete_objects(to_delete, log=True)

                # reparent the replacements to the actor rig
                new_objects = []
                for child in temp_rig.children:
                    if utils.object_exists_is_mesh(child):
                        new_objects.append(child)
                        child.parent = rig
                        mod = modifiers.get_armature_modifier(child, armature=rig)
                        temp_obj_cache = temp_chr_cache.get_object_cache(child)
                        new_obj_cache = chr_cache.add_object_cache(child, copy_from=temp_obj_cache)
                        new_obj_cache.object = child
                        # restore object names and object id's
                        if temp_obj_cache.source_name in original_data:
                            utils.force_object_name(child, original_data[temp_obj_cache.source_name]["name"])
                            new_obj_cache.object_id = original_data[temp_obj_cache.source_name]["object_id"]
                            utils.set_rl_object_id(child, new_obj_cache.object_id)
                        for mat in child.data.materials:
                            if utils.material_exists(mat):
                                temp_mat_cache = temp_chr_cache.get_material_cache(mat)
                                material_type = temp_mat_cache.material_type
                                new_mat_cache = chr_cache.add_material_cache(mat, material_type, copy_from=temp_mat_cache)
                                new_mat_cache.material = mat

                # generate a new json_local file with the updated data
                chr_json = chr_cache.get_json_data()
                chr_dir = chr_cache.get_import_dir()
                tmp_json = temp_chr_cache.get_json_data()
                tmp_dir = temp_chr_cache.get_import_dir()
                chr_meshes, chr_phys_meshes = jsonutils.get_character_meshes_json(chr_json, chr_cache.get_character_id())
                tmp_meshes, tmp_phys_meshes = jsonutils.get_character_meshes_json(tmp_json, temp_chr_cache.get_character_id())
                chr_colliders = jsonutils.get_physics_collision_shapes_json(chr_json, chr_cache.get_character_id())
                tmp_colliders = jsonutils.get_physics_collision_shapes_json(tmp_json, temp_chr_cache.get_character_id())
                if not chr_meshes:
                    utils.log_error("No mesh data in character json!")
                    return
                if not tmp_meshes:
                    utils.log_error("No mesh data in replacement character json!")
                    return
                # make physics json if none in character (copy colliders over if none)
                # ensures that chr_phys_meshes and chr_colliders exist
                if tmp_phys_meshes or tmp_colliders:
                    if tmp_colliders and not chr_colliders:
                        chr_phys_meshes, chr_colliders = jsonutils.add_physics_json(chr_json, chr_cache.get_character_id(), tmp_json, temp_chr_cache.get_character_id())
                    else:
                        chr_phys_meshes, chr_colliders = jsonutils.add_physics_json(chr_json, chr_cache.get_character_id())

                # replace the mesh json and soft physics mesh json data with the updates
                for obj_name in objects_to_replace_names:
                    obj_json = None
                    phys_obj_json = None
                    if obj_name in tmp_meshes:
                        utils.log_info(f"Replacing {obj_name} in chr meshes json.")
                        obj_json = copy.deepcopy(tmp_meshes[obj_name])
                        chr_meshes[obj_name] = obj_json
                    else:
                        utils.log_info(f"{obj_name} not found in temp meshes json.")
                    if tmp_phys_meshes and obj_name in tmp_phys_meshes:
                        utils.log_info(f"Replacing {obj_name} in chr physics meshes json.")
                        phys_obj_json = copy.deepcopy(tmp_phys_meshes[obj_name])
                        chr_phys_meshes[obj_name] = phys_obj_json
                    # remap the texture paths relative to the new json_local file (in chr_dir)
                    jsonutils.remap_mesh_json_tex_paths(obj_json, phys_obj_json, tmp_dir, chr_dir)

                # replace all the collider data if the rest pose has changed
                if new_rest_pose and chr_colliders and tmp_colliders:
                    chr_colliders.clear()
                    for bone_name in tmp_colliders:
                        chr_colliders[bone_name] = copy.deepcopy(tmp_colliders[bone_name])

                # write the changes to a .json_local
                jsonutils.write_json(chr_json, chr_cache.import_file, is_fbx_path=True, is_json_local=True)

                # remove unused images/folders from the update import files
                tmp_images = jsonutils.get_meshes_images(tmp_meshes)
                keep_images = jsonutils.get_meshes_images(tmp_meshes, filter=objects_to_replace_names)
                for img_path in tmp_images:
                    if img_path not in keep_images:
                        full_path = os.path.normpath(os.path.join(tmp_dir, img_path))
                        if os.path.exists(full_path):
                            utils.log_info(f"Deleting unused image file: {img_path}")
                            os.remove(full_path)

                if not replace_actions:
                    # remove temp chr actions (motion set)
                    if temp_rig_action:
                        rigutils.delete_motion_set(temp_rig_action)

                    # remap shapekey actions for the new objects
                    if rig_action:
                        source_actions = rigutils.find_source_actions(rig_action, rig)
                        rigutils.apply_source_key_actions(rig, source_actions, all_matching=True, filter=new_objects)

                # invalidate and clean up but don't delete the objects & materials
                # do this last as it invalidates the references
                temp_chr_cache.invalidate()
                temp_chr_cache.clean_up()
                chr_cache.clean_up()
                utils.remove_from_collection(props.import_cache, temp_chr_cache)

            # delete the temp rig
            if temp_rig:
                utils.delete_object_tree(temp_rig)

        else: # replace_all

            if rig and temp_rig:

                # copy old transform to new
                temp_rig.location = rig.location
                temp_rig.rotation_mode = rig.rotation_mode
                temp_rig.rotation_quaternion = rig.rotation_quaternion
                temp_rig.rotation_euler = rig.rotation_euler
                temp_rig.rotation_axis_angle = rig.rotation_axis_angle

                if not replace_actions:
                    # remove temp chr actions (motion set)
                    if temp_rig_action:
                        rigutils.delete_motion_set(temp_rig_action)

                    # copy/retarget actions from original rig to the replacement
                    if rig_action:
                        source_actions = rigutils.find_source_actions(rig_action, rig)
                        rigutils.apply_source_armature_action(temp_rig, source_actions)
                        rigutils.apply_source_key_actions(temp_rig, source_actions, all_matching=True)

                link_id = chr_cache.link_id
                character_name = chr_cache.character_name
                rig_name = rig.name
                rig_data_name = rig.data.name
                rl_armature_id = utils.get_rl_object_id(rig)
                temp_chr_cache.set_link_id(link_id)
                temp_chr_cache.character_name = character_name

                utils.set_rl_object_id(temp_rig, rl_armature_id)
                rig_obj_cache = temp_chr_cache.get_object_cache(temp_rig)
                if rig_obj_cache:
                    rig_obj_cache.object_id = rl_armature_id
                utils.force_object_name(temp_rig, rig_name)
                utils.force_armature_name(temp_rig.data, rig_data_name)

                # remove the original character
                # do this last as it invalidates the references
                chr_cache.invalidate()
                chr_cache.delete()
                chr_cache.clean_up()
                utils.remove_from_collection(props.import_cache, chr_cache)

    def receive_rigify_request(self, data):
        props = vars.props()
        props.validate_and_clean_up()

        # decode rigify request
        json_data = decode_to_json(data)
        name = json_data["name"]
        character_type = json_data["type"]
        link_id = json_data["link_id"]
        utils.log_info(f"Receive Rigify Request: {name} / {link_id}")

        # rigify actor armature
        actor = LinkActor.find_actor(link_id, search_name=name, search_type=character_type)
        if actor:
            chr_cache = actor.get_chr_cache()
            if chr_cache:
                if chr_cache.rigified:
                    utils.log_error(f"Character {actor.name} already rigified!")
                    return
                update_link_status(f"Rigifying: {actor.name}")
                chr_cache.select(only=True)
                cc3_rig = chr_cache.get_armature()
                bpy.ops.cc3.rigifier(param="ALL", no_face_rig=True, auto_retarget=True)
                rigutils.update_avatar_rig(chr_cache.get_armature())
                update_link_status(f"Character Rigified: {actor.name}")






LINK_SERVICE: LinkService = None


def get_link_service():
    global LINK_SERVICE
    return LINK_SERVICE


def link_state_update():
    global LINK_SERVICE
    if LINK_SERVICE:
        link_props = vars.link_props()
        link_props.link_listening = LINK_SERVICE.is_listening
        link_props.link_connected = LINK_SERVICE.is_connected
        link_props.link_connecting = LINK_SERVICE.is_connecting
        utils.update_ui()


def update_link_status(text):
    link_props = vars.link_props()
    link_props.link_status = text
    utils.update_ui()


def reconnect():
    global LINK_SERVICE
    link_props = vars.link_props()
    prefs = vars.prefs()

    if link_props.connected:
        if LINK_SERVICE and LINK_SERVICE.is_connected:
            utils.log_info("DataLink remains connected.")
        elif not LINK_SERVICE or not LINK_SERVICE.is_connected:
            utils.log_info("DataLink was connected. Attempting to reconnect...")
            bpy.ops.ccic.datalink(param="START")

    elif prefs.datalink_auto_start:
        if LINK_SERVICE and LINK_SERVICE.is_connected:
            utils.log_info("DataLink already connected.")
        elif not LINK_SERVICE or not LINK_SERVICE.is_connected:
            utils.log_info("Auto-starting datalink...")
            bpy.ops.ccic.datalink(param="START")


class CCICDataLink(bpy.types.Operator):
    """DataLink Control Operator"""
    bl_idname = "ccic.datalink"
    bl_label = "Listener"
    bl_options = {"REGISTER"}

    param: bpy.props.StringProperty(
            name = "param",
            default = "",
            options={"HIDDEN"}
        )

    def execute(self, context):
        global LINK_SERVICE

        if self.param == "GOB_START":
            self.link_start(is_go_b=True)
            return {'FINISHED'}

        if self.param == "START":
            self.link_start()
            return {'FINISHED'}

        elif self.param == "DISCONNECT":
            self.link_disconnect()
            return {'FINISHED'}

        elif self.param == "STOP":
            self.link_stop()
            return {'FINISHED'}

        if self.param in ["SEND_POSE", "SEND_ANIM", "SEND_ACTOR", "SEND_MORPH",
                          "SEND_REPLACE_MESH", "SEND_TEXTURES", "SYNC_CAMERA"]:
            if not LINK_SERVICE or not LINK_SERVICE.is_connected:
                self.link_start()
            if not LINK_SERVICE or not (LINK_SERVICE.is_connected or LINK_SERVICE.is_connecting):
                self.report({"ERROR"}, "Server not listening!")
                return {'FINISHED'}

        if LINK_SERVICE:

            if self.param == "SEND_POSE":
                LINK_SERVICE.send_pose_request()
                self.report({'INFO'}, f"Sending pose request ...")
                return {'FINISHED'}

            elif self.param == "SEND_ANIM":
                LINK_SERVICE.send_sequence_request()
                self.report({'INFO'}, f"Sending sequence request ...")
                return {'FINISHED'}

            elif self.param == "STOP_ANIM":
                LINK_SERVICE.abort_sequence()
                self.report({'INFO'}, f"Sequence stopped!")
                return {'FINISHED'}

            elif self.param == "SEND_ACTOR":
                count = LINK_SERVICE.send_actor()
                if count == 1:
                    self.report({'INFO'}, f"Actor sent ...")
                elif count > 1:
                    self.report({'INFO'}, f"{count} Actors sent ...")
                else:
                    self.report({'ERROR'}, f"No Actors sent!")
                return {'FINISHED'}

            elif self.param == "SEND_MORPH":
                if LINK_SERVICE.send_morph():
                    self.report({'INFO'}, f"Morph sent ...")
                else:
                    self.report({'ERROR'}, f"Morph not sent!")
                return {'FINISHED'}

            elif self.param == "SYNC_CAMERA":
                LINK_SERVICE.send_camera_sync()
                return {'FINISHED'}

            elif self.param == "SEND_REPLACE_MESH":
                count = LINK_SERVICE.send_replace_mesh()
                if count == 1:
                    self.report({'INFO'}, f"Replace Mesh sent ...")
                elif count > 1:
                    self.report({'INFO'}, f"{count} Replace Meshes sent ...")
                else:
                    self.report({'ERROR'}, f"No Replace Meshes sent!")
                return {'FINISHED'}

            elif self.param == "SEND_MATERIAL_UPDATE":
                count = LINK_SERVICE.send_material_update(context)
                if count == 1:
                    self.report({'INFO'}, f"Material sent ...")
                elif count > 1:
                    self.report({'INFO'}, f"{count} Materials sent ...")
                else:
                    self.report({'ERROR'}, f"No Materials sent!")
                return {'FINISHED'}

            elif self.param == "DEPIVOT":
                props = vars.props()
                chr_cache = props.get_context_character_cache(context)
                if chr_cache:
                    rigutils.de_pivot(chr_cache)
                return {'FINISHED'}

            elif self.param == "DEBUG":
                LINK_SERVICE.send(OpCodes.DEBUG)
                return {'FINISHED'}

            elif self.param == "TEST":
                test()
                return {'FINISHED'}

        if self.param == "SHOW_ACTOR_FILES":
            props = vars.props()
            chr_cache = props.get_context_character_cache(context)
            if chr_cache:
                utils.open_folder(chr_cache.get_import_dir())
            return {'FINISHED'}

        elif self.param == "SHOW_PROJECT_FILES":
            local_path = get_local_data_path()
            if local_path:
                utils.open_folder(local_path)
            return {'FINISHED'}

        return {'FINISHED'}

    def prep_local_files(self):
        data_path = get_local_data_path()
        if data_path:
            os.makedirs(data_path, exist_ok=True)
            import_path = os.path.join(data_path, "imports")
            export_path = os.path.join(data_path, "exports")
            os.makedirs(import_path, exist_ok=True)
            os.makedirs(export_path, exist_ok=True)

    def link_start(self, is_go_b=False):
        prefs = vars.prefs()
        global LINK_SERVICE

        self.prep_local_files()
        if not LINK_SERVICE:
            LINK_SERVICE = LinkService()
            LINK_SERVICE.changed.connect(link_state_update)

        if LINK_SERVICE:
            link_ip = "127.0.0.1"
            if is_go_b:
                # go_b only to local host
                prefs.datalink_target = "LOCAL"
            try:
                if prefs.datalink_target == "REMOTE":
                    link_ip = socket.gethostbyname(prefs.datalink_host)
                prefs.datalink_bad_hostname = False
            except:
                prefs.datalink_bad_hostname = True
                utils.log_error(f"Bad Remote DataLink Hostname! {prefs.datalink_host}")
                return
            LINK_SERVICE.service_start(link_ip, BLENDER_PORT)

    def link_stop(self):
        global LINK_SERVICE

        if LINK_SERVICE:
            LINK_SERVICE.service_stop()

    def link_disconnect(self):
        global LINK_SERVICE

        if LINK_SERVICE:
            LINK_SERVICE.service_disconnect()

    @classmethod
    def description(cls, context, properties):

        if properties.param == "GOB_START":
            return "Attempt to start the DataLink by connecting to the server running on CC4/iC8 to local host"

        if properties.param == "START":
            return "Attempt to start the DataLink by connecting to the server running on CC4/iC8"

        elif properties.param == "DISCONNECT":
            return "Disconnect from the DataLink server"

        elif properties.param == "STOP":
            return "Stop the DataLink on both client and server"

        elif properties.param == "SEND_POSE":
            return "Send the current pose (and frame) to CC4/iC8"

        elif properties.param == "SEND_ANIM":
            return "Send the animation on the character to CC4/iC8 as a live sequence"

        elif properties.param == "STOP_ANIM":
            return "Stop the live sequence"

        elif properties.param == "SEND_ACTOR":
            return "Send the character or prop to CC4/iC8"

        elif properties.param == "SEND_MORPH":
            return "Send the character body back to CC4 and create a morph slider for it"

        elif properties.param == "SEND_ACTOR_INVALID":
            return "This standard character has altered topology of the base body mesh and will not re-import into Character Creator"

        elif properties.param == "SEND_MORPH_INVALID":
            return "This standard character morph has altered topology of the base body mesh and will not re-import into Character Creator"

        elif properties.param == "SYNC_CAMERA":
            return "TBD"

        elif properties.param == "SEND_REPLACE_MESH":
            return "Send the mesh alterations back to CC4, only if the mesh topology has not changed"

        elif properties.param == "SEND_REPLACE_MESH_INVALID":
            return "*Warning* The selected (or one of the selected) mesh has changed in topology and cannot be sent back to CC4 via replace mesh.\n\n" \
                   "This mesh can now only be sent to CC4 with the entire character (Go CC)"

        elif properties.param == "SEND_MATERIAL_UPDATE":
            return "Send material data and textures for the currently selected meshe objects back to CC4"

        elif properties.param == "DEPIVOT":
            return "TBD"

        elif properties.param == "DEBUG":
            return "Debug!"

        elif properties.param == "TEST":
            return "Test!"

        elif properties.param == "SHOW_ACTOR_FILES":
            return "Open the actor imported files folder"

        elif properties.param == "SHOW_PROJECT_FILES":
            return "Open the project folder"

        return ""






def debug(debug_json):
    utils.log_always("")
    utils.log_always("DEBUG")
    utils.log_always("=====")

    # simulate service crash
    l = [0,1]
    l[2] = 0


def test():
    utils.log_always("")
    utils.log_always("TEST")
    utils.log_always("====")


class CCICLinkConfirmDialog(bpy.types.Operator):
    bl_idname = "ccic.link_confirm_dialog"
    bl_label = "Confirm Action"

    message: bpy.props.StringProperty(default="")
    name: bpy.props.StringProperty(default="")
    filepath: bpy.props.StringProperty(default="")
    link_id: bpy.props.StringProperty(default="")
    character_type: bpy.props.StringProperty(default="")
    mode: bpy.props.StringProperty(default="")
    prefs: bpy.props.StringProperty(default="")

    width=400
    wrap_width = width / 5.5

    def execute(self, context):
        global LINK_SERVICE
        props = vars.props()
        prefs = vars.prefs()

        if self.mode == "REPLACE":
            LINK_SERVICE.do_update_replace(self.name, self.link_id, self.filepath,
                                           self.character_type, True,
                                           objects_to_replace_names=None,
                                           replace_actions=True)

        if self.mode == "CAMERA":
            LINK_SERVICE.do_motion_import(self.link_id, self.filepath, self.character_type)

        if self.mode == "LIGHT":
            LINK_SERVICE.do_motion_import(self.link_id, self.filepath, self.character_type)

        if self.mode == "MOTION":
            LINK_SERVICE.do_motion_import(self.link_id, self.filepath, self.character_type)

        return {"FINISHED"}

    def invoke(self, context, event):
        props = vars.props()
        prefs = vars.prefs()
        chr_cache = props.get_context_character_cache(context)
        return context.window_manager.invoke_props_dialog(self, width=self.width)

    def cancel(self, context):
        #bpy.ops.ccic.link_confirm_dialog('INVOKE_DEFAULT',
        #                               message=self.message,
        #                               param=self.param)
        return

    def draw(self, context):
        props = vars.props()
        prefs = vars.prefs()
        layout = self.layout
        message: str = self.message
        lines = message.splitlines()
        wrapper = textwrap.TextWrapper(width=self.wrap_width)
        for line in lines:
            line = line.strip()
            wrapped_lines = wrapper.wrap(line)
            for wrapped_line in wrapped_lines:
                layout.label(text=wrapped_line)
        if self.prefs:
            layout.separator()
            if self.prefs == "datalink_confirm_mismatch":
                layout.prop(prefs, self.prefs, text="Always Confirm Mismatch")
            elif self.prefs == "datalink_confirm_replace":
                layout.prop(prefs, self.prefs, text="Always Confirm Character Replace")
            else:
                layout.prop(prefs, self.prefs, text="Always Confirm")
        layout.separator()

    @classmethod
    def description(cls, context, properties):
        return "Edit the character name and non-standard type"


class CCICLinkTest(bpy.types.Operator):
    bl_idname = "ccic.linktest"
    bl_label = "Link Test"

    def execute(self, context):

        chr_cache, obj, mat, obj_cache, mat_cache = utils.get_context_character(context)

        rig = chr_cache.get_armature()
        pose_bone = rig.pose.bones["CC_Base_R_Upperarm"]
        utils.log_always(pose_bone.rotation_quaternion)
        pose_bone.rotation_quaternion = (1,0,0,0)
        utils.log_always(pose_bone.rotation_quaternion)


        return {"FINISHED"}