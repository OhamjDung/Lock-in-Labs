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
    
    // Calculate normalized gaze point (scale-invariant: relative to face size)
    // This fixes the Z-axis problem: moving closer/farther won't affect stability
    
    // 1. Get eye centers
    cv::Point2f left_eye_center = (landmarks[LEFT_EYE_START] + landmarks[LEFT_EYE_START + 3]) * 0.5f;
    cv::Point2f right_eye_center = (landmarks[RIGHT_EYE_START] + landmarks[RIGHT_EYE_START + 3]) * 0.5f;
    cv::Point2f eye_center = (left_eye_center + right_eye_center) * 0.5f;
    
    // 2. Get face reference point (nose tip) and scale (face width)
    cv::Point2f nose_tip = landmarks[30];  // Nose tip landmark
    float face_width = cv::norm(landmarks[0] - landmarks[16]);  // Distance between jaw edges (points 0 and 16)
    
    // Protect against division by zero
    if (face_width < 1.0f) {
        face_width = 1.0f;
    }
    
    // 3. Calculate NORMALIZED gaze vector (relative position to nose, as percentage of face width)
    // If you move forward, both (eye_center - nose_tip) and face_width grow proportionally,
    // so this ratio stays constant (scale-invariant)
    cv::Point2f relative_gaze = (eye_center - nose_tip) / face_width;
    
    normalized_gaze_history_.push_back(relative_gaze);
    
    // Keep only recent gaze points (last 5 seconds at 30 FPS = 150 points)
    if (normalized_gaze_history_.size() > 150) {
        normalized_gaze_history_.pop_front();
    }
    
    // Track head position for head movement detection
    head_position_history_.push_back({current_time, nose_tip});
    
    // Keep only recent head positions (last 1 second for velocity calculation)
    int64_t head_history_window = 1000;
    while (!head_position_history_.empty() && (current_time - head_position_history_.front().first) > head_history_window) {
        head_position_history_.pop_front();
    }
    
    // Calculate head movement velocity (pixels per second)
    if (head_position_history_.size() >= 2) {
        cv::Point2f head_displacement = head_position_history_.back().second - head_position_history_.front().second;
        int64_t time_diff = head_position_history_.back().first - head_position_history_.front().first;
        if (time_diff > 0) {
            head_movement_velocity_ = (cv::norm(head_displacement) / time_diff) * 1000.0;  // Convert to pixels/second
        }
    } else {
        head_movement_velocity_ = 0.0;
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
    if (normalized_gaze_history_.size() < 10) {
        gaze_stability_ = 1.0;  // Not enough data
        return;
    }
    
    // Calculate "jitter" (micro-movements) instead of total variance
    // Large movements (intentional saccades/scanning) are filtered out
    // Only small, high-frequency jitter is measured (unintentional movement)
    
    // Filter: Calculate variance of FRAME-TO-FRAME differences (jitter)
    // This ignores large intentional movements and only tracks micro-movements
    if (normalized_gaze_history_.size() < 2) {
        gaze_stability_ = 1.0;
        return;
    }
    
    std::deque<double> frame_diff_magnitudes;
    auto it = normalized_gaze_history_.begin();
    cv::Point2f prev_pt = *it;
    ++it;
    
    const double LARGE_MOVEMENT_THRESHOLD = 0.05;  // Filter out large movements (normalized, so this is ~5% of face width)
    
    for (; it != normalized_gaze_history_.end(); ++it) {
        cv::Point2f diff = *it - prev_pt;
        double magnitude = cv::norm(diff);
        
        // Only count small movements (jitter), ignore large movements (intentional saccades)
        if (magnitude < LARGE_MOVEMENT_THRESHOLD) {
            frame_diff_magnitudes.push_back(magnitude);
        }
        // Large movements are ignored (they're intentional scanning, not instability)
        
        prev_pt = *it;
    }
    
    if (frame_diff_magnitudes.empty()) {
        // No jitter detected (all movements were large/intentional)
        // Check for head movement
        
        double new_stability = 1.0;  // Default: high stability
        
        if (head_movement_velocity_ > 130.0) {  // > 130 pixels/second = violent shaking
            new_stability = 0.50;  // Moderate-low stability
        } else if (head_movement_velocity_ > 40.0) {  // > 40 = noticeable movement
            new_stability = 0.80;  // Slightly lower stability
        }
        
        // Apply smoothing
        double alpha = (new_stability < gaze_stability_) ? 0.22 : 0.14;
        gaze_stability_ = (1.0 - alpha) * gaze_stability_ + alpha * new_stability;
        return;
    }
    
    // Calculate variance of jitter magnitudes
    double mean_jitter = 0.0;
    for (double jit : frame_diff_magnitudes) {
        mean_jitter += jit;
    }
    mean_jitter /= frame_diff_magnitudes.size();
    
    double jitter_variance = 0.0;
    for (double jit : frame_diff_magnitudes) {
        double diff = jit - mean_jitter;
        jitter_variance += diff * diff;
    }
    jitter_variance /= frame_diff_magnitudes.size();
    
    // Convert jitter variance to stability score (0-1, higher = more stable)
    // Using exponential decay: stability = exp(-jitter_variance / scale)
    // Scale adjusted for normalized vectors (smaller values since they're ratios)
    double scale = 0.0001;  // Adjusted for jitter variance in normalized coordinates
    double gaze_jitter_stability = std::exp(-jitter_variance / scale);
    gaze_jitter_stability = std::max(0.0, std::min(1.0, gaze_jitter_stability));  // Clamp to [0, 1]
    
    // ===== NEW: Factor in head movement velocity =====
    // Head movement should reduce stability score  
    // Tuned for good balance: responsive to shake, doesn't artificially tank
    const double NORMAL_HEAD_VELOCITY = 40.0;     // pixels/second (threshold for penalty)
    const double VIOLENT_THRESHOLD = 130.0;       // pixels/second (full penalty at this speed)
    
    double head_movement_penalty = 0.0;
    if (head_movement_velocity_ > NORMAL_HEAD_VELOCITY) {
        // Linear penalty (simpler, more predictable)
        double excess_velocity = head_movement_velocity_ - NORMAL_HEAD_VELOCITY;
        double max_excess = VIOLENT_THRESHOLD - NORMAL_HEAD_VELOCITY;
        head_movement_penalty = std::min(1.0, excess_velocity / max_excess);
    }
    
    // Combine gaze jitter stability with head movement penalty
    // Head movement has 30% weight
    double new_stability = (gaze_jitter_stability * 0.75) - (head_movement_penalty * 0.25);
    new_stability = std::max(0.0, std::min(1.0, new_stability));  // Clamp to [0, 1]
    
    // Apply exponential smoothing: fast drop (0.22), moderate recovery (0.14)
    // This balances responsiveness with stability
    double alpha = (new_stability < gaze_stability_) ? 0.22 : 0.14;
    gaze_stability_ = (1.0 - alpha) * gaze_stability_ + alpha * new_stability;
}

void GazeDetector::detect_zoning_out() {
    // Zoning out: static gaze (>30s) + very low blink rate
    if (gaze_stability_ > 0.95 && blink_rate_ < ZONING_OUT_BLINK_RATE_THRESHOLD) {
        // Potential zoning out - could add event here
    }
}
