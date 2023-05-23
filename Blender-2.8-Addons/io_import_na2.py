bl_info = {
    "name": "Import Civilization Animation (.na2)",
    "author": "Deliverator, Sukritact",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Civilization Animation (.na2)",
    "description": "Import Civilization Animation (.na2)",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"}

import bpy
from bpy.props import BoolProperty, IntProperty, EnumProperty, StringProperty
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.io_utils import ImportHelper
from datetime import datetime, timedelta

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
    return Matrix([cp * cy, cp * sy, -sp], [sr * sp * cy + cr * -sy, sr * sp * sy + cr * cy, sr * cp],
                  [cr * sp * cy + -sr * -sy, cr * sp * sy + -sr * cy, cr * cp])


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
    return Quaternion(cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
                      cr * cp * sy - sr * sp * cy)


# returns the next non-empty, non-comment line from the file
def getNextLine(file):
    ready = False
    while ready == False:
        line = file.readline()
        if len(line) == 0:
            print("Warning: End of file reached.")
            return line
        ready = True
        line = line.strip()
        if len(line) == 0 or line.isspace():
            ready = False
        if len(line) >= 2 and line[0] == '/' and line[1] == '/':
            ready = False
    return line


def import_na2(path):
    print("START NA2 IMPORT...")

    # get scene
    scene = bpy.context.scene
    if scene == None:
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

        print("Number of bones: %d" % numBones)
        print("Number of frames: %d" % numFrames)

        for i in range(numBones):
            try:
                boneName = file.readline().strip()
                boneNames.append(boneName)
            except ValueError:
                return "bone name is invalid!"

            frames = []

            for j in range(numFrames):
                try:
                    lines = getNextLine(file).split()
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

        time_before = datetime.now()

        scene.render.fps = fps
        currentFrame = scene.frame_current
        scene.frame_start = 1
        scene.frame_end = currentFrame + lastFrame

        allObjects = scene.objects
        armOb = allObjects[0]

        bpy.context.view_layer.objects.active = armOb
        bpy.ops.object.mode_set(mode='POSE')

        blender_action = bpy.context.blend_data.actions.new("Action")
        if armOb.animation_data is None:
            armOb.animation_data_create()
        armOb.animation_data.action = blender_action

        prev_bone_matrix = {}
        prev_matrix = None

        for y in range(numFrames):

            skipped_bones = 0
            frame_time_before = datetime.now()

            for z in range(1, numBones):
                boneName = boneNames[z]
                x = boneFrameSets[z][y]
                poseBone = armOb.pose.bones[boneName]
                if poseBone != None:

                    animMatrix = Matrix([[x[2][0], x[0][0], x[1][0], x[3][0]],
                                         [x[2][1], x[0][1], x[1][1], x[3][1]],
                                         [x[2][2], x[0][2], x[1][2], x[3][2]],
                                         [0, 0, 0, 1]])

                    if boneName in prev_bone_matrix:
                        prev_matrix = prev_bone_matrix[boneName]

                    prev_bone_matrix[boneName] = animMatrix

                    if prev_matrix and prev_matrix == animMatrix:
                        skipped_bones += 1
                        continue
                    else:
                        poseBone.matrix = animMatrix
                        bpy.context.view_layer.update()

                        poseBone.keyframe_insert(data_path="location", frame=currentFrame + y)
                        poseBone.keyframe_insert(data_path="rotation_quaternion", frame=currentFrame + y)

            frame_time_after = datetime.now()
            frame_diff = frame_time_after - frame_time_before
            frame_diff = frame_diff / timedelta(microseconds=1)
            print("Frame", str(y + 1), "/", numFrames, "loaded.", "Skipped bones:", skipped_bones, "; Took",
                  str(frame_diff), "microseconds.")

        time_after = datetime.now()
        diff = time_after - time_before
        print("Setting pose matrices done. Took ", str(diff.seconds), "seconds.")

    print("End.")

    return ""


###### IMPORT OPERATOR #######
class Import_na2(bpy.types.Operator, ImportHelper):
    bl_idname = "import_shape.na2"
    bl_label = "Import NA2 (.na2)"
    bl_description = "Import a Civilization Animation .na2 file"
    filename_ext = ".na2"
    filter_glob = StringProperty(default="*.na2", options={'HIDDEN'})

    filepath = StringProperty(name="File Path", description="Filepath used for importing the file", maxlen=1024,
                              subtype='FILE_PATH')

    def execute(self, context):
        import_na2(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


### REGISTER ###

def menu_func(self, context):
    self.layout.operator(Import_na2.bl_idname, text="Civilization Animation (.na2)")


def register():
    from bpy.utils import register_class
    register_class(Import_na2)

    bpy.types.TOPBAR_MT_file_import.append(menu_func)


def unregister():
    from bpy.utils import unregister_class
    unregister_class(Import_na2)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func)


if __name__ == "__main__":
    register()
