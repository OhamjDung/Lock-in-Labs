#include "gaze_detector.h"
#include <cmath>
#include <algorithm>

GazeDetector::GazeDetector() = default;

double GazeDetector::calculate_ear(const std::vector<cv::Point2f>& landmarks, bool left_eye) {
    if (landmarks.size() < 68) {
        return 0.5;  // Default value
    }
    
    int start_idx = left_eye ? LEFT_EYE_START : RIGHT_EYE_START;
    int end_idx = left_eye ? LEFT_EYE_END : RIGHT_EYE_END;
    
    // Calculate vertical distances
    double vertical1 = cv::norm(landmarks[start_idx] - landmarks[start_idx + 3]);
    double vertical2 = cv::norm(landmarks[start_idx + 1] - landmarks[start_idx + 5]);
    double vertical3 = cv::norm(landmarks[start_idx + 2] - landmarks[start_idx + 4]);
    
    // Calculate horizontal distance
    double horizontal = cv::norm(landmarks[start_idx] - landmarks[start_idx + 3]);
    
    if (horizontal < 1e-6) {
        return 0.5;  // Avoid division by zero
    }
    
    // EAR = average vertical / horizontal
    double avg_vertical = (vertical1 + vertical2 + vertical3) / 3.0;
    return avg_vertical / horizontal;
}

void GazeDetector::update(const std::vector<cv::Point2f>& landmarks, const cv::Mat& frame) {
    if (landmarks.size() < 68) {
        current_ear_ = 0.5;
        return;
    }
    
    // Calculate average EAR for both eyes
    double left_ear = calculate_ear(landmarks, true);
    double right_ear = calculate_ear(landmarks, false);
    current_ear_ = (left_ear + right_ear) / 2.0;
    
    int64_t current_time = cv::getTickCount() * 1000 / cv::getTickFrequency();
    
    // Add to history
    ear_history_.push_back({current_time, current_ear_});
    
    // Keep only recent history (last 5 seconds)
    int64_t history_window = 5000;
    while (!ear_history_.empty() && (current_time - ear_history_.front().first) > history_window) {
        ear_history_.pop_front();
    }
    
    // Calculate gaze point (center of both eyes)
    cv::Point2f left_eye_center = (landmarks[LEFT_EYE_START] + landmarks[LEFT_EYE_START + 3]) * 0.5f;
    cv::Point2f right_eye_center = (landmarks[RIGHT_EYE_START] + landmarks[RIGHT_EYE_START + 3]) * 0.5f;
    cv::Point2f gaze_point = (left_eye_center + right_eye_center) * 0.5f;
    
    gaze_points_.push_back(gaze_point);
    
    // Keep only recent gaze points (last 5 seconds at 30 FPS = 150 points)
    if (gaze_points_.size() > 150) {
        gaze_points_.pop_front();
    }
    
    // Detect blinks
    detect_blink(current_time);
    
    // Update metrics
    update_blink_rate(current_time);
    calculate_gaze_stability();
    detect_zoning_out();
}

void GazeDetector::detect_blink(int64_t current_time) {
    if (current_ear_ < EAR_THRESHOLD) {
        // Eyes closed
        if (!eyes_closed_) {
            // Start of blink
            eyes_closed_ = true;
            if (last_blink_time_ < 0 || (current_time - last_blink_time_) > 200) {
                // New blink (debounce: at least 200ms between blinks)
                blink_timestamps_.push_back(current_time);
                last_blink_time_ = current_time;
            }
        }
    } else {
        // Eyes open
        eyes_closed_ = false;
    }
    
    // Calculate PERCLOS (percentage of time eyes are closed)
    if (!ear_history_.empty()) {
        int closed_count = 0;
        for (const auto& entry : ear_history_) {
            if (entry.second < EAR_THRESHOLD) {
                closed_count++;
            }
        }
        perclos_ = static_cast<double>(closed_count) / ear_history_.size();
    }
}

void GazeDetector::update_blink_rate(int64_t current_time) {
    // Remove blinks outside 1-minute window
    while (!blink_timestamps_.empty() && 
           (current_time - blink_timestamps_.front()) > BLINK_WINDOW_MS) {
        blink_timestamps_.pop_front();
    }
    
    // Calculate blinks per minute
    if (blink_timestamps_.empty()) {
        blink_rate_ = 0.0;
    } else {
        int64_t time_span = current_time - blink_timestamps_.front();
        if (time_span > 0) {
            blink_rate_ = (static_cast<double>(blink_timestamps_.size()) / time_span) * 60000.0;
        }
    }
}

void GazeDetector::calculate_gaze_stability() {
    if (gaze_points_.size() < 10) {
        gaze_stability_ = 1.0;  // Not enough data
        return;
    }
    
    // Calculate variance of gaze points
    cv::Point2f mean(0, 0);
    for (const auto& pt : gaze_points_) {
        mean += pt;
    }
    mean *= (1.0f / gaze_points_.size());
    
    double variance = 0.0;
    for (const auto& pt : gaze_points_) {
        double dist = cv::norm(pt - mean);
        variance += dist * dist;
    }
    variance /= gaze_points_.size();
    
    // Convert variance to stability score (0-1, higher = more stable)
    // Normalize: stability decreases with variance
    // Using exponential decay: stability = exp(-variance / scale)
    double scale = 100.0;  // Adjust based on expected variance
    gaze_stability_ = std::exp(-variance / scale);
    gaze_stability_ = std::max(0.0, std::min(1.0, gaze_stability_));  // Clamp to [0, 1]
}

void GazeDetector::detect_zoning_out() {
    // Zoning out: static gaze (>30s) + very low blink rate
    if (gaze_stability_ > 0.95 && blink_rate_ < ZONING_OUT_BLINK_RATE_THRESHOLD) {
        // Potential zoning out - could add event here
    }
}
