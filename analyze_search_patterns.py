#!/usr/bin/env python3
"""
Analyze Google Search patterns from Docker logs to understand:
1. At what attempt number do we typically find successful articles?
2. How many attempts are wasted after finding a good result?
3. What's the success rate by attempt number?
"""

import re
import subprocess
import json
from collections import defaultdict, Counter

def get_docker_logs():
    """Get recent Docker logs"""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "2000", subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.strip()],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting Docker logs: {e}")
        return ""

def parse_search_attempts(logs):
    """Parse search attempts and results from logs"""
    
    # Patterns to match
    attempt_pattern = r"search attempt (\d+)/8.*?\"([^\"]+)\".*?\"([^\"]+)\""
    candidate_pattern = r"Candidate: (.+?) \| Score: (-?\d+) \| URL: (.+)"
    final_result_pattern = r"Found highly relevant clip \(score (\d+)\) for (.+?) -"
    
    search_data = defaultdict(list)
    current_loan = None
    current_vehicle = None
    
    lines = logs.split('\n')
    
    for line in lines:
        # Track search attempts
        attempt_match = re.search(attempt_pattern, line)
        if attempt_match:
            attempt_num = int(attempt_match.group(1))
            vehicle = attempt_match.group(2) + " " + attempt_match.group(3)
            current_vehicle = vehicle
            current_loan = f"attempt_{attempt_num}_{vehicle}"
            search_data[current_vehicle].append({
                'attempt': attempt_num,
                'candidates': [],
                'success': False
            })
        
        # Track candidates found in each attempt
        candidate_match = re.search(candidate_pattern, line)
        if candidate_match and current_vehicle:
            title = candidate_match.group(1)
            score = int(candidate_match.group(2))
            url = candidate_match.group(3)
            
            # Add to the most recent attempt for this vehicle
            if search_data[current_vehicle]:
                search_data[current_vehicle][-1]['candidates'].append({
                    'title': title,
                    'score': score,
                    'url': url
                })
        
        # Track final successful results
        success_match = re.search(final_result_pattern, line)
        if success_match:
            relevance = int(success_match.group(1))
            vehicle = success_match.group(2)
            
            # Mark the last attempt for this vehicle as successful
            if vehicle in search_data and search_data[vehicle]:
                search_data[vehicle][-1]['success'] = True
                search_data[vehicle][-1]['final_relevance'] = relevance
    
    return search_data

def analyze_patterns(search_data):
    """Analyze the search patterns"""
    
    print("🔍 GOOGLE SEARCH PATTERN ANALYSIS")
    print("=" * 50)
    
    success_by_attempt = Counter()
    total_by_attempt = Counter()
    successful_vehicles = []
    
    for vehicle, attempts in search_data.items():
        print(f"\n🚗 Vehicle: {vehicle}")
        
        for attempt_data in attempts:
            attempt_num = attempt_data['attempt']
            candidates = attempt_data['candidates']
            success = attempt_data.get('success', False)
            
            total_by_attempt[attempt_num] += 1
            
            print(f"  Attempt {attempt_num}: {len(candidates)} candidates found")
            
            if success:
                success_by_attempt[attempt_num] += 1
                successful_vehicles.append((vehicle, attempt_num, attempt_data.get('final_relevance', 0)))
                print(f"    ✅ SUCCESS! Final relevance: {attempt_data.get('final_relevance', 'unknown')}")
                
                # Show the successful candidates
                for candidate in candidates:
                    if candidate['score'] > 0:
                        print(f"    📄 {candidate['title'][:60]}... (score: {candidate['score']})")
            else:
                print(f"    ❌ No success")
    
    print(f"\n📊 SUCCESS RATE BY ATTEMPT")
    print("-" * 30)
    
    for attempt in range(1, 9):
        if total_by_attempt[attempt] > 0:
            success_rate = (success_by_attempt[attempt] / total_by_attempt[attempt]) * 100
            print(f"Attempt {attempt}: {success_by_attempt[attempt]}/{total_by_attempt[attempt]} = {success_rate:.1f}% success")
        else:
            print(f"Attempt {attempt}: No data")
    
    print(f"\n🎯 SUCCESSFUL RESULTS SUMMARY")
    print("-" * 30)
    print(f"Total successful vehicles: {len(successful_vehicles)}")
    
    if successful_vehicles:
        early_success = sum(1 for _, attempt, _ in successful_vehicles if attempt <= 3)
        late_success = sum(1 for _, attempt, _ in successful_vehicles if attempt > 3)
        
        print(f"Found in attempts 1-3: {early_success} ({early_success/len(successful_vehicles)*100:.1f}%)")
        print(f"Found in attempts 4-8: {late_success} ({late_success/len(successful_vehicles)*100:.1f}%)")
        
        print(f"\nSuccessful vehicles by attempt number:")
        for vehicle, attempt, relevance in successful_vehicles:
            print(f"  Attempt {attempt}: {vehicle} (relevance: {relevance})")

def main():
    print("Getting Docker logs...")
    logs = get_docker_logs()
    
    if not logs:
        print("❌ No Docker logs found. Make sure Docker container is running.")
        return
    
    print("Parsing search attempts...")
    search_data = parse_search_attempts(logs)
    
    if not search_data:
        print("❌ No search patterns found in logs.")
        return
    
    analyze_patterns(search_data)

if __name__ == "__main__":
    main() 