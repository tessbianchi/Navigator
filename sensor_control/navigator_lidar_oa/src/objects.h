#pragma once
#include <vector>
#include <iostream>
#include "ConnectedComponents.h"

/*
	This gives you a list of objects, where every objects that is classified as 'the same' is given a persistant id.
	This list does not persist past what is seen in immediate view
*/

class ObjectTracker{

private:
	std::vector<objectXYZ> saved_objects;
	float diff_thresh;
	int curr_id = 0;

public:

	ObjectTracker(float diff_thresh=.3){
		this->diff_thresh = diff_thresh;

	}

	std::vector<objectXYZ> add_objects(std::vector<objectXYZ> objects){
		saved_objects.clear();
		std::vector<objectXYZ> new_objects;
		for(auto obj : objects){
			float min_dist = 100;
			objectXYZ min_obj;
			for(auto s_obj : saved_objects){
				float xdiff = pow(obj.position.x - s_obj.position.x, 2);
				float ydiff = pow(obj.position.y - s_obj.position.y, 2);
				float zdiff = pow(obj.position.z - s_obj.position.z, 2);
				float diff = sqrt(xdiff+ydiff+zdiff);
				// TODO MAKE THIS A ROS PARAM
				if(diff < min_dist){
					min_dist = diff;
					min_obj = s_obj;
				}
			}
			auto new_obj = objectXYZ();
			if(min_dist < diff_thresh){
				new_obj.id = min_obj.id;
			}else{
				new_obj.id = curr_id;
				++curr_id;
			}
			new_objects.push_back(new_obj);

		}
		saved_objects.insert(saved_objects.end(), new_objects.begin(), new_objects.end());
		return saved_objects;
	}
};
