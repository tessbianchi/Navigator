#pragma once
#include <string>
#include <vector>
#include <opencv2/opencv.hpp>
#include <Eigen/Core>
#include <navigator_vision_lib/cv_tools.hpp>
#include <ros/ros.h>
#include <image_transport/image_transport.h>

class ColorTracker{
public:
  bool track(cv::Mat frame_left, std::vector<cv::Point2f> points, double image_proc_scale, std::vector<char>& colors);
  void clear();

private:
  ros::NodeHandle nh;
  image_transport::ImageTransport image_transport = image_transport::ImageTransport(nh);
  image_transport::Publisher debug_image_color = image_transport.advertise("stereo_model_fitter/debug_img/color", 1, true);

};

