bl_info = {
    "name": "Batch Convert .nb2 to .cn6 (.dat)",
    "author": "Deliverator",
    "version": (1, 0),
    "blender": (2, 71, 0),
    "location": "File > Import > Batch .nb2 -> .cn6 (.dat)",
    "description": "Batch .nb2 -> .cn6 (.dat)",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"}

import bpy
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.io_utils import unpack_list, unpack_face_list, ExportHelper
import math
from math import radians
import array
from bpy.props import (
        BoolProperty,
        FloatProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import unpack_list, unpack_face_list
import re
import os
import glob

# Converts ms3d euler angles to a rotation matrix
def RM(a):
    sy = sin(a[2])
    cy = cos(a[2])
    sp = sin(a[1])
    cp = cos(a[1])
    sr = sin(a[0])
    cr = cos(a[0])
    return Matrix([cp*cy, cp*sy, -sp], [sr*sp*cy+cr*-sy, sr*sp*sy+cr*cy, sr*cp],[cr*sp*cy+-sr*-sy, cr*sp*sy+-sr*cy, cr*cp])

# Converts ms3d euler angles to a quaternion
def RQ(a):
    angle = a[2] * 0.5
    sy = sin(angle)
    cy = cos(angle)
    angle = a[1] * 0.5
    sp = sin(angle)
    cp = cos(angle)
    angle = a[0] * 0.5
    sr = sin(angle)
    cr = cos(angle)
    return Quaternion((cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy))

def getRotationMatrix(matrix_4x4):
    return Matrix([[matrix_4x4[0][0], matrix_4x4[0][1], matrix_4x4[0][2]],
                   [matrix_4x4[1][0], matrix_4x4[1][1], matrix_4x4[1][2]],
                   [matrix_4x4[2][0], matrix_4x4[2][1], matrix_4x4[2][2]]])


def writeRotationMatrix(matrix_4x4, matrix_3x3):
    for x in range(0, 3):
        for y in range(0, 3):
            matrix_4x4[x][y] = matrix_3x3[x][y]


# returns the next non-empty, non-comment line from the file
def getNextLine(file):
    ready = False
    while ready == False:
        line = file.readline()
        if len(line) == 0:
            print ("Warning: End of file reached.")
            return line
        ready = True
        line = line.strip()
        if len(line) == 0 or line.isspace():
            ready = False
        if len(line) >= 2 and line[0] == '/' and line[1] == '/':
            ready = False
    return line



def getTranslationOrientation(ob):
    if isinstance(ob, bpy.types.Bone):

        ob_matrix_local = ob.matrix_local.copy()
        ob_matrix_local.transpose()
        t = ob_matrix_local
        ob_matrix_local = Matrix([[-t[2][0], -t[2][1], -t[2][2], -t[2][3]],
                                [t[1][0], t[1][1], t[1][2], t[1][3]],
                                [t[0][0], t[0][1], t[0][2], t[0][3]],
                                [t[3][0], t[3][1], t[3][2], t[3][3]]])

        rotMatrix_z90_4x4 = Matrix.Rotation(math.radians(90.0), 4, 'Z')
        rotMatrix_z90_4x4.transpose()

        t = rotMatrix_z90_4x4 * ob_matrix_local
        matrix = Matrix([[t[0][0], t[0][1], t[0][2], t[0][3]],
                                [t[1][0], t[1][1], t[1][2], t[1][3]],
                                [t[2][0], t[2][1], t[2][2], t[2][3]],
                                [t[3][0], t[3][1], t[3][2], t[3][3]]])

        parent = ob.parent
        if parent:
            parent_matrix_local = parent.matrix_local.copy()
            parent_matrix_local.transpose()
            t = parent_matrix_local
            parent_matrix_local = Matrix([[-t[2][0], -t[2][1], -t[2][2], -t[2][3]],
                                    [t[1][0], t[1][1], t[1][2], t[1][3]],
                                    [t[0][0], t[0][1], t[0][2], t[0][3]],
                                    [t[3][0], t[3][1], t[3][2], t[3][3]]])
            par_matrix = rotMatrix_z90_4x4 * parent_matrix_local
            par_matrix_cpy = par_matrix.copy()
            par_matrix_cpy.invert()
            matrix = matrix * par_matrix_cpy

        matrix.transpose()
        loc, rot, sca = matrix.decompose()
    else:
        matrix = ob.matrix_world
        if matrix:
            loc, rot, sca = matrix.decompose()
        else:
            raise "error: this should never happen!"
    return loc, rot

def getBoneTreeDepth(bone, currentCount):
    if (bone.parent):
        currentCount = currentCount + 1
        return getBoneTreeDepth(bone.parent, currentCount)
    else:
        return currentCount


def BPyMesh_meshWeight2List(ob, me):
    """ Takes a mesh and return its group names and a list of lists, one list per vertex.
    aligning the each vert list with the group names, each list contains float value for the weight.
    These 2 lists can be modified and then used with list2MeshWeight to apply the changes.
    """

    # Clear the vert group.
    groupNames = [g.name for g in ob.vertex_groups]
    len_groupNames = len(groupNames)

    if not len_groupNames:
        # no verts? return a vert aligned empty list
        return [[] for i in range(len(me.vertices))], []
    else:
        vWeightList = [[0.0] * len_groupNames for i in range(len(me.vertices))]

    for i, v in enumerate(me.vertices):
        for g in v.groups:
            # possible weights are out of range
            index = g.group
            if index < len_groupNames:
                vWeightList[i][index] = g.weight

    return groupNames, vWeightList


def meshNormalizedWeights(ob, me):
    groupNames, vWeightList = BPyMesh_meshWeight2List(ob, me)

    if not groupNames:
        return [], []

    for i, vWeights in enumerate(vWeightList):
        tot = 0.0
        for w in vWeights:
            tot += w

        if tot:
            for j, w in enumerate(vWeights):
                vWeights[j] = w / tot

    return groupNames, vWeightList

def getBoneWeights(boneName, weights):
    if boneName in weights[0]:
        group_index = weights[0].index(boneName)
        vgroup_data = [(j, weight[group_index]) for j, weight in enumerate(weights[1]) if weight[group_index]]
    else:
        vgroup_data = []

    return vgroup_data


def do_import(path, materialNameToMaterialMap, DELETE_TOP_BONE=True):
    # limits
    MAX_NUMMESHES = 1000000
    MAX_NUMVERTS = 10000000
    MAX_NUMNORMALS = 10000000
    MAX_NUMTRIS = 10000000
    MAX_NUMMATS = 10000000
    MAX_NUMBONES = 1000000
    MAX_NUMPOSKEYS = 0
    MAX_NUMROTKEYS = 0

    # get scene
    scn = bpy.context.scene
    if scn == None:
        return "No scene to import to!"

    # open the file
    try:
        file = open(path, 'r')
    except IOError:
        return "Failed to open the file!"

    try:
        if not path.endswith(".nb2"):
            raise IOError
    except IOError:
        return "Must be an nb2 file!"

    # Read frame info
    try:
        lines = getNextLine(file).split()
        if len(lines) != 2 or lines[0] != "Frames:":
            raise ValueError
        lines = getNextLine(file).split()
        if len(lines) != 2 or lines[0] != "Frame:":
            raise ValueError
    except ValueError:
        return "Frame information is invalid!"

    # Create the mesh
    meshName = "Mesh Object"

    # Before adding any meshes or armatures go into Object mode.
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    # read the number of meshes
    try:
        lines = getNextLine(file).split()
        if len(lines) != 2 or lines[0] != "Meshes:":
            raise ValueError
        numMeshes = int(lines[1])
        if numMeshes < 0 or numMeshes > MAX_NUMMESHES:
            raise ValueError
    except ValueError:
        return "Number of meshes is invalid!"

    # read meshes
    boneIds = [[], [], [], []]
    boneWeights = [[], [], [], []]
    meshVertexGroups = {}
    vCount = 0

    meshes = []
    meshObjects = []

    materialIndexToMeshes = {}

    for i in range(numMeshes):
        # read name, flags and material
        try:
            lines = re.findall(r'\".*\"|[^ ]+', getNextLine(file))
            if len(lines) != 3:
                raise ValueError
            meshName = lines[0]
            meshName = meshName[1:-1] + '#M'
            print ("processing mesh name:%s..." % meshName)
            materialId = int(lines[2])
        except ValueError:
            return "Name, flags or material in mesh " + str(i + 1) + " are invalid!"

        meshes.append(bpy.data.meshes.new(meshName))
        meshObjects.append(bpy.data.objects.new(meshName, meshes[i]))
        scn.objects.link(meshObjects[i])

        if materialId in materialIndexToMeshes:
            materialIndexToMeshes[materialId].add(meshObjects[i])
        else:
            materialIndexToMeshes[materialId] = {meshObjects[i]}

        # read the number of vertices
        try:
            numVerts = int(getNextLine(file))
            if numVerts < 0 or numVerts > MAX_NUMVERTS:
                raise ValueError
        except ValueError:
            return "Number of vertices in mesh " + str(i + 1) + " is invalid!"

        print ("Number of vertices in mesh:%d" % numVerts)

        # read vertices
        coords = []
        uvs = []
        for j in range(numVerts):
            try:
                lines = getNextLine(file).split()
                if len(lines) != 14:
                    raise ValueError
                coords.append([float(lines[1]), float(lines[2]), float(lines[3])])
                uvs.append([float(lines[4]), 1 - float(lines[5])])
                boneIds[0].append(int(lines[6]))
                boneWeights[0].append(float(lines[7]))
                boneIds[1].append(int(lines[8]))
                boneWeights[1].append(float(lines[9]))
                boneIds[2].append(int(lines[10]))
                boneWeights[2].append(float(lines[11]))
                boneIds[3].append(int(lines[12]))
                boneWeights[3].append(float(lines[13]))
                meshVertexGroups[vCount] = meshName  # uses the long mesh name - may be > 21 chars
                vCount += 1
            except ValueError:
                return "Vertex " + str(j + 1) + " in mesh " + str(i + 1) + " is invalid!"

        meshes[i].vertices.add(len(coords))
        meshes[i].vertices.foreach_set("co", unpack_list(coords))

        # read number of normals
        try:
            numNormals = int(getNextLine(file))
            if numNormals < 0 or numNormals > MAX_NUMNORMALS:
                raise ValueError
        except ValueError:
            return "Number of normals in mesh " + str(i + 1) + " is invalid!"

        print ("Number of normals in mesh:%d" % numNormals)

        # read normals
        normals = []
        for j in range(numNormals):
            try:
                lines = getNextLine(file).split()
                if len(lines) != 3:
                    raise ValueError
                normals.append([float(lines[0]), float(lines[1]), float(lines[2])])
            except ValueError:
                return "Normal " + str(j + 1) + " in mesh " + str(i + 1) + " is invalid!"

        # read the number of triangles
        try:
            numTris = int(getNextLine(file))
            if numTris < 0 or numTris > MAX_NUMTRIS:
                raise ValueError
        except ValueError:
            return "Number of triangles in mesh " + str(i + 1) + " is invalid!"

        print ("Number of triangles in mesh:%d" % numTris)

        # read triangles
        faces = []
        for j in range(numTris):
            # read the triangle
            try:
                lines = getNextLine(file).split()
                if len(lines) != 8:
                    raise ValueError
                v1 = int(lines[1])
                v2 = int(lines[2])
                v3 = int(lines[3])

                if v1 < numVerts and v2 < numVerts and v3 < numVerts:
                    faces.append([v1, v2, v3, 0])
            except ValueError:
                return "Triangle " + str(j + 1) + " in mesh " + str(i + 1) + " is invalid!"

        meshes[i].tessfaces.add(len(faces))
        for fi, fpol in enumerate(faces):
            vlen = len(fpol)
            if vlen == 3 or vlen == 4:
                for v in range(vlen):
                    meshes[i].tessfaces[fi].vertices_raw[v] = fpol[v]

        # set texture coordinates and material
        meshes[i].tessface_uv_textures.new()
        for j, face in enumerate(meshes[i].tessfaces):
            face_uv = meshes[i].tessface_uv_textures[0].data[j]

            face_uv.uv1 = Vector(uvs[face.vertices[0]])
            face_uv.uv2 = Vector(uvs[face.vertices[1]])
            face_uv.uv3 = Vector(uvs[face.vertices[2]])

            face.material_index = 0

    print("materialIndexToMeshes")
    print(materialIndexToMeshes)

    for mesh in meshes:
        mesh.update()

    # read the number of materials
    try:
        lines = getNextLine(file).split()
        if len(lines) != 2 or lines[0] != "Materials:":
            raise ValueError
        numMats = int(lines[1])
        print("numMats")
        print(numMats)
        if numMats < 0 or numMats > MAX_NUMMATS:
            raise ValueError
    except ValueError:
        return "Number of materials is invalid!"

    materialIdToMaterialNameMap = {}

    # read the materials
    for i in range(numMats):
        # read name
        materialName = getNextLine(file)[1:-1]

        # read ambient color
        try:
            lines = getNextLine(file).split()
            if len(lines) != 4:
                raise ValueError
        except ValueError:
            return "Ambient color in material " + str(i + 1) + " is invalid!"

        # read diffuse color
        try:
            lines = getNextLine(file).split()
            if len(lines) != 4:
                raise ValueError
        except ValueError:
            return "Diffuse color in material " + str(i + 1) + " is invalid!"

        # read specular color
        try:
            lines = getNextLine(file).split()
            if len(lines) != 4:
                raise ValueError
        except ValueError:
            return "Specular color in material " + str(i + 1) + " is invalid!"

        # read emissive color
        try:
            lines = getNextLine(file).split()
            if len(lines) != 4:
                raise ValueError
        except ValueError:
            return "Emissive color in material " + str(i + 1) + " is invalid!"

        # read shininess
        try:
            shi = float(getNextLine(file))
        except ValueError:
            return "Shininess in material " + str(i + 1) + " is invalid!"

        # read transparency
        try:
            alpha = float(getNextLine(file))
        except ValueError:
            return "Transparency in material " + str(i + 1) + " is invalid!"

        # read texturemap
        texturemap = getNextLine(file)[1:-1]
        alphamap = getNextLine(file)[1:-1]

        print("adding material")
        materialName = texturemap.replace(".dds", "")

        materialIdToMaterialNameMap[i] = materialName

        if (materialName in materialNameToMaterialMap):
            material = materialNameToMaterialMap[materialName]
        else:
            material = bpy.data.materials.new(materialName)
            materialNameToMaterialMap[materialName] = material

    for materialIndex in materialIndexToMeshes.keys():
        for meshObject in materialIndexToMeshes[materialIndex]:
            meshMaterial = materialNameToMaterialMap[materialIdToMaterialNameMap[materialIndex]]
            meshObject.data.materials.append(meshMaterial)

    # read the number of bones
    try:
        lines = getNextLine(file).split()
        if len(lines) != 2 or lines[0] != "Bones:":
            raise ValueError
        numBones = int(lines[1])
        if numBones < 0 or numBones > MAX_NUMBONES:
            raise ValueError
    except:
        return "Number of bones is invalid!"

    # create the armature
    armature = None
    armOb = None

    print ("numBones:%d" % numBones)

    if numBones > 0:
        armature = bpy.data.armatures.new("Armature")
        armOb = bpy.data.objects.new("ArmatureObject", armature)
        armature.draw_type = 'STICK'
        scn.objects.link(armOb)
        scn.objects.active = armOb

    # read bones
#    posKeys = {}
#    rotKeys = {}
    boneNames = []
    bpy.ops.object.editmode_toggle()
    bpy.types.EditBone.rot_matrix = bpy.props.FloatVectorProperty(name="Rot Matrix", size=9)

    for i in range(numBones):
        # read name
        fullName = getNextLine(file)[1:-1]
        boneNames.append(fullName)
        bone = armature.edit_bones.new(fullName)

        # read parent
        parentBoneName = getNextLine(file)[1:-1]
        if len(parentBoneName) > 0:
            bone.parent = armature.bones.data.edit_bones[parentBoneName]

        # read position and rotation
        try:
            line = getNextLine(file)
            lines = line.split()
            if not (len(lines) == 8 or len(lines) == 24):
                raise ValueError
            pos = [float(lines[1]), float(lines[2]), float(lines[3])]
            quat = [float(lines[4]), float(lines[5]), float(lines[6]), float(lines[7])]
        except ValueError:
            return "Invalid position or orientation in a bone!"

        # Granny Rotation Quaternions are stored X,Y,Z,W but Blender uses W,X,Y,Z
        quaternion = Quaternion((quat[3], quat[0], quat[1], quat[2]))
        rotMatrix = quaternion.to_matrix()
        rotMatrix.transpose()  # Need to transpose to get same behaviour as 2.49 script

        # if ("Pelvis" in fullName or "Ik" in fullName):
        #	print ("Bone Data")
        #	print (fullName)
        #	print (pos)
        #	print (rotMatrix)

        boneLength = 3
        # set position and orientation
        if bone.parent:
            bone_parent_matrix = Matrix(
                [[bone.parent.rot_matrix[0], bone.parent.rot_matrix[1], bone.parent.rot_matrix[2]],
                 [bone.parent.rot_matrix[3], bone.parent.rot_matrix[4], bone.parent.rot_matrix[5]],
                 [bone.parent.rot_matrix[6], bone.parent.rot_matrix[7], bone.parent.rot_matrix[8]]])
            bone.head = Vector(pos) * bone_parent_matrix + bone.parent.head
            bone.tail = bone.head + Vector([boneLength, 0, 0])
            tempM = rotMatrix * bone_parent_matrix
            bone.rot_matrix = [tempM[0][0], tempM[0][1], tempM[0][2],
                               tempM[1][0], tempM[1][1], tempM[1][2],
                               tempM[2][0], tempM[2][1], tempM[2][2]]
            bone.matrix = Matrix([[-bone.rot_matrix[3], bone.rot_matrix[0], bone.rot_matrix[6], bone.head[0]],
                                  [-bone.rot_matrix[4], bone.rot_matrix[1], bone.rot_matrix[7], bone.head[1]],
                                  [-bone.rot_matrix[5], bone.rot_matrix[2], bone.rot_matrix[8], bone.head[2]],
                                  [0, 0, 0, 1]])
        else:
            bone.head = Vector(pos)
            bone.tail = bone.head + Vector([boneLength, 0, 0])
            bone.rot_matrix = [rotMatrix[0][0], rotMatrix[0][1], rotMatrix[0][2],
                               rotMatrix[1][0], rotMatrix[1][1], rotMatrix[1][2],
                               rotMatrix[2][0], rotMatrix[2][1], rotMatrix[2][2]]
            bone.matrix = Matrix([[-bone.rot_matrix[3], bone.rot_matrix[0], bone.rot_matrix[6], bone.head[0]],
                                  [-bone.rot_matrix[4], bone.rot_matrix[1], bone.rot_matrix[7], bone.head[1]],
                                  [-bone.rot_matrix[5], bone.rot_matrix[2], bone.rot_matrix[8], bone.head[2]],
                                  [0, 0, 0, 1]])

        # read the number of position key frames
        try:
            numPosKeys = int(getNextLine(file))
            if numPosKeys < 0 or numPosKeys > MAX_NUMPOSKEYS:
                raise ValueError
        except ValueError:
            return "Invalid number of position key frames!"

        # read position key frames
        # posKeys[name] = []
        for j in range(numPosKeys):
            # read time and position
            try:
                lines = getNextLine(file).split()
                if len(lines) != 4:
                    raise ValueError
            except ValueError:
                return "Invalid position key frame!"

        # read the number of rotation key frames
        try:
            numRotKeys = int(getNextLine(file))
            if numRotKeys < 0 or numRotKeys > MAX_NUMROTKEYS:
                raise ValueError
        except ValueError:
            return "Invalid number of rotation key frames!"

        # read rotation key frames
        # rotKeys[name] = []
        for j in range(numRotKeys):
            # read time and rotation
            try:
                lines = getNextLine(file).split()
                if len(lines) != 4:
                    raise ValueError
            except ValueError:
                return "Invalid rotation key frame!"

    # Roll fix for all bones
    for bone in armature.bones.data.edit_bones:
        roll = bone.roll
        bone.roll = roll - radians(90.0)

    # Create Vertex Groups
    vi = 0
    for meshOb in meshObjects:
        mesh = meshOb.data
        for mvi, vertex in enumerate(mesh.vertices):
            for bi in range(numBones):
                for j in range(4):
                    if bi == boneIds[j][vi]:
                        name = boneNames[bi]
                        if not meshOb.vertex_groups.get(name):
                            meshOb.vertex_groups.new(name)
                        grp = meshOb.vertex_groups.get(name)
                        grp.add([mvi], boneWeights[j][vi], 'ADD')
            vi = vi + 1

        # Give mesh object an armature modifier, using vertex groups but not envelopes
        mod = meshOb.modifiers.new('mod_' + mesh.name, 'ARMATURE')
        mod.object = armOb
        mod.use_bone_envelopes = False
        mod.use_vertex_groups = True
        # Parent Mesh Object to Armature Object
        meshOb.parent = armOb
        meshOb.parent_type = 'ARMATURE'

    if DELETE_TOP_BONE:
        # Adjust object names, remove top bone for Civ V
        bone = armature.bones.data.edit_bones[boneNames[0]]
        while not bone.parent is None:
            bone = bone.parent

        print ('Found World Bone: %s' % bone.name)

        name = bone.name
        armOb.name = name

        # Delete top bone unless that would leave zero bones
        if (len(armature.bones.data.edit_bones) > 1):
            bpy.ops.object.select_pattern(pattern=name)
            bpy.ops.armature.delete()

    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()

    # for bone in armature.bones:
    #	if ("Ik" in bone.name):
    #		print ("Bone Data")
    #		print (bone.name)
    #		print (bone.matrix_local)
    #		print (bone.matrix)

    # The import was a success!
    return materialNameToMaterialMap

def do_export(filename):
    print ("Start CN6 Export...")

    file = open( filename, 'w')
    filedata = "// CivNexus6 CN6 - Exported from Blender for import to CivNexus6\n"

    try:
        modelObs = {}
        modelMeshes = {}

        for object in bpy.data.objects:
            if object.type == 'ARMATURE':
                modelObs[object.name] = object

            if object.type == 'MESH':
                print ("Getting parent for mesh: %s" % object.name)
                parentArmOb = object.modifiers[0].object
                if not parentArmOb.name in modelMeshes:
                    modelMeshes[parentArmOb.name] = []
                modelMeshes[parentArmOb.name].append(object)

        for modelObName in modelObs.keys():
            boneIds = {}

            # Write Skeleton
            filedata += "skeleton\n"

            armOb = modelObs[modelObName]
            armature = armOb.data

            # Calc bone depths and sort
            boneDepths = []
            for bone in armature.bones.values():
                boneDepth = getBoneTreeDepth(bone, 0)
                boneDepths.append((bone, boneDepth))

            boneDepths = sorted(boneDepths, key=lambda k: k[0].name)
            boneDepths = sorted(boneDepths, key=lambda k: k[1])
            sortedBones = boneDepths

            for boneid, boneTuple in enumerate(sortedBones):
                boneIds[boneTuple[0].name] = boneid

            boneIds[armOb.name] = -1 # Add entry for World Bone

            # Write World Bone
            filedata += '%d "%s" %d ' % (0, armOb.name, -1)
            filedata += '%.8f %.8f %.8f ' % (0.0, 0.0, 0.0)
            filedata += '%.8f %.8f %.8f %.8f ' % (0.0, 0.0, 0.0, 1.0)
            filedata += '%.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f\n' % (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

            print ("armOb.name/armature.bones[0].name/len(boneIds)")
            print (armOb.name)
            print (armature.bones[0].name)
            print (len(boneIds))

            if (len(boneIds) > 1 or armOb.name != armature.bones[0].name):
                for boneid, boneTuple in enumerate(sortedBones):
                    bone = boneTuple[0]
                    #boneDepth = boneTuple[1]

                    position, orientationQuat = getTranslationOrientation(bone)

                    # Get Inverse World Matrix for bone
                    x = bone.matrix_local.copy()
                    x.transpose()
                    t = Matrix([[-x[2][0], -x[2][1], -x[2][2], -x[2][3]],
                                [x[1][0], x[1][1], x[1][2], x[1][3]],
                                [x[0][0], x[0][1], x[0][2], x[0][3]],
                                [x[3][0], x[3][1], x[3][2], x[3][3]]])
                    t.invert()
                    invWorldMatrix = Matrix([[t[0][1], -t[0][0], t[0][2], t[0][3]],
                                        [t[1][1], -t[1][0], t[1][2], t[1][3]],
                                        [t[2][1], -t[2][0], t[2][2], t[2][3]],
                                        [t[3][1], -t[3][0], t[3][2], t[3][3]]])

                    outputBoneName = bone.name

                    filedata += '%d "%s" ' % (boneid + 1, outputBoneName)   # Adjust bone ids + 1 as zero is the World Bone

                    parentBoneId = 0
                    if bone.parent:
                        parentBoneId = boneIds[bone.parent.name] + 1   # Adjust bone ids + 1 as zero is the World Bone

                    filedata += '%d ' % parentBoneId
                    filedata +='%.8f %.8f %.8f ' % (position[0], position[1], position[2])
                    filedata +='%.8f %.8f %.8f %.8f ' % (orientationQuat[1], orientationQuat[2], orientationQuat[3], orientationQuat[0]) # GR2 uses x,y,z,w for Quaternions rather than w,x,y,z
                    filedata += '%.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f' % (invWorldMatrix[0][0], invWorldMatrix[0][1], invWorldMatrix[0][2], invWorldMatrix[0][3],
                                                                                        invWorldMatrix[1][0], invWorldMatrix[1][1], invWorldMatrix[1][2], invWorldMatrix[1][3],
                                                                                        invWorldMatrix[2][0], invWorldMatrix[2][1], invWorldMatrix[2][2], invWorldMatrix[2][3],
                                                                                        invWorldMatrix[3][0], invWorldMatrix[3][1], invWorldMatrix[3][2], invWorldMatrix[3][3])
                    #End of bone line
                    filedata += "\n"

            if len(modelMeshes) == 0:
                filedata += 'meshes:%d\n' % 0
            else:
                filedata += 'meshes:%d\n' % len(modelMeshes[modelObName])

                for meshObject in modelMeshes[modelObName]:

                    mesh = meshObject.data
                    meshName = meshObject.name

                    filedata += 'mesh:"%s"\n' % meshName

                    filedata += 'materials\n'
                    for material in meshObject.data.materials:
                        filedata += '\"%s\"\n' % material.name

                    # Read in preserved Normals, Binormals and Tangents
                    vertexBinormalsTangents = {}
                    originalVertexNormals = {}

                    useOriginalNormals = meshObject.vertex_groups.get("VERTEX_KEYS") is not None and mesh.get('originalTangentsBinormals') is not None

                    if useOriginalNormals:
                        for index, vertex in enumerate(mesh.vertices):

                                keyVertexGroup = meshObject.vertex_groups.get("VERTEX_KEYS")
                                if keyVertexGroup is not None:
                                    weight = vertex.groups[keyVertexGroup.index].weight * 2000000
                                    decodedVertexIndex = str(int(round(weight)))

                                    print ("{}: decodedVertexIndex:{}".format(index, decodedVertexIndex))

                                    if mesh['originalTangentsBinormals'].get(decodedVertexIndex) is not None:
                                        tangentsBinormals = mesh['originalTangentsBinormals'][decodedVertexIndex]
                                        originalVertexNormals[str(index)] = tangentsBinormals

                    # This will wipe out custom normals
                    mesh.calc_tangents(mesh.uv_layers[0].name)

                    for poly in mesh.polygons:
                        for loop_index in poly.loop_indices:

                            currentVertexIndex = mesh.loops[loop_index].vertex_index
                            loop = mesh.loops[loop_index]

                            currentVertBinormTang = (loop.normal[0], loop.normal[1], loop.normal[2], loop.tangent[0],loop.tangent[1],loop.tangent[2], loop.bitangent[0], loop.bitangent[1], loop.bitangent[2])

                            if not currentVertexIndex in vertexBinormalsTangents:
                                vertexBinormalsTangents[currentVertexIndex] = []
                            vertexBinormalsTangents[currentVertexIndex].append(currentVertBinormTang)

                    if useOriginalNormals:
                        # Reset Custom Loop Normals
                        mesh.create_normals_split()

                        matchedLoops = 0
                        for loopIndex, loop in enumerate(mesh.loops):
                            if originalVertexNormals.get(str(loop.vertex_index)) is not None:
                                normalsEtc = originalVertexNormals[str(loop.vertex_index)]
                                loop.normal =  (normalsEtc[0], normalsEtc[1], normalsEtc[2])
                                matchedLoops += 1

                        mesh.validate(clean_customdata=False)

                        clnors = array.array('f', [0.0] * (len(mesh.loops) * 3))
                        mesh.loops.foreach_get("normal", clnors)

                        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))

                        mesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
                        mesh.use_auto_smooth = True
                        mesh.show_edge_sharp = True

                    # Average out Normals, Tangents and Bitangents for each Vertex
                    vertexNormsBinormsTangsSelected = {}

                    for vertId in vertexBinormalsTangents.keys():

                        sum0, sum1, sum2, sum3, sum4, sum5, sum6, sum7, sum8 = 0,0,0,0,0,0,0,0,0

                        for currentrow in vertexBinormalsTangents[vertId]:
                            sum0 = sum0 + currentrow[0]
                            sum1 = sum1 + currentrow[1]
                            sum2 = sum2 + currentrow[2]

                            sum3 = sum3 + currentrow[3]
                            sum4 = sum4 + currentrow[4]
                            sum5 = sum5 + currentrow[5]

                            sum6 = sum6 + currentrow[6]
                            sum7 = sum7 + currentrow[7]
                            sum8 = sum8 + currentrow[8]

                        numRows = len(vertexBinormalsTangents[vertId])

                        vertexNormsBinormsTangsSelected[vertId] = (sum0/numRows, sum1/numRows, sum2/numRows,
                                                                    sum3/numRows, sum4/numRows, sum5/numRows,
                                                                    sum6/numRows, sum7/numRows, sum8/numRows)

                    # Get Bone Weights
                    weights = meshNormalizedWeights(meshObject, mesh)
                    vertexBoneWeights = {}
                    print (meshName)
                    print ("len(mesh.polygons)")
                    print (len(mesh.polygons))
                    print ("len(mesh.loops)")
                    print (len(mesh.loops))
                    print ("len(weights[0])")
                    print (len(weights[0]))

                    for boneName in boneIds.keys():
                        vgroupDataForBone = getBoneWeights(boneName, weights)

                        for vgData in vgroupDataForBone:
                            vertexId = vgData[0]
                            weight = vgData[1]
                            if not vertexId in vertexBoneWeights:
                                vertexBoneWeights[vertexId] = []
                            vertexBoneWeights[vertexId].append((boneName, weight))

                    print ("len(mesh.vertices)")
                    print (len(mesh.vertices))
                    print ("len(vertexBoneWeights.keys())")
                    print (len(vertexBoneWeights.keys()))

                    grannyVertexBoneWeights = {}
                    for vertId in vertexBoneWeights.keys():

                        rawBoneIdWeightTuples = []
                        firstBoneId = 0
                        for i in range(max(8,len(vertexBoneWeights[vertId]))):
                            if i < len(vertexBoneWeights[vertId]):
                                vertexBoneWeightTuple = vertexBoneWeights[vertId][i]
                                boneName = vertexBoneWeightTuple[0]
                                rawBoneIdWeightTuples.append((boneIds[boneName] + 1, vertexBoneWeightTuple[1]))
                                if i == 0:
                                    firstBoneId = boneIds[boneName] + 1
                            else:
                                rawBoneIdWeightTuples.append((firstBoneId, 0))

                        # Sort bone mappings by weight highest to lowest
                        sortedBoneIdWeightTuples = sorted(rawBoneIdWeightTuples, key=lambda rawBoneIdWeightTuple: rawBoneIdWeightTuple[1], reverse=True)

                        # Pick first 8 highest weighted bones
                        boneIdsList = []
                        rawBoneWeightsList = []
                        for i in range(8):
                            boneIdsList.append(sortedBoneIdWeightTuples[i][0])
                            rawBoneWeightsList.append(sortedBoneIdWeightTuples[i][1])

                        rawWeightTotal = 0
                        for weight in rawBoneWeightsList:
                            rawWeightTotal = rawWeightTotal + weight

                        boneWeightsList = []
                        for weight in rawBoneWeightsList:
                            calcWeight = round(255 * weight / rawWeightTotal)
                            boneWeightsList.append(calcWeight)

                        # Ensure that total of vertex bone weights is 255
                        runningTotal = 0
                        for i, weight in enumerate(boneWeightsList):
                            runningTotal = runningTotal + weight

                        if runningTotal != 255:
                            boneWeightsList[0] = boneWeightsList[0] + (255 - runningTotal)

                        runningTotal = 0
                        for i, weight in enumerate(boneWeightsList):
                            runningTotal = runningTotal + weight

                        #print("Current Running Total")
                        #print(runningTotal)

                        if runningTotal != 255:
                            raise "Error: Vertex bone weights do not total 255!"

                        if not vertId in grannyVertexBoneWeights:
                            grannyVertexBoneWeights[vertId] = []
                        grannyVertexBoneWeights[vertId] = (boneIdsList, boneWeightsList)

                    position, orientationQuat = getTranslationOrientation(meshObject)

                    filedata += "vertices\n"

                    print ("grannyVertexBoneWeights")
                    print (len(grannyVertexBoneWeights))
                    print ("Write Vertices")

                    # Get unique vertex/uv coordinate combinations
                    uniqueVertSet = set()
                    uniqueVertUVIndexes = {}
                    uniqueVertUVs = []
                    currentVertUVIndex = 0

                    currentTriangleId = 0
                    triangleVertUVIndexes = []
                    triangleMaterialIndexes = []

                    for poly in mesh.polygons:
                        triangleVertUVIndexes.append([])

                        for loop_index in poly.loop_indices:
                            vertexId = mesh.loops[loop_index].vertex_index

                            if (mesh.uv_layers[0]):
                                uv = mesh.uv_layers[0].data[loop_index].uv
                            else:
                                uv = (0.0, 1.0)

                            if (len(mesh.uv_layers) > 1):
                                uv2 = mesh.uv_layers[1].data[loop_index].uv
                            else:
                                uv2 = (0.0, 1.0)

                            if (len(mesh.uv_layers) > 2):
                                uv3 = mesh.uv_layers[2].data[loop_index].uv
                            else:
                                uv3 = (0.0, 1.0)

                            uvt = tuple(uv)
                            uv2t = tuple(uv2)
                            uv3t = tuple(uv3)

                            vertSig = '%i|%.8f|%.8f|%.8f|%.8f|%.8f|%.8f' % (vertexId, uvt[0], uvt[1], uv2t[0], uv2t[1], uv3t[0], uv3t[1])

                            if vertSig in uniqueVertSet:
                                triangleVertUVIndex = uniqueVertUVIndexes[vertSig]
                            else:
                                uniqueVertSet.add(vertSig)
                                uniqueVertUVIndexes[vertSig] = currentVertUVIndex
                                uniqueVertUVs.append((vertexId, uvt[0], uvt[1], uv2t[0], uv2t[1], uv3t[0], uv3t[1]))
                                triangleVertUVIndex = currentVertUVIndex
                                currentVertUVIndex = currentVertUVIndex + 1

                            triangleVertUVIndexes[currentTriangleId].append(triangleVertUVIndex)

                        triangleMaterialIndexes.append(poly.material_index)
                        currentTriangleId = currentTriangleId + 1

                    # Write Vertices
                    preservedTangsBinormsCount = 0
                    calculatedTangsBinormsCount = 0

                    # Write Vertices
                    for uniqueVertUV in uniqueVertUVs:

                        vertexIndex = uniqueVertUV[0]
                        vertex = mesh.vertices[vertexIndex]
                        vertCoord = tuple(vertex.co)

                        uv = (uniqueVertUV[1], uniqueVertUV[2])
                        uv2 = (uniqueVertUV[3], uniqueVertUV[4])
                        uv3 = (uniqueVertUV[5], uniqueVertUV[6])

                        vertexFound = False

                        if originalVertexNormals.get(str(vertexIndex)) is not None:
                            tangentsBinormals = originalVertexNormals[str(vertexIndex)]
                            vertNormal = (tangentsBinormals[0],tangentsBinormals[1],tangentsBinormals[2])
                            vertTangent = (tangentsBinormals[3],tangentsBinormals[4],tangentsBinormals[5])
                            vertBinormal = (tangentsBinormals[6],tangentsBinormals[7],tangentsBinormals[8])
                            vertexFound = True
                        else:
                            vertNBT = vertexNormsBinormsTangsSelected[vertexIndex]
                            vertNormal = (vertNBT[0], vertNBT[1], vertNBT[2])
                            vertTangent = (vertNBT[3], vertNBT[4], vertNBT[5])
                            vertBinormal = (vertNBT[6], vertNBT[7], vertNBT[8])

                        if (vertexFound):
                            preservedTangsBinormsCount += 1
                        else:
                            calculatedTangsBinormsCount += 1

                        filedata +='%.8f %.8f %.8f ' % (vertCoord[0] + position[0],  vertCoord[1] +  position[1], vertCoord[2] + position[2])
                        filedata +='%.8f %.8f %.8f ' % (vertNormal[0], vertNormal[1], vertNormal[2])
                        filedata +='%.8f %.8f %.8f ' % (vertTangent[0], vertTangent[1], vertTangent[2])
                        filedata +='%.8f %.8f %.8f ' % (vertBinormal[0], vertBinormal[1], vertBinormal[2])

                        filedata +='%.8f %.8f ' % (uv[0], 1 - uv[1])
                        filedata +='%.8f %.8f ' % (uv2[0], 1 - uv2[1])
                        filedata +='%.8f %.8f ' % (uv3[0], 1 - uv3[1])

                        if vertexIndex in grannyVertexBoneWeights:
                            vBoneWeightTuple = grannyVertexBoneWeights[vertexIndex]
                        else:
                            #raise "Error: Mesh has unweighted vertices!"
                            vBoneWeightTuple = ([-1,-1,-1,-1,-1,-1,-1,-1],[-1,-1,-1,-1,-1,-1,-1,-1]) # Unweighted vertex - raise error

                        filedata +='%d %d %d %d %d %d %d %d ' % (vBoneWeightTuple[0][0], vBoneWeightTuple[0][1],vBoneWeightTuple[0][2],vBoneWeightTuple[0][3], vBoneWeightTuple[0][4], vBoneWeightTuple[0][5],vBoneWeightTuple[0][6],vBoneWeightTuple[0][7]) # Bone Ids
                        filedata +='%d %d %d %d %d %d %d %d\n' % (vBoneWeightTuple[1][0], vBoneWeightTuple[1][1],vBoneWeightTuple[1][2],vBoneWeightTuple[1][3], vBoneWeightTuple[1][4], vBoneWeightTuple[1][5],vBoneWeightTuple[1][6],vBoneWeightTuple[1][7]) # Bone Weights

                    # Write Triangles
                    filedata += "triangles\n"

                    outputTriangles = []
                    for triangle_id, triangle in enumerate(triangleVertUVIndexes): # mesh.polygons:
                        materialIndex = triangleMaterialIndexes[triangle_id]
                        outputTriangles.append((triangle[0],triangle[1],triangle[2], materialIndex))

                    sortedOutputTriangles = sorted(outputTriangles, key=lambda triangle: triangle[3])

                    for triangle in sortedOutputTriangles:
                        filedata += '%i %i %i %i\n' % (triangle[0],triangle[1],triangle[2], triangle[3])

                    print ("meshName: {}".format(meshName))
                    print ("preservedTangsBinormsCount: {}".format(preservedTangsBinormsCount))
                    print ("calculatedTangsBinormsCount: {}".format(calculatedTangsBinormsCount))

        for armObject in modelObs.values():
            if armObject.type == 'ARMATURE':
                armObject.select = True
        bpy.ops.object.delete()

        for meshList in modelMeshes.values():
            for meshObject in meshList:
                if meshObject.type == 'MESH':
                    meshObject.select = True
        bpy.ops.object.delete()

        #material = bpy.data.materials.get('Material')
        #bpy.data.materials.remove(material)

        filedata += "end"
        file.write(filedata)
        file.flush()
        file.close()
    except:
        filedata += "aborted!"
        file.write(filedata)
        file.flush()
        file.close()
        raise

    print ("End CN6 Export.")
    return ""


def do_batch_convert(filename):
    print ("Start batch .nb2 -> .cn6 conversion...")

    directory = os.path.dirname(filename)

    lines = [line.rstrip('\n') for line in open(filename)]

    for line in lines:
        exportDone = False
        lineBits = line.split(";")
        modelName = lineBits[0].lower()

        nb2FilenameRoot = directory + "\\" + modelName.replace(".gr2","")

        # Handle *_model.nb2
        path = nb2FilenameRoot + "_model*.nb2"
        materialNameToMaterialMap = {}
        for filename in glob.glob(path):
            print("Import %s" % filename)
            materialNameToMaterialMap = do_import(filename, materialNameToMaterialMap)

        # Handle *__modelname.nb2
        path = nb2FilenameRoot + "__*.nb2"
        for filename in glob.glob(path):
            print("Import %s" % filename)
            materialNameToMaterialMap = {}
            do_import(filename, materialNameToMaterialMap)
            shortFilename = os.path.basename(filename)
            cn6Filename = directory + "\\" + shortFilename.replace(".nb2", ".cn6")
            print("Export %s" % cn6Filename)
            do_export(cn6Filename)
            exportDone = True

        # Handle direct matches
        path = nb2FilenameRoot + ".nb2"
        materialNameToMaterialMap = {}
        for filename in glob.glob(path):
            print("Import %s" % filename)
            materialNameToMaterialMap = do_import(filename, materialNameToMaterialMap)

        if not exportDone:
            cn6Filename = directory + "\\" + modelName.replace(".gr2", ".cn6")
            print("Export %s" % cn6Filename)
            do_export(cn6Filename)


###### IMPORT OPERATOR #######
class ConvertNB2CN6(bpy.types.Operator):
    bl_idname = "import_nb2_cn6.dat"
    bl_label = "Batch convert .nb2 to .cn6 (.dat)"
    bl_description = "Batch convert .nb2 to .cn6"
    filename_ext = ".dat"
    filter_glob = StringProperty(default="*.dat", options={'HIDDEN'})

    filepath = StringProperty(name="File Path", description="Filepath used for importing the DAT file", maxlen=1024,
                              default="")

    def execute(self, context):
        do_batch_convert(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


### REGISTER ###

def menu_func(self, context):
    self.layout.operator(ConvertNB2CN6.bl_idname, text="Batch .nb2 -> .cn6 (.dat)")


def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_import.append(menu_func)


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
    register()