import bpy

DATA_NODE_GROUP = "RL_Data_Group"


def get_data_group():
    if DATA_NODE_GROUP not in bpy.data.node_groups:
        bpy.data.node_groups.new(DATA_NODE_GROUP, 'ShaderNodeTree')
    data_group = bpy.data.node_groups[DATA_NODE_GROUP]
    return data_group


def get_node_id(chr_cache, id):
    if id:
        chr_id = "Global" if chr_cache is None else chr_cache.character_name
        return f"RL_{chr_id}_{id}"
    return ""


def get_rgbcurve_node(data_group, node_id, shape=None):
    if data_group and node_id:
        for node in data_group.nodes:
            if node.name == node_id:
                return node
        node: bpy.types.ShaderNodeRGBCurve = data_group.nodes.new("ShaderNodeRGBCurve")
        node.name = node_id
        if shape == "IN":
            P = node.mapping.curves[3].points
            P[0].location = (0, 0)
            P[1].location = (1, 1)
        elif shape == "OUT":
            P = node.mapping.curves[3].points
            P[0].location = (0, 1)
            P[1].location = (1, 0)
        return node
    return None


def eval_curve(fcurve_data: bpy.types.ShaderNodeRGBCurve, position: float):
    return fcurve_data.mapping.evaluate(fcurve_data.mapping.curves[3], position)


def get_fcurve_data(chr_cache, id, shape=None):
    data_group = get_data_group()
    node_id = get_node_id(chr_cache, id)
    node = get_rgbcurve_node(data_group, node_id, shape=shape)
    return node



