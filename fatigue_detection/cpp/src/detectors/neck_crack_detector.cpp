#include "neck_crack_detector.h"
#include <cmath>
#include <algorithm>

NeckCrackDetector::NeckCrackDetector() = default;

void NeckCrackDetector::calculate_head_pose(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox,
                                            double& pitch, double& yaw, double& roll) {
    if (landmarks.size() < 68 || face_bbox.width == 0) {
        pitch = yaw = roll = 0.0;
        return;
    }
    
    // Eye centers (more stable than single points)
    cv::Point2f left_eye_center = (landmarks[36] + landmarks[39]) * 0.5f;
    cv::Point2f right_eye_center = (landmarks[42] + landmarks[45]) * 0.5f;
    cv::Point2f eye_center = (left_eye_center + right_eye_center) * 0.5f;
    
    // Nose tip
    cv::Point2f nose_tip = landmarks[30];
    
    // Mouth corners (for roll calculation)
    cv::Point2f mouth_left = landmarks[48];   // Left mouth corner
    cv::Point2f mouth_right = landmarks[54];  // Right mouth corner
    
    // Calculate rotation angles per axis
    
    // Yaw (left-right rotation): Use eye line
    cv::Point2f eye_line = right_eye_center - left_eye_center;
    yaw = std::atan2(eye_line.y, eye_line.x) * 180.0 / CV_PI;
    
    // Pitch (up-down rotation): Vertical position of nose relative to eye center
    cv::Point2f nose_vec = nose_tip - eye_center;
    pitch = std::atan2(nose_vec.y, std::abs(nose_vec.x)) * 180.0 / CV_PI;
    
    // Roll (tilt/rotation): Angle of eye line from horizontal
    // Also check mouth line for consistency
    cv::Point2f mouth_line = mouth_right - mouth_left;
    double eye_angle = std::atan2(eye_line.y, eye_line.x) * 180.0 / CV_PI;
    double mouth_angle = std::atan2(mouth_line.y, mouth_line.x) * 180.0 / CV_PI;
    roll = std::abs(eye_angle - mouth_angle);  // Difference indicates tilt
}

void NeckCrackDetector::update(const std::vector<cv::Point2f>& landmarks, const cv::Rect& face_bbox) {
    if (landmarks.size() < 68) {
        return;
    }
    
    // Calculate head pose per axis
    double current_pitch, current_yaw, current_roll;
    calculate_head_pose(landmarks, face_bbox, current_pitch, current_yaw, current_roll);
    
    int64_t current_time = cv::getTickCount() * 1000 / cv::getTickFrequency();
    
    // Detect crack if we have previous rotation data
    if (last_update_time_ > 0) {
        detect_crack(current_time, current_pitch, current_yaw, current_roll);
    }
    
    // Update state
    last_pitch_ = current_pitch;
    last_yaw_ = current_yaw;
    last_roll_ = current_roll;
    last_update_time_ = current_time;
    frames_since_last_crack_++;
    
    // Update crack count
    update_crack_count(current_time);
}

void NeckCrackDetector::detect_crack(int64_t current_time, double /*current_pitch*/, double current_yaw, double current_roll) {
    // Fixed neck crack detection: Monitor specific axes (Roll and Yaw)
    // Most neck cracks are Roll (ear to shoulder) or Yaw (looking left/right)
    // Pitch (nodding) is rarely a crack, so we ignore it
    
    // Calculate delta (velocity) per axis (degrees per frame)
    // At 30fps, 1 frame = ~33ms, so we're measuring degrees per frame
    double d_roll = std::abs(current_roll - last_roll_);
    double d_yaw = std::abs(current_yaw - last_yaw_);
    // Ignore pitch for crack detection (nodding is normal movement)
    
    // Check if EITHER Roll OR Yaw exceeds the speed threshold
    // Normal head movement: ~0.5 to 2.0 degrees per frame
    // Neck crack whip-motion: usually > 8.0 degrees per frame
    bool roll_crack = d_roll > CRACK_VELOCITY_THRESHOLD;
    bool yaw_crack = d_yaw > CRACK_VELOCITY_THRESHOLD;
    
    if (roll_crack || yaw_crack) {
        // Debounce: Only count 1 crack every 2 seconds (60 frames at 30fps)
        if (frames_since_last_crack_ > CRACK_DEBOUNCE_FRAMES) {
            crack_timestamps_.push_back(current_time);
            last_crack_time_ = current_time;
            frames_since_last_crack_ = 0;  // Reset counter
        }
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
