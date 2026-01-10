#include "gaze_detector.h"
#include <cmath>
#include <algorithm>

GazeDetector::GazeDetector() = default;

double GazeDetector::calculate_ear(const std::vector<cv::Point2f>& landmarks, bool left_eye) {
    if (landmarks.size() < 68) {
        return 0.5;  // Default value
    }
    
    // 68-point model eye landmarks:
    // Left eye:  36 (outer), 37 (top), 38 (top), 39 (inner), 40 (bottom), 41 (bottom)
    // Right eye: 42 (inner), 43 (top), 44 (top), 45 (outer), 46 (bottom), 47 (bottom)
    
    int start_idx = left_eye ? LEFT_EYE_START : RIGHT_EYE_START;
    
    // Calculate vertical distances (top to bottom at different points)
    // Vertical1: top point to bottom point (e.g., 37 to 41 for left eye)
    double vertical1 = cv::norm(landmarks[start_idx + 1] - landmarks[start_idx + 5]);
    // Vertical2: top middle to bottom middle (e.g., 38 to 40 for left eye)
    double vertical2 = cv::norm(landmarks[start_idx + 2] - landmarks[start_idx + 4]);
    // Vertical3: outer corner to inner corner (diagonal, but gives vertical component)
    // Actually, let's use a third vertical measurement: average of top points to average of bottom points
    cv::Point2f top_avg = (landmarks[start_idx + 1] + landmarks[start_idx + 2]) * 0.5f;
    cv::Point2f bottom_avg = (landmarks[start_idx + 4] + landmarks[start_idx + 5]) * 0.5f;
    double vertical3 = cv::norm(top_avg - bottom_avg);
    
    // Calculate horizontal distance (outer corner to inner corner)
    // For left eye: 36 to 39, for right eye: 42 to 45
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
    // Improved blink detection: detect transition from open -> closed -> open
    // This ensures we only count complete blinks, not just eye closure
    if (current_ear_ < ear_threshold_) {
        // Eyes closed (or closing)
        if (!eyes_closed_) {
            // Transition: eyes were open, now closing
            eyes_closed_ = true;
            // Don't count blink yet - wait for eyes to open again
        }
    } else {
        // Eyes open (or opening)
        if (eyes_closed_) {
            // Transition: eyes were closed, now opening - this is a complete blink!
            eyes_closed_ = false;
            // Only count if enough time has passed since last blink (debounce)
            if (last_blink_time_ < 0 || (current_time - last_blink_time_) > 200) {
                // Valid blink detected
                blink_timestamps_.push_back(current_time);
                last_blink_time_ = current_time;
            }
        }
    }
    
    // Calculate PERCLOS (percentage of time eyes are closed)
    if (!ear_history_.empty()) {
        int closed_count = 0;
        for (const auto& entry : ear_history_) {
            if (entry.second < ear_threshold_) {
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
