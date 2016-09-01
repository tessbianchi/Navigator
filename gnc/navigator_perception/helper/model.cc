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
    std::cout<<"check point"<<std::endl;
    current_points.push_back(point);
//    for(Eigen::Vector3d point : current_points){
//        std::cout << "[ " << point(0) << ", "  << point(1) << ", " << point(2) << "]" << std::endl;
//    }

    std::cout<<"size"<<current_points.size()<<std::endl;
    for(float dist : unused_distances){
        std::cout << dist << ", ";
    }
    std::cout<<std::endl;

    if(current_points.size()  == 1)
    {
        return true;
    }



    Eigen::Vector3d starting_point = current_points[0];
    Eigen::Vector3d diff = starting_point - point;
    float dist_from_starting = sqrt(pow(diff[0], 2) + pow(diff[1], 2) + pow(diff[2], 2));
    std::cout<<"dist_from_starting"<<std::endl;
    std::cout<<dist_from_starting<<std::endl;
    if(check){
      visualize_points(current_points, img, left_cam_mat, "poo");
    }
    bool ans = false;
    double mindist = 100;
    double minel = -1;
    std::cout<<"-------"<<std::endl;
    for(float dist : unused_distances)
    {
        float err = dist * .2;
        float upper = dist + err;
        float lower = dist - err;


        std::cout<<"dist"<< dist<<std::endl;
        std::cout<<"Upper"<< upper<<std::endl;
        std::cout<<"lower"<< lower<<std::endl;


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
                    // This is supposed to copy current_points into a new element of potential points.
                    potential_models.push_back(current_points);
                }
            ans = true;
        }
    }
    std::cout<<"-------"<<std::endl;
    std::cout<<" "<<std::endl;
    std::cout<<" "<<std::endl;
    std::cout<<" "<<std::endl;
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
    cv::waitKey(0);
}

bool Model::get_model(std::vector<Eigen::Vector3d>& model3d, std::vector<cv::Point>& model2d, cv::Mat picture, cv::Matx34d left_cam_mat)
{
    std::cout<<"POTENTIAL MODELS"<<std::endl;
  std::cout<< potential_models.size()<<std::endl;
       float min_cost = 100000;
    std::vector<Eigen::Vector3d> min_model;


    for(std::vector<Eigen::Vector3d> mymodel: potential_models){
      visualize_points(mymodel, picture, left_cam_mat, "models");
                Eigen::Vector3d a = mymodel[0];
        Eigen::Vector3d b;
        Eigen::Vector3d c;
        Eigen::Vector3d d;
         for(int i = 1; i != 4; ++i){
             int ret = which_point(a, mymodel[i]);
            if(ret == 1){
              b = mymodel[i];
            }
            else if(ret == 2){
              c = mymodel[i];
            }
            else{
              d = mymodel[i];
            }
        }

        Eigen::Vector3d e = b - a;
        Eigen::Vector3d f = c - a;
        e.normalize();
        f.normalize();
        double t1 = acos(e.dot(f));

        Eigen::Vector3d g = a - b;
        Eigen::Vector3d h = d - b;
        g.normalize();
        h.normalize();
        double t2 = acos(g.dot(h));

        Eigen::Vector3d i = a - c;
        Eigen::Vector3d j = d - c;
        i.normalize();
        j.normalize();
        double t3 = acos(i.dot(j));

        Eigen::Vector3d k = c - d;
        Eigen::Vector3d l = b - d;

        k.normalize();
        l.normalize();
        double t4 = acos(k.dot(l));

        double x = (10 * fabs(t1 - M_PI/2));
        double y = (10 * fabs(t2 - M_PI/2));
        double z = (10 * fabs(t3 - M_PI/2));
        double w = (10 * fabs(t4 - M_PI/2));

        double cost =  x + y + z + w;

        Eigen::Vector3d n1 = f.cross(e);
        Eigen::Vector3d n2 = l.cross(k);
        n1.normalize();
        n2.normalize();

        double c1 = acos(n1.dot(n2));
        cost += c1 * 10;

        if((float)cost < min_cost){
          min_cost = cost;
          min_model = mymodel;
        }
        std::cout<<cost<<std::endl;
    }
    model3d = min_model;

    std::cout<<"DA BEST MODEL"<<std::endl;
    std::cout<< min_cost<<std::endl;
    visualize_points(min_model, picture, left_cam_mat, "WINNER");

    return true;
}

bool Model::complete()
{
    if(current_points.size()  == 4)
        {
            return true;
        }
    return true;
}

int Model::which_point( Eigen::Vector3d a,  Eigen::Vector3d b){
  Eigen::Vector3d diff = a - b;
  float dist_from_starting = sqrt(pow(diff[0], 2) + pow(diff[1], 2) + pow(diff[2], 2));
  float min_err = 1000;
  float min = -1;
  for(float dist : unused_distances)
  {
      float err = dist * .2;
      float upper = dist + err;
      float lower = dist - err;

      float min_ans = -1;
      if(dist_from_starting > lower && dist_from_starting < upper)
      {
        if(fabs(dist_from_starting-dist) < min_err){
          min_err = fabs(dist_from_starting-dist);
          min = dist;
        }
      }
  }
  if(min == width){
    return 1;
  }
  if(min == height){
    return 2;
  }else{
    return 3;
  }
}
