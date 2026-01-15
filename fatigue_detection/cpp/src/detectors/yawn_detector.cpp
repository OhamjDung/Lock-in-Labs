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

double YawnDetector::calculate_ear(const std::vector<cv::Point2f>& landmarks) {
    if (landmarks.size() < 68) {
        return 0.5;  // Default value
    }
    
    // Calculate EAR for both eyes and average
    // Left eye: points 36-41, Right eye: points 42-47
    
    // Left eye EAR
    cv::Point2f left_eye_top = (landmarks[37] + landmarks[38]) * 0.5f;
    cv::Point2f left_eye_bottom = (landmarks[40] + landmarks[41]) * 0.5f;
    double left_vertical = cv::norm(left_eye_top - left_eye_bottom);
    double left_horizontal = cv::norm(landmarks[36] - landmarks[39]);
    double left_ear = (left_horizontal > 1e-6) ? (left_vertical / left_horizontal) : 0.5;
    
    // Right eye EAR
    cv::Point2f right_eye_top = (landmarks[43] + landmarks[44]) * 0.5f;
    cv::Point2f right_eye_bottom = (landmarks[46] + landmarks[47]) * 0.5f;
    double right_vertical = cv::norm(right_eye_top - right_eye_bottom);
    double right_horizontal = cv::norm(landmarks[42] - landmarks[45]);
    double right_ear = (right_horizontal > 1e-6) ? (right_vertical / right_horizontal) : 0.5;
    
    // Average EAR
    return (left_ear + right_ear) / 2.0;
}

void YawnDetector::update(const std::vector<cv::Point2f>& landmarks, const cv::Mat& frame) {
    if (landmarks.size() < 68) {
        current_mar_ = 0.0;
        landmarks_.clear();
        return;
    }
    
    // Store landmarks for use in detect_yawn (needed for EAR calculation)
    landmarks_ = landmarks;
    
    current_mar_ = calculate_mar(landmarks);
    
    int64_t current_time = cv::getTickCount() * 1000 / cv::getTickFrequency();
    
    // Add to history
    mar_history_.push_back({current_time, current_mar_});
    
    // Keep only recent history (last 10 seconds)
    int64_t history_window = 10000;
    while (!mar_history_.empty() && (current_time - mar_history_.front().first) > history_window) {
        mar_history_.pop_front();
    }
    
    // Detect yawn (uses landmarks_ for EAR calculation)
    detect_yawn(current_time);
    
    // Update yawn count
    update_yawn_count(current_time);
}

void YawnDetector::detect_yawn(int64_t current_time) {
    // Improved yawn detection with "Squint Yawn" logic and sliding window for robustness
    // Two types of yawns:
    // 1. "Monster Yawn": Mouth extremely wide open (MAR > 0.60) - eyes don't matter
    // 2. "Squint Yawn": Mouth moderately open (MAR > 0.45) + Eyes closed (EAR < 0.20)
    //    Most people close their eyes when yawning - this differentiates from talking
    
    // Handle case where face is not detected (landmarks empty)
    if (landmarks_.empty()) {
        // Face not detected - don't reset, just skip this frame
        // This prevents jittery face detection from resetting yawn detection
        return;
    }
    
    // Calculate EAR for squint yawn detection (needed for fusion logic)
    double current_ear = calculate_ear(landmarks_);
    
    // Determine if this frame is a yawn frame
    bool is_yawn_frame = false;
    
    // LOGIC 1: The "Monster Yawn" (Mouth huge, eyes don't matter)
    if (current_mar_ >= MAR_THRESHOLD_HUGE) {
        is_yawn_frame = true;
    }
    // LOGIC 2: The "Squint Yawn" (Mouth moderate + Eyes Closed)
    // This differentiates it from talking (where eyes are usually open)
    else if (current_mar_ >= MAR_THRESHOLD_MODERATE && current_ear < EAR_CLOSED_THRESHOLD) {
        is_yawn_frame = true;
    }
    
    // Add this frame to sliding window
    yawn_frame_history_.push_back({current_time, is_yawn_frame});
    
    // Remove frames outside the 1-second window
    while (!yawn_frame_history_.empty() && 
           (current_time - yawn_frame_history_.front().first) > YAWN_DETECTION_WINDOW_MS) {
        yawn_frame_history_.pop_front();
    }
    
    // Check if enough frames in the window are yawn frames (80% threshold)
    if (yawn_frame_history_.size() >= 10) {  // Need at least 10 frames for reliable detection
        int yawn_frame_count = 0;
        for (const auto& entry : yawn_frame_history_) {
            if (entry.second) {  // is_yawn_frame
                yawn_frame_count++;
            }
        }
        
        double yawn_ratio = static_cast<double>(yawn_frame_count) / yawn_frame_history_.size();
        
        // If 80% of frames in the last second are yawn frames, trigger yawn detection
        if (yawn_ratio >= YAWN_THRESHOLD_RATIO) {
            if (!is_yawning_) {
                // Valid yawn detected (mouth open for 80% of the last second)
                yawn_timestamps_.push_back(current_time);
                is_yawning_ = true;  // Lock state to prevent double-counting
            }
        } else {
            // Not enough yawn frames - reset lock (allows detection of new yawn)
            is_yawning_ = false;
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
