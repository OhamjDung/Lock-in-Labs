#ifndef FATIGUE_DETECTOR_H
#define FATIGUE_DETECTOR_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <memory>
#include <string>
#include <cstdint>

// Forward declarations
class FaceEngine;
class YawnDetector;
class GazeDetector;
class FidgetDetector;
class NeckCrackDetector;
class ProfileManager;

// State vector structure
struct StateVector {
    // Raw metrics
    double blink_rate = 0.0;              // Blinks per minute
    int blink_count_total = 0;            // Total blinks detected in current session
    double perclos = 0.0;                 // Percentage of eyelid closure (0-1)
    double current_ear = 0.0;             // Current Eye Aspect Ratio (for calibration/debugging)
    double current_mar = 0.0;             // Current Mouth Aspect Ratio (for calibration/debugging)
    int yawn_count_5min = 0;              // Yawn count in last 5 minutes
    double gaze_stability = 0.0;          // Gaze stability score (0-1, higher = more stable)
    double fidgeting_score = 0.0;         // Fidgeting score (0-1, higher = more fidgeting)
    int neck_crack_count_1min = 0;        // Neck crack count in last minute
    
    // Detection regions (for visualization)
    // Note: These are on the DOWNSCALED frame (640x480), need to scale up for display
    int face_bbox_x = 0;                  // Face bounding box (x, y, width, height)
    int face_bbox_y = 0;
    int face_bbox_width = 0;
    int face_bbox_height = 0;
    double scale_factor = 1.0;           // Scale factor from downscaled to original frame
    std::vector<double> left_eye_points;  // Left eye landmarks (6 points: x,y pairs)
    std::vector<double> right_eye_points; // Right eye landmarks (6 points: x,y pairs)
    std::vector<double> mouth_points;     // Mouth landmarks (20 points: x,y pairs for 48-67)
    std::vector<double> nose_tip;         // Nose tip (x, y)
    
    // Scaled coordinates for visualization (already scaled to original frame)
    std::vector<double> face_bbox_scaled;  // [x, y, width, height] scaled to original frame
    std::vector<double> landmarks_scaled;  // All 68 landmarks (x,y pairs) scaled to original frame
    
    // Z-scores (clamped)
    double z_score_blink = 0.0;
    double z_score_gaze = 0.0;
    double z_score_posture = 0.0;
    double z_score_fidget = 0.0;
    
    // Final outputs
    double fatigue_score = 0.0;           // Overall fatigue score (0-1)
    std::string fatigue_level;            // "focused", "moderate", "high"
    std::string recommendation;           // "continue", "take_short_break", "take_long_break"
    
    // Events
    std::vector<std::string> events;      // Recent events (e.g., "yawn_detected", "zoning_out")
    
    // Helper to convert to dict-like structure for Python
    std::string to_json() const;
};

class FatigueEngine {
public:
    FatigueEngine(const std::string& user_id, const std::string& profile_path = "");
    ~FatigueEngine();
    
    // Process a frame and return state vector
    StateVector process_frame(const cv::Mat& frame, int64_t timestamp_ms);
    
    // Profile management
    bool load_profile(const std::string& profile_path);
    void update_profile(const StateVector& session_stats, double user_rating);
    
    // Configuration
    void set_downscale_width(int width) { downscale_width_ = width; }
    void set_downscale_height(int height) { downscale_height_ = height; }
    
    // Calibration methods (forward to detectors)
    void set_ear_threshold(double threshold);
    void set_mar_threshold(double threshold);
    double get_ear_threshold() const;
    double get_mar_threshold() const;
    
private:
    // Frame processing hierarchy
    int frame_counter_ = 0;
    static constexpr int MOTION_FRAME_INTERVAL = 5;  // Every 5th frame
    static constexpr int ZSCORE_FRAME_INTERVAL = 30; // Every 30th frame
    
    // Downscaling configuration
    int downscale_width_ = 640;
    int downscale_height_ = 480;
    
    // Components
    std::unique_ptr<FaceEngine> face_engine_;
    std::unique_ptr<YawnDetector> yawn_detector_;
    std::unique_ptr<GazeDetector> gaze_detector_;
    std::unique_ptr<FidgetDetector> fidget_detector_;
    std::unique_ptr<NeckCrackDetector> neck_crack_detector_;
    std::unique_ptr<ProfileManager> profile_manager_;
    
    // State
    cv::Mat prev_frame_;                  // Previous frame for motion energy
    std::vector<cv::Point2f> landmarks_;  // Current face landmarks
    cv::Rect face_bbox_;                  // Current face bounding box
    StateVector current_state_;           // Current state vector
    
    // Internal processing methods
    void process_face_landmarks(const cv::Mat& frame);
    void process_motion_energy(const cv::Mat& frame);
    void calculate_z_scores_and_fatigue();
    
    std::string user_id_;
};

#endif // FATIGUE_DETECTOR_H
