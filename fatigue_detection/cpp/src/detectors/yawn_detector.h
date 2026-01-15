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
    
    // Eye Aspect Ratio (EAR) calculation (for squint yawn detection)
    static double calculate_ear(const std::vector<cv::Point2f>& landmarks);
    
    // Allow threshold adjustment for calibration
    void set_mar_threshold(double threshold) { mar_threshold_ = threshold; }
    double get_mar_threshold() const { return mar_threshold_; }
    double get_current_mar() const { return current_mar_; }  // Expose for calibration
    
private:
    // Configuration
    double mar_threshold_ = 0.8;  // Threshold for "mouth open" (configurable, default 0.8)
    static constexpr double MAR_THRESHOLD_HUGE = 0.60;  // Wide open yawn (monster yawn)
    static constexpr double MAR_THRESHOLD_MODERATE = 0.45;  // Moderate yawn (can be squint yawn)
    static constexpr double EAR_CLOSED_THRESHOLD = 0.20;  // Eyes closed threshold (for squint yawn)
    static constexpr int64_t YAWN_WINDOW_MS = 300000;  // 5 minutes (for counting yawns)
    static constexpr int64_t YAWN_DETECTION_WINDOW_MS = 1000;  // 1 second sliding window
    static constexpr double YAWN_THRESHOLD_RATIO = 0.80;  // 80% of frames must be open
    
    // State
    std::deque<std::pair<int64_t, double>> mar_history_;  // (timestamp, MAR)
    std::deque<int64_t> yawn_timestamps_;  // Timestamps of detected yawns
    double current_mar_ = 0.0;
    int64_t yawn_start_time_ = -1;
    int yawn_count_5min_ = 0;
    std::vector<cv::Point2f> landmarks_;  // Store landmarks for EAR calculation in detect_yawn
    
    // Sliding window for robust yawn detection (handles jittery face detection)
    std::deque<std::pair<int64_t, bool>> yawn_frame_history_;  // (timestamp, is_yawn_frame)
    bool is_yawning_ = false;  // Lock state to prevent double-counting
    
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
