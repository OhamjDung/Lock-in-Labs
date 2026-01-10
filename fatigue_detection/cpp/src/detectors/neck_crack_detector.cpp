#include "neck_crack_detector.h"
#include <cmath>
#include <algorithm>

NeckCrackDetector::NeckCrackDetector() = default;

double NeckCrackDetector::calculate_head_rotation(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox) {
    if (landmarks.size() < 68 || face_bbox.width == 0) {
        return 0.0;
    }
    
    // Simple rotation estimation using nose tip and eye centers
    // More sophisticated would use solvePnP, but this is a simpler approximation
    
    // Eye centers
    cv::Point2f left_eye_center = (landmarks[36] + landmarks[39]) * 0.5f;
    cv::Point2f right_eye_center = (landmarks[42] + landmarks[45]) * 0.5f;
    
    // Nose tip
    cv::Point2f nose_tip = landmarks[30];
    
    // Calculate angles
    cv::Point2f eye_center = (left_eye_center + right_eye_center) * 0.5f;
    cv::Point2f vec = nose_tip - eye_center;
    
    // Yaw rotation (left-right)
    double yaw = std::atan2(vec.x, vec.y) * 180.0 / CV_PI;
    
    // Pitch rotation (up-down)
    double pitch = std::atan2(vec.y, std::abs(vec.x)) * 180.0 / CV_PI;
    
    // Combine into single rotation metric (weighted)
    return yaw * 0.7 + pitch * 0.3;
}

void NeckCrackDetector::update(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox) {
    if (landmarks.size() < 68) {
        return;
    }
    
    double current_rotation = calculate_head_rotation(landmarks, face_bbox);
    int64_t current_time = cv::getTickCount() * 1000 / cv::getTickFrequency();
    
    // Add to history
    rotation_history_.push_back({current_time, current_rotation});
    
    // Keep only recent history (last 2 seconds)
    int64_t history_window = 2000;
    while (!rotation_history_.empty() && 
           (current_time - rotation_history_.front().first) > history_window) {
        rotation_history_.pop_front();
    }
    
    // Detect crack if we have previous rotation
    if (last_update_time_ > 0) {
        detect_crack(current_time, current_rotation);
    }
    
    last_rotation_ = current_rotation;
    last_update_time_ = current_time;
    
    // Update crack count
    update_crack_count(current_time);
}

void NeckCrackDetector::detect_crack(int64_t current_time, double current_rotation) {
    double time_delta = (current_time - last_update_time_) / 1000.0;  // Convert to seconds
    
    if (time_delta < 1e-6) {
        return;  // Avoid division by zero
    }
    
    // Calculate rotation velocity (degrees per second)
    double rotation_delta = std::abs(current_rotation - last_rotation_);
    double velocity = rotation_delta / time_delta;
    
    // Detect sudden high-velocity rotation (neck crack)
    if (velocity > ROTATION_VELOCITY_THRESHOLD) {
        // Potential neck crack detected
        // Additional check: should return to center quickly
        crack_timestamps_.push_back(current_time);
    }
}

void NeckCrackDetector::update_crack_count(int64_t current_time) {
    // Remove cracks outside 1-minute window
    while (!crack_timestamps_.empty() && 
           (current_time - crack_timestamps_.front()) > CRACK_WINDOW_MS) {
        crack_timestamps_.pop_front();
    }
    
    crack_count_1min_ = static_cast<int>(crack_timestamps_.size());
}
