"""Generate synthetic 30-day history for testing memory system."""

import json
from datetime import datetime, timedelta
from pathlib import Path

def generate_history():
    """Generate realistic 30-day narrative: 'The Runner's Knee Injury'."""
    base_date = datetime.now() - timedelta(days=30)
    logs = []
    
    scenarios = [
        # WEEK 1: High Motivation (Days 0-6)
        {"day": 0, "text": "Ate oatmeal. Ran 3km. Felt easy.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 1, "text": "Work was boring. Did 20 pushups. Completed all tasks on time.", "type": "routine", "pillar": "CAREER", "sentiment": "neutral"},
        {"day": 2, "text": "AMAZING run today! Hit 5km for the first time. Felt like I could fly. This is working!", "type": "milestone", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 3, "text": "Rest day. Watched a movie. Ate pizza.", "type": "routine", "pillar": "MENTAL", "sentiment": "neutral"},
        {"day": 4, "text": "Ran 4km. Legs feel strong. Thinking about signing up for a 10k race.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 5, "text": "Did yoga. Ate healthy meal.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 6, "text": "Rest day. Read a book about running form.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        
        # WEEK 2: The Mistake - Overconfidence (Days 7-13)
        {"day": 7, "text": "Pushed for 7km today. Shin splints hurt a bit but I powered through. I'm getting stronger!", "type": "warning", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 8, "text": "Ate a salad. Completed coding project. Feeling productive.", "type": "routine", "pillar": "CAREER", "sentiment": "neutral"},
        {"day": 9, "text": "Knee feels weird when I walk down stairs. Ignored it and did squats anyway. No pain during the workout.", "type": "warning", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 10, "text": "Ran 6km. Ignored the weird knee feeling. Pushed through it. Mind over matter!", "type": "warning", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 11, "text": "Ate breakfast. Work meeting went well.", "type": "routine", "pillar": "CAREER", "sentiment": "neutral"},
        {"day": 12, "text": "Knee feels stiff in the morning. Still ran 5km. It'll get better with time.", "type": "warning", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 13, "text": "Rest day. Knee still feels off but I'm sure it's nothing.", "type": "warning", "pillar": "PHYSICAL", "sentiment": "negative"},
        
        # WEEK 3: The Crash - Injury (Days 14-20)
        {"day": 14, "text": "FUCK. Sharp pain in right knee at mile 1. Had to walk home. Limping now. This is bad.", "type": "failure", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 15, "text": "Can't walk without pain. Mood is trash. I hate this. Why did I push so hard?", "type": "emotion", "pillar": "MENTAL", "sentiment": "negative"},
        {"day": 16, "text": "Ate pizza. Did nothing. Knee still hurts. Feeling demotivated.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 17, "text": "Skipped all exercise. Knee is better but still hurts when I bend it. Frustrated.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "negative"},
        {"day": 18, "text": "Went to doctor. They said it's likely 'Runner's Knee' from overuse. Need to rest.", "type": "insight", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 19, "text": "Ate healthy. Work was fine. Knee still bothering me.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 20, "text": "Read about Runner's Knee online. Feeling anxious about recovery time.", "type": "emotion", "pillar": "MENTAL", "sentiment": "negative"},
        
        # WEEK 4: The Lesson - Recovery (Days 21-29)
        {"day": 21, "text": "Read about 'Runner's Knee' in detail. Realized I increased mileage too fast in Week 2. Need to strengthen glutes and quads.", "type": "insight", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 22, "text": "Started glute bridge exercises. Knee feels more stable. Learned my lesson about gradual progression.", "type": "correction", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 23, "text": "Ate well. Did glute exercises. No running. Being patient with recovery.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 24, "text": "Knee feeling better. Did light stretching. Still no running but staying active with strength work.", "type": "correction", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 25, "text": "Did glute bridges today. Knee feels stable. Going to stick to Zone 2 cardio only when I return. Learned: gradual progression prevents injury.", "type": "correction", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 26, "text": "Work was busy. Ate lunch. Knee improving daily.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 27, "text": "First walk-jog test. 2km total, mostly walking. Knee handled it well. Feeling optimistic.", "type": "correction", "pillar": "PHYSICAL", "sentiment": "positive"},
        {"day": 28, "text": "Ate breakfast. Completed work tasks. Recovery going well.", "type": "routine", "pillar": "PHYSICAL", "sentiment": "neutral"},
        {"day": 29, "text": "Planning next week: Max 3km runs, focus on form, add glute strength work. Won't make the same mistake twice.", "type": "insight", "pillar": "PHYSICAL", "sentiment": "positive"},
    ]

    for s in scenarios:
        date_str = (base_date + timedelta(days=s["day"])).strftime("%Y-%m-%d")
        logs.append({
            "date": date_str,
            "content": s["text"],
            "type": s["type"],
            "pillar": s["pillar"],
            "sentiment": s["sentiment"],
        })
        
    return logs


if __name__ == "__main__":
    # Ensure debug directory exists
    Path("debug").mkdir(exist_ok=True)
    
    data = generate_history()
    output_path = Path("debug/mock_history.json")
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print("=" * 60)
    print("[OK] GENERATED 30 DAYS OF MOCK HISTORY")
    print("=" * 60)
    print(f"Output: {output_path}")
    print(f"Total entries: {len(data)}")
    print("\nNarrative Arc:")
    print("  Week 1: High motivation, good progress (milestone: 5km PR)")
    print("  Week 2: Warning signs ignored (shin splints, weird knee feeling)")
    print("  Week 3: Injury crash (sharp knee pain, demotivation)")
    print("  Week 4: Recovery and lesson learned (glute work, gradual progression)")
    print("\nNext: Run test_significance.py to verify significance gate")
