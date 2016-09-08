#include <navigator_vision_lib/model.h>

Model::Model(float width, float height, int min_points): width(width), height(height), min_points(min_points)
{
    unused_distances.push_back(width);
    unused_distances.push_back(height);
    unused_distances.push_back(sqrt(pow(width, 2) + pow(height, 2)));
}

Model::~Model()
{
}

void Model::clear(){
  potential_models.clear();
}


bool Model::check_point(Eigen::Vector3d point, cv:: Mat img, cv::Matx34d left_cam_mat, bool check)
{
    current_points.push_back(point);
    if(current_points.size()  == 1)
    {
        return true;
    }
    Eigen::Vector3d starting_point = current_points[0];
    Eigen::Vector3d diff = starting_point - point;
    float dist_from_starting = sqrt(pow(diff[0], 2) + pow(diff[1], 2) + pow(diff[2], 2));
    bool ans = false;
    double mindist = 100;
    double minel = -1;
    for(float dist : unused_distances)
    {
        float err = dist * .4;
        float upper = dist + err;
        float lower = dist - err;

        if(dist_from_starting > lower && dist_from_starting < upper)
        {

            double m = fabs(dist_from_starting);
            if(m < mindist){
              minel = dist;
              mindist = m;
            }

            std::stringstream ss;
            ss<<point(0)<<point(1)<<point(2);
            point_to_distance.insert(std::pair<std::string,float>(ss.str(), dist));
            if(current_points.size()  == min_points)
            {
                potential_models.push_back(current_points);
            }
            ans = true;
        }
    }
    if(ans){
       unused_distances.erase(std::remove(unused_distances.begin(), unused_distances.end(), minel), unused_distances.end());
    }


    return ans;
}

void Model::remove_point(Eigen::Vector3d point)
{
    current_points.erase(std::remove(current_points.begin(), current_points.end(), point), current_points.end());
    std::stringstream ss;
    ss<<point(0)<<point(1)<<point(2);
    if(point_to_distance.find( ss.str()) != point_to_distance.end()){
      float dist = point_to_distance[ss.str()];
      unused_distances.push_back(dist);
      point_to_distance.erase(ss.str());
    }
}

void Model::visualize_points(std::vector<Eigen::Vector3d>  feature_pts_3d, cv:: Mat img, cv::Matx34d left_cam_mat, std::string name)
{
    cv::Mat current_image_left = img.clone();
    // visualize reconstructions
    for(size_t i = 0; i < feature_pts_3d.size(); i++)
        {
            Eigen::Vector3d pt = feature_pts_3d[i];
            cv::Matx41d position_hom(pt(0), pt(1), pt(2), 1);
            cv::Matx31d pt_L_2d_hom = left_cam_mat * position_hom;
            cv::Point2d L_center2d(pt_L_2d_hom(0) / pt_L_2d_hom(2), pt_L_2d_hom(1) / pt_L_2d_hom(2));
            cv::Scalar color(255, 0, 255);
            std::stringstream label;
            label << i;
            cv::circle(current_image_left, L_center2d, 5, color, -1);
            cv::putText(current_image_left, label.str(), L_center2d, cv::FONT_HERSHEY_SIMPLEX,
                    0.0015 * current_image_left.rows, cv::Scalar(0, 0, 0), 2);
        }

    cv::imshow(name, current_image_left);
    cv::waitKey(33);
}

bool Model::get_model(std::vector<Eigen::Vector3d>& model3d, cv::Mat picture, cv::Matx34d left_cam_mat)
{
    double min_cost = 100000;
    std::vector<Eigen::Vector3d> min_model;

    for(std::vector<Eigen::Vector3d> mymodel: potential_models){
        double cost = 0;
        for(int i = 0; i != 4; ++i){
          Eigen::Vector3d a = mymodel[i];
          Eigen::Vector3d b;
          Eigen::Vector3d c;
          bool b_init = true;
          int furthest_point = get_furthest_point(mymodel, i);
          for(int j = 0; j != 4; ++j){
            if(j != furthest_point && j != i && b_init){
               b_init = false;
               b = mymodel[j];
            }else if(j != furthest_point && j != i){
               c = mymodel[j];
               break;
            }
          }
          Eigen::Vector3d e = b - a;
          Eigen::Vector3d f = c - a;
          e.normalize();
          f.normalize();
          double h = e.dot(f);
          double t1 = acos(h);
          double x = (10 * fabs(t1 - M_PI/2));
          cost += x;

        }

        if(cost < min_cost){
          min_cost = cost;
          min_model = mymodel;
        }
    }
    model3d = min_model;
    if(potential_models.size() != 0 && min_cost < 4){
      visualize_points(min_model, picture, left_cam_mat, "WINNER");
    }
    return true;
}

bool Model::complete()
{
    if(current_points.size()  == 4)
    {
        return true;
    }
    return false;
}

int Model::get_furthest_point(std::vector<Eigen::Vector3d> mymodel, int point){
  float max_val = 0;
  int max = -1;
  for(int j = 0; j != 4; ++j){
    if(j == point) continue;
    Eigen::Vector3d diff = mymodel[point] - mymodel[j];
    float dist_from_starting = sqrt(pow(diff[0], 2) + pow(diff[1], 2) + pow(diff[2], 2));
    if(dist_from_starting > max_val){
      max_val = dist_from_starting;
      max = j;
    }
  }
  return max;
}

