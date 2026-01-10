#include "yawn_detector.h"
#include <cmath>
#include <algorithm>

YawnDetector::YawnDetector() = default;

double YawnDetector::calculate_mar(const std::vector<cv::Point2f>& landmarks) {
    if (landmarks.size() < 68) {
        return 0.0;  // Not enough landmarks
    }
    
    // Vertical distances
    double vertical1 = cv::norm(landmarks[MOUTH_TOP] - landmarks[MOUTH_BOTTOM]);
    double vertical2 = cv::norm(landmarks[MOUTH_TOP + 1] - landmarks[MOUTH_BOTTOM - 1]);
    double vertical3 = cv::norm(landmarks[MOUTH_TOP + 2] - landmarks[MOUTH_BOTTOM - 2]);
    
    // Horizontal distance
    double horizontal = cv::norm(landmarks[MOUTH_LEFT] - landmarks[MOUTH_RIGHT]);
    
    if (horizontal < 1e-6) {
        return 0.0;  // Avoid division by zero
    }
    
    // MAR = average vertical / horizontal
    double avg_vertical = (vertical1 + vertical2 + vertical3) / 3.0;
    return avg_vertical / horizontal;
}

void YawnDetector::update(const std::vector<cv::Point2f>& landmarks, const cv::Mat& frame) {
    if (landmarks.size() < 68) {
        current_mar_ = 0.0;
        return;
    }
    
    current_mar_ = calculate_mar(landmarks);
    
    int64_t current_time = cv::getTickCount() * 1000 / cv::getTickFrequency();
    
    // Add to history
    mar_history_.push_back({current_time, current_mar_});
    
    // Keep only recent history (last 10 seconds)
    int64_t history_window = 10000;
    while (!mar_history_.empty() && (current_time - mar_history_.front().first) > history_window) {
        mar_history_.pop_front();
    }
    
    // Detect yawn
    detect_yawn(current_time);
    
    // Update yawn count
    update_yawn_count(current_time);
}

void YawnDetector::detect_yawn(int64_t current_time) {
    if (current_mar_ < MAR_THRESHOLD) {
        // Mouth closed - reset yawn start time
        if (yawn_start_time_ > 0) {
            // Was yawning, now closed - check if duration was sufficient
            double duration = current_time - yawn_start_time_;
            if (duration >= YAWN_DURATION_MS) {
                // Valid yawn detected
                yawn_timestamps_.push_back(yawn_start_time_);
            }
            yawn_start_time_ = -1;
        }
    } else {
        // Mouth open
        if (yawn_start_time_ < 0) {
            // Start of potential yawn
            yawn_start_time_ = current_time;
        }
    }
}

void YawnDetector::update_yawn_count(int64_t current_time) {
    // Remove yawns outside 5-minute window
    while (!yawn_timestamps_.empty() && 
           (current_time - yawn_timestamps_.front()) > YAWN_WINDOW_MS) {
        yawn_timestamps_.pop_front();
    }
    
    yawn_count_5min_ = static_cast<int>(yawn_timestamps_.size());
}
