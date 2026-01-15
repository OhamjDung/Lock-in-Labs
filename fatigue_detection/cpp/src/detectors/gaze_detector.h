#ifndef GAZE_DETECTOR_H
#define GAZE_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <deque>
#include <cstdint>

class GazeDetector {
public:
    GazeDetector();
    
    // Update with new landmarks
    void update(const std::vector<cv::Point2f>& landmarks, const cv::Mat& frame);
    
    // Get metrics
    double get_blink_rate() const { return blink_rate_; }  // Blinks per minute
    int get_blink_count_total() const { return static_cast<int>(blink_timestamps_.size()); }  // Total blinks detected
    double get_perclos() const { return perclos_; }  // Percentage of eyelid closure (0-1)
    double get_gaze_stability() const { return gaze_stability_; }  // Stability score (0-1)
    double get_current_ear() const { return current_ear_; }  // Current Eye Aspect Ratio (for calibration)
    
    // Allow threshold adjustment for calibration
    void set_ear_threshold(double threshold) { ear_threshold_ = threshold; }
    double get_ear_threshold() const { return ear_threshold_; }
    
private:
    // Configuration
    double ear_threshold_ = 0.20;  // Eye Aspect Ratio threshold for blink (configurable, default 0.20)
    static constexpr double ZONING_OUT_STATIC_TIME_MS = 30000.0;  // 30 seconds
    static constexpr double ZONING_OUT_BLINK_RATE_THRESHOLD = 2.0;  // Blinks per minute
    static constexpr int64_t BLINK_WINDOW_MS = 60000;  // 1 minute
    
    // Eye Aspect Ratio (EAR) calculation
    static double calculate_ear(const std::vector<cv::Point2f>& landmarks, bool left_eye);
    
    // Landmark indices (68-point model)
    static constexpr int LEFT_EYE_START = 36;
    static constexpr int LEFT_EYE_END = 41;
    static constexpr int RIGHT_EYE_START = 42;
    static constexpr int RIGHT_EYE_END = 47;
    
    // State
    std::deque<std::pair<int64_t, double>> ear_history_;  // (timestamp, EAR)
    std::deque<int64_t> blink_timestamps_;  // Timestamps of detected blinks
    std::deque<cv::Point2f> normalized_gaze_history_;  // Normalized gaze vectors (relative to face size)
    std::deque<std::pair<int64_t, cv::Point2f>> head_position_history_;  // (timestamp, nose_tip_position)
    
    double current_ear_ = 0.5;
    double blink_rate_ = 0.0;
    double perclos_ = 0.0;
    double gaze_stability_ = 1.0;
    double head_movement_velocity_ = 0.0;  // Pixels per frame
    
    int64_t last_blink_time_ = -1;
    bool eyes_closed_ = false;
    
    // Detection logic
    void detect_blink(int64_t current_time);
    void update_blink_rate(int64_t current_time);
    void calculate_gaze_stability();
    void detect_zoning_out();
};

#endif // GAZE_DETECTOR_H
