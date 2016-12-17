#!/usr/bin/env python
from __future__ import division
import txros
import std_srvs.srv
import numpy as np
import tf
import tf.transformations as trns
from navigator_msgs.msg import ShooterDoAction, ShooterDoActionGoal
from navigator_msgs.srv import CameraToLidarTransform,CameraToLidarTransformRequest
from geometry_msgs.msg import Point
from std_srvs.srv import SetBool, SetBoolRequest
from twisted.internet import defer
from image_geometry import PinholeCameraModel
from visualization_msgs.msg import Marker,MarkerArray
import navigator_tools
from navigator_tools import fprint, MissingPerceptionObject
import genpy

class DetectDeliverMission:
    # Note, this will be changed when the shooter switches to actionlib
    shoot_distance_meters = 3.1
    theta_offset = np.pi / 2.0
    spotings_req = 1
    circle_radius = 10
    platform_radius = 0.925
    search_timeout_seconds = 300
    SHAPE_CENTER_TO_BIG_TARGET = 0.42
    SHAPE_CENTER_TO_SMALL_TARGET = -0.42
    NUM_BALLS = 4
    LOOK_AT_TIME = 5

    def __init__(self, navigator):
        self.navigator = navigator
        self.cameraLidarTransformer = navigator.nh.get_service_client("/camera_to_lidar/right_right_cam", CameraToLidarTransform)
        self.shooterLoad = txros.action.ActionClient(
            self.navigator.nh, '/shooter/load', ShooterDoAction)
        self.shooterFire = txros.action.ActionClient(
            self.navigator.nh, '/shooter/fire', ShooterDoAction)
        self.identified_shapes = {}
        self.last_shape_error = ""
        self.last_lidar_error = ""
        self.shape_pose = None

    def _bounding_rect(self,points):
        np_points = map(navigator_tools.point_to_numpy, points)
        xy_max = np.max(np_points, axis=0)
        xy_min = np.min(np_points, axis=0)
        return np.append(xy_max, xy_min)

    @txros.util.cancellableInlineCallbacks
    def set_shape_and_color(self):
        target = yield self.navigator.mission_params["detect_deliver_target"].get()
        if target == "BIG":
            self.target_offset_meters = self.SHAPE_CENTER_TO_BIG_TARGET
        elif target == "SMALL":
            self.target_offset_meters = self.SHAPE_CENTER_TO_SMALL_TARGET
        self.Shape = yield self.navigator.mission_params["detect_deliver_shape"].get()
        self.Color = yield self.navigator.mission_params["detect_deliver_color"].get()
        fprint("Color={} Shape={} Target={}".format(self.Color, self.Shape, target), title="DETECT DELIVER",  msg_color='green')

    @txros.util.cancellableInlineCallbacks
    def get_waypoint(self):
        res = yield self.navigator.database_query("shooter")
        if not res.found:
            fprint("shooter waypoint not found", title="DETECT DELIVER",  msg_color='red')
            raise MissingPerceptionObject("shooter", "Detect Deliver Waypoint not found")
        self.waypoint_res = res

    @txros.util.cancellableInlineCallbacks
    def get_any_shape(self):
        shapes = yield self.get_shape()
        if shapes.found:
            for shape in shapes.shapes.list:
                normal_res = yield self.get_normal(shape)
                if normal_res.success:
                    enu_cam_tf = yield self.navigator.tf_listener.get_transform('/enu', '/'+shape.header.frame_id, shape.header.stamp)
                    self.update_shape(shape, normal_res, enu_cam_tf)
                    defer.returnValue( ((shape.Shape, shape.Color), self.identified_shapes[(shape.Shape, shape.Color)]) )
                else:
                    fprint("Normal not found Error={}".format(normal_res.error), title="DETECT DELIVER", msg_color='red')
        else:
            fprint("shape not found Error={}".format(shapes.error), title="DETECT DELIVER", msg_color="red")
        defer.returnValue(False)

    @txros.util.cancellableInlineCallbacks
    def circle_search(self):
        platform_np = navigator_tools.rosmsg_to_numpy(self.waypoint_res.objects[0].position)
        yield self.navigator.move.look_at(platform_np).set_position(platform_np).backward(self.circle_radius).yaw_left(90,unit='deg').go(move_type="drive")

        done_circle = False
        @txros.util.cancellableInlineCallbacks
        def do_circle():
            yield self.navigator.move.circle_point(platform_np).go()
            done_circle = True

        circle_defer = do_circle()
        while not done_circle:
            res = yield self.get_any_shape()
            if res == False:
                yield self.navigator.nh.sleep(0.25)
                continue
            fprint("Shape ({}found, using normal to look at other 3 shapes if needed".format(res[0]), title="DETECT DELIVER", msg_color="green")
            #  circle_defer.cancel()
            shape_color, found_shape_pose = res
            if self.correct_shape(shape_color):
                self.shape_pose = found_shape_pose
                return
            #Pick other 3 to look at
            rot_right = np.array([[0, -1], [1, 0]])
            (shape_point, shape_normal) = found_shape_pose
            rotated_norm = np.append(rot_right.dot(shape_normal[:2]), 0)
            center_point = shape_point - shape_normal * (self.platform_radius/2.0)
            
            point_opposite_side = center_point - shape_normal * self.circle_radius
            move_opposite_side = self.navigator.move.set_position(point_opposite_side).look_at(center_point).yaw_left(90, unit='deg')

            left_or_whatever_point = center_point + rotated_norm * self.circle_radius
            move_left_or_whatever = self.navigator.move.set_position(left_or_whatever_point).look_at(center_point).yaw_left(90, unit='deg')

            right_or_whatever_point = center_point - rotated_norm * self.circle_radius
            move_right_or_whatever = self.navigator.move.set_position(right_or_whatever_point).look_at(center_point).yaw_left(90, unit='deg')

            yield self.search_sides((move_left_or_whatever, move_opposite_side, move_right_or_whatever))
            return
        fprint("No shape found after complete circle",title="DETECT DELIVER", msg_color='red')
        raise Exception("No shape found on platform")

    def update_shape(self, shape_res, normal_res, tf):
       self.identified_shapes[(shape_res.Shape, shape_res.Color)] = self.get_shape_pos(normal_res, tf)

    def correct_shape(self, (shape,color)):
        return (self.Color == "ANY" or self.Color == color) and (self.Shape == "ANY" or self.Shape == shape)

    @txros.util.cancellableInlineCallbacks
    def search_side(self):
        fprint("Searching side",title="DETECT DELIVER", msg_color='green')
        start_time = self.navigator.nh.get_time()
        while self.navigator.nh.get_time() - start_time < genpy.Duration(self.LOOK_AT_TIME):
            res = yield self.get_any_shape()
            if not res == False:
                defer.returnValue(res)
            yield self.navigator.nh.sleep(0.1)
        defer.returnValue(False)

    @txros.util.cancellableInlineCallbacks
    def search_sides(self, moves):
        for move in moves:
            yield move.go(move_type="drive")
            res = yield self.search_side()
            if res == False:
                fprint("No shape found on side",title="DETECT DELIVER", msg_color='red')
                continue
            shape_color, found_pose = res
            if self.correct_shape(shape_color):
                self.shape_pose = found_pose
                return
            fprint("Saw (Shape={}, Color={}) on this side".format(shape_color[0], shape_color[1]),title="DETECT DELIVER", msg_color='green')

    @txros.util.cancellableInlineCallbacks
    def search_shape(self):
        shapes = yield self.get_shape()
        if shapes.found:
            for shape in shapes.shapes.list:
                normal_res = yield self.get_normal(shape)
                if normal_res.success:
                    enu_cam_tf = yield self.navigator.tf_listener.get_transform('/enu', '/'+shape.header.frame_id, shape.header.stamp)
                    if self.correct_shape(shape):
                        self.shape_pose = self.get_shape_pos(normal_res, enu_cam_tf)
                        defer.returnValue(True)
                    self.update_shape(shape, normal_res, enu_cam_tf)

                else:
                    if not self.last_lidar_error == normal_res.error:
                        fprint("Normal not found Error={}".format(normal_res.error), title="DETECT DELIVER", msg_color='red')
                    self.last_lidar_error = normal_res.error
        else:
            if not self.last_shape_error == shapes.error:
                fprint("shape not found Error={}".format(shapes.error), title="DETECT DELIVER", msg_color="red")
            self.last_shape_error = shapes.error
        defer.returnValue(False)

    def select_backup_shape(self):
        for (shape, color), point_normal in self.identified_shapes.iteritems():
            self.shape_pose = point_normal
            if self.Shape == shape or self.Color == color:
                fprint("Correct shape not found, resorting to shape={} color={}".format(shape, color), title="DETECT DELIVER",  msg_color='yellow')
                return
        if self.shape_pose == None:
            raise Exception("None seen")
        fprint("Correct shape not found, resorting to random shape", title="DETECT DELIVER",  msg_color='yellow')

    @txros.util.cancellableInlineCallbacks
    def align_to_target(self):
        if self.shape_pose == None:
            self.select_backup_shape()
        shooter_baselink_tf = yield self.navigator.tf_listener.get_transform('/base_link','/shooter')
        goal_point, goal_orientation = self.get_aligned_pose(self.shape_pose[0], self.shape_pose[1])
        move = self.navigator.move.set_position(goal_point).set_orientation(goal_orientation).forward(self.target_offset_meters)
        move = move.left(-shooter_baselink_tf._p[1]).forward(-shooter_baselink_tf._p[0]) #Adjust for location of shooter
        fprint("Aligning to shoot at {}".format(move), title="DETECT DELIVER", msg_color='green')
        yield move.go(move_type="drive")

    def get_shape(self):
        return self.navigator.vision_proxies["get_shape"].get_response(Shape="ANY", Color="ANY")

    def get_aligned_pose(self, enupoint, enunormal):
        aligned_position = enupoint + self.shoot_distance_meters * enunormal  # moves x meters away
        angle = np.arctan2(-enunormal[0], enunormal[1])
        aligned_orientation = trns.quaternion_from_euler(0, 0, angle)  # Align perpindicular
        return (aligned_position, aligned_orientation)

    def get_shape_pos(self, normal_res, enu_cam_tf):
        enunormal = enu_cam_tf.transform_vector(navigator_tools.rosmsg_to_numpy(normal_res.normal))
        enupoint = enu_cam_tf.transform_point(navigator_tools.rosmsg_to_numpy(normal_res.closest))
        return (enupoint, enunormal)

    @txros.util.cancellableInlineCallbacks
    def get_normal(self, shape):
        req = CameraToLidarTransformRequest()
        req.header = shape.header
        req.point = Point()
        req.point.x = shape.CenterX
        req.point.y = shape.CenterY
        rect = self._bounding_rect(shape.points)
        req.tolerance = int(min(rect[0]-rect[3],rect[1]-rect[4])/2.0)
        normal_res = yield self.cameraLidarTransformer(req)
        if not self.normal_is_sane(normal_res.normal):
            normal_res.success = False
            normal_res.error = "UNREASONABLE NORMAL"
        defer.returnValue(normal_res)

    def normal_is_sane(self, vector3):
         return abs(navigator_tools.rosmsg_to_numpy(vector3)[1]) < 0.4

    @txros.util.cancellableInlineCallbacks
    def shoot_all_balls(self):
        for i in range(self.NUM_BALLS):
            goal = yield self.shooterLoad.send_goal(ShooterDoAction())
            fprint("Loading Shooter {}".format(i), title="DETECT DELIVER",  msg_color='green')
            res = yield goal.get_result()
            yield self.navigator.nh.sleep(2)
            goal = yield self.shooterFire.send_goal(ShooterDoAction())
            fprint("Firing Shooter {}".format(i), title="DETECT DELIVER",  msg_color='green')
            res = yield goal.get_result()

    @txros.util.cancellableInlineCallbacks
    def find_and_shoot(self):
        yield self.navigator.vision_proxies["get_shape"].start()
        yield self.set_shape_and_color()  # Get correct goal shape/color from params
        yield self.get_waypoint()  # Get waypoint of shooter target
        yield self.circle_search()  # Go to waypoint and circle until target found
        yield self.align_to_target()
        yield self.shoot_all_balls()
        yield self.navigator.vision_proxies["get_shape"].stop()

@txros.util.cancellableInlineCallbacks
def setup_mission(navigator):
    color = "RED"
    shape = "TRIANGLE"
    #color = yield navigator.mission_params["scan_the_code_color3"].get()
    fprint("Setting search shape={} color={}".format(shape, color), title="DETECT DELIVER",  msg_color='green')
    yield navigator.mission_params["detect_deliver_shape"].set(shape)
    yield navigator.mission_params["detect_deliver_color"].set(color)

@txros.util.cancellableInlineCallbacks
def main(navigator, **kwargs):
    yield setup_mission(navigator)
    fprint("STARTING MISSION", title="DETECT DELIVER",  msg_color='green')
    mission = DetectDeliverMission(navigator)
    yield mission.find_and_shoot()
    fprint("ENDING MISSION", title="DETECT DELIVER",  msg_color='green')
