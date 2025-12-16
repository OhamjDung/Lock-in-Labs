import subprocess
import sys
import os
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_simulation():
    # Define the inputs based on the user's transcript
    inputs = [
        "I would do some journaling, and then excercise, and then some vocal practice to improve my communication skills. Then i would love to dedicate some time to volleyball, to coding, and to family and friends.",
        "coding is more of a solitary thing for me. I love creating and being productive, regardless of people are doing it or not. If things were to fail in my code, i would just adapt. I would find the issue, solve the issue if possible, if the problem lies in the foundation then ill change the foundation.",
        "I think connections for me is more functional but its also emotional. Having friends is fun, i get to study with them and stuff and it makes me less lonely, but theyre also good people to ask feedback and play volleyball with.",
        "i would listen first, then i would offer some solutions. Ill also ask if they want me to listen or give advice. When in a team effort i try to help but not be too demanding",
        "exit" # Ensure we exit if the loop continues
    ]
    
    # Path to main.py
    main_script = os.path.join(os.path.dirname(__file__), '..', 'src', 'main.py')
    
    # Start the process
    process = subprocess.Popen(
        [sys.executable, main_script],
        stdin=subprocess.PIPE,
        stdout=sys.stdout, # Print output to console
        stderr=sys.stderr,
        text=True,
        bufsize=0 # Unbuffered
    )
    
    print("--- Starting Simulation ---")
    
    # Give the system a moment to initialize and print the first prompt
    time.sleep(2)
    
    for user_input in inputs:
        if process.poll() is not None:
            print("Process ended early.")
            break
            
        print(f"\n[SIMULATION] Sending input: {user_input[:50]}...")
        try:
            process.stdin.write(user_input + "\n")
            process.stdin.flush()
        except OSError:
            print("Process closed stdin.")
            break
            
        # Wait for the AI to process and respond
        # This is a heuristic; in a real test we'd wait for a specific prompt
        time.sleep(10) 
        
    process.wait()
    print("\n--- Simulation Complete ---")

if __name__ == "__main__":
    run_simulation()
