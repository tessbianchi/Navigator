
import atexit


class ObjectRecorder(object):

    def __init__(self, nh):
        self.nh = nh
        self.load()
        self.found_objects = {}

    def init_(self):
        self.db_serv = yield self.nh.service_proxy('/database/requests', ObjectDBQuery)
        self.convert_serv = yield self.nh.service_proxy('/convert', CoordinateConversion)
        self.listener = yield self.nh.subscribe('/database/objects', PerceptionObjectArray. self.db_cb)

    def db_cb(self, obj):
        for o in obj.objects:
            if o.id not in self.found_objects or (o.id in self.found_objects and self.found_objects[o.id] != o.name):
                req = CoordinateConversion
                req.point = Point(o.position.x, o.position.y, 0)
                req.frame = "enu"
                coords = yield self.convert_serv(req)
                self.found_objects[o.id] = (o.name, coords.lla)

    def load(self, file):
        f = open("recorded_objs.txt", 'w+')
        for o in self.found_objects:
            f.writeLine(o)

if __name__ == "main":
    pass