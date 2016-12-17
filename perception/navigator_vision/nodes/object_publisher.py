
class ObjectPublisher(object):
    def __init__(self, nh):
        self.nh = nh
        self.load()
        self.found_object_ids = []
        self.predefined_objects = {}

    def init_(self):
        self.db_serv = yield self.nh.service_proxy('/database/requests', ObjectDBQuery)
        self.convert_serv = yield self.nh.service_proxy('/convert', CoordinateConversion)
        self.listener = yield self.nh.subscribe('/database/objects', PerceptionObjectArray. self.db_cb)

    def db_cb(self, obj):
        for o in obj.objects:
            if o.id not in self.found_object_ids:
                pos = nt.rosmsg_to_numpy(o.position)
                value, correct_o = min(self.predefined_objects, key=lambda x: npl.norm(x - pos))
                if value < 3.0:
                    self.found_object_ids.append(o.id)
                    req = ObjectDBQuery()
                    req.cmd = "lock {} {}".format(o.id, correct_o)

    def load(self, file):
        f = open(file, 'rb')
        for l in f:
        	l = l.split()
            name = l[0]
            pos1 = l[1]
            pos2 = l[2]
            req = CoordinateConversion()
            req.point = Point(pos1, pos2, 0)
            req.frame = "lla"
            coords = yield self.convert_serv(req)
            coords = coords.enu
            self.predefined_objects[name] = coords[:2]

if __name__ == "main":
