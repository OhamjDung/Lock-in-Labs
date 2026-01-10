#ifndef FIDGET_DETECTOR_H
#define FIDGET_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <deque>
#include <cstdint>

class FidgetDetector {
public:
    FidgetDetector();
    
    // Calculate motion energy with relative ROI (from face bbox)
    double calculate_motion_energy(const cv::Mat& curr_frame, 
                                    const cv::Mat& prev_frame,
                                    const cv::Rect& face_bbox);
    
private:
    // Configuration
    static constexpr double STRETCH_THRESHOLD = 150.0;  // Large motion = stretching
    static constexpr double FIDGET_THRESHOLD = 20.0;   // Small motion = fidgeting
    
    // Calculate torso ROI relative to face position
    static cv::Rect calculate_torso_roi(const cv::Rect& face_bbox, const cv::Size& image_size);
    
    // History for smoothing
    std::deque<double> motion_history_;
    static constexpr size_t HISTORY_SIZE = 10;
};

#endif // FIDGET_DETECTOR_H
