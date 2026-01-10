#ifndef YAWN_DETECTOR_H
#define YAWN_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <cstdint>

class YawnDetector {
public:
    YawnDetector();
    
    // Update with new landmarks
    void update(const std::vector<cv::Point2f>& landmarks, const cv::Mat& frame);
    
    // Get yawn count in last 5 minutes
    int get_yawn_count_5min() const { return yawn_count_5min_; }
    
    // Mouth Aspect Ratio (MAR) calculation
    static double calculate_mar(const std::vector<cv::Point2f>& landmarks);
    
private:
    // Configuration
    static constexpr double MAR_THRESHOLD = 0.5;  // Threshold for "mouth open"
    static constexpr double YAWN_DURATION_MS = 2000.0;  // 2 seconds
    static constexpr int64_t YAWN_WINDOW_MS = 300000;  // 5 minutes
    
    // State
    std::deque<std::pair<int64_t, double>> mar_history_;  // (timestamp, MAR)
    std::deque<int64_t> yawn_timestamps_;  // Timestamps of detected yawns
    double current_mar_ = 0.0;
    int64_t yawn_start_time_ = -1;
    int yawn_count_5min_ = 0;
    
    // Detection logic
    void detect_yawn(int64_t current_time);
    void update_yawn_count(int64_t current_time);
    
    // Landmark indices for mouth (68-point model)
    static constexpr int MOUTH_LEFT = 48;
    static constexpr int MOUTH_RIGHT = 54;
    static constexpr int MOUTH_TOP = 51;
    static constexpr int MOUTH_BOTTOM = 57;
};

#endif // YAWN_DETECTOR_H
