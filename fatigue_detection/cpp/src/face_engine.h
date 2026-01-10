#ifndef FACE_ENGINE_H
#define FACE_ENGINE_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <string>

class FaceEngine {
public:
    FaceEngine();
    ~FaceEngine();
    
    // Initialize with model paths
    bool initialize(const std::string& face_detector_model = "",
                    const std::string& landmark_predictor_model = "");
    
    // Detect face and landmarks in frame
    bool detect_landmarks(const cv::Mat& frame, 
                         std::vector<cv::Point2f>& landmarks,
                         cv::Rect& face_bbox);
    
    // Check if initialized
    bool is_initialized() const { return initialized_; }
    
private:
    bool initialized_ = false;
    
    // Dlib objects will be stored here
    // For now, using pimpl pattern (forward declaration)
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

#endif // FACE_ENGINE_H
