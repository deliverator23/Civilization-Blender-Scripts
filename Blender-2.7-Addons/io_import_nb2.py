bl_info = {
    "name": "Import Nexus Buddy 2(.nb2)",
    "author": "Deliverator",
    "version": (1, 0),
    "blender": (2, 71, 0),
    "location": "File > Import > Nexus Buddy 2 (.nb2)",
    "description": "Import Nexus Buddy 2 (.nb2)",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"}

import bpy
from bpy.props import BoolProperty, IntProperty, EnumProperty, StringProperty
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.io_utils import unpack_list, unpack_face_list
from math import radians
import re

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
	angle = a[2] * 0.5;
	sy = sin(angle);
	cy = cos(angle);
	angle = a[1] * 0.5;
	sp = sin(angle);
	cp = cos(angle);
	angle = a[0] * 0.5;
	sr = sin(angle);
	cr = cos(angle);
	return Quaternion((cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy))

def getRotationMatrix(matrix_4x4):
	return Matrix([[matrix_4x4[0][0],matrix_4x4[0][1],matrix_4x4[0][2]],
				[matrix_4x4[1][0],matrix_4x4[1][1],matrix_4x4[1][2]],
				[matrix_4x4[2][0],matrix_4x4[2][1],matrix_4x4[2][2]]])
				
def writeRotationMatrix(matrix_4x4, matrix_3x3):
	for x in range(0, 3):
		for y in range(0, 3):
			matrix_4x4[x][y] = matrix_3x3[x][y]

# returns the next non-empty, non-comment line from the file
def getNextLine(file):
	ready = False
	while ready==False:
		line = file.readline()
		if len(line)==0:
			print ("Warning: End of file reached.")
			return line
		ready = True
		line = line.strip()
		if len(line)==0 or line.isspace():
			ready = False
		if len(line)>=2 and line[0]=='/' and line[1]=='/':
			ready = False
	return line

def do_import(path, DELETE_TOP_BONE=True):

	# get scene
	scn = bpy.context.scene
	if scn==None:
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
		if len(lines)!=2 or lines[0]!="Meshes:":
			raise ValueError
		numMeshes = int(lines[1])
		if numMeshes < 0:
			raise ValueError
	except ValueError:
		return "Number of meshes is invalid!"

	# read meshes
	boneIds = [[],[],[],[]]
	boneWeights = [[],[],[],[]]
	meshVertexGroups = {}
	vCount = 0
	
	meshes = []
	meshObjects = []

	materialIndexToMeshes = {}
	
	for i in range(numMeshes):
		# read name, flags and material
		try:
			lines = re.findall(r'\".*\"|[^ ]+', getNextLine(file))
			if len(lines)!=3:
				raise ValueError
			meshName = lines[0]
			meshName = meshName[1:-1] + '#M'
			print ("processing mesh name:%s..." % meshName)
			materialId = int(lines[2])
		except ValueError:
			return "Name, flags or material in mesh " + str(i+1) + " are invalid!"
		
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
			if numVerts < 0:
				raise ValueError
		except ValueError:
			return "Number of vertices in mesh " + str(i+1) + " is invalid!"
			
		print ("Number of vertices in mesh:%d" % numVerts)
		
		# read vertices
		coords = []
		uvs = []
		for j in range(numVerts):
			try:
				lines = getNextLine(file).split()
				if len(lines)!=14:
					raise ValueError
				coords.append([float(lines[1]), float(lines[2]), float(lines[3])])
				uvs.append([float(lines[4]), 1-float(lines[5])])
				boneIds[0].append(int(lines[6]))
				boneWeights[0].append(float(lines[7]))
				boneIds[1].append(int(lines[8]))
				boneWeights[1].append(float(lines[9]))
				boneIds[2].append(int(lines[10]))
				boneWeights[2].append(float(lines[11]))
				boneIds[3].append(int(lines[12]))
				boneWeights[3].append(float(lines[13]))
				meshVertexGroups[vCount] = meshName     # uses the long mesh name - may be > 21 chars
				vCount += 1
			except ValueError:
				return "Vertex " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"
		
		meshes[i].vertices.add(len(coords))
		meshes[i].vertices.foreach_set("co", unpack_list(coords))
		
		# read number of normals
		try:
			numNormals = int(getNextLine(file))
			if numNormals < 0:
				raise ValueError
		except ValueError:
			return "Number of normals in mesh " + str(i+1) + " is invalid!"

		print ("Number of normals in mesh:%d" % numNormals)
			
		# read normals
		normals = []
		for j in range(numNormals):
			try:
				lines = getNextLine(file).split()
				if len(lines)!=3:
					raise ValueError
				normals.append([float(lines[0]), float(lines[1]), float(lines[2])])
			except ValueError:
				return "Normal " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"

		# read the number of triangles
		try:
			numTris = int(getNextLine(file))
			if numTris < 0:
				raise ValueError
		except ValueError:
			return "Number of triangles in mesh " + str(i+1) + " is invalid!"

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
					faces.append([v1,v2,v3,0])
			except ValueError:
				return "Triangle " + str(j+1) + " in mesh " + str(i+1) + " is invalid!"
		
		meshes[i].tessfaces.add(len(faces))
		for fi, fpol in enumerate(faces):
			vlen = len(fpol)
			if vlen == 3 or vlen == 4:
				for v in range(vlen):
					meshes[i].tessfaces[fi].vertices_raw[v]= fpol[v]
		
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
		if len(lines)!=2 or lines[0]!="Materials:":
			raise ValueError
		numMats = int(lines[1])
		print("numMats")
		print(numMats)
		if numMats < 0:
			raise ValueError
	except ValueError:
		return "Number of materials is invalid!"

	materialNameToMaterialMap = {}

	# read the materials
	for i in range(numMats):
			# read name
			materialName = getNextLine(file)[1:-1]

			# read ambient color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
			except ValueError:
				return "Ambient color in material " + str(i+1) + " is invalid!"

			# read diffuse color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
			except ValueError:
				return "Diffuse color in material " + str(i+1) + " is invalid!"

			# read specular color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
			except ValueError:
				return "Specular color in material " + str(i+1) + " is invalid!"

			# read emissive color
			try:
				lines = getNextLine(file).split()
				if len(lines)!=4:
					raise ValueError
			except ValueError:
				return "Emissive color in material " + str(i+1) + " is invalid!"

			# read shininess
			try:
				shi = float(getNextLine(file))
			except ValueError:
				return "Shininess in material " + str(i+1) + " is invalid!"

			# read transparency
			try:
				alpha = float(getNextLine(file))
			except ValueError:
				return "Transparency in material " + str(i+1) + " is invalid!"

			# read texturemap
			texturemap = getNextLine(file)[1:-1]
			alphamap = getNextLine(file)[1:-1]

			print("adding material")
			materialName = texturemap.replace(".dds", "")

			if (materialName in materialNameToMaterialMap):
				material = materialNameToMaterialMap[materialName]
			else:
				material = bpy.data.materials.new(materialName)
				materialNameToMaterialMap[materialName] = material

			for meshObject in materialIndexToMeshes[i]:
				meshObject.data.materials.append(material)

	# read the number of bones
	try:
		lines = getNextLine(file).split()
		if len(lines)!=2 or lines[0]!="Bones:":
			raise ValueError
		numBones = int(lines[1])
		if numBones < 0:
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
	posKeys = {}
	rotKeys = {}
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
		rotMatrix.transpose() # Need to transpose to get same behaviour as 2.49 script

		#if ("Pelvis" in fullName or "Ik" in fullName):
		#	print ("Bone Data")
		#	print (fullName)
		#	print (pos)
		#	print (rotMatrix)
		
		boneLength = 3
		# set position and orientation
		if bone.parent:
			bone_parent_matrix = Matrix([[bone.parent.rot_matrix[0], bone.parent.rot_matrix[1], bone.parent.rot_matrix[2]],
										[bone.parent.rot_matrix[3], bone.parent.rot_matrix[4], bone.parent.rot_matrix[5]],
										[bone.parent.rot_matrix[6], bone.parent.rot_matrix[7], bone.parent.rot_matrix[8]]])
			bone.head =  Vector(pos) * bone_parent_matrix + bone.parent.head
			bone.tail = bone.head + Vector([boneLength,0,0]) 
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
			bone.tail = bone.head + Vector([boneLength,0,0])
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
			if numPosKeys < 0:
				raise ValueError
		except ValueError:
			return "Invalid number of position key frames!"

		# read position key frames
		#posKeys[name] = []
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
			if numRotKeys < 0:
				raise ValueError
		except ValueError:
			return "Invalid number of rotation key frames!"

		# read rotation key frames
		#rotKeys[name] = []
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
					if bi==boneIds[j][vi]:
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
		meshOb.parent_type ='ARMATURE'

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

	#for bone in armature.bones:
	#	if ("Ik" in bone.name):
	#		print ("Bone Data")
	#		print (bone.name)
	#		print (bone.matrix_local)
	#		print (bone.matrix)

	# The import was a success!
	return ""


###### IMPORT OPERATOR #######
class Import_nb2(bpy.types.Operator):

    bl_idname = "import_shape.nb2"
    bl_label = "Import NB2 (.nb2)"
    bl_description= "Import a Nexus Buddy .nb2 file"
    filename_ext = ".nb2"
    filter_glob = StringProperty(default="*.nb2", options={'HIDDEN'})

    filepath= StringProperty(name="File Path", description="Filepath used for importing the NB2 file", maxlen=1024, default="")
    DELETE_TOP_BONE= BoolProperty(name="Delete Top Bone", description="Delete Top Bone", default=True)

    def execute(self, context):
        do_import(self.filepath, self.DELETE_TOP_BONE)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager   
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}

### REGISTER ###

def menu_func(self, context):
    self.layout.operator(Import_nb2.bl_idname, text="Nexus Buddy (.nb2)")

 
def register():
    bpy.utils.register_module(__name__) 

    bpy.types.INFO_MT_file_import.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_import.remove(menu_func)

if __name__ == "__main__":
    register()
