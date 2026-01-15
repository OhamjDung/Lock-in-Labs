#ifndef PROFILE_MANAGER_H
#define PROFILE_MANAGER_H

#include "detector.h"
#include <string>
#include <memory>

struct BaselineStats {
    // Blink metrics
    double avg_blink_rate = 12.5;
    double blink_rate_std = 2.1;
    
    // Posture metrics
    double avg_posture_height = 450.0;
    double posture_height_std = 15.2;
    
    // Head movement
    double head_movement_variance = 5.2;
    double head_movement_std = 1.8;
    
    // Gaze metrics
    double gaze_stability_baseline = 0.15;
    double gaze_stability_std = 0.05;
    
    // Motion metrics (fidgeting/body movement)
    double motion_energy_baseline = 85.0;
    double motion_energy_std = 12.3;
    
    // MAR (mouth aspect ratio) baseline
    double mar_baseline = 0.08;
    double mar_std = 0.02;
    
    // PERCLOS baseline (eye closure)
    double perclos_baseline = 0.10;
    double perclos_std = 0.05;
    
    // Calibration flags
    bool work_session_calibrated = false;  // Has completed work session calibration
    bool break_session_calibrated = false; // Has completed break session calibration
};

class ProfileManager {
public:
    ProfileManager();
    
    // Load profile from JSON file
    bool load_profile(const std::string& profile_path);
    
    // Save profile to JSON file
    bool save_profile(const std::string& profile_path) const;
    
    // Calculate fatigue state from current metrics using Z-scores
    StateVector calculate_fatigue_state(const StateVector& current_state) const;
    
    // Update baseline stats with weighted moving average
    void update_baseline(const StateVector& session_stats, double user_rating);
    
    // Calibration session management
    void start_calibration_session(const std::string& session_type);
    void end_calibration_session(const StateVector& session_stats, double user_rating);
    
    // Check if profile is calibrated
    bool is_calibrated() const;
    
    // Get baseline stats
    const BaselineStats& get_baseline() const { return baseline_stats_; }
    
private:
    // Sigmoid-clamped Z-score calculation
    double calculate_clamped_z_score(double current, double baseline, double std_dev) const;
    
    // Configuration
    static constexpr double LEARNING_RATE = 0.1;
    static constexpr double MIN_STD_DEV = 0.01;  // Prevent division by zero
    
    BaselineStats baseline_stats_;
    bool profile_loaded_ = false;
    std::string profile_path_;
    std::string current_session_type_;  // Track current calibration session type
    
    // Helper for JSON parsing (simplified)
    bool parse_json_file(const std::string& path);
    bool write_json_file(const std::string& path) const;
};

#endif // PROFILE_MANAGER_H
