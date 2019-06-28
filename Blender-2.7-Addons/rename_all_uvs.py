import bpy

for obj in bpy.context.selected_objects :
    if obj.type == 'MESH':
        for uvmap in  obj.data.uv_layers :
            uvmap.name = 'UVMap'