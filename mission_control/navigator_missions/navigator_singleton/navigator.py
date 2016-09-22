#!/usr/bin/env python
from __future__ import division

import os
import numpy as np
import yaml

import genpy
import rospkg
from twisted.internet import defer
from txros import action, util, tf, NodeHandle
from pose_editor import PoseEditor2

from uf_common.msg import MoveToAction, PoseTwistStamped
from nav_msgs.msg import Odometry
from std_srvs.srv import SetBool, SetBoolRequest
from navigator_tools import rosmsg_to_numpy, odometry_to_numpy
import navigator_msgs.srv as navigator_srvs

class Navigator(object):
    def __init__(self, nh):
        self.nh = nh

        self.vision_proxies = {}
        self._load_vision_serivces()

        # If you don't want to use txros
        self.pose = None
        self.ecef_pose = None

    @util.cancellableInlineCallbacks
    def _init(self):
        self._moveto_action_client = yield action.ActionClient(self.nh, 'moveto', MoveToAction)
        self._odom_sub = yield self.nh.subscribe('odom', Odometry, lambda odom: setattr(self, 'pose', odometry_to_numpy(odom)[0]))
        self._ecef_odom_sub = yield self.nh.subscribe('absodom', Odometry, lambda odom: setattr(self, 'ecef_pose', odometry_to_numpy(odom)[0]))

        self._change_wrench = yield self.nh.get_service_client('/change_wrench', navigator_srvs.WrenchSelect)
        self.tf_listener = yield tf.TransformListener(self.nh)

        print "Waiting for odom..."
        yield self._odom_sub.get_next_message()  # We want to make sure odom is working before we continue
        yield self._ecef_odom_sub.get_next_message()

        defer.returnValue(self)

    @property
    @util.cancellableInlineCallbacks
    def tx_pose(self):
        last_odom_msg = yield self._odom_sub.get_next_message()
        defer.returnValue(odometry_to_numpy(last_odom_msg)[0])

    @property
    @util.cancellableInlineCallbacks
    def tx_ecef_pose(self):
        last_odom_msg = yield self._ecef_odom_sub.get_next_message()
        defer.returnValue(odometry_to_numpy(last_odom_msg)[0])

    @property
    def move(self):
        return PoseEditor2(self, self.pose)

    def vision_request(self, request_name, **kwargs):
        print "DEPREICATED: Please use new dictionary based system."
        return self.vision_proxies[request_name].get_response()

    def change_wrench(self, source):
        return self._change_wrench(navigator_srvs.WrenchSelectRequest(source))

    def search(self, *args, **kwargs):
        return Searcher(self, *args, **kwargs)

    def _load_vision_serivces(self, fname="vision_services.yaml"):
        rospack = rospkg.RosPack()
        config_file = os.path.join(rospack.get_path('navigator_missions'), 'navigator_singleton', fname)
        f = yaml.load(open(config_file, 'r'))

        for name in f:
            s_type = getattr(navigator_srvs, f[name]["type"])
            s_req = getattr(navigator_srvs, "{}Request".format(f[name]["type"]))
            s_args = f[name]['args']
            s_client = self.nh.get_service_client(f[name]["topic"], s_type)
            s_switch = self.nh.get_service_client(f[name]["topic"] + '/switch', SetBool)
            self.vision_proxies[name] = VisionProxy(s_client, s_req, s_args, s_switch)

class VisionProxy(object):
    def __init__(self, client, request, args, switch):
        self.client = client
        self.request = request
        self.args = args
        self.switch = switch

    def start(self):
        # Returns deferred object, make sure to yield on this (same for below)
        return self.switch(SetBoolRequest(data=True))

    def stop(self):
        return self.switch(SetBoolRequest(data=False))

    def get_response(self, **kwargs):
        s_args = dict(self.args.items() + kwargs.items())
        s_req = self.request(**s_args)

        return self.client(s_req)

class Searcher(object):
    def __init__(self, nav, vision_proxy, search_pattern, **kwargs):
        self.nav = nav
        self.vision_proxy = vision_proxy
        self.vision_kwargs = kwargs
        self.search_pattern = search_pattern

        self.object_found = False
        self.response = None

    def catch_error(self, failure):
        if failure.check(defer.CancelledError):
            print "SEARCHER - Cancelling defer."
        else:
            print "SEARCHER - There was an error."
            print failure.printTraceback()
            # Handle error

    @util.cancellableInlineCallbacks
    def start_search(self, timeout=60, loop=True, spotings_req=2, speed=.1):
        print "SEARCHER - Starting."
        looker = self._run_look(spotings_req).addErrback(self.catch_error)
        finder = self._run_search_pattern(loop, speed).addErrback(self.catch_error)

        start_pose = self.nav.move.forward(0)
        start_time = self.nav.nh.get_time()
        try:
            while self.nav.nh.get_time() - start_time < genpy.Duration(timeout):

                # If we find the object
                if self.object_found:
                    finder.cancel()
                    print "SEARCHER - Object found."
                    defer.returnValue(self.response)

                yield self.nav.nh.sleep(0.1)

        except KeyboardInterrupt:
            # This doesn't work...
            print "SEARCHER - Control C detected!"

        print "SEARCHER - Object NOT found. Returning to start position."
        finder.cancel()
        searcher.cancel()

        yield start_pose.go()

    @util.cancellableInlineCallbacks
    def _run_search_pattern(self, loop, speed):
        '''
        Look around using the search pattern.
        If `loop` is true, then keep iterating over the list until timeout is reached or we find it.
        '''

        def pattern():
            for pose in self.search_pattern:
                print "SEARCHER - going to next position."
                if type(pose) == list or type(pose) == np.ndarray:
                    yield self.nav.move.relative(pose).go(speed=speed)
                else:
                    yield pose.go(speed=speed)

                yield self.nav.nh.sleep(2)

        print "SEARCHER - Executing search pattern."

        if loop:
            while True:
                yield util.cancellableInlineCallbacks(pattern)()
        else:
            yield util.cancellableInlineCallbacks(pattern)()

    @util.cancellableInlineCallbacks
    def _run_look(self, spotings_req):
        '''
        Look for the object using the vision proxy.
        Only return true when we spotted the objects `spotings_req` many times (for false positives).
        '''
        spotings = 0
        print "SEARCHER - Looking for object."
        while spotings < spotings_req:
            resp = yield self.nav.vision_request(self.vision_proxy, **self.vision_kwargs)
            if resp.found:
                print "SEARCHER - Object found! {}/{}".format(spotings + 1, spotings_req)
                spotings += 1
            else:
                spotings = 0

            yield self.nav.nh.sleep(.5)

        if spotings >= spotings_req:
            self.object_found = True
            self.response = resp


@util.cancellableInlineCallbacks
def main():
    nh = yield NodeHandle.from_argv("testing")
    n = yield Navigator(nh)._init()
    yield n.vision_proxies['tester'].get_response()


if __name__ == '__main__':
    from twisted.internet import defer, reactor
    import signal
    import traceback
    reactor.callWhenRunning(main)
    reactor.run()
