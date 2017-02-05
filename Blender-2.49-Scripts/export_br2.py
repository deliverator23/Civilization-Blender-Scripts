#!BPY
# coding: utf-8
""" 
Name: 'Nexus Buddy 2 (.br2)...'
Blender: 249
Group: 'Export'
Tooltip: 'Export to Nexus Buddy 2 format (.br2).'
"""

__author__ = ["Deliverator"]
__url__ = ("")
__version__ = "0.1"
__bpydoc__ = """\

Nexus Buddy 2 Import
"""

######################################################
# Importing modules
######################################################

import Blender
import bpy
import BPyMesh 
import BPyObject 
import BPyMessages
from Blender.Mathutils import Matrix, Vector, RotationMatrix

rotMatrix_z90_4x4 = RotationMatrix(90, 4, 'z') 

def getTranslationOrientation(ob, file):
	if isinstance(ob, Blender.Types.BoneType):
		
		matrix = rotMatrix_z90_4x4 * ob.matrix['ARMATURESPACE']
		
		parent = ob.parent
		if parent:
			par_matrix = rotMatrix_z90_4x4 * parent.matrix['ARMATURESPACE'] 
			matrix = matrix * par_matrix.copy().invert()
		
		matrix_rot =	matrix.rotationPart()
		
		loc =			tuple(matrix.translationPart())
		rot =			matrix_rot.toQuat()
	else:
		matrix = ob.matrixWorld
		if matrix:
			loc = tuple(matrix.translationPart())
			matrix_rot = matrix.rotationPart()
			rot = tuple(matrix_rot.toQuat())
		else:
			raise "error: this should never happen!"
	return loc, rot

def getBoneTreeDepth(bone, currentCount):
	if (bone.hasParent()):
		currentCount = currentCount + 1
		return getBoneTreeDepth(bone.parent, currentCount)
	else:
		return currentCount
		
def meshNormalizedWeights(mesh):
	try: 
		groupNames, vWeightList = BPyMesh.meshWeight2List(mesh)
	except:
		return [],[]
	
	if not groupNames:
		return [],[]
		
	for i, vWeights in enumerate(vWeightList):
		tot = 0.0
		for w in vWeights:
			tot+=w
			
		#print 'i:%d tot:%f' %  (i, tot)
		if tot:
			for j, w in enumerate(vWeights):
				vWeights[j] = w/tot
				#if w/tot > 0:
					#print 'i:%d j:%d w:%f w/tot:%f' %  (i, j, w, vWeights[j])
	
	return groupNames, vWeightList
	
def getBoneWeights(boneName, weights):
	if boneName in weights[0]:
		group_index = weights[0].index(boneName)
		vgroup_data = [(j, weight[group_index]) for j, weight in enumerate(weights[1]) if weight[group_index]] 
	else:
		vgroup_data = []
	
	return vgroup_data
	
def saveBR2(filename):
	if not filename.lower().endswith('.br2'):
		filename += '.br2'
	
	if not BPyMessages.Warning_SaveOver(filename):
		return
	
	print "Start BR2 Export..."
	Blender.Window.WaitCursor(1)
	file = open( filename, 'wb')
	
	scene = Blender.Scene.GetCurrent()
	allObjects = scene.objects
	
	filedata = "// Nexus Buddy BR2 - Exported from Blender for import to Nexus Buddy 2\n"
	
	modelObs = {}
	modelMeshes = {}
	
	# will need list of these for multi-skeleton
	boneIds = {}
	
	for object in allObjects:
		if object.type == 'Armature':
			modelObs[object.name] = object
			
		if object.type == 'Mesh':
			print "Getting parent for mesh: %s" % object.name
			parentArmOb = BPyObject.getObjectArmature(object)
			if not parentArmOb.name in modelMeshes:
				modelMeshes[parentArmOb.name] = []
			modelMeshes[parentArmOb.name].append(object)

	for modelObName in modelObs.keys():
	
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
		
		for boneid, boneTuple in enumerate(sortedBones):
			bone = boneTuple[0]
			boneDepth = boneTuple[1]
			#boneid = boneid + 1 # World bone is zero
			
			position, orientationQuat = getTranslationOrientation(bone, file)
			
			# Get Inverse World Matrix for bone
			t = bone.matrix['ARMATURESPACE'].copy().invert()
			invWorldMatrix = Matrix([t[0][1], -t[0][0], t[0][2], t[0][3]],
								[t[1][1], -t[1][0], t[1][2], t[1][3]],
								[t[2][1], -t[2][0], t[2][2], t[2][3]],
								[t[3][1], -t[3][0], t[3][2], t[3][3]])
			
			outputBoneName = bone.name
			if len(outputBoneName) == 29:
				for item in armOb.getAllProperties():
					if (("B_" + outputBoneName) == item.getName()):
						outputBoneName = item.getData()
						print 'Decode Bone Name: "%s" >' % item.getName()
						print '                  "%s"' % item.getData()
						break
			
			filedata += '%d "%s" ' % (boneid + 1, outputBoneName)   # Adjust bone ids + 1 as zero is the World Bone
			
			parentBoneId = 0
			if bone.hasParent():
				parentBoneId = boneIds[bone.parent.name] + 1   # Adjust bone ids + 1 as zero is the World Bone
			
			filedata += '%d ' % parentBoneId
			filedata +='%.8f %.8f %.8f ' % (position[0], position[1] , position[2])
			filedata +='%.8f %.8f %.8f %.8f ' % (orientationQuat[1], orientationQuat[2], orientationQuat[3], orientationQuat[0]) # GR2 uses x,y,z,w for Quaternions rather than w,x,y,z
			filedata += '%.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f' % (
								invWorldMatrix[0][0], invWorldMatrix[0][1], invWorldMatrix[0][2], invWorldMatrix[0][3], 
								invWorldMatrix[1][0], invWorldMatrix[1][1], invWorldMatrix[1][2], invWorldMatrix[1][3],
								invWorldMatrix[2][0], invWorldMatrix[2][1], invWorldMatrix[2][2], invWorldMatrix[2][3],
								invWorldMatrix[3][0], invWorldMatrix[3][1], invWorldMatrix[3][2], invWorldMatrix[3][3])
			#End of bone line
			filedata += "\n"
		
		filedata += 'meshes:%d\n' % len(modelMeshes[modelObName])
		
		for meshObject in modelMeshes[modelObName]:
			
			mesh = meshObject.data
			meshName = meshObject.name
			
			filedata += 'mesh:"%s"\n' % meshName
			
			parentArmOb = BPyObject.getObjectArmature(meshObject)
			
			# Fetch long mesh names from Armature properties
			if len(meshName) == 19:
				for item in parentArmOb.getAllProperties():
					if ("M_" + meshName == item.getName()):
						meshName = item.getData()
						print 'Decode Mesh Name: %s > %s' % (item.getName(), item.getData())
						break
			
			#file.write('meshname:%s\n' % meshName)
			#file.write('parent Arm:%s\n' % parentArmOb)
			
			weights = meshNormalizedWeights(mesh)
			vertexBoneWeights = {}
			for boneName in boneIds.keys():
				vgroupDataForBone = getBoneWeights(boneName, weights)
				#file.write('bone:%s vg:%s\n' % (boneName, vgroupDataForBone))
				
				for vgData in vgroupDataForBone:
					vertexId = vgData[0]
					weight = vgData[1]
					if not vertexId in vertexBoneWeights:
						vertexBoneWeights[vertexId] = []
					vertexBoneWeights[vertexId].append((boneName, weight))
					#file.write('vert:%d bone:%s \n' % (vertexId, (boneName, weight)))
			
			grannyVertexBoneWeights = {}
			for vertId in vertexBoneWeights.keys():
				#file.write('vert:%d ' % vertId)
				
				rawBoneIdWeightTuples = []
				firstBoneId = 0
				for i in range(max(4,len(vertexBoneWeights[vertId]))):
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
				
				#if len(vertexBoneWeights[vertId]) > 4:
				#	print  "len(vertexBoneWeights[vertId]): %s" % len(vertexBoneWeights[vertId])
				#	print  "sortedBoneIdWeightTuples: %s" % sortedBoneIdWeightTuples
				
				# Pick first four highest weighted bones
				boneIdsList = []
				rawBoneWeightsList = []
				for i in range(4): 
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
					if runningTotal > 255:
						boneWeightsList[i] = weight - 1
						break
				
				if runningTotal < 255:
					boneWeightsList[0] = boneWeightsList[0] + 1
				
				runningTotal = 0
				for i, weight in enumerate(boneWeightsList):
					runningTotal = runningTotal + weight
				
				if runningTotal != 255:
					raise "Error: Vertex bone weights do not total 255!"
				
				if not vertId in grannyVertexBoneWeights:
					grannyVertexBoneWeights[vertId] = []
				grannyVertexBoneWeights[vertId] = (boneIdsList, boneWeightsList)
				
				#file.write('%s %s ' % (boneIdsList, boneWeightsList))
				#file.write("\n")
			
			position, orientationQuat = getTranslationOrientation(meshObject, file)
			
			#file.write('position:%.8f %.8f %.8f\n' % (position[0], position[1], position[2]))
			#file.write('orientationQuat:%.8f %.8f %.8f %.8f\n' % (orientationQuat[1], orientationQuat[2], orientationQuat[3], orientationQuat[0]))
			#file.write(meshName+"\n")
			
			filedata += "vertices\n"

			# Determine unique vertex/UVs for output
			uniqueVertSet = set()
			uniqueVertUVIndexes = {}
			uniqueVertUVs = []
			currentVertUVIndex = 0
			
			currentTriangleId = 0
			triangleVertUVIndexes = []
			
			for triangle in mesh.faces:
				vertIds = [v.index for v in triangle]
				vertIds = tuple(vertIds)
				triangleVertUVIndexes.append([])
				
				for i, uv in enumerate(triangle.uv):
					vertexId = vertIds[i]
					uvt = tuple(uv)
					vertSig = '%i|%.8f|%.8f' % (vertexId, uvt[0], uvt[1])
					
					if vertSig in uniqueVertSet:
						triangleVertUVIndex = uniqueVertUVIndexes[vertSig]
					else:
						uniqueVertSet.add(vertSig)
						uniqueVertUVIndexes[vertSig] = currentVertUVIndex
						uniqueVertUVs.append((vertexId, uvt[0], uvt[1]))
						triangleVertUVIndex = currentVertUVIndex
						currentVertUVIndex = currentVertUVIndex + 1
					
					triangleVertUVIndexes[currentTriangleId].append(triangleVertUVIndex)
				currentTriangleId = currentTriangleId + 1
			
			meshVerts = {}
			for i,vert in enumerate(mesh.verts):
				meshVerts[i] = vert
				
			# Write Vertices
			for uniqueVertUV in uniqueVertUVs:
			
				index = uniqueVertUV[0]
				vert = meshVerts[index]
				vertCoord = tuple(vert.co)
				vertNormal = tuple(vert.no)
				filedata +='%.8f %.8f %.8f ' % (vertCoord[0] + position[0], vertCoord[1] + position[1], vertCoord[2] +  position[2])
				filedata +='%.8f %.8f %.8f ' % vertNormal
				filedata +='%.8f %.8f ' % (uniqueVertUV[1], 1 - uniqueVertUV[2])

				if index in grannyVertexBoneWeights:
					vBoneWeightTuple = grannyVertexBoneWeights[index]
				else:
					raise "Error: Mesh has unweighted vertices!"
					#vBoneWeightTuple = ([-1,-1,-1,-1],[-1,-1,-1,-1]) # Unweighted vertex - raise error
				
				filedata +='%d %d %d %d ' % (vBoneWeightTuple[0][0], vBoneWeightTuple[0][1],vBoneWeightTuple[0][2],vBoneWeightTuple[0][3]) # Bone Ids
				filedata +='%d %d %d %d\n' % (vBoneWeightTuple[1][0], vBoneWeightTuple[1][1],vBoneWeightTuple[1][2],vBoneWeightTuple[1][3]) # Bone Weights
			
			# Write Triangles
			filedata += "triangles\n"
			for triangle in triangleVertUVIndexes:
				#filedata += '%i %i %i\n' % tuple(triangle)
				filedata += '%i %i %i\n' % (triangle[0],triangle[1],triangle[2])
	
	filedata += "end"
	file.write(filedata)
	file.close()
	Blender.Window.WaitCursor(0)
	print "End BR2 Export."

if __name__=='__main__':
	Blender.Window.FileSelector(saveBR2, "Export BR2", Blender.sys.makename(ext='.br2'))