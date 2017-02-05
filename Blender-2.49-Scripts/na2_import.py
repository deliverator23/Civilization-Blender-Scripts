#!BPY
""" 
Name: 'Nexus Buddy 2 Animation (.na2)...'
Blender: 245
Group: 'Import'
Tooltip: 'Import from Nexus Buddy 2 file format (.na2)'
"""
# Original Milkshape ASCII Txt Import:
# Author: Markus Ilmola
# Email: markus.ilmola@pp.inet.fi
#
# Additional changes by Deliverator
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#

# import needed stuff
import os.path
import re
import math
from math import *
import Blender
from Blender import Mathutils, Window, Draw
from Blender.Mathutils import *

GLOBALS = {}
EVENT_NONE = 0
EVENT_EXIT = 1
EVENT_REDRAW = 2
EVENT_FILESEL = 3

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
	return Quaternion(cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy)

# takes a texture filename and tries to load it
def loadImage(path, filename):
	image = None
	try:
		image = Blender.Image.Load(os.path.abspath(filename))
	except IOError:
		print "Warning: Failed to or: " + filename + ". Trying short path instead...\n"
		try:
			image = Blender.Image.Load(os.path.dirname(path) + "/" + os.path.basename(filename))
		except IOError:
			print "Warning: Failed to load image: " + os.path.basename(filename) + "!\n"
	return image

# returns the next non-empty, non-comment line from the file
def getNextLine(file):
	ready = False
	while ready==False:
		line = file.readline()
		if len(line)==0:
			print "Warning: End of file reached."
			return line
		ready = True
		line = line.strip()
		if len(line)==0 or line.isspace():
			ready = False
		if len(line)>=2 and line[0]=='/' and line[1]=='/':
			ready = False
	return line	
	
# imports a MilkShape3D ascii file to the current scene
def import_na2(path):

	print("START NA2 IMPORT...")

	# get scene
	scn = Blender.Scene.GetCurrent()
	if scn==None:
		return "No scene to import to!"

	# open the file
	try:
		file = open(path, 'r')
	except IOError:
		return "Failed to open the file!"
	
	try:
		if not path.endswith(".na2"):
			raise IOError
	except IOError:
		return "Must be an NA2 file!"

	try:
		lines = getNextLine(file).split()
		if len(lines) != 2 or lines[0] != "FrameSets:":
			raise ValueError
		frameSets = int(lines[1])
	except ValueError:
		return "FrameSets is invalid!"
		
	for y in range(frameSets):
		try:
			lines = getNextLine(file).split()
			if len(lines) != 2 or lines[0] != "FrameCount:":
				raise ValueError
			numFrames = int(lines[1])
		except ValueError:
			return "FrameCount is invalid!"

		try:
			lines = getNextLine(file).split()
			if len(lines) != 2 or lines[0] != "FirstFrame:":
				raise ValueError
			firstFrame = int(lines[1])
		except ValueError:
			return "FirstFrame is invalid!"
			
		try:
			lines = getNextLine(file).split()
			if len(lines) != 2 or lines[0] != "LastFrame:":
				raise ValueError
			lastFrame = int(lines[1])
		except ValueError:
			return "LastFrame is invalid!"
			
		try:
			lines = getNextLine(file).split()
			if len(lines) != 2 or lines[0] != "FPS:":
				raise ValueError
			fps = int(lines[1])
		except ValueError:
			return "FPS is invalid!"

		try:
			lines = getNextLine(file).split()
			if len(lines) != 2 or lines[0] != "Bones:":
				raise ValueError
			numBones = int(lines[1])
		except ValueError:
			return "numBones is invalid!"
			
		boneNames = []
		boneFrameSets = []
		
		print("numBones %d" % numBones)
		
		for i in xrange(numBones):
			try:
				boneName = file.readline().strip()
				boneNames.append(boneName)
			except ValueError:
				return "bone name is invalid!"
				
			frames = []
			
			for j in xrange(numFrames):
				try:
					lines = getNextLine(file).split()
					#print(lines)
					if len(lines) != 16:
						raise ValueError
					frames.append( \
						[ \
							[float(lines[0]), float(lines[1]), float(lines[2]), float(lines[3])], \
							[float(lines[4]), float(lines[5]), float(lines[6]), float(lines[7])], \
							[float(lines[8]), float(lines[9]), float(lines[10]), float(lines[11])], \
							[float(lines[12]), float(lines[13]), float(lines[14]), float(lines[15])] \
						] \
					)    
				except ValueError:
					return "bone frame matrix invalid!"
				
			boneFrameSets.append(frames)
			
		scene = Blender.Scene.GetCurrent()
		scene.getRenderingContext().fps = fps
		currentFrame = scene.getRenderingContext().currentFrame()
		scene.getRenderingContext().startFrame(1)
		scene.getRenderingContext().endFrame(currentFrame + lastFrame)
		
		allObjects = scene.objects
		armOb = allObjects[0]
		pose = armOb.getPose()
		action = armOb.getAction()
		if not action:
			action = Blender.Armature.NLA.NewAction()
			action.setActive(armOb)
		
		for y in xrange(numFrames): 
			for z in xrange(numBones):
				boneName = boneNames[z]
				x = boneFrameSets[z][y]
				poseBone = pose.bones[boneName]
				if poseBone != None:
					matrix = Matrix([-x[1][0],-x[1][1],-x[1][2],0], 
									[x[0][0],x[0][1],x[0][2],0],
									[x[2][0],x[2][1],x[2][2],0],
									[x[3][0],x[3][1],x[3][2],1])
									
					poseBone.poseMatrix = matrix
					pose.update()
					poseBone.insertKey(armOb, currentFrame + y, Blender.Object.Pose.LOC, True)
					poseBone.insertKey(armOb, currentFrame + y, Blender.Object.Pose.ROT, True)
			
			#for z in xrange(numBones):
			#	boneName = boneNames[z]
			#	x = boneFrameSets[z][y]
			#	poseBone = pose.bones[boneName]
			#	if poseBone != None:
			#		
			#		if (y == 0) and boneName.startswith("Staff_"):
			#			print(boneName)
			#			bone = armOb.data.bones[boneName]
			#			print(bone.matrix)
			#			print(poseBone.poseMatrix)

	Blender.Redraw()

	return ""

# load the model
def fileCallback(filename):
	error = import_na2(filename)
	if error!="":
		Blender.Draw.PupMenu("An error occured during import: " + error + "|Not all data might have been imported succesfully.", 2)

def write_ui():
	Blender.Window.FileSelector(fileCallback, 'Import')
	
if __name__ == '__main__':
	if not set:
		Draw.PupMenu('Error%t|A full install of python2.3 or python 2.4+ is needed to run this script.')
	else:
		write_ui()
