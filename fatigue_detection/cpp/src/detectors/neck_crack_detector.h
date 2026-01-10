#ifndef NECK_CRACK_DETECTOR_H
#define NECK_CRACK_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <cstdint>

class NeckCrackDetector {
public:
    NeckCrackDetector();
    
    // Update with landmarks and face bbox
    void update(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox);
    
    // Get crack count in last minute
    int get_crack_count_1min() const { return crack_count_1min_; }
    
private:
    // Configuration
    static constexpr double ROTATION_VELOCITY_THRESHOLD = 45.0;  // Degrees per second
    static constexpr int64_t CRACK_WINDOW_MS = 60000;  // 1 minute
    
    // Head pose calculation (simplified: using nose tip and eye centers)
    double calculate_head_rotation(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox);
    
    // State
    std::deque<std::pair<int64_t, double>> rotation_history_;  // (timestamp, rotation angle)
    std::deque<int64_t> crack_timestamps_;  // Timestamps of detected cracks
    
    double last_rotation_ = 0.0;
    int64_t last_update_time_ = -1;
    int crack_count_1min_ = 0;
    
    // Detection logic
    void detect_crack(int64_t current_time, double current_rotation);
    void update_crack_count(int64_t current_time);
};

#endif // NECK_CRACK_DETECTOR_H
