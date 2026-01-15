"""
Simple HTTP test to verify the daemon is running without WebSocket issues.
"""
import requests
import time

def test_http_endpoint():
    """Test if the daemon is responding to HTTP requests."""
    base_url = "http://127.0.0.1:8000"
    
    print("\n" + "=" * 80)
    print("DAEMON HTTP TEST")
    print("=" * 80)
    
    try:
        # Test root endpoint
        print("\n[1] Testing root endpoint...")
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"    Status: {response.status_code}")
        
        # Test health endpoint
        print("[2] Testing /health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"    Status: {response.status_code}")
        print(f"    Response: {response.json()}")
        
        # Test metrics endpoint
        print("[3] Testing /metrics endpoint...")
        response = requests.get(f"{base_url}/metrics", timeout=5)
        print(f"    Status: {response.status_code}")
        print(f"    Active connections: {response.json().get('active_connections', 'N/A')}")
        
        print("\n✅ Daemon is responsive on HTTP!")
        return True
        
    except Exception as e:
        print(f"\n❌ Daemon is not responding: {e}")
        print("   Make sure to run: python -m fatigue_detection.app")
        return False

if __name__ == "__main__":
    test_http_endpoint()
