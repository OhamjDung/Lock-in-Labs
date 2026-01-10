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
    
    // Allow threshold adjustment for calibration
    void set_mar_threshold(double threshold) { mar_threshold_ = threshold; }
    double get_mar_threshold() const { return mar_threshold_; }
    double get_current_mar() const { return current_mar_; }  // Expose for calibration
    
private:
    // Configuration
    double mar_threshold_ = 0.35;  // Threshold for "mouth open" (configurable, default 0.35)
    static constexpr double YAWN_DURATION_MS = 1500.0;  // 1.5 seconds (reduced from 2s)
    static constexpr double YAWN_PEAK_MAR_THRESHOLD = 0.50;  // Peak MAR for yawn detection (must exceed this)
    static constexpr int64_t YAWN_WINDOW_MS = 300000;  // 5 minutes
    
    // State
    std::deque<std::pair<int64_t, double>> mar_history_;  // (timestamp, MAR)
    std::deque<int64_t> yawn_timestamps_;  // Timestamps of detected yawns
    double current_mar_ = 0.0;
    int64_t yawn_start_time_ = -1;
    int yawn_count_5min_ = 0;
    
    // Consecutive frame counter for talking vs yawning differentiation
    int consecutive_frames_open_ = 0;  // Frames with mouth continuously open
    bool is_yawning_ = false;  // Lock state to prevent double-counting
    static constexpr int MIN_YAWN_FRAMES = 45;  // 1.5 seconds at 30fps (must be open continuously)
    
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
