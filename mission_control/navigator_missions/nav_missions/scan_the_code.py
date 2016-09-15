#!/usr/bin/env python
import txros
import tf
import numpy as np
import navigator_tools
import math as m
import matplotlib.pyplot as plt

@txros.util.cancellableInlineCallbacks
def main(navigator):
    # activate stereo model fitter
    navigator.change_wrench("autonomous")
    granularity = 6
    distance = 11
    angle = 360/granularity * 3.14/180
    n = [0,0]
    # this is the absolute position, give it the relative position option
    base = [3,-17,0]

    for i in range(0,granularity+1):
        n[0] = distance * m.cos(i*angle) ; n[1] = distance * m.sin(i*angle)
        new = [n[0]+base[0], n[1]+base[1],0]
        yield navigator.move.set_position(new).look_at([3,-17,0]).go()
        # call the rosservice, get status
        # if the things isn't found, keep going
        # if the thing is found, wait for colors until timeout, and then if it works, return


   # if it doesn't work fill in random colors, die



    yield navigator.nh.sleep(2)












