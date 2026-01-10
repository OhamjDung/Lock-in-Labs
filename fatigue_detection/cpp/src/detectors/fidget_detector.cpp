#include "fidget_detector.h"
#include <algorithm>
#include <cmath>

FidgetDetector::FidgetDetector() = default;

cv::Rect FidgetDetector::calculate_torso_roi(const cv::Rect& face_bbox, const cv::Size& image_size) {
    if (face_bbox.width == 0 || face_bbox.height == 0) {
        return cv::Rect();
    }
    
    int face_center_x = face_bbox.x + face_bbox.width / 2;
    int face_center_y = face_bbox.y + face_bbox.height / 2;
    
    // Try Standard Torso (Below Face) - preferred method
    int torso_width = static_cast<int>(face_bbox.width * 1.5);
    int torso_height = static_cast<int>(face_bbox.height * 2.0);
    int torso_x = face_center_x - torso_width / 2;
    int torso_y = face_bbox.y + face_bbox.height;  // Start at chin
    
    // Check if we have enough space below face (at least 50 pixels)
    // If face is too low in frame, torso ROI would be off-screen
    if ((image_size.height - torso_y) > 50) {
        // STANDARD MODE: Track Chest/Torso below face
        // Clamp to image bounds
        torso_x = std::max(0, std::min(torso_x, image_size.width - torso_width));
        torso_y = std::max(0, std::min(torso_y, image_size.height - torso_height));
        torso_width = std::min(torso_width, image_size.width - torso_x);
        torso_height = std::min(torso_height, image_size.height - torso_y);
        
        // Ensure valid ROI
        if (torso_width > 0 && torso_height > 0) {
            return cv::Rect(torso_x, torso_y, torso_width, torso_height);
        }
    }
    
    // FALLBACK MODE: Track Shoulders (Left/Right of face)
    // This is useful when user is close to camera or camera is tilted up
    // Shoulders are usually at face level or slightly below
    int shoulder_width = static_cast<int>(face_bbox.width * 3.0);  // Wider to capture both shoulders
    int shoulder_height = static_cast<int>(face_bbox.height * 1.0);  // Same height as face
    int shoulder_x = face_center_x - shoulder_width / 2;
    int shoulder_y = face_center_y;  // Center on face level (shoulders are usually at this level)
    
    // Clamp to image bounds
    shoulder_x = std::max(0, std::min(shoulder_x, image_size.width - shoulder_width));
    shoulder_y = std::max(0, std::min(shoulder_y, image_size.height - shoulder_height));
    shoulder_width = std::min(shoulder_width, image_size.width - shoulder_x);
    shoulder_height = std::min(shoulder_height, image_size.height - shoulder_y);
    
    // Ensure valid ROI
    if (shoulder_width > 0 && shoulder_height > 0) {
        return cv::Rect(shoulder_x, shoulder_y, shoulder_width, shoulder_height);
    }
    
    // If all else fails, return empty ROI
    return cv::Rect();
}

double FidgetDetector::calculate_motion_energy(const cv::Mat& curr_frame, 
                                                const cv::Mat& prev_frame,
                                                const cv::Rect& face_bbox) {
    if (curr_frame.empty() || prev_frame.empty() || face_bbox.width == 0) {
        return 0.0;
    }
    
    // Calculate torso ROI relative to face position
    cv::Rect torso_roi = calculate_torso_roi(face_bbox, curr_frame.size());
    
    if (torso_roi.width <= 0 || torso_roi.height <= 0) {
        return 0.0;  // Invalid ROI
    }
    
    // Ensure ROI is within bounds
    cv::Rect image_rect(0, 0, curr_frame.cols, curr_frame.rows);
    cv::Rect valid_roi = torso_roi & image_rect;
    
    if (valid_roi.width <= 0 || valid_roi.height <= 0) {
        return 0.0;  // Invalid ROI
    }
    
    // Extract ROI regions
    cv::Mat curr_roi = curr_frame(valid_roi);
    cv::Mat prev_roi = prev_frame(valid_roi);
    
    // Convert to grayscale if needed
    cv::Mat curr_gray, prev_gray;
    if (curr_roi.channels() == 3) {
        cv::cvtColor(curr_roi, curr_gray, cv::COLOR_BGR2GRAY);
        cv::cvtColor(prev_roi, prev_gray, cv::COLOR_BGR2GRAY);
    } else {
        curr_gray = curr_roi.clone();
        prev_gray = prev_roi.clone();
    }
    
    // Calculate frame difference (Motion Energy)
    cv::Mat diff;
    cv::absdiff(curr_gray, prev_gray, diff);
    
    // Sum of pixel differences
    cv::Scalar total = cv::sum(diff);
    double pixel_count = valid_roi.width * valid_roi.height;
    double motion_energy = total[0] / pixel_count;  // Normalized
    
    // Add to history for smoothing
    motion_history_.push_back(motion_energy);
    if (motion_history_.size() > HISTORY_SIZE) {
        motion_history_.pop_front();
    }
    
    // Return smoothed average
    double sum = 0.0;
    for (double val : motion_history_) {
        sum += val;
    }
    double smoothed = motion_history_.empty() ? 0.0 : sum / motion_history_.size();
    
    // Classify: large motion = stretching (healthy), small jittery motion = fidgeting (anxiety)
    // Return normalized fidgeting score (0-1)
    // Higher motion energy that is consistent = stretching (low fidget score)
    // Low but constant motion = fidgeting (high fidget score)
    
    // Simple heuristic: motion < threshold = fidgeting
    double fidget_score = 1.0 - std::min(1.0, smoothed / FIDGET_THRESHOLD);
    return std::max(0.0, std::min(1.0, fidget_score));  // Clamp to [0, 1]
}
