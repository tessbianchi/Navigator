#!/usr/bin/env python
import txros
import navigator_tools as nt
from navigator_tools import fprint, MissingPerceptionObject
from twisted.internet import defer
from navigator_tools import rosmsg_to_numpy
import numpy as np


def get_closest_objects(position, objects, max_len=3, max_dist=30):
    num = len(objects)
    idx = max_len
    if num < max_len:
        idx = num
    objects = sorted(objects, key=lambda x: np.linalg.norm(position - rosmsg_to_numpy(x.position)))
    objects = objects[:idx]
    dists = map(lambda x: np.linalg.norm(position - rosmsg_to_numpy(x.position)), objects)
    final_objs = []
    for i, d in enumerate(dists):
        if d < max_dist:
            final_objs.append(objects[i])
        else:
            break
    return final_objs


@txros.util.cancellableInlineCallbacks
def wait_for_object(objec, helper, nh):
    helper.set_looking_for(objec)
    while not helper.is_found_func():
        yield nh.sleep(1)


@txros.util.cancellableInlineCallbacks
def go_to_objects(navigator, position, objs):
    objects = get_closest_objects(position, objs)
    for o in objects:
        fprint("MOVING TO OBJECT WITH ID {}".format(o.id), msg_color="green")
        yield navigator.nh.sleep(5)
        pos = nt.rosmsg_to_numpy(o.position)
        yield navigator.move.look_at(pos).set_position(pos).backward(7).go()


@txros.util.cancellableInlineCallbacks
def myfunc(navigator, looking_for, center_marker):
    high_prob_objs = ["shooter", "dock", "scan_the_code", "totem"]
    pos = yield navigator.tx_pose
    pos = pos[0]
    if center_marker is None or center_marker == "None":
        defer.returnValue(True)
    center_marker = center_marker.name

    try:
        print center_marker
        center_marker = yield navigator.database_query(object_name=center_marker)
        center_marker = center_marker.objects[0]
    except Exception as e:
        print e
        fprint("A marker has not been set", msg_color="red")
        defer.returnValue(True)

    mark_pos = nt.rosmsg_to_numpy(center_marker.position)
    dist = np.linalg.norm(pos - mark_pos)
    if dist > 10:
        yield navigator.move.set_position(mark_pos).go()

    if looking_for is None or looking_for == 'None':
        defer.returnValue(True)

    pos = yield navigator.tx_pose
    pos = pos[0]

    if looking_for in high_prob_objs:
        try:
            obj = yield navigator.database_query(object_name=looking_for)
            fprint("EXPLORER FOUND OBJECT", msg_color="blue")
            yield navigator.database_query(cmd="lock {} {}".format(obj.id, looking_for))
            defer.returnValue(True)
        except MissingPerceptionObject:
            fprint("The object {} is not in the database".format(looking_for), msg_color="red")
    try:
        objs = yield navigator.database_query(object_name="all")
        objs = get_closest_objects(pos, objs.objects)
    except Exception as e:
        print e
        defer.returnValue(False)

    for o in objs:
        obj_pos = nt.rosmsg_to_numpy(o.position)
        yield navigator.move.look_at(obj_pos).set_position(mark_pos).backward(7).go()
        cam_obj = yield navigator.camera_database_query(object_name=looking_for, id=o.id)
        if cam_obj.found:
            yield navigator.database_query(cmd="lock {} {}".format(o.id, looking_for))
            fprint("EXPLORER FOUND OBJECT", msg_color="blue")
            defer.returnValue(True)

    fprint("NO OBJECT FOUND", msg_color="blue")
    defer.returnValue(False)


@txros.util.cancellableInlineCallbacks
def main(navigator, **kwargs):
    center_marker = kwargs["center_marker"]
    looking_for = kwargs["looking_for"]

    # FOR TESTING
    # center_marker = "Shooter"
    # looking_for = "scan_the_code"

    navigator.change_wrench("autonomous")
    yield navigator.nh.sleep(.1)
    good = yield myfunc(navigator, looking_for, center_marker)
    defer.returnValue(good)
