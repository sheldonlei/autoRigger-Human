import maya.cmds as cmds

from .base import bone
from autoRigger import util
from utility.setup import outliner
from utility.rigging import joint


class Spine(bone.Bone):
    """ This module creates a biped spine rig"""

    def __init__(self, side, name, rig_type='Spine', length=6.0, segment=6):
        """ Initialize Spine class with side and name

        :param side: str
        :param name: str
        """

        self.interval = length/(segment-1)
        self.segment = segment
        self.scale = 0.5

        self.locs, self.jnts, self.ctrls, self.clusters = ([] for i in range(4))

        bone.Bone.__init__(self, side, name, rig_type)

    def assign_secondary_naming(self):
        for i in range(self.segment):
            self.locs.append('{}{}_loc'.format(self.base_name, i))
            self.jnts.append('{}{}_jnt'.format(self.base_name, i))
            self.ctrls.append('{}{}_ctrl'.format(self.base_name, i))
            self.clusters.append('{}{}_cluster'.format(self.base_name, i))
        # ik has different ctrl name
        self.ik_curve = '{}ik_curve'.format(self.base_name)
        self.ik = '{}_ik'.format(self.base_name)

    def set_controller_shape(self):
        self._shape = list(range(2))

        self._shape[0] = cmds.circle(nr=(0, 1, 0), c=(0, 0, 0), radius=1, s=8, name=self.namer.tmp)[0]
        cmds.scale(2, 2, 2, self._shape[0])

        self._shape[1] = cmds.circle(nr=(0, 1, 0), c=(0, 0, 0), radius=1, s=8, name=self.namer.tmp)[0]
        cmds.move(0, 0, 0.75, relative=1)
        cmds.rotate(0, 0, 90, self._shape[1])
        cmds.scale(0.5, 0.5, 0.5, self._shape[1])

    def create_locator(self):
        grp = cmds.group(em=1, n=self.loc_grp)

        for i in range(self.segment):
            spine = cmds.spaceLocator(n=self.locs[i])
            # root locator of spine parent to the spine group
            if i == 0:
                cmds.parent(spine, grp, relative=1)
                cmds.scale(self.scale, self.scale, self.scale, spine)
            # spine locator parent to the previous locator
            else:
                cmds.parent(spine, self.locs[i-1], relative=1)
                # move spine locator along +y axis
                cmds.move(0, self.interval, 0, spine, relative=1)

        cmds.parent(grp, util.G_LOC_GRP)
        return grp

    def create_joint(self):
        cmds.select(clear=1)

        for i, loc in enumerate(self.locs):
            loc_pos = cmds.xform(loc, q=1, t=1, ws=1)
            jnt = cmds.joint(p=loc_pos, name=self.jnts[i])
            cmds.setAttr(jnt + '.radius', self.scale)

        cmds.parent(self.jnts[0], util.G_JNT_GRP)
        return self.jnts[0]
    
    def place_controller(self):
        grp = cmds.group(em=1, name=self.ctrl_grp)
        
        for i, spine in enumerate(self.jnts):
            spine_pos = cmds.xform(spine, q=1, t=1, ws=1)
            spine_ctrl = cmds.duplicate(self._shape[1], name=self.ctrls[i])[0]
            if i == 0:
                self.global_ctrl = cmds.duplicate(self._shape[0], name=self.ctrl)[0]
                cmds.move(spine_pos[0], spine_pos[1], spine_pos[2], self.global_ctrl)
                cmds.makeIdentity(self.global_ctrl, apply=1, t=1, r=1, s=1)
                cmds.parent(spine_ctrl, self.global_ctrl, relative=1)
            elif i != 0:
                cmds.parent(spine_ctrl, self.ctrls[i-1])
            cmds.move(spine_pos[0], spine_pos[1], spine_pos[2]-5, spine_ctrl)
            cmds.move(spine_pos[0], spine_pos[1], spine_pos[2], spine_ctrl+'.scalePivot', spine_ctrl+'.rotatePivot', absolute=1)
            cmds.makeIdentity(spine_ctrl, apply=1, t=1, r=1, s=1)

            # parent line shape under curve transform (combine curve shape)
            line = cmds.curve(degree=1, point=[(spine_pos[0], spine_pos[1], spine_pos[2]), (spine_pos[0], spine_pos[1], spine_pos[2]-5)], name='{}line{}_ctrl'.format(self.base_name, i))
            line_shape = cmds.listRelatives(line, shapes=1)
            cmds.parent(line_shape, spine_ctrl, relative=1, shape=1)
            cmds.delete(line)

        cmds.parent(self.ctrl, grp)
        cmds.parent(grp, util.G_CTRL_GRP)
        return grp

    def build_ik(self):
        # Create Spine Curve
        curve_points = []
        for i, spine in enumerate(self.jnts):
            spine_pos = cmds.xform(spine, q=1, t=1, ws=1)
            curve_points.append(spine_pos)
        cmds.curve(p=curve_points, name=self.ik_curve)
        cmds.setAttr(self.ik_curve+'.visibility', 0)
        # turning off inherit transform avoid curve move/scale twice as much
        cmds.inheritTransform(self.ik_curve, off=1)

        # Create Spline IK
        cmds.ikHandle(startJoint=self.jnts[0], endEffector=self.jnts[-1], name=self.ik, curve=self.ik_curve, createCurve=False, parentCurve=1, roc=1, solver='ikSplineSolver')
        cmds.setAttr(self.ik+'.visibility', 0)
        cmds.parent(self.ik, util.G_CTRL_GRP)

        # Create Cluster
        cvs = cmds.ls('{}.cv[0:]'.format(self.ik_curve), fl=1)
        for i, cv in enumerate(cvs):
            cluster = cmds.cluster(cv, name=self.clusters[i])[-1]
            if i != 0:
                cmds.parent(cluster, '{}Handle'.format(self.clusters[i-1]), relative=False)
            else:
                cmds.parent(cluster, util.G_CTRL_GRP)
            cmds.setAttr(cluster+'.visibility', 0)

    def add_constraint(self):
        self.build_ik()
        for i in range(0, self.segment):
            spine_cluster = cmds.ls('{}Handle'.format(self.clusters[i]))
            spine_ctrl = cmds.ls(self.ctrls[i])
            cmds.pointConstraint(spine_ctrl, spine_cluster)
        cmds.connectAttr(self.ctrls[-1]+'.rotateY', '{}.twist'.format(self.ik))

    def lock_controller(self):
        for ctrl in self.ctrls:
            for transform in 'ts':
                for axis in 'xyz':
                    cmds.setAttr(ctrl+'.'+transform+axis, l=1, k=0)


class SpineQuad(bone.Bone):
    """ This module creates a quadruped spine rig """

    def __init__(self, side, name, rig_type='QuadSpine', length=6.0, segment=7):
        """ Initialize SpineQuad class with side and name

        :param side: str
        :param name: str
        """

        self.interval = length / (segment-1)
        self.segment = segment
        self.scale = 0.4

        self.locs, self.jnts, self.clusters, self.ctrls, self.ctrl_offsets = ([] for _ in range(5))
        self.master_ctrl = None
        self.master_offset = None
        self.ik_curve = None
        self.ik = None

        bone.Bone.__init__(self, side, name, rig_type)

    def assign_secondary_naming(self):

        for i in range(self.segment):
            self.locs.append('{}{}_loc'.format(self.base_name, i))
            self.jnts.append('{}{}_jnt'.format(self.base_name, i))

        for name in ['root', 'mid', 'top']:
            self.ctrls.append('{}{}_ctrl'.format(self.base_name, name))
            self.ctrl_offsets.append('{}{}_offset'.format(self.base_name, name))
            self.clusters.append('{}{}_cluster'.format(self.base_name, name))

        # ik has different name
        self.master_ctrl = '{}master_ctrl'.format(self.base_name, name)
        self.master_offset = '{}master_offset'.format(self.base_name, name)
        self.ik_curve = '{}ik_curve'.format(self.base_name)
        self.ik = '{}_ik'.format(self.base_name)

    def set_controller_shape(self):
        sphere = cmds.createNode('implicitSphere')
        self._shapes = list(range(2))

        self._shapes[0] = cmds.rename(cmds.listRelatives(sphere, p=1), self.namer.tmp)
        cmds.scale(0.3, 0.3, 0.3, self._shapes[0])

        self._shapes[1] = cmds.circle(nr=(1, 0, 0), c=(0, 0, 0), radius=1, s=8, name=self.namer.tmp)[0]
        cmds.scale(1, 1, 1, self._shapes[1])

    def create_locator(self):
        grp = cmds.group(em=1, n=self.loc_grp)

        for i in range(self.segment):
            spine = cmds.spaceLocator(n=self.locs[i])
            if i == 0:
                cmds.parent(spine, grp, relative=1)
                cmds.scale(self.scale, self.scale, self.scale, spine)
            else:
                cmds.parent(spine, self.locs[i-1], relative=1)
                # move spine locator along +z axis
                cmds.move(0, 0, self.interval, spine, relative=1)

        cmds.parent(grp, util.G_LOC_GRP)
        return grp

    def create_joint(self):
        cmds.select(clear=1)

        for i, loc in enumerate(self.locs):
            loc_pos = cmds.xform(loc, q=1, t=1, ws=1)
            jnt = cmds.joint(p=loc_pos, name=self.jnts[i])
            cmds.setAttr(jnt+'.radius', self.scale)

        cmds.parent(self.jnts[0], util.G_JNT_GRP)
        joint.orient_joint(self.jnts[0])
        return self.jnts[0]

    def place_controller(self):
        root_pos = cmds.xform(self.jnts[0], q=1, t=1, ws=1)
        root_rot = cmds.xform(self.jnts[0], q=1, ro=1, ws=1)
        top_pos = cmds.xform(self.jnts[-1], q=1, t=1, ws=1)
        top_rot = cmds.xform(self.jnts[-1], q=1, ro=1, ws=1)

        # master ctrl is positioned on top of root ctrl
        cmds.duplicate(self._shapes[0], name=self.master_ctrl)
        cmds.group(em=1, name=self.master_offset)
        cmds.move(root_pos[0], root_pos[1]+2, root_pos[2], self.master_offset)
        cmds.parent(self.master_ctrl, self.master_offset, relative=1)

        # root ctrl is positioned at the root joint
        # root ctrl needs to be accessed outside for parenting
        cmds.duplicate(self._shapes[1], name=self.ctrls[0])
        cmds.group(em=1, name=self.ctrl_offsets[0])
        cmds.move(root_pos[0], root_pos[1], root_pos[2], self.ctrl_offsets[0])
        cmds.rotate(root_rot[0], root_rot[1], root_rot[2], self.ctrl_offsets[0])
        cmds.parent(self.ctrls[0], self.ctrl_offsets[0], relative=1)

        # top ctrl is positioned at the top joint
        # top ctrl needs to be accessed outside for parenting
        cmds.duplicate(self._shapes[1], name=self.ctrls[-1])
        cmds.group(em=1, name=self.ctrl_offsets[-1])
        cmds.move(top_pos[0], top_pos[1], top_pos[2], self.ctrl_offsets[-1])
        cmds.rotate(top_rot[0], top_rot[1], top_rot[2], self.ctrl_offsets[-1])
        cmds.parent(self.ctrls[-1], self.ctrl_offsets[-1], relative=1)

        # mid ctrl is positioned at the middle joint / or middle two joint
        if self.segment % 2 != 0:
            index = int((self.segment-1)/2)
            mid_pos = cmds.xform(self.jnts[index], q=1, t=1, ws=1)
            mid_rot = cmds.xform(self.jnts[index], q=1, ro=1, ws=1)
        else:
            mid_upper_pos = cmds.xform(self.jnts[(self.segment+1) / 2], q=1, t=1, ws=1)
            mid_upper_rot = cmds.xform(self.jnts[(self.segment+1) / 2], q=1, ro=1, ws=1)
            mid_lower_pos = cmds.xform(self.jnts[(self.segment-1) / 2], q=1, t=1, ws=1)
            mid_lower_rot = cmds.xform(self.jnts[(self.segment-1) / 2], q=1, ro=1, ws=1)
            mid_pos = [(mid_upper_pos[0]+mid_lower_pos[0]) / 2, (mid_upper_pos[1]+mid_lower_pos[1]) / 2, (mid_upper_pos[2]+mid_lower_pos[2]) / 2]
            mid_rot = [(mid_upper_rot[0]+mid_lower_rot[0]) / 2, (mid_upper_rot[1]+mid_lower_rot[1]) / 2, (mid_upper_rot[2]+mid_lower_rot[2]) / 2]

        cmds.duplicate(self._shapes[1], name=self.ctrls[1])
        cmds.group(em=1, name=self.ctrl_offsets[1])
        cmds.move(mid_pos[0], mid_pos[1], mid_pos[2], self.ctrl_offsets[1])
        cmds.rotate(mid_rot[0], mid_rot[1], mid_rot[2], self.ctrl_offsets[1])
        cmds.parent(self.ctrls[1], self.ctrl_offsets[1], relative=1)

        # Cleanup
        outliner.batch_parent([self.ctrl_offsets[0], self.ctrl_offsets[1], self.ctrl_offsets[-1]], self.master_ctrl)
        cmds.parent(self.master_offset, util.G_CTRL_GRP)
        return self.master_ctrl

    def build_ik(self):
        # use ik auto create curve with 2 span (5 cvs), exclude the root joint
        cmds.ikHandle(startJoint=self.jnts[1], endEffector=self.jnts[-1], name=self.ik, createCurve=1,
                      parentCurve=False, roc=1, solver='ikSplineSolver', simplifyCurve=1, numSpans=2)
        cmds.rename('curve1', self.ik_curve)

        cmds.cluster(self.ik_curve+'.cv[0:1]', name=self.clusters[0])
        cmds.cluster(self.ik_curve+'.cv[2]', name=self.clusters[1])
        cmds.cluster(self.ik_curve+'.cv[3:4]', name=self.clusters[-1])

        cmds.setAttr(self.ik+'.visibility', 0)  # hide ik
        cmds.parent(self.ik, util.G_CTRL_GRP)

    def add_constraint(self):
        # each ik control is the parent of spine clusters
        self.build_ik()
        for i, cluster in enumerate(self.clusters):
            spine_cluster = cmds.ls('{}Handle'.format(cluster))
            spine_ctrl = cmds.ls(self.ctrls[i])
            cmds.parent(spine_cluster, spine_ctrl)

        # middle control is driven by the top and root control
        cmds.pointConstraint(self.ctrls[-1], self.ctrls[0], self.ctrls[1])
        cmds.parentConstraint(self.ctrls[0], self.jnts[0])

        # scaling of the spine
        arc_len = cmds.arclen(self.ik_curve, constructionHistory=1)
        cmds.rename(arc_len, self.ik_curve+'Info')
        cmds.parent(self.ik_curve, util.G_CTRL_GRP)
        cmds.setAttr(self.ik_curve+'.visibility', 0)

        # create curve length node and multiply node
        init_len = cmds.getAttr(self.ik_curve+'Info.arcLength')
        stretch_node = cmds.shadingNode('multiplyDivide', asUtility=1, name=self.ctrl+'Stretch')
        cmds.setAttr(stretch_node+'.operation', 2)
        cmds.setAttr(stretch_node+'.input2X', init_len)
        cmds.connectAttr(self.ik_curve+'Info.arcLength', stretch_node+'.input1X')
        for i in range(self.segment):
            cmds.connectAttr(stretch_node+'.outputX', self.jnts[i]+'.scaleX')

        # enable advance twist control
        cmds.setAttr(self.ik+'.dTwistControlEnable', 1)
        cmds.setAttr(self.ik+'.dWorldUpType', 4)
        cmds.connectAttr(self.ctrls[0]+'.worldMatrix[0]', self.ik+'.dWorldUpMatrix', f=1)
        cmds.connectAttr(self.ctrls[-1]+'.worldMatrix[0]', self.ik+'.dWorldUpMatrixEnd', f=1)

    def lock_controller(self):
        for ctrl in self.ctrls+[self.master_ctrl]:
            for transform in 's':
                for axis in 'xyz':
                    cmds.setAttr(ctrl+'.'+transform+axis, l=1, k=0)
