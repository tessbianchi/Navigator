#include <navigator_vision_lib/color_tracker.hpp>


void ColorTracker::track(cv::Mat frame_left, std::vector<cv::Point2f> points_small, double image_proc_scale){

  if(colors_found == 3){
    mission_complete = 1;
  }

  double reset_scaling = 1 / image_proc_scale;
  std::vector<cv::Point> mypoints;



  cv::Mat draw = frame_left.clone();
  for (size_t i = 0; i < points_small.size(); i++)
  {
      cv::Point2d pt_L = points_small[ i ];
      pt_L = pt_L * reset_scaling;
      mypoints.push_back(pt_L);
      cv::circle(draw, pt_L, 5, cv::Scalar(0,0,0), -1);

  }

  cv::Point pts[1][4];
  pts[0][0] = mypoints[0];
  pts[0][1] = mypoints[1];
  pts[0][2] = mypoints[2];
  pts[0][3] = mypoints[3];

  const cv::Point* points[1] = {pts[0]};
  int npoints = 4;

  // Create the mask with the polygon
  cv::Mat1b mask(frame_left.rows, frame_left.cols, uchar(0));
  cv::fillPoly(mask, points, &npoints, 1, cv::Scalar(255));
  debug_image_color.publish(nav::convert_to_ros_msg("mono8", mask));
  ros::spinOnce();
  cv::Scalar average = cv::mean(frame_left, mask);
  if(last_color != NULL){
    cv::Scalar diff = last_color->mul(1/cv::norm(*last_color)) - average.mul(1/cv::norm(average));
    double distance = cv::norm(diff);
    auto poop = average[0]/average[1]/average[2];
    if(fabs(!turned_black && (poop) - 1) > .1){
      ROS_INFO("Turned Black");
      turned_black = true;
    }
    else if(distance > .2){
      ROS_INFO("Found a new color");
      ++colors_found;
      cv::Scalar dr = red.mul(1/cv::norm(red)) - average.mul(1/cv::norm(average));
      double distr = cv::norm(dr);
      cv::Scalar dg = red.mul(1/cv::norm(green)) - average.mul(1/cv::norm(average));
      double distg = cv::norm(dg);
      cv::Scalar db = red.mul(1/cv::norm(red)) - average.mul(1/cv::norm(average));
      double distb = cv::norm(db);
      cv::Scalar dy = red.mul(1/cv::norm(red)) - average.mul(1/cv::norm(average));
      double disty = cv::norm(dy);
      std::vector<double> dists;
      dists.push_back(distr);
      dists.push_back(distg);
      dists.push_back(distb);
      dists.push_back(disty);

      colors_and_distance.push_back(dists);
    }else{
      ROS_INFO("Same color"
               "");

    }


  }
  last_color = &average;



}

void ColorTracker::clear(){
  status = 0;
  mission_complete = 0;
  colors_and_distance.clear();
  turned_black = 0;
  colors_found = 0;
  last_color = NULL;
}

bool ColorTracker::check_status(navigator_msgs::ScanTheCodeMission::Request &req,
                               navigator_msgs::ScanTheCodeMission::Response &resp){
  resp.tracking_model = status;
  resp.mission_complete = mission_complete;

  int max_num = -1;
  double max = 0;
  std::vector<std::string> mins;
  for(int j = 0; j != colors_and_distance.size(); ++j){
      std::vector<double> color_dist = colors_and_distance[j];
      int min_num = -1;
      double min = 100;
      for(int i = 0; i != color_dist.size(); ++i){
        double d = color_dist[i];
        if(d<min) min = d; min_num = i;
      }
      if(min < max) max = min; max_num = j;
      if(min_num == 0) mins.push_back("r");
      if(min_num == 1) mins.push_back("g");
      if(min_num == 2) mins.push_back("b");
      if(min_num == 3) mins.push_back("y");
  }
  mins.erase(mins.begin() + max_num);

  if(status){
    resp.colors = mins;
  }

  return true;

}

void ColorTracker::set_status(bool i){
  status = i;
}
