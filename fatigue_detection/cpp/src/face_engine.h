#ifndef FACE_ENGINE_H
#define FACE_ENGINE_H

#include <opencv2/opencv.hpp>
#include <opencv2/objdetect.hpp>
#include <vector>
#include <string>

class FaceEngine {
public:
    FaceEngine();
    ~FaceEngine();
    
    // Initialize with model paths
    // face_detector_model: Path to YuNet ONNX model (e.g., "models/face_detection_yunet_2023mar.onnx")
    // landmark_predictor_model: Path to dlib landmark predictor
    bool initialize(const std::string& face_detector_model = "",
                    const std::string& landmark_predictor_model = "");
    
    // Detect face and landmarks in frame
    bool detect_landmarks(const cv::Mat& frame, 
                         std::vector<cv::Point2f>& landmarks,
                         cv::Rect& face_bbox);
    
    // Check if initialized
    bool is_initialized() const { return initialized_; }
    
    // Manual Offset Control (for fine-tuning landmark alignment)
    // Separate offsets for eyes and mouth
    void set_eye_offset(float x, float y);
    void set_mouth_offset(float x, float y);
    std::pair<float, float> get_eye_offset() const;
    std::pair<float, float> get_mouth_offset() const;
    
    // Legacy: Combined offset (applies to both eyes and mouth)
    void set_offset(float x, float y);
    std::pair<float, float> get_offset() const;
    
private:
    bool initialized_ = false;
    
    // Using pimpl pattern (forward declaration)
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

#endif // FACE_ENGINE_H
