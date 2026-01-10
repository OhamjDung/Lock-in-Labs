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
    static constexpr double CRACK_VELOCITY_THRESHOLD = 8.0;  // Degrees per frame (lowered for better sensitivity)
    static constexpr int64_t CRACK_WINDOW_MS = 60000;  // 1 minute
    static constexpr int CRACK_DEBOUNCE_FRAMES = 60;  // 2 seconds at 30fps (prevent double-counting)
    
    // Head pose calculation - returns separate axes
    void calculate_head_pose(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox,
                            double& pitch, double& yaw, double& roll);
    
    // State
    std::deque<std::pair<int64_t, double>> rotation_history_;  // (timestamp, rotation angle)
    std::deque<int64_t> crack_timestamps_;  // Timestamps of detected cracks
    
    // Per-axis tracking for better crack detection
    double last_pitch_ = 0.0;
    double last_yaw_ = 0.0;
    double last_roll_ = 0.0;
    int64_t last_update_time_ = -1;
    int64_t last_crack_time_ = -1;  // Last time a crack was detected (for cooldown)
    int frames_since_last_crack_ = 0;  // Frame counter for debouncing
    int crack_count_1min_ = 0;
    
    // Detection logic
    void detect_crack(int64_t current_time, double current_pitch, double current_yaw, double current_roll);
    void update_crack_count(int64_t current_time);
};

#endif // NECK_CRACK_DETECTOR_H
